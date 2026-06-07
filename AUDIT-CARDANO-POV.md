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

---

# Addendum — Pass 2: Ouroboros Praos consensus (VRF leader election) — opened, clean

Closing the Cardano *consensus* coverage gap (Pass 1 was value conservation). Audited the leader
election in `IntersectMBO/ouroboros-consensus`
(`Ouroboros/Consensus/Protocol/Praos.hs` + `Praos/VRF.hs`). The consensus "conservation" analog is
**leadership integrity**: no party can forge, bias, or over-claim the right to produce blocks beyond
its stake (Sybil-resistance bounded by stake). A new consensus family for the corpus — **private,
unbiasable, stake-proportional VRF leadership** — distinct from BFT quorum (MonadBFT), PoW
(Bitcoin/Kaspa), hashgraph (Hedera), and explicit-vote chains.

## The leader lottery — unbiasable VRF input
`mkInputVRF(slot, eNonce) = Hash(slot ‖ epochNonce)` (`VRF.hs:69-78`): the VRF input is fixed by the
**slot number** and the **epoch nonce** (itself evolved from prior blocks' VRF outputs). So a would-be
leader **cannot grind the input** — it's determined by the slot and an unbiasable evolving nonce. Leader
and nonce VRF outputs are **domain-separated** (`hashVRF` prefixes `"L"` vs `"N"`, `:hashVRF`), so one
certificate can't be reused across purposes. The output is range-extended to a `BoundedNatural` in
`[0, 2^256)` by `vrfLeaderValue` (`:108-115`).

## The verification every node runs — `doValidateVRFSignature` (`Praos.hs:565-595`)
On each incoming block, three checks gate validity (reject/throw on any failure — the correct
halt-over-accept philosophy):
1. **Registered-key binding:** the issuer's pool key hash must be in the stake distribution
   (`VRFKeyUnknown` otherwise), and the pool's *registered* VRF key hash must equal the block's VRF key
   (`vrfHKStake == vrfHKBlock` or `VRFKeyWrongVRFKey`). **No impersonation** — you must use the VRF key
   you registered on-chain with your stake pool.
2. **VRF proof verification:** `VRF.verifyCertified () vrfK (mkInputVRF slot eta0) vrfCert`
   (`VRFKeyBadProof` on failure) — the VRF output is cryptographically bound to your key and the
   unbiasable input. **Unforgeable** — you can't fabricate a winning value.
3. **Stake-proportional threshold:** `checkLeaderNatValue vrfLeaderVal sigma f` (`VRFLeaderValueTooBig`
   otherwise), where `sigma` = the issuer's individual pool-stake fraction and `f` = the active slot
   coefficient. Election succeeds only if the leader value is below `φ(σ) = 1 − (1−f)^σ` — so the
   probability of winning a slot is **proportional to stake**. **No over-claiming.**
(`meetsLeaderThreshold`, `:533-553`, is the symmetric local "am I leader?" check.) KES forward-secure
block signatures (`validateKESSignature`) are a further layer, read at interface.

## Connections to the corpus
- **Determinism spine (§4g).** The VRF output is *deterministic* given key + input, so every node
  agrees on exactly who was eligible for each slot — leadership is a verifiable, deterministic function,
  not a race. Same "all nodes compute the same thing" backbone as OCC/GHOSTDAG, here for *eligibility*.
- **Sybil-resistance = stake.** This is the consensus analog of conservation: block-production rights
  are conserved against the stake distribution (you can't manufacture leadership beyond `σ`), just as
  value can't be manufactured beyond inputs. The "trustless until whom?" answer (Law 4): a >50%-stake
  adversary (the honest-stake-majority assumption + the security parameter k).
- **Residual kind (per §4h).** The remaining trust is **VRF cryptographic soundness** (unforgeability +
  pseudorandomness) — a *cryptographic-soundness* residual, like zkSync's circuit and Filecoin's
  PoRep, not an equivalence one. The on-chain *enforcement* (key binding + proof verify + threshold)
  is verified clean here; only the VRF primitive's soundness and the chain-density/k-security argument
  (the longest/densest-chain selection rule, not opened) remain.

**Verdict (Pass 2): clean.** Ouroboros Praos leader election enforces, on every block, registered-VRF-key
binding, VRF-proof verification against an unbiasable `Hash(slot ‖ epochNonce)` input, and a
stake-proportional threshold — so leadership cannot be forged, biased, or over-claimed beyond stake.
A new consensus-family data point (private/unbiasable/stake-proportional VRF), with the residual being
the VRF primitive's cryptographic soundness + the k-security chain-selection rule. No finding.
