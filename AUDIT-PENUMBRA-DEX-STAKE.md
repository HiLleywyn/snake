# Penumbra — DEX Swap & Staking-Penalty Arithmetic: Conservation Review

**Target:** `penumbra-zone/penumbra` @ `36a31c1`. **Question hunted:** *not*
"can I counterfeit," but **"can rounding, rate conversion, or penalty math
systematically create more claimable value than was consumed?"**
**Read-only.** No exploit code, PoCs, or invalid-witness tests written.
**Verdicts (strict):** `enforced` · `deterministic safe rounding` ·
`governance/trusted parameter assumption` · `unclear needs human review` ·
`not enforced`.

---

## Answer

**No systematic value-creating path was found in the reviewed arithmetic.** The
design is consistently *protocol-favorable*: trade **outputs round down**, trade
**inputs round up**, batch **pro-rata rounds down and is circuit-enforced**, and
**penalty / exchange-rate conversions round down**. Underneath all of it, the
DEX **Value Circuit Breaker** is a checked, fail-closed per-asset accounting
invariant. The residual items are a precision/`round-once` documentation
mismatch (low severity) and a workspace-level `overflow-checks` hardening
recommendation — neither is a live value-creation path.

---

## Rounding & arithmetic primitives (foundation)

| Primitive | File:line | Behavior |
|---|---|---|
| `U128x128::round_down` | `num/fixpoint.rs:102-105` | floor |
| `U128x128::round_up` | `num/fixpoint.rs:108-116` | ceil, **checked** (errors on overflow) |
| `U128x128 * ` (`checked_mul`) | `num/fixpoint.rs:119-154` | **rounds down** (drops low 128 bits) |
| `U128x128 / ` (`checked_div`) | `num/fixpoint.rs:156-158` | **rounds down** (discards remainder) |
| `apply_to_amount` | `num/fixpoint.rs:182-189` | mul then **round_down** |
| `Amount::checked_add/sub` | `num/amount.rs:54-64` | checked (Option) |
| `Amount + / -` (operators) | `num/amount.rs:385-409` | **plain `u128`** — unchecked |

---

## Path-by-path

### SWAP EXECUTION

**S1 — `fill`, partial-fill branch** · `lp/trading_function.rs:322-336`
- **Op:** `lambda_2 = round_down(effective_price_inv · delta_1)`; `r1 += delta_1`, `r2 -= lambda_2`.
- **Invariant:** per-fill value conservation `R+Δ = R+Λ`; trader output ≤ fair.
- **Rounding:** output **down** — error retained by the pool.
- **Overflow:** `r1+delta_1` native unchecked add, but `r1 ≤ MAX_RESERVE_AMOUNT = 2⁸⁰` (`position.rs:15,164`) ⇒ no u128 overflow; `r2-lambda_2` guarded by `lambda_2 ≤ r2` (`:324-327`).
- **Trust boundary:** permissionless (anyone opens positions / submits swaps).
- **Verdict:** **deterministic safe rounding** (down).

**S2 — `fill`, max-fill branch** · `lp/trading_function.rs:353-386`
- **Op:** `fillable_delta_1 = round_up(effective_price · r2)`; `unfilled = delta_1 − fillable`; `r1 += fillable`, `r2 = 0`; output `= r2`.
- **Invariant:** input ≥ fair to drain `r2`; `unfilled ≥ 0` (proved `:365-379`).
- **Rounding:** input **up** — error retained by the pool. *But* `effective_price` (`:413-419`) is itself `(q/p)` then `/gamma`, **two round-downs**, then `convert_to_delta_1` multiplies (round-down) **before** the ceil — so the code's "we only round once … ensures conservation" comment (`:305-307`) is **not literally** met.
- **Overflow:** `round_up` checked; reserves bounded 2⁸⁰.
- **Trust boundary:** permissionless.
- **Verdict:** **deterministic safe rounding** (up) in all realistic ranges — the ceil dominates the sub-unit underestimate when `r2 ≤ 2⁸⁰`. The documentation/implementation mismatch on "round once" is **unclear needs human review** for precision only (worst-case the pool could receive ~1 base unit less than the ideal on an extreme-reserve drain; bounded, not systematically extractable). *Remediation:* compute `ceil(r2·q / (p·gamma))` as a single rational to honor the documented single-rounding.

