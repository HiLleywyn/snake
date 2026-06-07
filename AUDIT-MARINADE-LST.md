# Marinade Liquid Staking (mSOL) — Six-Bucket Trust Audit

**Target:** `marinade-finance/liquid-staking-program`, program `marinade-finance`
(Anchor, full source — real instruction bodies under `instructions/{user,management,crank,liq_pool,admin}`).
Cloned `/tmp/liquid-staking-program`. The canonical Solana LST: deposit SOL → mint mSOL;
redeem via delayed-unstake ticket (1:1, after cooldown) or instant **liquid-unstake** (mSOL→SOL
from an LP, minus a fee).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite
the exact constraint. Any untrusted-input→unvalidated→value path would route privately to
Marinade; none found. Focused on the conservation/arithmetic core (the LST's whole risk
surface), not an exhaustive read — coverage gaps stated.

**Why this target:** first **liquid-staking** entry in the corpus, and the first to pass the
"full-source" filter (`AUDIT-METEORA-VAULT-SDK.md`: real instruction bodies, not an SDK
mirror) cleanly. It is a fresh **§11 execution-model data point** — conservation in the
"stake-pool" model — against the canonical reference implementation.

---

## Bucket 1 / 5 — the mSOL↔SOL exchange rate (the LST core; enforced)

mSOL is a share token; its value is `total_virtual_staked_lamports / msol_supply`. Three
properties, all verifiable from source:

1. **Backing is an internal ledger, not a raw balance (donation-resistant).**
   `total_virtual_staked_lamports() = total_lamports_under_control() − circulating_ticket_balance`
   (`state/mod.rs:206`, `saturating_sub`), where `total_lamports_under_control =
   total_active_balance + total_cooling_down + available_reserve_balance` (`:190`) — all
   **tracked fields**, updated through deposit/unstake/crank paths. A raw SOL transfer into a
   reserve/leg account does **not** move the share price → the ERC-4626 first-depositor
   inflation attack is defeated at the design level (same defense seen in the Sui staking pool
   and Meteora vault). **enforced by design** — conditional on the cranks maintaining the
   ledger (the management/crank bodies are present but not exhaustively re-derived here).
2. **Rounding is pool-favorable both ways.** `proportional(amount, num, den)` (`calc.rs:11`)
   computes `(amount·num/den)` over `u128` with **truncating division (rounds down)**. Deposit
   mints `calc_msol_from_lamports = lamports·supply/value` (down → fewer mSOL minted); redeem
   `msol_to_sol = msol·value/supply` (down → less SOL out). Both favor the pool / remaining
   holders; dust accrues to the pool. **enforced.**
3. **Tickets don't dilute holders.** Delayed-unstake creates a ticket and adds to
   `circulating_ticket_balance`, which is **subtracted** from virtual staked (`:209`) — so SOL
   reserved for in-flight tickets is removed from the mSOL backing immediately, conserving
   value across the two redemption paths (instant LP vs delayed ticket). **enforced.**

**Caps & overflow:** `check_staking_cap` (`:196`) bounds `total_lamports_under_control` by
`staking_sol_cap`; `proportional` uses `u128` intermediates with a checked `u64::try_from`
(`calc.rs:15`) → `CalculationFailure` on overflow. **enforced.**

### Two honest hardening notes (not findings)

- **`proportional` returns `amount` when `denominator == 0`** (`calc.rs:12`–`14`). This is a
  deliberate first-mint convenience (`shares_from_value` mints 1:1 when `total_shares==0`,
  `:25`), but `proportional` is a *general* helper reused in `liq_pool`/`validator_system`; a
  future caller that hits a legitimately-zero denominator would get the raw `amount` back
  instead of an error. The current callers all guard, so it is latent, not live. **hardening
  debt** (a general math helper that silently no-ops on zero denominator is a foot-gun if
  reused without the guard).
- **Post-total-slashing degeneracy.** If `total_virtual_staked` saturates to 0 (`:207`
  comment: "if we get slashed it may be negative … use 0"), `msol_to_sol → 0` while new
  deposits mint 1:1. Purely theoretical — Solana mainnet has **no slashing today** — and the
  `saturating_sub` is the defensive choice; noted for completeness, not a finding.

---

## Bucket 5 — the instant liquid-unstake fee curve (enforced & bounded)

The LP lets a user swap mSOL→SOL immediately; the fee scales with how depleted the SOL leg
is, protecting LPs from cheap draining (`state/liq_pool.rs`):

```rust
fn linear_fee(&self, lamports: u64) -> Fee {           // lamports = SOL leg liquidity
    if lamports >= self.lp_liquidity_target { self.lp_min_fee }      // :68 full pool → min fee
    else { max - proportional(delta, lamports, target) }            // :71 linear interpolate
}                                                                    // delta = max − min
```

Recompute: at `lamports = target`, fee `= max − delta = min`; at `lamports = 0`, fee `= max`.
Monotonic, correct direction (emptier pool → higher fee). Since `lamports < target` in the
else-branch, `proportional(delta, lamports, target) < delta`, so the subtraction **cannot
underflow** and `fee ∈ (min, max)`. The discount is rounded **down** (`proportional`), so the
fee rounds **up** → LP-favorable. **enforced.**

