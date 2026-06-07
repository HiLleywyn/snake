# XRP Ledger (XRP) — conservation via the InvariantCheck framework — clean, the *tightest* floor

**Target:** `XRPLF/rippled`, cloned `/tmp/rippled`, HEAD `949887f`. Top-100 L1 (C++). Audited the
**InvariantCheck** framework — rippled's post-transaction runtime conservation checks. **Posture:**
defensive; no exploit. **Result: clean — no finding.** Fresh domain; self-check + connections applied.

## Conservation = an exact, runtime-enforced invariant (the tightest reviewed)
rippled runs a suite of `InvariantCheck` subclasses *after* every transaction; failure rejects the tx
(`include/xrpl/tx/invariants/InvariantCheck.h`: `XRPNotCreated`, `XRPBalanceChecks`,
`AccountRootsNotDeleted`, `NoBadOffers`, …). The conservation core, `XRPNotCreated::finalize`
(`InvariantCheck.cpp`):
```
drops_ = Σ (after − before) XRP across all accounts the tx modified
if (drops_ > 0)      → fail  // "transaction created XRP out of thin air. That's not possible."
if (-drops_ != fee)  → fail  // net XRP decrease must equal EXACTLY the fee charged
```
So **every transaction's total XRP delta == `−fee`, exactly.** This is *tighter* than the UTXO
`Σinputs ≥ Σoutputs` floor (`AUDIT-LITECOIN-SIX-BUCKET.md`): Bitcoin/Litecoin let the miner claim the
slack (block reward), but **XRP is never issued** (no mining/staking rewards) — it only deflates by
fees — so the invariant demands exact equality, not an inequality. `XRPBalanceChecks::visitEntry`
additionally bounds every account: `0 ≤ balance ≤ kInitialXrp` (can't go negative, can't exceed the
ever-issued 100B). **enforced — exact, runtime, fail-the-tx.**

## Connections (cross-corpus)
- **"Conservation as a first-class *checked* property" family — XRPL is the tightest member.** Cardano
  POV (`consumed == produced`), Osmosis registered invariant, Aptos Move Prover `supply` specs,
  marginfi rate-decomposition, and XRPL (`net XRP delta == −fee`). XRPL asserts *exact equality* and
  *fails the transaction*, the strongest form. (`AUDIT-CARDANO-POV.md`,
  `AUDIT-CONNECTIONS-AND-SELFCHECK.md`.)
- **Defense-in-depth "re-derive conservation after execution, then halt/fail" pattern:** XRPL
  `InvariantCheck` (post-tx, reject) ≈ **Sui** expensive conservation check (post-tx,
  `AUDIT-SUI-SIX-BUCKET.md`) ≈ **Monad** `MONAD_ASSERT` (`AUDIT-MONAD-PARALLEL.md`). All three compute
  the value delta *after* the logic ran and refuse to commit if it's wrong — a belt over the
  transaction logic's suspenders. (XRPL's was added after its 2014 XRP-creation incident — a chain
  that learned the exact lesson the methodology centers on.)
- **Native-asset issuance models** now span the full range: PoW block-reward (Bitcoin/Litecoin),
  PoS subsidy from genesis (Sui/Cardano), bridge-mint (fetchd), copyable mint-cap (Aptos), system-tx
  mint (Sui native), and **XRPL = pure deflation, zero issuance** (the only never-minted base asset in
  the corpus; the invariant makes creation structurally impossible).

## What this audit did NOT cover (coverage honesty)
- The **payment/rippling engine** (`Flow`, offer-crossing, pathfinding) — *how* value moves through
  trust-line chains and the built-in DEX; the InvariantCheck is the backstop *over* it, but the
  engine's own correctness (e.g., IOU rippling, offer execution) wasn't traced. The IOU/trust-line
  (non-XRP) conservation is governed by issuers, not `XRPNotCreated`.
- The **consensus** (XRPL RPCA / negative-UNL) — separate domain.
- The other invariants (`NoBadOffers`, `AccountRootsNotDeleted`, ledger-entry-count) beyond reading
  their existence.

## Verdict
**Clean.** XRPL enforces the tightest conservation floor reviewed: a post-transaction runtime
invariant requiring the total XRP delta to equal exactly the fee burned (no creation, exact
destruction), plus per-account balance bounds — on a purely deflationary, never-issued base asset.
A defense-in-depth re-derivation that fails the tx on violation (the Sui/Monad pattern), born from
their 2014 incident. No finding; nothing routed.
