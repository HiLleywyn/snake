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
Move ability checker enforces it (verified at the verifier level for Move in Sui Pass 7 — Aptos runs
its own Move fork of the same ability design). `extract` (`:939`) is the conserved split (assert
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
