# The verification layer — accepting external truth: a consensus client, a BTC SPV bridge, and a TEE attestation verifier

**Why this hunt exists.** A distinct cut across the stack: three live systems whose core job is to **verify a proof
of something that happened outside their own state** and accept or reject it. The bug class is singular and
catastrophic — **accept a forged proof of external truth**: a beacon block/attestation that violates the spec, a
Bitcoin SPV proof of a tx that never confirmed, or an Intel SGX/TDX quote that never ran in a genuine enclave. Each
is the trust root for everything built on it.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute the
acceptance logic from source and ask "what stops a forged proof from being accepted here?" Anything real and live
would be stopped and routed for private disclosure (redacted here). **All three came back clean — no live
finding** — and one of them (DCAP) had its HEAD *be* the patch for a real, recomputed-from-source bypass.

| Target | What it verifies | "Forged proof accepted" = | Verdict |
|---|---|---|---|
| **Lighthouse** (`v8.1.3`) | beacon blocks/attestations + fork choice (Rust consensus client) | follow a wrong head / finality break / DoS | **clean** (DoS+gossip exhaustively checked; fork-choice spec-faithful) |
| **tBTC v2** (HEAD `d24b9c8`) | Bitcoin SPV proofs of deposit/redemption (Solidity bridge holding real BTC) | mint tBTC without BTC backing / steal BTC | **clean** (Σ tBTC ≡ Bank ≡ SPV-proven BTC) |
| **Automata DCAP** (HEAD `c95a281`) | Intel SGX/TDX remote-attestation quotes (on-chain verifier) | a fake "ran in a genuine enclave" | **clean** (HEAD *is* the cert-chain-bypass fix; verified complete) |

---

## 1. Lighthouse — verifying the beacon chain (a bug follows the wrong head)

**Repo:** `sigp/lighthouse`, **`v8.1.3`** (`176cce5`); disclosure `security@sigmaprime.io`. Runs a large share of
mainnet validators. Same confidence-discipline as the Reth hunt: lead with the exhaustively-checkable surfaces,
honest caveat that full fork-choice/state-transition spec-equivalence is ef-test territory, not provable by reading.

- **Fork-choice — clean (spec-faithful in every path read).** Proto-array weight propagation
  (`proto_array.rs:154-298`) uses full `checked_add/sub`, forces invalid-execution nodes to weight 0, and handles
  proposer-boost by subtracting the *previous* and adding the *new* boost; equivocators get a single one-time
  negative delta then their root is zeroed (no repeat deduction); the post-Deneb viability filter
  (`voting_source.epoch + 2 >= current_epoch` + finalized-ancestor) matches `filter_block_tree`. `on_block` and
  `validate_on_attestation` are faithful (parent-known, after-finalized, target-epoch, no-future-block).
- **Gossip validation — clean.** The EIP-7045 (Deneb) attestation slot range (valid across the whole previous
  epoch, with clock-disparity tolerance) plus the complete p2p condition set: single-committee-bit, future/past-slot,
  unknown-target/head, dedup, aggregator-in-committee, selection-proof.
- **Slashing protection — clean (EIP-3076 complete).** `check_attestation` rejects source>target and runs the full
  double-vote + surrounding + surrounded queries with a min/max-bound guard, all inside the DB transaction before
  insert — no path to sign a slashable message.
- **Panic / DoS — clean (the highest-confidence section).** The RPC varint length prefix is bounds-checked
  (`ssz_limits.is_out_of_bounds`) **before** the `vec![0; length]` allocation, with decompression wrapped in
  `take(max_compressed_len)`; gossip index lookups all use `.get(idx).ok_or(...)`; the non-test `unreachable!`/`expect`
  are on the self-generated encode path only.

**No live finding.**

---

## 2. tBTC v2 — verifying Bitcoin SPV proofs (a bug mints unbacked tBTC)

**Repo:** `keep-network/tbtc-v2`, HEAD `d24b9c8`. Live mainnet, holds real BTC, Threshold/Immunefi bounty (Critical
up to $500k). The conservation chain closes end-to-end: **Σ tBTC ≡ Bank balance ≡ SPV-proven BTC backing**, with
`Bank._increaseBalance` (the sole balance source) gated `onlyBridge` and reachable only after a proven sweep.

- **Deposit → sweep → mint backing (highest) — clean.** The deposit reveal reconstructs the exact P2(W)SH script
  from `msg.sender` + blinding + wallet/refund PKH and byte-matches the on-chain funding output; the amount is read
  from the actual BTC output, not user-supplied. `revealedAt == 0` blocks double-reveal; `sweptAt == 0` blocks
  double-sweep; optimistic-minting tracks `optimisticMintingDebt` repaid against the later real sweep so a deposit
  never mints twice.
- **Redemption — clean.** The redeemer's Bank balance is pulled up front; `submitRedemptionProof` binds the single
  input to the wallet's main UTXO, burns only outputs matching a pending request within the fee range, then
  `delete`s the request (replay-protected); timeout and watchtower-veto return balance correctly.
- **SPV / BTC relay — clean.** `validateProof` proves tx merkle inclusion **and additionally proves the coinbase tx
  is in the same block** (post-audit hardening, `merkleProof.length == coinbaseProof.length`); the pinned
  `bitcoin-spv-sol@3.4.0` carries the CVE-2012-2459 guard (rejects the 64-byte single-step ambiguity); difficulty
  must equal the relay's current/previous epoch with `observedDiff >= requestedDiff * 6` (6-confirmation work).
