# marginfi v2 (lending) — Six-Bucket Trust Audit

**Target:** `mrgnlabs/marginfi-v2`, program `marginfi` (full source — the stub `lib.rs`
hits are bundled *mock* programs, not marginfi). Cloned `/tmp/marginfi`. A cross-margined
Solana lending protocol (banks with share-based asset/liability accounting, utilization-curve
interest, health-based liquidation) — plus real adapters that route deposits into **external**
lending protocols (Kamino, Solend, Drift, JupLend).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite
the exact constraint. Any untrusted-input→unvalidated→value path would route privately to
mrgnlabs; none found. Focused on the **interest-flow conservation** (the lending-defining
invariant) and the integration seam; not an exhaustive read. Coverage gaps stated.

**Why this target:** first **lending** primitive in the corpus — the last major DeFi category
missing — and a fresh **§11 data point**: in a lending book, conservation is *"borrower
interest paid == lender interest earned + protocol fees,"* enforced not by a balance equation
but by a **self-consistent rate decomposition**.

---

## Bucket 1 — interest-flow conservation (verified by recompute; enforced)

A lending book mints value if borrowers are charged less than lenders + the protocol are
credited (or vice-versa). marginfi's rate model (`state/interest_rate.rs`) makes the two
sides algebraically identical. From `calc_interest_rate` (`:196`) and
`calc_interest_rate_accrual_state_changes` (`:449`):

```
ur            = total_liabilities / total_assets                      (:458)
lending_rate  = base_rate · ur                                        (:217)
borrowing_rate= base_rate · (1 + fee_ir) + fee_fixed                  (:221)   where
               fee_ir    = insurance_rate + group_rate + protocol_rate (:206)
               fee_fixed = insurance_fixed + group_fixed + protocol_fixed (:207)
fee_apr_k     = base_rate · rate_fee_k + fixed_fee_k                   (:225–229, calc_fee_rate)
```

**Recompute of the conservation identity** (per unit time, real arithmetic):

- borrowers pay: `total_liab · borrowing_rate = total_liab · (base + base·fee_ir + fee_fixed)`
- lenders earn: `total_assets · lending_rate = total_assets · base · ur = base · total_liab`
  *(the `·ur` factor is exactly what "symmetrizes payments between borrowers and depositors,"
  comment `:216` — lenders collectively earn interest only on what is actually borrowed)*
- fees collected: `total_liab · Σ fee_apr_k = total_liab · (base·fee_ir + fee_fixed)`
- **lenders + fees** `= base·total_liab + total_liab·(base·fee_ir + fee_fixed)`
  `= total_liab·(base + base·fee_ir + fee_fixed)` `= borrowers` ✓

The fee APRs are computed the *same way* they are folded into the borrow rate, so the spread
between borrow and lend is exactly the fees — **no value is created or destroyed by interest
accrual.** Lender/borrower share values grow via `value·(1 + apr·dt/yr)`
(`calc_accrued_interest_payment_per_period`, `:393`); fees are charged on `total_liabilities`
(`calc_interest_payment_for_period`, `:409`). All `checked_*` over `I80F48` fixed-point; rates
asserted ≥ 0 (`:231`–`:235`). **Verdict: enforced invariant** (interest conservation holds by
construction of the rate decomposition).

### Honest residuals on the conservation (Bucket 5)

- **Independent rounding of the three flows.** The identity is exact in real arithmetic, but
  the *applied* asset-share growth (on `total_assets`), liability-share growth (on
  `total_liabilities`), and fee charges (on `total_liabilities`) are computed and rounded
  **separately** in `I80F48`. The book stays solvent only if the rounding consistently favors
  the protocol (lender credit rounds down / borrower charge rounds up). Verifying that
  reconciliation requires the *application* site (`marginfi_group.rs::accrue_interest`, not
  read in depth here). **scope boundary — the rate model conserves; the rounding reconciliation
  is the thing to confirm.**
- **`ur > 1` edge.** `utilization = total_liab / total_assets` (`:458`); the multipoint curve
  clamps `ur ∈ [0,1]` (`:278`) but the legacy curve and `lending_rate = base·ur` do not. `ur>1`
  implies over-borrowed (liabilities > assets) — a broken state the borrow/health checks must
  prevent upstream. **named — depends on the (unaudited here) borrow-side health gate.**
