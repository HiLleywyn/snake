# Aptos (APT) — Move coin conservation audit (clean) + Sui comparison

**Target:** `aptos-labs/aptos-core`, cloned `/tmp/aptos`, HEAD `226bc17e`. Top-100 L1; the *other*
Move chain. Audited the value-conservation core (`aptos-framework/sources/coin.move` + the
`Coin`↔`FungibleAsset` bridge). **Posture:** defensive; no exploit, no PoC. **Result: clean — no
finding, nothing to disclose.** Chosen as a standout because it lets me extend the deepest verified
result of this corpus (Sui's linear-type floor, `AUDIT-SUI-SIX-BUCKET.md` Pass 7) to a different Move
object/account model and compare.

## Conservation floor — same as Sui (linear typing), confirmed
`struct Coin<phantom CoinType> has store` (`coin.move:130`) — `store` without `copy`/`drop`, exactly
like Sui's `Balance`. So a `Coin` cannot be duplicated or discarded by any accepted bytecode; the
Move ability checker enforces it. **[Self-check correction]** I originally extrapolated this from
*Sui's* verifier (Pass 7); on review I read **Aptos's own** Move verifier
(`third_party/move/move-bytecode-verifier/src/type_safety.rs`) and independently confirmed the same
rules: `Pop → POP_WITHOUT_DROP_ABILITY` (`:620`), `CopyLoc → COPYLOC_WITHOUT_COPY_ABILITY` (`:838`),
`ReadRef → READREF_WITHOUT_COPY_ABILITY` (`:991`), plus a `WriteRef`-needs-`drop` check (`:1011`). So
the floor is now verified on Aptos's actual verifier, not assumed from Sui's. `extract` (`:939`) is
the conserved split (assert
`value >= amount` → decrement → return `Coin{amount}`), and it carries **Move Prover `spec` blocks
tracking a ghost `supply`** — Aptos *formally specifies* the conservation, not just asserts it.
`mint`/`burn` are gated by `MintCapability`/`BurnCapability`. **enforced.**

## The Aptos-specific surface — `Coin` ↔ `FungibleAsset` conversion (conserves 1:1)
Aptos has two token standards (legacy `Coin<T>` and the newer `FungibleAsset`) and migrates between
them — a dual-representation seam Sui doesn't have. Both directions conserve exactly:
- `coin_to_fungible_asset(coin)` (`:406`): `amount = burn_internal(coin)` then
  `fungible_asset::mint_internal(metadata, amount)` — burn X of Coin, mint X of FA. 1:1.
- `fungible_asset_to_coin(fa)` (`:415`): asserts the FA's `PairedCoinType` **== `CoinType`**
  (`:420-428`, `ECOIN_TYPE_MISMATCH`) — the critical guard preventing FA-of-token-A from being
  converted into Coin-of-token-B (a cross-type forge) — then burn X of FA, mint X of Coin. 1:1.
So combined (Coin supply + FA supply) for a token is invariant across conversions, and the
type-match assertion blocks cross-type confusion. **enforced — dual-representation conversion
conserves with a type guard.**

## Sui vs Aptos (the comparison)
| | Sui | Aptos |
|---|---|---|
| Coin primitive | `Balance<T>` (`store`, no copy/drop) | `Coin<T>` (`store`, no copy/drop) — **same floor** |
| Storage model | object model (coins are objects) | global storage (`CoinStore<T> has key` at addresses) |
| Token standards | one (`Coin`/`Balance`) | **two** (`Coin` + `FungibleAsset`) + a 1:1 conserving bridge |
| Mint authority | `TreasuryCap` (key+store, non-copyable, unique) | `MintCapability` (**copy**+store — holder can duplicate/share) |
| Conservation proof | linear typing (verifier-enforced) | linear typing **+ Move Prover `supply` specs** |
Both bottom out on the same Move linear-type guarantee. Aptos adds formal `spec` annotations and the
dual-standard bridge (which conserves); the notable design difference is the **copyable
`MintCapability`** (vs Sui's unique `TreasuryCap`) — by design (a shareable mint authority), not a
defect, but a per-coin trust note: whoever holds a `MintCapability` can replicate it.

## What this audit did NOT cover (coverage honesty)
- The **aggregator-based supply** + **Block-STM** optimistic parallel execution — Aptos's parallel
  conservation surface (analogous to Monad's OCC/relaxed-merge, `AUDIT-MONAD-PARALLEL.md`); the
  deepest Aptos-specific surface, not opened here.
- The `fungible_asset` module internals (store/freeze/balance), `primary_fungible_store`, and the
  capability-management (`PairedFungibleAssetRefs`).
- AptosBFT (Jolteon) consensus — separate surface (cf. `AUDIT-MONADBFT-CONSENSUS.md`).

## Verdict
**Clean.** Aptos's coin conservation rests on the same linear-type floor as Sui, with a
correctly-conserving `Coin`↔`FungibleAsset` bridge (1:1, type-guarded) and Move Prover supply specs.
No untrusted-input→value path, nothing to disclose. The next pull for Aptos is the aggregator +
Block-STM parallel-execution conservation (the relaxed-OCC class), not the coin module.

---

# Addendum — Pass 2: Block-STM parallel execution (the Monad OCC twin) — opened, sound

Closing the coverage gap flagged in Pass 1, using `AUDIT-MONAD-PARALLEL.md` as the explicit reference
(Connection B in `AUDIT-CONNECTIONS-AND-SELFCHECK.md`): Aptos Block-STM and Monad's optimistic
parallel EVM are the **same technique** — optimistic concurrent execution + read-set conflict
detection + deterministic re-execution + ordered commit. Mapping Monad's anatomy onto Aptos:

| Monad (C++) | Aptos Block-STM (Rust) |
|---|---|
| `state.original()` read-set | `captured_reads.rs` (`DataRead` per key) |
| `can_merge` (re-validate reads vs committed) | `validate_data_reads_impl` (`captured_reads.rs:924`) — re-reads each key via `fetch_data_no_record` and checks `compare_data_reads(...) == Contains` |
| relaxed-merge (`min_balance`, balance-only) | **read-kind granularity** (`DataRead::{Value, Metadata, ResourceSize, Exists}`, `:79`) — a read conflicts only if the *granularity it observed* changed (read `Exists` → valid even if the value changed). *More general/principled than Monad's balance-specific relaxation.* |
| `prev_` promise chain (ordered commit) | the `scheduler` commits in strictly increasing `TxnIndex`; a tx commits only after lower indices validate |
| `MONAD_ASSERT(can_merge)` halt | `Err(Dependency/Unresolved)` → validation failure → re-execute (new incarnation) |

**Verdict: sound, same OCC family as Monad.** Re-validation re-reads the live multi-version map and
fails the tx if any captured read is no longer `Contains`-consistent; conflicts force re-execution at
a new incarnation; commit is deterministic in txn order. So Block-STM's result equals sequential
execution (the published Block-STM guarantee), and conservation holds across parallelism the same way
Monad's does. **Load-bearing piece (per the Monad template):** the `compare_data_reads` / `Contains`
semantics — the analog of Monad's `try_fix_account_mismatch`; soundness requires `Contains` to never
say "valid" when the precise observed granularity actually changed. Read at the rule level; the
read-kind comparator is the deepest residual (matches the Monad relaxed-merge residual). **No
finding.**
