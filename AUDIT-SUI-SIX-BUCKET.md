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
- The stake-subsidy fund's own conservation (`stake_subsidy.move::advance_epoch`) — where
  *genuinely new* SUI issuance (inflation) is metered out of a pre-funded balance; this is
  the real "is inflation bounded" question and deserves its own pass.
- `validator_set.move` reward distribution / slashing arithmetic — only its `advance_epoch`
  signature was read.
- Older execution-adapter versions (`v0`–`v3`) — they carry the same call sites but were
  not diffed against `latest`.

## Nothing routed privately

No untrusted-input→unvalidated→value-moving path was found. The largest residual (the
epoch supply delta) is a *by-design* relocation to consensus, not an exploitable defect:
a single actor cannot forge the `ChangeEpoch` figures because every honest validator
re-derives them deterministically. There is nothing here to disclose to a security
channel — only an architectural fact to record: **on Sui, "SUI conservation is checked"
is true for every transaction except the one transaction that changes the SUI supply,
where it is instead an agreement property of the consensus layer.**