`validate()` (`:101`) hard-bounds the curve: `lp_max_fee ≤ 10%` (`MAX_FEE`, `:34`), `max ≥
min` (right way round), `lp_liquidity_target ≥ 50 SOL` (`MIN_LIQUIDITY_TARGET`, prevents a
trivially-small target that would flatten/manipulate the curve), `treasury_cut ≤ 75%`. All
admin-set params are range-checked. **enforced by constraint.**

---

## Bucket 6 — settlement seams & delegation trust

- **6a (reduced, on-chain): the two redemption paths.** Instant (LP, fee) and delayed
  (ticket, 1:1, cooldown) are reconciled through `circulating_ticket_balance` so neither
  dilutes the other; the cranks (`stake_reserve`, `deactivate_stake`, `merge_stakes`,
  `redelegate`) move lamports between reserve/active/cooling-down while preserving the ledger.
- **6b (irreducible): mSOL value ⇄ real validator stake.** The deepest equivalence is "the
  ledger's `total_active_balance` equals SOL actually staked-and-earning at the delegated
  validators." That is maintained by the **off-chain validator set + crank operators** and the
  Solana stake program; the contract trusts the cranks to report and rebalance honestly within
  bounds (`max_stake_moved_per_epoch`, validator scores). This is the LST analogue of the
  bridge/rollup 6b: a representation (`total_active_balance`) the contract cannot itself prove
  against external reality each block. **named, irreducible** — discharged by the staking
  primitive + operator honesty, bounded by per-epoch movement caps.

---

## Bucket 4 / governance ceiling — where the residual trust sits

The arithmetic/conservation floor is strong; the ceiling is the admin/manager surface
(`instructions/admin/`, `instructions/management/`):
- **admin** (`config_marinade`, `config_lp`, `config_validator_system`, `change_authority`,
  `emergency_pause`) — fee curve params, caps, authority handoff, and a global pause.
- **validator manager** (`set_validator_score`, `add_validator`, `remove_validator`,
  `emergency_unstake`, `partial_unstake`) — controls *where* SOL is delegated, i.e. the 6b
  trust above. A malicious/compromised manager can't mint mSOL or break the exchange-rate math,
  but can steer delegation (within `max_stake_moved_per_epoch`) — a bounded but real power.
- **BPF upgrade authority** (off-repo) — apex power per `AUDIT-GOVERNANCE-CEILING.md`.

These are by-design administrative capabilities, range-checked where they touch the fee curve
(`liq_pool::validate`) and movement-capped where they touch delegation. Their key custody
(multisig/timelock) is the deployment fact to verify on-chain. **trust-boundary debt (by
design).**

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1/5 | mSOL↔SOL exchange rate | **enforced** — ledger-priced (donation-resistant), pool-favorable rounding both ways |
| 1 | Delayed-ticket non-dilution | **enforced** — `circulating_ticket_balance` removed from backing |
| 5 | Liquid-unstake linear fee curve | **enforced & bounded** — monotonic, no underflow, LP-favorable rounding, ≤10% hard cap |
| 5 | `proportional` zero-denominator → returns `amount` | **hardening debt** — latent foot-gun if reused unguarded |
| 6a | Two redemption paths reconciled | **reduced** — via ticket-balance accounting + cranks |
| 6b | mSOL value ⇄ real validator stake | **irreducible** — off-chain stake reality + operator honesty, movement-capped |
| 4 / ceiling | admin / validator-manager / upgrade authority | **trust-boundary debt (by design)** — fee params range-checked, delegation movement-capped |

## What this audit did NOT cover (coverage honesty)

- The crank state machine internals (`stake_reserve`, `deactivate_stake`, `merge_stakes`,
  `redelegate`, `update_active`/`update_deactivated`) beyond confirming they operate on the
  ledger fields — the ledger-maintenance correctness (Bucket-1 §1 condition) lives here and
  deserves its own pass.
- The delayed-unstake ticket lifecycle (`delayed_unstake_ticket.rs`, claim path) beyond the
  dilution accounting.
- `validator_system` stake-distribution math (`:270` proportional use) and scoring.
- LP add/remove liquidity share math (`liq_pool` mint/burn) beyond the fee curve.

## Nothing routed privately

No untrusted-input→value path found. The exchange rate is ledger-priced (donation-resistant)
with pool-favorable rounding both directions, tickets are removed from backing to prevent
dilution, and the instant-unstake fee curve is monotonic, underflow-free, LP-favorable, and
hard-capped. This is a strong conservation/arithmetic **floor** in the stake-pool model. The
residual trust is the corpus norm: the **6b delegation seam** (ledger `total_active_balance` ⇄
real staked SOL, discharged by the staking primitive + movement-capped operators) and the
**governance ceiling** (admin fee/cap params — range-checked; validator-manager delegation —
movement-capped; BPF upgrade authority). Two honest hardening notes (`proportional`
zero-denominator foot-gun; post-total-slash degeneracy — theoretical, no Solana slashing).
Companion to `AUDIT-METEORA-VAULT-SDK.md` (the share-accounting counterpart),
`AUDIT-GOVERNANCE-CEILING.md`, and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §11 (a new
"stake-pool" rung: conservation as ledger-priced runtime arithmetic + an off-chain delegation
6b).