**S3 — `fill_output` (router reverse fill)** · `lp/trading_function.rs:255-280`
- **Op:** `fillable_delta_1 = round_up(convert_to_delta_1(lambda_2))`; `r1 += fillable`, `r2 -= lambda_2` (guarded `lambda_2 ≤ r2`, `:246`).
- **Rounding:** input **up**. Same `effective_price` composition note as S2.
- **Verdict:** **deterministic safe rounding** (up); same precision note → **unclear needs human review** (documentation parity only).

**S4 — fee / `gamma`** · `lp/trading_function.rs:444-446`, `lp/position.rs:184`
- **Op:** `gamma = (10_000 − fee)/10_000`; `fee` is native `u32`.
- **Invariant:** `0 ≤ fee ≤ 5000` so `10_000 − fee` cannot underflow.
- **Overflow:** `fee > MAX_FEE_BPS (5000)` is **rejected** at `position.rs:184` (`check_stateless`).
- **Trust boundary:** position opener (permissionless) — but bound-checked.
- **Verdict:** **enforced** (fee bound at `position.rs:184`).

### POSITION RESERVES / LP

**S5 — reserve bounds & LP accounting** · `lp/position.rs:15,164-168`; `lp/reserves.rs`
- **Op:** reserves are `Amount`; `r1,r2 ≤ 2⁸⁰` enforced at open.
- **Invariant:** keeps all per-fill `Amount +/-` far below u128 overflow.
- **Verdict:** **enforced** (bound check). LP position NFT value is reconstructed from final reserves on withdraw and gated by the VCB (see S11).

### BATCH SWAP PRO-RATA (the classic "sum of shares > total" bug)

**S6 — `pro_rata_outputs` (host)** · `dex/batch_swap_output_data.rs:47-83`
- **Op:** `share = delta_i/delta` (round-down), `lambda_i = round_down(share·lambda + share·unfilled)`.
- **Invariant:** `Σ_i lambda_i ≤ lambda` (no over-distribution); dust stays in the DEX.
- **Rounding:** **down** (division and final `round_down`).
- **Verdict:** **deterministic safe rounding** (down).

**S7 — pro-rata enforced in the swap-claim circuit** · `dex/batch_swap_output_data.rs:229-276` + `dex/swap_claim/proof.rs:269-298`
- **Op:** the circuit recomputes pro-rata (`round_down` at `:272-273`) and `enforce_equal`s the claimed output-note amounts (`proof.rs:274-275`), which feed the output note commitments (`:286-298`).
- **Invariant:** a claimant cannot mint more than their floored pro-rata share.
- **Trust boundary:** permissionless claimant; `BatchSwapOutputData` is consensus-produced.
- **Verdict:** **enforced** (in-circuit equality) + **deterministic safe rounding** (down).

### STAKING PENALTY / EXCHANGE RATE

**S8 — penalty application** · `stake/penalty.rs:60-74` (`compound`, `apply_to_amount`)
- **Op:** kept-rate `∈ [0,1]`; `compound = k₁·k₂` (round-down); `apply_to_amount = round_down(amount·kept)`.
- **Invariant:** unbonded staking returned ≤ `kept · unbonding_amount`.
- **Rounding:** **down**; `from_percent/from_bps` use `saturating_mul` (`:25,32`); `from_bps_squared` asserts `≤ 1_0000_0000` (`:38`).
- **Trust boundary:** penalty is consensus-recorded slashing state (validator misbehavior), bound into the undelegate-claim proof as a public input.
- **Verdict:** **deterministic safe rounding** (down) + **governance/trusted parameter assumption** (the penalty value).

**S9 — delegation exchange rate** · `stake/rate.rs:142-167` (`delegation_amount`), `:195-210` (`unbonded_amount`), `:169-180` (`slash`)
- **Op:** delegate `= round_down(unbonded / rate)`; undelegate `= round_down(delegation · rate)`; slash `= round_down(rate · kept)`.
- **Invariant:** both conversion directions round **down**, so a delegate→undelegate round-trip strictly loses dust — never gains. The code comment (`:133-141,186-194`) documents this intentional asymmetry.
- **Trust boundary:** `validator_exchange_rate` is consensus state (reward/penalty driven), not user-chosen.
- **Verdict:** **deterministic safe rounding** (down) + **governance/trusted parameter assumption** (exchange rate).

