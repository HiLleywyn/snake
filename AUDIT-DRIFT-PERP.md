# Drift v2 (perpetuals DEX) — Six-Bucket Trust Audit

**Target:** `drift-labs/protocol-v2`, program `drift` (~149K LOC Rust/Anchor, full source —
real instruction bodies). Cloned `/tmp/drift`. Solana's canonical perps DEX: cross-margined
perps + spot lending, vAMM + orderbook fulfillment, funding, liquidation, insurance fund.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite
the exact constraint. Any untrusted-input→unvalidated→value path would route privately to
Drift; none found. **Tightly focused** on the one invariant that defines a perp's solvency —
*can settling PnL create value or drain the pool* — not an exhaustive 149K-line read.
Coverage gaps stated.

**Why this target:** first **perpetuals / derivatives** entry in the corpus, and the densest
conservation-arithmetic surface yet. It is a fresh **§11 execution-model data point**: in a
perp, conservation is *not* a single invariant (`Σ in == Σ out`) — it is a **layered
settlement cap**, because a position's "value" is a price-dependent claim, not a held balance.

---

## The perp conservation core: positive-PnL settlement is triple-capped (enforced)

A winning trader must be paid from a finite pool. If they could realize *unrealized* gains
freely, the pool would drain and last-out users would eat bad debt. Drift prevents this with
**three nested caps**, each verifiable from source.

### Cap 1 — per-user: claimable ≤ realized-by-closing + pool excess (`state/user.rs:1316`)

```rust
fn get_claimable_pnl(&self, oracle_price, pnl_pool_excess) -> i128 {
    let (_, unrealized_pnl) = calculate_base_asset_value_and_pnl_with_oracle_price(self, oracle_price)?;
    if unrealized_pnl > 0 {
        let max_positive_pnl = (quote_asset_amount − quote_entry_amount).max(0)   // realized by reducing/closing
                                 .safe_add(pnl_pool_excess.max(0))?;              // + pool's spare capacity
        Ok(unrealized_pnl.min(max_positive_pnl))                                  // ← the cap
    } else { Ok(unrealized_pnl) }                                                 // losers settle in full
}
```

The first term is the PnL **actually locked in by trading out of the position**
(`quote_asset_amount − quote_entry_amount`); the second is the pool's excess. A trader with an
open winning position therefore **cannot extract paper gains** beyond what they have realized
by closing plus what the pool can spare. This is the single most important line for perp
solvency. **enforced by constraint.**

### Cap 2 — market: pool excess = available tokens − net PnL owed to everyone (`controller/pnl.rs:236`)

```rust
let pnl_tokens_available = pnl_pool_token_amount + fee_pool_token_amount / 5;   // pool + 1/5 fee-pool buffer (:228)
let net_user_pnl = calculate_net_user_pnl(&perp_market.amm, oracle_price)?;     // aggregate owed across all users
let max_pnl_pool_excess = if net_user_pnl < pnl_tokens_available {
    pnl_tokens_available − net_user_pnl.max(0)                                  // only the surplus beyond all obligations
} else { 0 };
```