- **Fraud / moving-funds — clean.** The fraud sighash is computed **inside the contract** from the preimage (no
  forged-sighash accusation); a challenge is defeatable only by proving the spent UTXO is in the approved set
  (`sweptAt > 0 || spentMainUTXOs || movedFundsSweepRequests == Processed`), so a wallet that signs an unapproved tx
  can't defeat it and is slashed.

**No live finding.** By-design trust assumptions named (optimistic-minting's 1-of-n Minter/Guardian set; the
documented most-recent-epoch relay limitation), not inflated.

---

## 3. Automata DCAP — verifying Intel enclave quotes (HEAD *is* the bypass fix)

**Repos:** `automata-dcap-attestation` HEAD `c95a281` + `automata-on-chain-pccs` HEAD `5241b64`; deployed
`AutomataDcapAttestationFee` at `0x27188ABA…`; audited by Trail of Bits (Feb 2025) + OpenZeppelin (Oct 2025). A bug
here forges the "this ran in a genuine SGX/TDX enclave" claim — the trust root of every TEE protocol consuming it.

**The headline: HEAD itself is a security patch, and the pre-fix bug was recomputed from source.** PR #141 (the HEAD
merge) closes a real cert-chain signature-verification bypass: in `verifyCertChain`, `verified` was **not reset per
loop iteration**, and the AKI/SKI issuer-binding used `BytesUtils.compareBytes` where `compareBytes("","") == true`
— so an attacker-supplied cert with empty/missing AKI/SKI extensions could **skip its own ECDSA check yet inherit
`verified == true` from the prior iteration**, forging a PCK chain. The hunt confirmed the patch is complete at HEAD.

- **Cert chain / root-of-trust (highest) — safe (post-patch).** Root pinned as the hardcoded `ROOTCA_PUBKEY_HASH`
  (not attacker-supplied), checked at the last cert; each link's signature verified
  `ecdsaVerify(sha256(tbs), sig, issuer.pubkey)`. Patch guards confirmed: `verified = false` reset each iteration +
  `if (!verified) break`, plus empty-key-identifier rejection. CRL revocation + expiry enforced.
- **Quote signature + key binding — safe.** QE-report-data binding `sha256(attestationKey || qeAuthData) ==
  qeReport.reportData[0:32]`; the two-step chain (QE report signed by PCK-leaf, quote `header||body` signed by the
  attestation key); exact-length enclave-report parse; P256 via RIP-7212 (low-s handled).
- **TCB / collateral — safe.** TCBInfo/QEIdentity signatures verified against the Intel TCB-signing cert at upsert;
  `TCB_REVOKED` short-circuits to failure; out-of-date/config-needed are *surfaced not silenced*; collateral expiry
  enforced (`issuedAt <= timestamp <= expiredAt`, the OZ-reported fix) with upsert monotonicity (no rollback to older
  `evaluationDataNumber`).
- **Parsing / measurement binding — safe.** All parsing uses Solidity 0.8 calldata slices (revert on OOB); the
  output faithfully binds `quoteBody` (MRENCLAVE/MRSIGNER/reportData) + `tcbStatus` + `fmspc` + version.
- **zk-coprocessor trust boundary — characterized.** The zk path (RiscZero/SP1/Pico) verifies a SNARK against a
  pinned `programIdentifier` and **re-checks the collateral content-hashes in the zk output against the currently
  stored on-chain PCCS collateral** — so a prover can't substitute revoked/older collateral. **Honest by-design
  observation (below the forgery bar, flagged not inflated):** the zk-path `timestamp` is prover-supplied and bounded
  only by the current collateral's `[issuedAt, expiredAt]` window — no `timestamp <= block.timestamp` freshness bound,
  so a valid proof is replayable for the collateral's lifetime. This does *not* forge an attestation (the quote and
  collateral are genuine); it's a freshness/replay-window property worth the consuming protocol's awareness.

**No live finding** (the bypass is already public + patched; the zk timestamp-window is by-design).

---

## Synthesis — what the verification layer taught

1. **One question, three proof systems.** "What stops a forged proof from being accepted?" resolves to a different
   mechanism each time: Lighthouse's gossip/fork-choice conditions, tBTC's SPV merkle+PoW+coinbase-inclusion, DCAP's
   pinned-root cert chain + quote-sig + TCB. The forged-proof must fail at a *specific* checked step, and the hunt's
   job was naming that step and confirming no path around it.
2. **The richest result was recomputing a real bug that was already fixed.** DCAP's HEAD *is* the PR-#141 patch; the
   hunt re-derived the pre-fix bypass (`verified` not reset + `compareBytes("","")==true`) from source and confirmed
   the fix — the same "deployed == audited" discipline that, applied to a *patch commit*, verifies the patch rather
   than trusting the PR title.
3. **Freshness/replay windows are the honest sub-forgery findings.** DCAP's prover-supplied zk timestamp is the
   round's one genuine observation: not a forgery (the proof is real), but a replay-window the consumer should know —
   flagged below the bar, calibrated, not inflated. The mirror of severity-down discipline at the verification layer.
4. **CVE/known-issue anchoring held.** tBTC's CVE-2012-2459 merkle guard + coinbase-inclusion hardening, DCAP's
   recomputed cert-chain bypass + the OZ collateral-expiry fix — each hunt located the historically sensitive spot
   and confirmed it handled at the analyzed version.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