### u128 / Amount CONVERSIONS & OVERFLOW

**S10 — native `Amount` operators are unchecked** · `num/amount.rs:385-409`; workspace `Cargo.toml`
- **Op:** `Amount + Amount` / `Amount - Amount` use plain `u128` `+`/`-`.
- **Overflow behavior:** the workspace sets **no `overflow-checks`** (only `[profile.dist]` exists, without it) ⇒ in release/dist builds these **wrap** instead of panicking.
- **Invariant intended:** none at the type level — safety relies on per-call-site guards (e.g. S1/S2) and value bounds (S5).
- **Trust boundary:** internal computation; the value-conservation boundary is the VCB (S11).
- **Verdict:** **not enforced** (at the type level). In the *reviewed DEX paths* it is unreachable (reserves ≤ 2⁸⁰) and backstopped by the VCB; for the rest of the codebase, confirming every `Amount +/-` is guarded is **unclear needs human review**. *Remediation:* set `overflow-checks = true` on release/dist profiles (defense-in-depth; turns any missed guard into a fail-closed panic rather than a silent wrap), or migrate hot paths to `checked_*`.

### CONSERVATION BACKSTOP

**S11 — DEX Value Circuit Breaker** · `dex/component/circuit_breaker/value.rs:26-80`
- **Op:** every DEX inflow `dex_vcb_credit` (`checked_add`, `:36`) and outflow `dex_vcb_debit` (`checked_sub`, `:65`) updates a per-asset balance.
- **Invariant:** **per-asset cumulative outflow ≤ inflow**; an underflowing debit **errors and aborts** the swap/block (test `:239-297`).
- **Overflow behavior:** explicit `checked_*` → fail closed.
- **Trust boundary:** protocol-level, wraps all DEX value movement.
- **Verdict:** **enforced** — this is the hard conservation invariant that makes any internal rounding/arithmetic slip non-value-creating: even if execution mis-accounted, the DEX cannot pay out more of an asset than was paid in.

---

## Bottom line

Against the actual question — *can rounding / rate / penalty math systematically
mint claimable value?* — the answer in the reviewed code is **no**:

- Every trade rounding is protocol-favorable (**output down / input up**), and
  conservation per fill is exact (S1–S3).
- Batch pro-rata is **round-down and circuit-enforced**, so `Σ` claims ≤ total
  (S6–S7).
- Penalty and exchange-rate conversions **round down** in both directions, so
  conversions and round-trips only lose dust (S8–S9).
- The **VCB** (`checked_add/checked_sub`, fail-closed) is a per-asset hard cap on
  outflow (S11), backstopping any arithmetic slip.

**Two hardening items, neither a live path:**
1. **S2/S3 precision** — `effective_price` is composed from pre-rounded
   sub-quantities before the ceil, so the "round once" guarantee in the comment
   isn't literally met; recommend a single-rational `ceil(r2·q/(p·gamma))`.
   *(unclear needs human review — precision/documentation, bounded ≤ ~1 base
   unit, not extractable.)*
2. **S10 overflow-checks** — native `Amount +/-` wraps in release; recommend
   `overflow-checks = true` on release/dist so any unguarded site fails closed.
   *(not enforced at type level; unreachable in reviewed DEX paths.)*

## Disclosure posture
Defensive arithmetic review of public code at a named commit; no value-creating
path demonstrated, no exploit/PoC written. Both residual items are
"tighten a bound / add a profile flag" hardening. Anything concrete would go to
Penumbra's security channel under coordinated disclosure, not a public PR.

## Files reviewed
`lp/trading_function.rs`, `lp/position.rs`, `lp/reserves.rs`,
`batch_swap_output_data.rs`, `swap_claim/proof.rs`,
`component/circuit_breaker/value.rs`; `stake/penalty.rs`, `stake/rate.rs`;
`num/fixpoint.rs`, `num/amount.rs`; workspace `Cargo.toml`.