"Excess" is what remains **after the pool can cover everyone's net PnL** — so a single user's
positive settlement (Cap 1's second term) is funded only from genuine surplus, never from
funds owed to others. **enforced by constraint.**

### Cap 3 — settlement: only move what the pool actually holds (`controller/pnl.rs:261`)

`update_pool_balances(..., user_unsettled_pnl, ...)` returns `pnl_to_settle_with_user`, which
can be **less** than the capped claim if the pool still can't cover; settlement of 0 returns
`PnlPoolCantSettleUser` (`:281`). And a third party **cannot** crank a user's *positive*
settlement unless the pool is in excess or the user is being liquidated
(`user_must_settle_themself`, `:289`) — preventing forced realization griefing.

**Composite verdict (Bucket 1/6): enforced invariant** — positive PnL settlement is bounded
by `min(realized_by_closing + (pool − net_owed), actual_pool_balance)`. Three independent caps
mean settling a winner provably cannot mint value or draw the pool below collective
obligations. Losers (`unrealized_pnl < 0`) settle in full but only against their own collateral
(`InsufficientCollateralForSettlingPNL`, `controller/pnl.rs:117`), moving the loss to their
balance rather than creating bad debt elsewhere.

---

## Bucket 5 — arithmetic discipline (enforced)

All value math goes through `safe_math.rs` (`safe_add/sub/mul/div` → `MathError`) and
`casting.rs` (checked `cast::<T>()`), with explicit `ceil_div.rs` / `floor_div.rs` for
**rounding-direction control** — the perp equivalent of an AMM's pool-favorable rounding
(fees/funding round against the user, payouts round down). The conservation caps above are
built from these (`safe_sub`, `.max(0)`, `safe_add`). No unchecked arithmetic on the PnL path
reviewed. **enforced** (spot-checked, not exhaustively proven across 149K LOC).

---

## Bucket 6b — the irreducible residual: the oracle

Every quantity above — `unrealized_pnl`, `net_user_pnl`, health/margin, liquidation triggers —
is computed `with_oracle_price`. **The entire conservation edifice is priced at the oracle.**
The contract cannot prove the oracle equals the true market price; it can only bound *trust* in
it. Drift's defenses (`math/oracle.rs`): staleness, confidence-interval, and mark-vs-oracle
divergence checks gate whether a price is `Valid` before it is used. But the equivalence
*"oracle price ⇄ real market price"* is **irreducible** — the derivatives analogue of the
bridge/rollup/LST 6b seam (`RETROSPECTIVE §9`): a representation of external reality the system
must accept, discharged here by **oracle-aggregator trust + validity gating + confidence
bounds**, never by an in-program proof. This — not the PnL arithmetic — is where a perp's real
risk concentrates. **named, irreducible.**

---

## Bucket 4 / governance ceiling & the solvency backstop

- **Insurance Fund + bankruptcy (the last-resort conservation layer).** When pool + IF cannot
  cover (a position goes bankrupt with negative equity), `controller/liquidation.rs` +
  `math/bankruptcy.rs` **socialize the loss** across the market (reducing all holders' claims)
  rather than minting value. This is the explicit "conservation by loss-socialization" backstop
  — the perp's equivalent of a rollup's escape hatch: the system stays solvent by *distributing*
  the shortfall, transparently. **enforced (backstop).**
- **Admin ceiling.** Market creation/params, oracle-source configuration, fee/margin ratios,
  and pause are admin-gated; the **oracle source choice** is itself an admin power that sits
  upstream of the 6b residual (a bad oracle config undermines all of §Bucket-6b). Plus the BPF
  upgrade authority (apex, `AUDIT-GOVERNANCE-CEILING.md`). **trust-boundary debt (by design)** —
  and here the most consequential ceiling power is *which oracle*, not fee tuning.

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1/6 | Positive-PnL settlement (3 nested caps) | **enforced invariant** — claimable ≤ realized-by-closing + (pool − net owed), ≤ actual pool balance |
| 1 | Negative-PnL settlement | **enforced** — full, but against own collateral (no premature bad debt) |
| 5 | Safe-math + checked casts + ceil/floor rounding | **enforced** (spot-checked) |
| 6b | Oracle ⇄ true market price | **irreducible** — validity/staleness/confidence-gated trust, never proven; the real risk locus |
| 4 | Insurance fund / bankruptcy socialization | **enforced backstop** — solvency by loss-distribution, not minting |
| ceiling | Admin (esp. oracle-source choice) + upgrade authority | **trust-boundary debt (by design)** — "which oracle" is the apex-relevant power |

## What this audit did NOT cover (coverage honesty)

149K LOC — this pass deliberately scoped to the **PnL-settlement conservation** invariant.
Not reviewed in depth: the vAMM curve / repeg / amm-spread, funding-rate accrual, the
liquidation engine's margin math and liquidator incentives, orderbook matching/auctions/JIT,
spot lending interest accrual, the LP pool, and the oracle validity internals beyond their
role. Each is a substantial surface; the settlement cap was chosen as the single
perp-defining invariant.

## Nothing routed privately

No untrusted-input→value path found. Positive-PnL settlement is triple-capped so a winner
cannot mint value or drain the pool below collective obligations; losses settle against own
collateral; shortfalls socialize through the insurance-fund/bankruptcy backstop rather than
breaking conservation; arithmetic is checked with explicit rounding control. This is a strong,
sophisticated conservation **floor** for the derivatives model — *conservation as a layered
settlement cap rather than a single equation*. The irreducible residual is the **oracle** (and
the admin power to choose it), exactly where a perp's trust must ultimately sit. Companion to
`AUDIT-MARINADE-LST.md` and `AUDIT-METEORA-DAMM-V2.md` (other full-source conservation floors)
and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9/§11 (the oracle 6b; a new "derivatives" rung where
the floor is a settlement cap and the ceiling is the oracle choice).
