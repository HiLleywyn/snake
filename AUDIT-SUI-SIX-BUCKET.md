# Sui — Six-Bucket Trust Audit (Object 0x2 Move package → Rust epoch-change layer)

**Target:** `sui::balance` / `sui::coin` (framework object `0x2`), `sui_system` (`0x3`),
and the Rust execution adapter that drives epoch change.
**Source:** MystenLabs/sui, cloned `/tmp/sui` (HEAD `5406f210`).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. A verdict says
"enforced by constraint X" / "deterministically derived at Y" / "not enforced in
reviewed path" / "unclear, needs human review" — never bare "safe."

This audit deliberately crosses a layer boundary, because Sui's value-conservation
story is split across two languages: the **Move type system** (user coins) and the
**Rust consensus/execution layer** (the native SUI coin's per-epoch supply delta).
The headline of the Move-only pass was that the second half lives in Rust; this pass
went and read it.

---

## Bucket 1 — Conservation

### 1a. User coins: enforced by the Move type system (strongest discharge in the series)

`balance.move`:

```move
public struct Supply<phantom T> has store { value: u64 }   // :30
public struct Balance<phantom T> has store { value: u64 }  // :36
```

Both have `store` and **lack `copy` and `drop`**. In Move that is not a convention —
it is a checked property of the bytecode verifier enforced at *publish* time. A value
of a type without `copy` cannot be duplicated; a value of a type without `drop` cannot
be silently discarded. Therefore a `Balance<T>` cannot be forged (no copy) and cannot
vanish (no drop) — it can only be created through `increase_supply` (which bumps
`Supply.value`, `:56`), split/joined (value-preserving, `:76`/`:83`), or burned through
`decrease_supply` (which lowers `Supply.value`, `:63`). The invariant

> Σ all live `Balance<T>` == `Supply<T>.value`

holds *by construction* for every `T` that goes through this module, and the proof
obligation is discharged by the type checker, not by a runtime assert. This is the
cleanest Bucket-1 result we have recorded — stronger than an asserted balance equation,
because there is no path that even *could* violate it that the verifier would admit.

**Verdict: enforced invariant** (compile-time, by linear typing).

### 1b. The native SUI coin: NOT type-enforced. Two holes are cut on purpose.

`balance.move` has a `=== SUI specific operations ===` section (`:128`) with two
private functions that deliberately break the linear-type discipline:

```move
fun create_staking_rewards<T>(value: u64, ctx: &TxContext): Balance<T> {  // :141
    assert!(ctx.sender() == @0x0, ENotSystemAddress);
    assert!(<T == 0x2::sui::SUI>, ENotSUI);
    Balance { value }            // a Balance with NO matching Supply increase
}
fun destroy_storage_rebates<T>(self: Balance<T>, ctx: &TxContext) {        // :154
    assert!(ctx.sender() == @0x0, ENotSystemAddress);
    assert!(<T == 0x2::sui::SUI>, ENotSUI);
    let Balance { value: _ } = self;   // a Balance destroyed with NO Supply decrease
}
```

These are the only two ways SUI changes total amount outside of `increase_supply`/
`decrease_supply`. They are gated by **two constraints, both asserted in-line**:

1. `ctx.sender() == @0x0` — only the system (epoch-change) transaction runs as `0x0`.
   A normal user transaction cannot have sender `0x0`; that is enforced by signature
   verification upstream (a user must sign, `0x0` has no key).
2. `T` must be exactly `0x2::sui::SUI` (compared by fully-qualified type name with
   defining IDs, `:144`/`:157`) — these holes cannot be turned on any other coin.

The two functions carry `#[allow(unused_function)]` and are **private** (`fun`, not
`public`). Grepping the entire Move corpus confirms **there is no Move caller**:

```
$ grep -rn 'create_staking_rewards|destroy_storage_rebates' crates/.../*.move
  → only the definitions in balance.move (+ docs/bytecode)
```

So who calls them? The Rust execution layer, by *name*, when it assembles the
epoch-change programmable transaction. That is the seam this audit follows.

**Verdict (Move layer): not enforced in the reviewed (Move) path — by design.**
The native-SUI conservation obligation is *relocated* to Rust. Tracked below.

---

## The relocation, traced end to end (recompute, not summary)

### Step 1 — Move `advance_epoch` receives rewards; it never mints them.

`sui_system.move:589`:

```move
fun advance_epoch(
    storage_reward: Balance<SUI>,       // passed IN
    computation_reward: Balance<SUI>,   // passed IN
    ...
): Balance<SUI> {                       // storage_rebate passed OUT
    assert!(ctx.sender() == @0x0, ENotSystemAddress);   // :604 — same 0x0 gate
    ...
}
```

The Move epoch entrypoint is a *pure function of balances handed to it*. It does not
create or destroy SUI; it routes reward balances to validators and returns the
storage-rebate balance. The mint and the burn happen *outside* it.

### Step 2 — The Rust adapter builds the mint→advance→burn PT.

`sui-execution/latest/sui-adapter/src/execution_engine.rs`:

`mint_epoch_rewards_in_pt` (`:1150`) emits two `programmable_move_call`s to
`balance::create_staking_rewards` — one for `params.storage_charge`, one for
`params.computation_charge` (`:1160`, `:1174`). `construct_advance_epoch_pt` (`:1184`)
then:

1. mints the two reward balances,
2. passes them into `sui_system::advance_epoch` (`:1216`),
3. takes the returned rebate balance and feeds it to `balance::destroy_storage_rebates`
   (`:1225`).

So the entire native-SUI supply delta for the epoch is:

```
ΔSUI = (storage_charge + computation_charge)   [minted, create_staking_rewards]
     − storage_rebate                          [burned, destroy_storage_rebates]
```

and all three numbers come straight off the `ChangeEpoch` struct (`:1294`–`:1304`),
which is built by **consensus**, not by the executor.

### Step 3 — The runtime conservation guard, and the exemption that matters.

Every non-genesis transaction is run through `run_conservation_checks` (`:700`), which
calls `check_sui_conserved_expensive` (`temporary_store.rs:1382`) when expensive checks
are on. That function sums total SUI in input objects vs output objects (including the
storage-rebate field carried on every object, and accumulator events) and requires
`total_input_sui == total_output_sui`, panicking otherwise (`execution_engine.rs:753`).
For a *normal* tx this is an airtight Bucket-1 guard: the executor itself refuses to
mint or burn SUI.

**But the epoch tx is special, and this is the crux.** Look at how the equation is
balanced for the epoch tx (`temporary_store.rs:1424`):

```rust
total_output_sui += gas_summary.computation_cost + gas_summary.non_refundable_storage_fee;
if let Some((epoch_fees, epoch_rebates)) = advance_epoch_gas_summary {
    total_input_sui  += epoch_fees;     // == computation_charge + storage_charge
    total_output_sui += epoch_rebates;  // == storage_rebate
}
```

and where `advance_epoch_gas_summary` comes from (`transaction.rs:1944`):

```rust
Some((e.computation_charge + e.storage_charge, e.storage_rebate))
```

**The same three numbers from `ChangeEpoch` that are used to *mint and burn* the SUI
(Step 2) are added to the conservation equation to *balance* it (Step 3).** The check
is therefore tautological for the epoch transaction: if `computation_charge` were
inflated, the executor would mint that many extra SUI via `create_staking_rewards`
*and* add the identical figure to `total_input_sui`, so `input == output` still holds
and the guard stays green. The expensive conservation check verifies that **the PT
moved exactly the SUI it declared** — it does **not** verify that **the declaration is
correct**.

This is reinforced by the FIXME at `execution_engine.rs:692`:

```rust
// FIXME: we cannot fail the transaction if this is an epoch change transaction.
result = Err(e);
```

The one transaction whose amounts are *not* independently re-derivable by the local
conservation check is also the one the executor structurally cannot abort.

**Where the real constraint lives:** the correctness of `storage_charge`,
`computation_charge`, and `storage_rebate` is established **upstream in consensus** —
they are the aggregation of the per-checkpoint `GasCostSummary`s over the epoch, and
all honest validators recompute the same `ChangeEpoch` deterministically from the
agreed checkpoint contents. A single validator cannot forge these figures because the
epoch-change tx's effects must match across the BFT quorum. So the invariant is real;
it is just discharged by **deterministic re-execution + BFT agreement**, not by the
Move type system and not by the local conservation check.

**Verdict: trust-boundary debt (by design, discharged elsewhere).** SUI's per-epoch
supply delta is a Bucket-6a inter-layer deferral: the Move/execution layer trusts a
summary (`ChangeEpoch`) produced by the consensus layer, and the proof that the summary
is honest is a *reproducibility* argument (every validator derives the same number),
not a local check. This is the correct place to put it — but it should be named, not
assumed, and "the conservation check is green" must **not** be read as "the epoch
mint amount is correct." It cannot see that.

---

## Bucket 2 — Witnessed cryptographic objects

- **One-time witness for `Supply`.** `create_supply<T: drop>(_: T)` (`balance.move:51`)
  consumes a `drop` witness; combined with the one-time-witness pattern in `coin.move`
  (`create_currency<T: drop>`), this makes "there is at most one `Supply<T>` per coin
  type" a checked property — minting authority is a unique, non-forgeable capability.
- **`TreasuryCap<phantom T> has key, store`** (`coin.move:80`) wraps the `Supply` — mint
  authority is an *object* you must possess, transferable but not copyable.
  **enforced invariant.**
- **`0x0` sender as a capability.** The system-address gate on the SUI holes and on
  `advance_epoch` is "witnessed" by the absence of any private key for `0x0`. This is a
  cryptographic fact (no signature can claim `0x0`) reused as an authorization
  primitive. **enforced by constraint (signature verification upstream).**

## Bucket 3 — Dual representations

- **`u64` (Move `Balance.value`) ↔ `u64` (Rust `Balance { value }`, `balance.rs:43`).**
  Same width, same BCS layout (`Balance::layout`, `:115`, asserts a single `U64` field).
  The Rust side is the deserialization mirror of the Move struct; `is_balance_layout`
  (`:126`) re-validates the shape before trusting it. No width mismatch. **deterministically
  derived.**
- **`u128` accumulator ↔ `u64` balance.** `settled_funds_value` (`balance.move:119`)
  reads a `u128` from the accumulator root and clamps with `min(u64::MAX, val)` before
  the `as u64` cast (`:124`). The clamp prevents a silent truncation wrap; a value above
  `u64::MAX` saturates rather than wrapping. **enforced by constraint (explicit min before cast).**
  *Note (hardening debt, not a finding):* saturation means a (pathological, system-only)
  over-`u64::MAX` accumulator reads back as `u64::MAX` rather than aborting; this is a
  read-side view function, not a settlement path, so it does not move value.

## Bucket 4 — Dependency / fork lineage

- **System-state versioning.** `load_inner_maybe_upgrade` (`sui_system.move:642`) lazily
  migrates `SuiSystemStateInner` v1→v2 and asserts `inner.system_state_version() ==
  self.version` (`:654`) on every load — a fork/version-skew guard. **enforced by constraint.**
- **System package upgrades** run inside the same epoch-change tx (`process_system_packages`,
  `execution_engine.rs:1355`) and `.expect("System Package Publish must succeed")` — a
  failed framework upgrade is a hard stop, not a silent skip. Lineage of the framework
  bytecode is therefore tied to epoch boundaries and to consensus agreement on
  `change_epoch.system_packages`.

## Bucket 5 — Arithmetic / bounds

- `increase_supply` asserts `value <= u64::MAX - self.value` before adding (`:57`) —
  explicit overflow guard. **enforced by constraint.**
- `decrease_supply` / `split` assert sufficiency (`self.value >= value`, `:65`/`:84`) —
  no underflow. **enforced by constraint.**
- `join` (`:78`) relies on Move's native u64 add-overflow abort rather than an explicit
  check. This is sound (Move aborts on u64 overflow) but is *implicit* where the sibling
  functions are explicit — **hardening debt** (cosmetic asymmetry, not a hole; the native
  abort is a real constraint).
- Rust `Balance::withdraw` (`balance.rs:91`) re-checks `self.value >= amount` with
  `fp_ensure!`; `deposit_for_safe_mode` (`:103`) does a bare `+=` — safe because it is
  only reachable on the system safe-mode path with consensus-supplied amounts, but it is
  the Rust mirror of the `join` implicit-overflow point. **not enforced in reviewed path
  (relies on caller being the system tx); needs human review if ever exposed.**

## Bucket 6 — Cross-layer settlement seams

- **6a (reducible, inter-layer deferral): the SUI epoch supply delta.** Documented above.
  Move trusts `ChangeEpoch`; `ChangeEpoch` is trusted because consensus re-derives it
  deterministically. The conservation check is tautological for this one tx, and the tx
  cannot be failed. This is the single largest residual and it is *correctly placed* —
  but it is trust-boundary debt that must be named.
- **6b (irreducible, interpretation): "gas charged this epoch" → "SUI to mint."** The
  semantic equivalence "the rewards we mint equal the fees burned during the epoch" is an
  *interpretation* glue between the gas subsystem and the supply subsystem. The code comment
  at `temporary_store.rs:1173` states the intended equality ("mints staking rewards equal
  to the gas fees burned in the previous epoch"); the *enforcement* of that equality is the
  consensus aggregation, not a local invariant. Irreducible: no amount of proving inside
  one tx can establish that the aggregated epoch figure faithfully summed the epoch's real
  gas, because the evidence for that lives in other transactions in other checkpoints.
- **Safe mode** (`advance_epoch_safe_mode`, `temporary_store.rs:1084`; PT builder
  `execution_engine.rs:1235`) is the fallback when the normal epoch PT *errors*: writes are
  dropped (`:1329`), storage cost/rebate reset (`:1331`), and the rewards are deposited
  directly into the `0x5` system object rather than distributed. This is a graceful
  degradation seam — it preserves conservation (the minted balance still lands somewhere
  accounted) while skipping distribution. Worth a dedicated human read if ever changed.

---

## Summary table

| Bucket | Subject | Verdict |
|---|---|---|
| 1a | User coins `Balance<T>`/`Supply<T>` | **enforced invariant** — compile-time linear typing (Σ Balance == Supply by construction) |
| 1b | Native SUI mint/burn holes | not enforced in Move; **relocated** to Rust+consensus |
| 1b→6a | SUI epoch supply delta | **trust-boundary debt** — conservation check is tautological for the epoch tx; correctness discharged by consensus re-derivation + BFT, not by a local check |
| 2 | `Supply` OTW / `TreasuryCap` / `0x0` sender | **enforced** (unique capability objects; no key for 0x0) |
| 3 | Move↔Rust `Balance`; u128↔u64 accumulator | **deterministically derived** / **enforced** (explicit clamp before cast) |
| 4 | System-state version + framework upgrade lineage | **enforced** (version assert; publish-must-succeed) |
| 5 | Supply over/underflow guards | **enforced** explicitly; `join`/`deposit_for_safe_mode` rely on native abort (**hardening debt**) |
| 6a | Epoch supply delta inter-layer deferral | irreducibly relocated, correctly placed, must be **named** |
| 6b | "fees burned" ⇄ "rewards minted" equivalence | **irreducible interpretation** — enforced by consensus aggregation, not locally |

## What this audit did NOT cover (coverage honesty)

- The consensus-side construction and BFT agreement on `GasCostSummary`/`ChangeEpoch`
  (the place where the 6a/6b trust is actually discharged) — read only at its interface,
  not its internals.
- ~~The stake-subsidy fund's own conservation (`stake_subsidy.move::advance_epoch`)~~ —
  **now covered in the Addendum below (Pass 2).** Short version: there is no genuinely new
  issuance; the subsidy is a drawdown of a genesis-pre-allocated `Balance<SUI>`.
- ~~`validator_set.move` reward distribution / slashing arithmetic~~ — **now covered in
  the Addendum below (Pass 3).** Conservation is type-enforced; every arithmetic residual
  degrades to a checked abort, never to minted/burned SUI.
- Older execution-adapter versions (`v0`–`v3`) — they carry the same call sites but were
  not diffed against `latest`.

---

# Addendum — Pass 2: Is SUI *inflation* bounded? (`stake_subsidy.move` → `genesis.move`)

Pass 1 answered "is the per-epoch supply delta *conserved*" (yes, by consensus
agreement). It did **not** answer the orthogonal question every token audit must ask:
"is *new issuance* bounded?" Those are different — a chain can conserve value per-tx
while still inflating without limit if rewards are minted from nothing. So I followed
the stake-subsidy path, which is where any inflation would live.

The result reframes the question: **on Sui there is no inflation in the supply sense at
all.** What is called the "stake subsidy" is a *drawdown of a finite, pre-minted balance
carved out of the genesis supply* — not creation of new tokens.

### The drawdown is overdraft-proof and self-limiting (`stake_subsidy.move`)

`StakeSubsidy.balance: Balance<SUI>` (`:16`) is a real linear `Balance` — the same
`store`-without-`copy`/`drop` type whose conservation the bytecode verifier enforces
(Pass 1, Bucket 1a). Each epoch draws from it via:

```move
let to_withdraw = self.current_distribution_amount.min(self.balance.value());  // :59
let stake_subsidy = self.balance.split(to_withdraw);                           // :62
```

Two independent guards make over-issuance impossible:
1. **`.min(self.balance.value())`** (`:59`) — the draw is clamped to the remaining fund,
   so it can never request more than exists.
2. **`split` itself asserts `self.value >= value`** (`balance.move:84`, `ENotEnough`) —
   even if the clamp were wrong, the linear-type split would abort, not overdraft.

Cumulative subsidy is therefore bounded above by the initial fund balance, full stop.
The amount also **decays geometrically**: every `stake_subsidy_period_length`
distributions it is reduced by `stake_subsidy_decrease_rate` bps (`:66`–`:73`). The
decrease arithmetic is safe: `decrease_rate <= 10000` is asserted at construction
(`:39`), so `decrease_amount = current * rate / 10000 <= current`, and the subtraction
at `:72` cannot underflow; the `u128`→`u64` cast is bounded by `current`.

**Verdict: enforced invariant** — cumulative stake subsidy ≤ genesis subsidy fund, by
linear typing + explicit overdraft clamp. Inflation is not merely bounded, it is *finite
and pre-allocated*.

### The fund is carved from genesis supply, and genesis is fully partitioned (`genesis.move`)

The fund is not minted — it is split off the one-time genesis supply (`:137`):

```move
let subsidy_fund = sui_supply.split(stake_subsidy_fund_mist);   // carve out the fund
...
allocate_tokens(sui_supply, allocations, &mut validators, ctx); // distribute the rest
...
sui_supply.destroy_zero();   // :206 — ABORTS unless the remainder is exactly zero
```

`sui_supply: Balance<SUI>` is the genesis-minted total (the one tx where conservation is
deliberately skipped — `execution_engine.rs:761`, "genesis transaction which mints the
SUI supply"). The closing `destroy_zero()` (`:206`) is a **linear-type conservation
assertion at the protocol's birth**: genesis cannot complete unless
`Σ allocations + subsidy_fund == total minted`, with no remainder (`destroy_zero` aborts
on non-zero, `balance.move:97`) and no overdraft (each `split` aborts on insufficiency).
The genesis books must balance to the mist or the chain does not start.

**Verdict: enforced invariant** — total SUI is fixed at genesis and exhaustively
partitioned; subsequent "rewards" are recycled gas (Pass 1) plus subsidy drawdown (this
pass), neither of which raises total supply.

### Where this lands

| Subject | Verdict |
|---|---|
| Stake-subsidy drawdown (overdraft) | **enforced invariant** — `.min()` clamp + linear `split` assert; ≤ fund balance |
| Stake-subsidy decay arithmetic | **enforced** — `rate <= 10000` asserted ⇒ no underflow / safe cast |
| Genesis supply partition | **enforced invariant** — `destroy_zero()` forces exact partition (no remainder, no overdraft) |
| "Sui inflation" framing | **reframed** — not new issuance; a finite genesis-allocated fund released over time |

### Two honest residuals from Pass 2 (neither is a finding)

- **`stake_subsidy_period_length` is not asserted non-zero.** `advance_epoch` computes
  `distribution_counter % stake_subsidy_period_length` (`:66`); a zero period length
  would be a division-by-zero abort. It is a genesis/governance parameter (trusted system
  config, not user input), and a zero value would brick epoch change loudly rather than
  move value — **constraint debt**, not exploitable. Worth a one-line assert in `create`.
- **The hardcoded epoch-560 catch-up branch** (`sui_system_state_inner.move:921`,
  `distribution_counter == 540 && old_epoch > 560`) is a one-time historical
  reconciliation for a mainnet safe-mode incident (the 560→561 change where reward
  distribution was skipped — the very safe-mode seam flagged in Pass 1, observed firing
  in production). It is bounded and self-limiting: each catch-up still routes through
  `advance_epoch()`'s `.min()` clamp (so it cannot exceed the fund), and the
  `counter == 540` guard is a one-shot (after catch-up the counter exceeds 540 and the
  branch is never re-entered). It is *evidence* that the safe-mode degradation path is
  real and has been exercised — a good audit signal, not a defect. **enforced / bounded.**

---

# Addendum — Pass 3: Reward distribution & slashing arithmetic (`validator_set.move`)

Passes 1–2 established that SUI is conserved per-epoch and fixed globally. This pass
reads the *inside* of the epoch reward split — `validator_set::advance_epoch` and its
`mul_div!` proportional math — to check whether the distribution itself can leak, mint,
or misallocate value. The conclusion is the strongest structural one in the report:
**the reward arithmetic does not need to be correct for conservation to hold; it only
needs to be not-too-large.** Linear typing carries the invariant; the numbers are
advisory.

### Conservation is enforced by the `Balance` type, not by the amount math

`advance_epoch` (`sui_system_state_inner.move:959`) passes `computation_reward` and
`storage_fund_reward` **by `&mut`** into `validators.advance_epoch`, which computes a
vector of per-validator amounts and then `split`s them out (`validator_set.move:1197`,
`:1207`, `:1210`). The amounts come from `compute_unadjusted_reward_distribution` /
`compute_adjusted_reward_distribution`. But note what actually moves value: every payout
is a `Balance::split`, which **asserts `self.value >= value`** (`balance.move:84`).

Therefore, whatever the amount vectors say:
- If they sum to **more** than the balance, the offending `split` *aborts* — the epoch
  tx fails and falls into safe mode (the seam from Pass 1), distributing nothing
  improperly. No over-payment is possible.
- If they sum to **less** (the normal case, due to integer truncation), the remainder
  stays in the `&mut` balances and is **explicitly swept to the storage fund**:

```move
// sui_system_state_inner.move:983
// Because of precision issues with integer divisions, we expect that there will be some
// remaining balance ... All of these go to the storage fund.
let mut leftover_staking_rewards = storage_fund_reward;
leftover_staking_rewards.join(computation_reward);   // :987 — dust captured, not dropped
```

So no SUI is minted (splits can't exceed the balance) and none vanishes (`Balance` has
no `drop`; the dust is `join`ed onward). The code even keeps an explicit **recompute
witness** of how much left each balance:

```move
let computation_reward_distributed =                 // :974
    computation_reward_amount_before_distribution - computation_reward_amount_after_distribution;
```

**Verdict: enforced invariant** — distribution conservation is a property of the linear
`Balance` type, independent of the correctness of the `mul_div!` results.

### The slashing redistribution is exactly conservative (modulo dust)

`compute_reward_adjustments` (`:1007`) accumulates `total_staking_reward_adjustment` in
lockstep with each `individual_staking_reward_adjustment` it records (`:1033`–`:1035`).
In `compute_adjusted_reward_distribution`, slashed validators have their adjustment
*subtracted* (`:1151`), and unslashed validators have a proportional share of the same
total *added* (`:1155`–`:1161`, by `mul_div!(total_adjustment, voting_power,
total_unslashed_voting_power)`). The amount removed from the punished set therefore
equals the amount redistributed to the honest set, up to the truncation in the
proportional `mul_div!` — and that truncation is, again, swept to the storage fund.
**Slashed rewards are never burned and never minted; they flow to honest validators or
to the storage fund.** Slashing here is a *re-routing* of reward flow, not a destruction
of SUI. **enforced invariant** (re-routing conserved by linear typing).

### Arithmetic / bounds (Bucket 5, the dangerous part)

`mul_div!` is `((a as u128) * (b as u128) / (c as u128)) as u64` (`:1312`).

- **Multiplication overflow:** none. `u64::MAX² < 2¹²⁸`, so the `u128` product never
  overflows — this is exactly what the `as u128` widening buys. **enforced by constraint.**
- **The final `as u64` cast:** Move casts are *checked* — a `u128 → u64` that exceeds
  `u64::MAX` **aborts**, it does not wrap. For the share computations (`mul_div(vp_i,
  total, total_vp)` with `vp_i ≤ total_vp`) the result is provably `≤ total ≤ u64::MAX`,
  so the cast is safe by construction. For the storage-fund-reward computation at
  `sui_system_state_inner.move:937` (`mul_div(storage_fund_balance, computation_charge,
  total_stake)`) the `≤ u64::MAX` bound relies on the *economic* invariant
  `computation_charge ≤ total_stake` (epoch gas fees are tiny next to total staked SUI),
  which is **not asserted in code**. If it were ever violated, the result is a **checked
  abort → safe mode**, not value creation. **bounds debt (liveness-only; not exploitable).**
- **Division by zero:** the denominators are `total_voting_power` (a constant `10000`,
  never zero — `voting_power.move`), `total_stake`/`length`/`num_unslashed_validators`,
  and `total_unslashed_validator_voting_power`. The last two appear **only** inside the
  *unslashed* branch (`:1155`, `:1175`), which by construction is reached only when there
  is ≥ 1 unslashed validator, so the divisor is ≥ 1 there. `length`/`total_stake` rely on
  the system invariant "the active validator set is non-empty with non-zero stake"
  (`distribute_reward` asserts `length > 0`, `:1193`, though `compute_unadjusted` divides
  by `length` slightly earlier). **constraint debt** — depends on a system invariant
  rather than a local guard; a violation is an abort, not a leak.
- **Slashing-rate underflow:** the slashed-validator path computes
  `unadjusted - adjustment` (`:1151`) where `adjustment = mul_div(unadjusted, rate,
  10000)`. This is `≤ unadjusted` **iff `rate ≤ 10000`**. `reward_slashing_rate` is a
  protocol-config value; if it exceeded `10000` the subtraction would underflow-abort.
  Trusted config, not user input — **constraint debt**, abort not leak.

### Where this lands

| Subject | Verdict |
|---|---|
| Reward distribution conservation | **enforced invariant** — `split` assert + dust swept to storage fund; amounts are advisory |
| Slashing redistribution | **enforced invariant** — re-routing; `total == Σ individual` by construction; conserved modulo dust |
| `mul_div!` multiplication | **enforced** — `u128` widening; no product overflow |
| `mul_div!` final `as u64` (share math) | **enforced** — bounded `≤ total` by construction (Move cast is checked) |
| `mul_div!` final `as u64` (storage-fund reward, `:937`) | **bounds debt** — relies on unasserted economic bound; violation aborts, not leaks |
| Division-by-zero guards | **constraint debt** — rely on system invariants / control flow, not local asserts; violations abort |
| Slashing-rate `≤ 10000` | **constraint debt** — trusted protocol config; violation aborts |

**The throughline of Pass 3:** Sui's reward math is allowed to be imprecise (and it is —
it truncates everywhere) without ever threatening conservation, because the *type system*,
not the *arithmetic*, is load-bearing. Every residual above degrades to a **checked
abort** (→ safe mode), never to minted or burned SUI. That is the right place for the
fragility to live.

---

# Addendum — Pass 4: Staking-pool exchange rate & rounding direction (`staking_pool.move`)

This is the most *staker-facing* surface: the share↔asset exchange rate that governs
stake-in and withdraw-out. It is the classic home of two value-extraction bugs —
**rounding in the wrong direction** (withdrawer rounds up, drains the pool) and the
**first-depositor / share-inflation attack** (ERC-4626 style: mint 1 share, donate to
inflate the rate, later depositors round to 0 shares and lose their deposit). I went
looking for both. Sui closes both, and does so with explicit guards rather than luck.

### Rounding is uniformly *down, toward the pool* — on both legs

The two conversion primitives both use the truncating `mul_div!` (`:650`, `:660`):

```move
fun get_sui_amount(rate, token_amount):  mul_div!(rate.sui_amount,        token_amount, rate.pool_token_amount)  // :650
fun get_token_amount(rate, sui_amount):  mul_div!(rate.pool_token_amount, sui_amount,   rate.sui_amount)          // :660
```

- **Staking** mints `get_token_amount(sui)` → rounds *down* → you get slightly fewer
  shares than the exact ratio; the pool keeps the dust.
- **Withdrawing** redeems `get_sui_amount(tokens)` → rounds *down* → you get slightly
  less SUI than exact; the pool keeps the dust.

Both legs favor the pool (i.e. the *remaining* stakers). A user can never round **up** to
extract more than their proportional share; rounding dust is socialized to the collective.
This is the correct, safe direction, and the fungible-staked-SUI withdraw path makes it a
*checked* property rather than an emergent one:

```move
// calculate_fungible_staked_sui_withdraw_amount, :263
// invariant check, just in case
assert!(principal_withdraw_amount + rewards_withdraw_amount <= expected_sui_amount, EInvariantFailure);
```

The withdrawal is asserted `<=` what the exchange rate says you are owed — an explicit
anti-over-withdrawal guard. **enforced invariant** (rounding direction + `<=` assert).

### The share-inflation / donation attack is structurally closed

The attack needs an attacker-controllable way to move `sui_amount` without a matching
`pool_token_amount` move, between a victim's quote and execution. On Sui the exchange rate
is **not a live function of a balance an attacker can poke** — it is a per-epoch snapshot
computed by the *system* at epoch boundaries:

```move
// process_pending_stake, :400 — called at epoch change from validator_set::advance_epoch
let latest_exchange_rate = PoolTokenExchangeRate {
    sui_amount: pool.sui_balance,
    pool_token_amount: pool.pool_token_balance,
};
...
pool.pool_token_balance = latest_exchange_rate.get_token_amount(pool.sui_balance);  // :413
```

and reads go through `pool_token_exchange_rate_at_epoch` (`:592`), which returns the
**historical stored snapshot** for the relevant epoch, not a recomputed-from-live value.
Rewards are added by the system at epoch change (`deposit_stake_rewards`), not by a public
donate. Three further guards:
- **First deposit is 1:1.** A preactive/empty pool returns `initial_exchange_rate()` =
  `{0, 0}`, and `get_token_amount`/`get_sui_amount` short-circuit to a 1:1 return when
  either side is 0 (`:646`, `:656`). No rate to inflate on the first staker.
- **Zero-share mint is rejected.** `convert_to_fungible_staked_sui` asserts
  `pool_token_amount > 0` (`:292`, `EStakedSuiBelowThreshold`) — you cannot be issued 0
  shares for non-zero principal (the dust-griefing primitive).
- **Cached rate must equal real balances.** `check_balance_invariants` (`:667`) asserts
  `get_token_amount(pool.sui_balance) == pool.pool_token_balance` — the stored rate cannot
  drift from the actual SUI/token balances. This ties the abstract rate back to held value.

**Verdict: not exploitable in the reviewed path** — the manipulable precondition (live,
donation-movable rate) does not exist; the rate is a system-computed, balance-tied,
per-epoch snapshot.

### Underflow / dust bookkeeping is explicit, not accidental

- `request_withdraw_stake` excludes preactive pools from the direct-withdraw branch
  *specifically* "to avoid potential underflow on subtraction" (`:163`).
- `calculate_fungible_staked_sui_withdraw_amount` clamps
  `principal.min(total_sui_amount)` before the `total_sui_amount - principal` subtraction
  (`:242`–`:248`) — explicit underflow guard.
- `process_pending_stake_withdraw` handles the case where withdrawals exceed
  `sui_balance` by carrying the deficit as an `UnderflowSuiBalance` extra-field and
  reconciling it on the next `process_pending_stake` (`:375`–`:412`), with `else 0`
  clamps instead of underflowing. Careful cross-epoch dust accounting. **enforced.**

### Two honest residuals (neither a finding)

- **The author-flagged "unreachable" fallback.** `pool_token_exchange_rate_at_epoch`
  ends with `// This line really should be unreachable. Do we want an assert false here?`
  and returns a 1:1 `initial_exchange_rate()` (`:611`–`:612`). If the lookup ever fell
  through (it shouldn't — it's bounded by `activation_epoch`), it would return a *1:1*
  rate, which could misprice a withdrawal. The author's own uncertainty is the right
  signal here. **hardening debt** — an `abort` would be safer than a silent 1:1 default.
- **The 1:1 zero-side short-circuit** in `get_sui_amount`/`get_token_amount` (`:646`,
  `:656`). Acknowledged dust case ("The other amount might be non-zero when there's dust
  left in the pool"). Not reachable for extraction (it requires total pool tokens or total
  SUI to be 0, i.e. nobody holds a claim), but it is an interpretation seam worth a human
  eye if the pool lifecycle changes. **noted, not a finding.**

### Where this lands

| Subject | Verdict |
|---|---|
| Rounding direction (stake & withdraw) | **enforced invariant** — both legs truncate toward the pool; `<= expected` assert on FSS withdraw |
| Share-inflation / donation attack | **not exploitable in reviewed path** — rate is a system, balance-tied, per-epoch snapshot; first deposit 1:1; zero-share mint rejected; `check_balance_invariants` ties rate to balances |
| Underflow / dust bookkeeping | **enforced** — explicit `.min()` clamps, preactive exclusion, `UnderflowSuiBalance` carry |
| `mul_div!` overflow / cast | **enforced** — `u128` widening; checked `as u64` abort (per Pass 3) |
| "unreachable" 1:1 exchange-rate fallback | **hardening debt** — author-flagged; silent 1:1 default rather than abort |

**Throughline of Pass 4:** the place where stakers could lose value to rounding is
defended the way it should be — rounding is forced *against* the withdrawer, the
exchange rate is a system snapshot rather than a pokeable live value, and the one soft
spot is the author's own flagged "should be unreachable" default, which fails safe-ish
(1:1) rather than dangerously. Consistent with the whole report: the residuals are
*liveness/hardening* shaped, not *value-creation* shaped.

---

# Addendum — Pass 5: Validator identity & proof-of-possession (`validator.move` → Rust crypto)

Passes 1–4 were all about *value*. This pass audits *identity* — and it matters because
Pass 1's entire conservation argument bottomed out at "every **honest validator**
re-derives `ChangeEpoch` deterministically." That sentence is only as strong as the gate
that decides *who is a validator*. So this pass checks the admission witness: can an actor
register a BLS protocol key it does not actually control (a rogue-key attack), or rebind
someone else's key/identity?

This is a pure **Bucket 2** (witnessed cryptographic object) question, and it crosses the
Move→Rust seam: the Move layer stores the metadata, but the cryptographic check is a
native function.

### The gate is comprehensive — every key entry and rotation is verified

`ValidatorMetadata.validate()` (`validator.move:906`) is called at the constructor
(`:261`, used by genesis and `request_add_validator_candidate`) **and at every single
metadata-mutation setter** — `update_next_epoch_protocol_pubkey`,
`update_candidate_protocol_pubkey`, and the dozen sibling updaters (`:705`–`:864`). There
is no path that writes or rotates a protocol public key without re-running validation.
**enforced — no bypass surface.**

`validate()` BCS-serializes the metadata and calls the native `validate_metadata_bcs`
(`:910`), which (`sui-move-natives/.../validator.rs:62`) deserializes into
`ValidatorMetadataV1` and calls `verify(true)`. The crypto is in Rust, but it is **not a
deferral** (unlike the Pass-1 6a seam) — it is an actual signature check performed inline,
which the Move layer cannot skip.

### The witness binds possession to identity, with domain separation

`verify_proof_of_possession` (`crypto.rs:108`):

```rust
protocol_pubkey.validate() ... ?;                       // :114 — subgroup/validity check on the pubkey
let mut msg = protocol_pubkey.as_bytes().to_vec();      // :118
msg.extend_from_slice(sui_address.as_ref());            // :119 — message = pubkey || address
pop.verify_secure(
    &IntentMessage::new(Intent::sui_app(IntentScope::ProofOfPossession), msg),  // :121 — domain-separated
    DEFAULT_EPOCH_ID,
    protocol_pubkey.into(),
)
```

Three properties, each load-bearing:

1. **Binds the key.** The PoP is a signature *under the protocol private key* over a
   message that commits to the protocol *public* key. You cannot register a public key
   you do not hold the secret for — this is the standard **rogue-key-attack mitigation**
   for BLS, which matters precisely because Sui aggregates authority signatures. (A rogue
   key would let an attacker contribute to aggregate signatures / voting they shouldn't.)
2. **Binds the identity.** The message also commits to `sui_address` (`:119`), so a PoP
   minted for address A cannot be replayed to claim the same key under address B. Key and
   on-chain identity are cryptographically welded together.
3. **Domain-separates.** `Intent::sui_app(IntentScope::ProofOfPossession)` (`:121`) tags
   the signed bytes with a PoP-specific scope, so a PoP can never be confused with — or
   replayed as — a transaction signature (or any other Sui signature), and vice versa.
   This is the anti-cross-protocol-replay guard.

I recompute-checked generate vs verify: `generate_proof_of_possession` (`:92`) builds the
*identical* message (`public().as_bytes() || address.as_ref()`, same `ProofOfPossession`
intent, `:96`–`:100`) that `verify` reconstructs (`:118`–`:121`). No asymmetry between the
signing and checking sides. **enforced invariant.**

### Rotation and role-separation are gated too

- **Next-epoch key rotation is PoP-gated.** `ValidatorMetadataV1::verify`
  (`sui_system_state_inner_v1.rs`) verifies the current protocol key (`:132`) *and* the
  next-epoch rotation key (`:184`), and **rejects a next-epoch pubkey supplied without a
  matching next-epoch PoP** (`:191`–`:193`, `E_METADATA_INVALID_POP`). You cannot rotate
  to a key you do not control. **enforced.**
- **Role keys must differ.** `worker_pubkey == network_pubkey` is rejected (`:139`–`:141`)
  — prevents collapsing distinct roles onto one key. Addresses are parsed and validated as
  anemo `Multiaddr`s (`:143`–`:163`). **enforced.**

### Where this lands

| Subject | Verdict |
|---|---|
| Validation coverage (all key entry/rotation paths) | **enforced — no bypass** (`validate()` at constructor + every setter) |
| PoP binds protocol key (rogue-key mitigation) | **enforced invariant** — signature under the key, over the key |
| PoP binds `sui_address` (identity welding) | **enforced invariant** — address committed in the signed message |
| Domain separation (`IntentScope::ProofOfPossession`) | **enforced** — no cross-protocol replay with tx signatures |
| Next-epoch key rotation | **enforced** — rotation key PoP-verified; missing PoP rejected |
| Pubkey validity / role separation | **enforced** — subgroup check; worker ≠ network |
| Epoch-independence of PoP (`DEFAULT_EPOCH_ID`) | **noted, not a finding** — intentional; safe because identity (address) is bound, so replay confers no benefit without the secret key |

### Why this closes a loop back to Pass 1

Pass 1 deferred SUI's per-epoch supply integrity to "honest validators re-derive the same
`ChangeEpoch`." Pass 5 shows the membership of that honest set is itself a
cryptographically witnessed object: you join only by proving possession of a protocol key
bound to your address, domain-separated from all other signatures. The consensus trust
root Pass 1 leaned on is not assumed — it is **admission-gated by an enforced Bucket-2
witness**. The two passes compose: conservation rests on consensus, consensus rests on
PoP-verified identity, and PoP-verified identity rests on a BLS signature whose message
welds key to address.

---

# Addendum — Pass 6: the MemeCore-class check (determinism + enforced-not-swallowed system calls)

*Motivated by the one real finding elsewhere in the corpus (`AUDIT-MEMECORE-POSA.md` §6-B/C): a PoSA
chain whose epoch reward system-call (a) **swallowed** the call's error (a reverting call still
produced a "valid" block) and (b) built the validator list from a **Go map** (non-deterministic
iteration) and passed it unsorted into the state-changing call — together a latent silent-consensus-
split. This pass re-examines Sui's epoch-change for that exact failure class. Sui is structurally
immune on both axes, and for an architectural reason.*

### Axis A — system-call results are enforced, not swallowed (the §6-B analog)

Sui's epoch transition (`execution_engine.rs::advance_epoch`) executes the whole mint→`advance_epoch`
→destroy-rebate PT atomically and **branches on the result** (`:1322`):

```rust
let result = SPT::execute::<System>(... advance_epoch_pt ...);
if let Err(err) = &result {
    tracing::error!("Failed to execute advance epoch transaction. Switching to safe mode. ...");
    temporary_store.drop_writes();                 // discard the failed partial state
    gas_charger.reset_storage_cost_and_rebate();
    temporary_store.advance_epoch_safe_mode(&params, protocol_config);   // defined fallback
}
```

The opposite of MemeCore: a failing epoch call **cannot silently proceed**. On error Sui *drops the
writes* and takes an explicit, defined **safe-mode** path (rewards parked on the `0x5` object, no
distribution). And the branch decision is the **deterministic** Move-execution `result`, so **all
validators take the same branch identically** → no node commits "normal epoch" while another commits
"safe mode." (The `#[cfg(msim)] maybe_modify_result_for` at `:1319` is a **simulation-test-only**
injection used to *exercise* safe mode, not a production path.) **enforced — failure is handled, not
swallowed; the success/safe-mode decision is deterministic across validators.**

### Axis B — no non-deterministic iteration feeds committed state (the §6-C analog)

MemeCore's split risk came from `for validator := range goMap` (randomized order) flowing into a
state-changing call. In Sui:
- **Rust execution adapter uses ordered maps exclusively** — `execution_engine.rs` + `temporary_store.rs`:
  **42 `BTreeMap`, 0 `HashMap`/`IndexMap`**. Modified/written objects are `BTreeMap`/`BTreeSet`
  (sorted keys); accumulator events iterate an ordered `Vec` (`.iter().enumerate()`). Iteration order
  is therefore identical on every validator.
- **Move has no `HashMap`.** The validator set is `active_validators: vector<Validator>`
  (`validator_set.move:62`) — an *ordered vector* that is part of the shared system-state object
  (byte-identical on all validators); reward distribution iterates it by index (Pass 3). `VecMap`
  (report records, voting powers) is insertion-ordered. **No structure whose iteration order varies
  across nodes ever feeds the committed state root.** **enforced — deterministic by container choice.**

### Why Sui is immune by construction

Sui is a BFT system where **all validators must agree on transaction effects**, so deterministic
execution is a hard requirement, not a nicety — hence ordered containers everywhere and explicit
failure handling. MemeCore inherited a clique/parlia PoSA where each validator *produces* blocks, and
the laxity crept into the off-Move glue (the Go reward-call construction). The general, checkable
property the contrast yields:

> **Determinism-safety for any consensus state transition = (ordered containers only, no map-iteration
> into committed state) + (system-call results enforced, never swallowed).** Sui satisfies both;
> MemeCore violated both in one function.

One related note (the *right* direction): Sui's epoch path uses **deterministic `.expect()`/panics**
(e.g. "System Package Publish must succeed", `:1397`) on conditions that hold identically on all
validators — so a bad state causes a **coordinated all-validator halt** (recoverable, agreed) rather
than a *silent divergence*. Preferring all-halt over silent-split is exactly the discipline MemeCore's
swallowed error lacked. **noted — correct failure philosophy.**

**Pass-6 verdict: Sui is structurally immune to the MemeCore failure class** — enforced (not swallowed)
deterministic safe-mode on epoch-call failure, and deterministic iteration (BTreeMap/ordered-vector
only) into all committed state. The itch is scratched: the bug that exists in MemeCore *cannot* take
the same form here, by Sui's architecture.

---

## Nothing routed privately

No untrusted-input→unvalidated→value-moving path was found. The largest residual (the
epoch supply delta) is a *by-design* relocation to consensus, not an exploitable defect:
a single actor cannot forge the `ChangeEpoch` figures because every honest validator
re-derives them deterministically. There is nothing here to disclose to a security
channel — only an architectural fact to record: **on Sui, "SUI conservation is checked"
is true for every transaction except the one transaction that changes the SUI supply,
where it is instead an agreement property of the consensus layer.**

Pass 2 adds the complementary fact: **that epoch transaction never raises total supply.**
SUI is minted exactly once, at genesis, into a `Balance<SUI>` that genesis exhaustively
partitions (`destroy_zero` forces the books to balance to the mist). What looks like
inflation — the stake subsidy — is a bounded drawdown of a genesis-pre-allocated fund,
overdraft-proof by linear typing plus an explicit `.min()` clamp, and geometrically
decaying. So the two passes bracket the supply question from both sides: per-epoch the
delta is *conserved* (by consensus), and globally the total is *fixed and finite* (by the
genesis partition). Neither guarantee lives where you would first look — one is in Rust,
the other at genesis — which is itself the methodology's recurring lesson.
