# Avalanche (AVAX) — X-Chain AVM UTXO conservation audit (clean)

**Target:** `ava-labs/avalanchego`, cloned `/tmp/avago` (shallow, HEAD current). Top-100 L1.
Audited the **value-conservation core of the UTXO chains** — the `FlowChecker`
(`vms/components/avax/flow_checker.go`) that every X-Chain (AVM) and P-Chain (PlatformVM)
transaction must pass, plus the capability-gated mint path (`vms/secp256k1fx`). **Posture:**
defensive; no exploit, no PoC. **Result: clean — no finding, nothing to disclose.**

Chosen as a standout because it is the corpus's **third native multi-asset UTXO floor** — a direct
comparison point for Cardano's eUTXO `MaryValue` conservation (`AUDIT-CARDANO-POV.md`) and the
Bitcoin/Litecoin input≥output floor (`AUDIT-LITECOIN-SIX-BUCKET.md`), implemented in a *third*
language (Go) by a *third* team. This is connection-driven auditing: I already verified the eUTXO
and account-model floors; Avalanche tests whether the same conservation law re-derives independently.

## Conservation floor — per-asset `produced ≤ consumed`, overflow-checked (Bucket 1)
The whole floor is one small, legible struct. `FlowChecker` holds two maps `consumed, produced
map[ids.ID]uint64` keyed by asset ID (multi-asset, like Cardano's `MaryValue`). `Verify()`
(`flow_checker.go:42-53`):
```
for assetID, producedAssetAmount := range fc.produced {
    consumedAssetAmount := fc.consumed[assetID]
    if producedAssetAmount > consumedAssetAmount {
        fc.errs.Add(ErrInsufficientFunds); break
    }
}
```
So for **every** asset, `produced ≤ consumed` — outputs can never exceed inputs; the excess
(`consumed − produced`) is the burned fee. An asset that is produced but never consumed has
`consumed[assetID] == 0`, so any positive production fails (`ErrInsufficientFunds`) — **you cannot
create units of an asset out of nothing.** The accumulation `add` (`:36-40`) uses
**checked `math.Add`** (`utils/math/safe_math.go:30` — `a > MaxUint−b → ErrOverflow`), and `Verify`
short-circuits on any accumulated error (`:43 !fc.errs.Errored()`), so **a summation overflow cannot
wrap a balance to forge headroom.** **enforced.**

### How the checker is driven (no bypass)
`VerifyTx` (`transferables.go:204-239`) is the single driver: it `Produce`s the fee first
(`:213` — *"The txFee must be burned"*), `Produce`s every output (`:221`), `Consume`s every input
(`:234`), and also enforces canonical sort/uniqueness on both (`ErrOutputsNotSorted`,
`ErrInputsNotSortedUnique` — a determinism guard, cf. the MemeCore non-determinism class: Avalanche
forces a canonical order, so no ordering ambiguity). The same `avax.Consume`/`avax.Produce` state
mutation drives the P-Chain executor (`platformvm/txs/executor/standard_tx_executor.go`, every tx
type) and the C↔X↔P atomic import/export (`saevm/cchain/tx/{import,export}.go`). One conservation
primitive, reused across all UTXO-model surfaces.

## The only supply-creation path — capability-gated mint, right-preserving (Bucket 5/governance)
New units can only enter via an AVM `OperationTx` mint. `secp256k1fx.verifyOperation`
(`fx.go:127-135`) requires:
1. the operation consumes an existing **`MintOutput`** UTXO (the on-chain minting capability), and
   the credentials satisfy *that* output's owners (`VerifyCredentials(... &utxo.OutputOwners)`);
2. `utxo.Equals(&op.MintOutput.OutputOwners)` or `ErrWrongMintCreated` (`:131-132`) — the mint
   **must re-create a `MintOutput` with the same owners**, so the minting right is preserved, not
   consumed or transferred to an attacker.
The `MintOperation` carries both a new `MintOutput` (the preserved capability) and a `TransferOutput`
(the freshly-minted units) (`mint_operation.go:15-19`). So minting is **authority-gated supply
creation** — the AVM analog of Sui's `TreasuryCap`, Aptos's `MintCapability`, and Cardano's
policy-script-gated mint. By design, capability-bounded; not a conservation hole.

## Connections to the corpus
| | Avalanche AVM | Cardano (Mary) | Bitcoin/Litecoin |
|---|---|---|---|
| Floor | `produced ≤ consumed` per asset (`FlowChecker`) | `consumed == produced` (`MaryValue`) | Σin ≥ Σout |
| Fee handling | excess `consumed−produced` burned (fee `Produce`d) | fee is an explicit term in `produced` | excess = miner fee |
| Multi-asset | yes (`map[ids.ID]uint64`) | yes (`MaryValue` multiasset) | no (BTC only) |
| Overflow | checked `math.Add` | bounded `Coin`/`Value` arithmetic | int64 consensus bounds |
| Mint | capability-`MintOutput`-gated, right-preserved | policy-script-gated | coinbase (schedule) |
The three independent UTXO teams converge on the **same conservation law** (outputs can't exceed
inputs, the gap is the fee, minting is authority-gated). Avalanche uses inequality (`≤`, excess
burned) where Cardano uses strict equality (`==`, fee explicit) — equivalent floors, different
bookkeeping. This is the §11 conservation-ladder bottom rung re-confirmed in a third codebase. The
canonical input/output sort is the same **determinism discipline** whose *absence* is the lone corpus
finding (`AUDIT-MEMECORE-POSA.md`); here ordering is forced, so that failure class is N/A.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I did not take "FlowChecker" on faith — I read the loop and
  confirmed the comparison direction (`produced > consumed → fail`, i.e. `produced ≤ consumed`) and
  that it iterates `produced` keys with a `0` default for absent consumed (so produce-from-nothing
  fails). I confirmed `math.Add` is the overflow-checked variant, not raw `+`.
- **Exposure to reversal.** This verdict would flip if: (a) any tx path mutated UTXO state
  *without* routing through `VerifyTx`/`avax.Consume`/`Produce` (I traced the AVM and PlatformVM
  executors and the atomic import/export to the same primitive, but did **not** exhaustively prove
  no other writer exists); or (b) the mint `Equals` check could be satisfied while transferring the
  capability (I read it as owner-equality preserving the right). Both are stated as bounded reads,
  not closed proofs.

## What this audit did NOT cover (coverage honesty)
- **The C-Chain (coreth/subnet-EVM)** — a separate EVM codebase, not in this repo's UTXO core.
- **The cross-chain atomic seam (Bucket 6, irreducible-ish).** X↔P↔C transfers move AVAX through
  **shared-memory atomic UTXOs** (`saevm/cchain/tx/{import,export}.go` each run their own
  `FlowChecker`). That each export is matched by exactly one import — no double-spend across the
  shared-memory seam — is the deepest residual settlement-conservation surface and is **not** opened
  here (analogous to the bridge/settlement seams flagged across the corpus).
- **Snowman/Avalanche consensus** (the agreement layer; the conservation analog audited for Monad in
  `AUDIT-MONADBFT-CONSENSUS.md`) — orthogonal to this validity floor, not opened.
- **The signature/credential crypto** (`VerifyCredentials`) — read at interface, not at the secp256k1
  primitive.

## Verdict
**Clean.** Avalanche's X-Chain/P-Chain value conservation rests on a small, legible per-asset
`produced ≤ consumed` floor with checked overflow arithmetic and a single reused
`Consume`/`Produce`/`Verify` primitive across all UTXO-model tx types; new supply enters only through
a capability-`MintOutput`-gated, right-preserving mint. It re-derives — independently, in Go — the
same conservation law verified for Cardano (eUTXO) and Bitcoin/Litecoin. No untrusted-input→value
path found, nothing to disclose. The decisive next pull is the **cross-chain atomic shared-memory
seam** (the X↔P↔C settlement floor), the natural Bucket-6 residual.
