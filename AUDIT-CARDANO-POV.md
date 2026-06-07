# Cardano (ADA) — Preservation-of-Value (eUTXO + multi-asset) — clean, the most *legible* floor

**Target:** `IntersectMBO/cardano-ledger`, cloned `/tmp/cardano`. Top-100 L1; **Haskell**, eUTXO +
native multi-asset. Audited the conservation rule (preservation-of-value, "POV"). **Posture:**
defensive; no exploit. **Result: clean — no finding.** Fresh functional domain; self-check +
connections applied.

## Conservation is an *explicit, named, checked* ledger rule
Unlike most chains where conservation is emergent from the code, Cardano makes it a first-class rule:
`validateValueNotConservedUTxO` (`Shelley/Rules/Utxo.hs:507`) does
**`failureUnless (consumedValue == producedValue)`** (`:515`), failing with `ValueNotConservedUTxO`
(`:176`). The spec comment is literally the invariant: *`consumed pp utxo txb = produced pp poolParams
txb`*. It's also backed by a formal ledger specification (Agda/exec spec) outside this repo.

## The multi-asset equation (the eUTXO twist — verified)
`Mary/UTxO.hs`:
```
getConsumedMaryValue = (Σ inputs) + inject(refunds + withdrawals)         -- :82-86
                       <> MaryValue mempty mintedMultiAsset               -- :78,80  positive mint only
getProducedMaryValue = shelleyProducedValue(outputs+fee+deposits)        -- :96
                       <> burnedMultiAssets(txBody)                       -- negative mint (burns)
```
Two elegant properties make `consumed == produced` exact while keeping ADA sound:
1. **ADA cannot be minted.** The mint is added as `MaryValue **mempty** mintedMultiAsset` — the ADA
   (Coin) component is forced to zero (`mempty`), so a normal transaction *structurally cannot create
   ADA*; only native (non-ADA) tokens can be minted. (The Sui-style "the base asset is special",
   but cleaner — it's a structural zero, not a gated function.)
2. **Native tokens are accounted on both sides:** positive mint → *consumed* (a value source the tx
   may spend), burns (negative mint) → *produced* (a value sink). So minting/burning per the token's
   policy script nets out of the equation; nothing is created or lost beyond what the policy allows.
Plus the staking accounting (deposit `refunds` + reward `withdrawals` on the consumed side; `deposits`
on the produced side) keeps the stake-deposit lifecycle value-neutral. **enforced — formally
specified conservation.**

## Connections (cross-corpus)
- **UTXO family:** Bitcoin/Litecoin = `Σ inputs == Σ outputs + fee` (`AUDIT-LITECOIN-SIX-BUCKET.md`).
  Cardano = the same UTXO conservation **extended** with (a) **multi-asset** (the mint/burn split),
  (b) **staking accounting** (refunds/withdrawals/deposits), and (c) **an explicit named rule + formal
  spec**. Litecoin's MWEB conserves via *commitment algebra*; Cardano conserves via *plaintext value
  with a first-class checked equation* — the most **legible** conservation floor in the corpus (you
  can point at the exact `consumed == produced` line).
- **"Base asset can't be minted in a normal tx":** Cardano (ADA-mint forced `mempty`) ≈ Sui (native
  SUI mint gated to the `@0x0` system tx, `AUDIT-SUI-SIX-BUCKET.md`). Cardano's is structural (zero),
  Sui's is access-gated — same intent, cleaner mechanism.
- **"Conservation as a first-class checked property"** family: Cardano (POV rule + formal spec),
  **Osmosis** (registered runtime invariant), **Aptos** (Move Prover `supply` specs), **marginfi**
  (self-consistent rate decomposition). These chains *assert/prove* conservation explicitly rather
  than leave it emergent — the opposite end from the imperative EVM/Cosmos-mutation substrate
  (`AUDIT-CONNECTIONS-AND-SELFCHECK.md`, conservation-location ladder).

## What this audit did NOT cover (coverage honesty)
- The **Plutus script** evaluation (eUTXO validators) and the script-context construction — the
  smart-contract layer that gates *who* can spend, distinct from value conservation.
- Per-era deltas (Alonzo/Babbage/Conway/Dijkstra) beyond confirming the POV rule carries forward;
  Conway governance deposits/refunds accounting.
- The minting-policy script enforcement itself (that a positive/negative mint is authorized by the
  policy) — the POV rule conserves *given* the mint; the policy authorizes the mint.

## Verdict
**Clean.** Cardano's preservation-of-value is an explicit, formally-specified `consumed == produced`
rule; the multi-asset extension keeps ADA structurally un-mintable (mint's ADA component forced to
zero) while accounting native-token mint/burn on both sides; staking deposits/refunds net out. The
most legible conservation floor reviewed. No finding; nothing routed.