- **Simple (per-accrual) interest**, explicitly documented (`:422`); compounds across accrual
  events, not continuously. Design choice, not a defect.

---

## Bucket 6 — the integration seam (the highest-value surface, named)

marginfi v2 is not a closed book: `state/{kamino,solend,drift,juplend}.rs` are **real adapters
that deposit user funds into external lending protocols**. This means marginfi's own asset
accounting now depends on **correctly reading the value of positions held inside another
protocol** — the exact "strategy value-reporting" risk flagged in `AUDIT-METEORA-VAULT-SDK.md`,
except here it is **full source and auditable**. The conservation §-above covers *marginfi's
internal* interest book; it does **not** cover whether `external_position_value` is read
soundly (staleness, the external protocol's own exchange-rate/rounding, a compromised or
upgraded external program). This is the **6b cross-protocol seam**: marginfi must accept
another program's account of "how much is your deposit worth," which it cannot prove. **named,
irreducible from marginfi's side — and the single highest-value place to spend a deeper
review** (each adapter × each external protocol's value-reporting contract).

## Bucket 6b — the oracle (shared with the perp model)

Collateral valuation for health and liquidation is oracle-priced (`state/price.rs`). As in
Drift (`AUDIT-DRIFT-PERP.md`), the equivalence *"oracle ⇄ true price"* is irreducible and
gated by validity/staleness/confidence, never proven. Liquidation solvency rests on it.
**named, irreducible.**

## Bucket 4 / governance ceiling

Bank config (collateral/liability weights, deposit/borrow caps, the interest curve points,
fee rates), the admin/group authority, a `panic_state` pause, and `staked_settings` — all
admin-gated parameter power, plus the BPF upgrade authority (apex). The collateral-weight and
oracle-source settings are the apex-relevant powers (they set who is solvent), per
`AUDIT-GOVERNANCE-CEILING.md`. **trust-boundary debt (by design).**

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1 | Interest-flow conservation (borrower == lender + fees) | **enforced invariant** — verified by recompute; self-consistent rate decomposition |
| 5 | Fixed-point arithmetic, ≥0 rate asserts, ur clamp (multipoint) | **enforced** (rate model); rounding reconciliation = **scope boundary** |
| 5 | `ur > 1` on legacy curve | **named** — depends on upstream borrow/health gate |
| 6 | Cross-protocol adapters (Kamino/Solend/Drift/JupLend) value-reporting | **named, irreducible & highest-value** — external position valuation marginfi can't prove |
| 6b | Oracle ⇄ true price (health/liquidation) | **irreducible** — validity-gated trust |
| 4 / ceiling | Bank config (weights/caps/curve/fees), pause, upgrade authority | **trust-boundary debt (by design)** — collateral-weight & oracle-source are apex-relevant |

## What this audit did NOT cover (coverage honesty)

- The interest *application* site (`marginfi_group.rs::accrue_interest`) and the share↔amount
  rounding reconciliation — the rate model was verified; its rounded application was not.
- The borrow-side health/margin gate and the liquidation engine (collateral/liability weights,
  liquidator incentives, bad-debt/bankruptcy) — the solvency counterpart to the interest book.
- The external adapters' internal CPI/value-reading logic (`kamino.rs` etc.) — flagged as the
  top follow-up, not traced.
- Emode (`emode.rs`), rate limiter, staked-collateral settings, Token-2022 paths.

## Nothing routed privately

No untrusted-input→value path found. Interest accrual conserves by construction — the fees
folded into the borrow rate are exactly the fees collected, so borrower interest equals lender
interest plus fees (recompute-verified). The residual trust is the corpus norm plus a lending-
specific twist: the **oracle** (collateral valuation, irreducible) and — most notably — the
**cross-protocol value-reporting seam** (marginfi accounting for funds held inside
Kamino/Solend/Drift/JupLend, which it must trust those programs to report honestly). That
integration seam, being full-source here, is the highest-value target for a deeper pass.
Companion to `AUDIT-DRIFT-PERP.md` (oracle 6b), `AUDIT-METEORA-VAULT-SDK.md` (the closed-source
version of this same value-reporting risk), and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9/§11 (a
new "lending" rung: conservation as a self-consistent rate decomposition; residual at the
cross-protocol + oracle seams).
