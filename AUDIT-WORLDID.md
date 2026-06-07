# World ID (Worldcoin proof-of-personhood) — Six-Bucket Trust Audit

**Target:** `worldcoin/world-id-contracts`, cloned `/tmp/worldid`, HEAD `f959f72`. The on-chain
World ID protocol: a Semaphore ZK identity Merkle tree (the set of orb-verified humans),
batch identity insertion/deletion with ZK proofs, membership-proof verification, and L1→L2 state
bridges (Optimism/Polygon). Upgradeable (`WorldIDIdentityManagerImplV1`→V3 behind a proxy).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe." Nothing routed
privately — none found. Focused on the identity-integrity + proof-verification core; coverage gaps
stated.

**Why this fits:** a ZK **proof-of-personhood** system — the methodology's Bucket 2 (witnessed
cryptographic objects) and the "conservation" analogue *"one human = one membership; one action =
one nullifier."* It is also the clean **on-chain counterpart to Humanity Protocol** (which kept all
proof-of-humanity off-chain on vanilla EAS): World ID puts the *tree integrity* on-chain under ZK.

---

## Bucket 2 — the witnessed ZK objects (the strong, on-chain part)

### Identity insertion is ZK-constrained (the operator can't forge membership)

`registerIdentities` (`ImplV1.sol:376`) is `onlyIdentityOperator`, requires `preRoot ==
_latestRoot` (sequential, no stale/concurrent insert, `:383`), and accepts the new root **only if a
ZK insertion proof verifies**:

```solidity
inputHash = keccak(startIndex, preRoot, postRoot, identityCommitments);    // binds exactly these identities + the transition
reducedElement = inputHash % SNARK_SCALAR_FIELD;
insertionVerifier.verifyProof(insertionProof, [reducedElement]);           // :401 — Merkle transition proven correct
// only on success:
_latestRoot = postRoot;  rootHistory[preRoot] = block.timestamp;           // :404
```

So the identity operator (the off-chain **sequencer**) **cannot forge the root or insert phantom
members**: the proof binds the exact `identityCommitments`, their `startIndex`, and the
`preRoot→postRoot` transition, and the Merkle update must be ZK-correct. **enforced invariant**
(tree integrity is ZK-witnessed).

### Membership proofs use a valid, fresh root

`verifyProof` checks a Semaphore proof via `semaphoreVerifier`, against a root validated by
`requireValidRoot` (`:495`): the root must be the latest **or** in `rootHistory` and **not expired**
— `block.timestamp - rootTimestamp > rootHistoryExpiry → ExpiredRoot` (`:510`), default
`rootHistoryExpiry = 1 hour` (`:324`). So proofs must use a root ≤ 1h old — bounding stale-root
replay. **enforced.**

---

## Bucket 1 (conservation analogue) — split across three layers (the key structural finding)

"Personhood conservation" in World ID is **not a single on-chain invariant**; it is layered:

1. **Tree integrity (no forged membership)** — **ZK-enforced on-chain** (above). The membership set
   can only change via proven-correct Merkle transitions. *Strong.*
2. **"One human = one membership"** — **off-chain.** Whether each `identityCommitment` corresponds
   to a *unique real human* is decided by the **orb** (iris biometric) + the **identity operator**
   that chooses which commitments to insert. The on-chain ZK proves the tree is *correct*, **not**
   that its members are distinct humans. So sybil-resistance ultimately rests on **orb + operator
   honesty (off-chain)** — a 6b seam the chain cannot verify.
3. **"One action = one nullifier"** — **app-side, not here.** The identity manager is a **stateless
   proof verifier**: it has **no nullifier mapping** and does **not** record/enforce nullifier
   uniqueness. The consuming application must store used `nullifierHash`es to prevent a verified
   human from acting twice. So the action-uniqueness conservation lives in each integrating app, not
   in this contract.

**Verdict:** the on-chain layer enforces *tree integrity* (ZK, strong); *personhood* is an
off-chain orb+operator trust (6b); *action-uniqueness* is delegated to integrators. This is a
correct and explicit layering — but it must be named: **World ID's on-chain contracts do not, by
themselves, guarantee "one action per unique human"** — they guarantee "this proof corresponds to a
member of an honestly-maintained tree, against a fresh root," and the rest is orb + app.

---

## Bucket 6 — state-bridge seam

`_stateBridge` (`:93`) propagates the latest root to L2s (Optimism/Polygon) so apps there can verify
membership. The bridged root must equal the canonical L1 root — a cross-layer seam (like Base's
anchor-root, `AUDIT-BASE-SIX-BUCKET.md`): an L2 verifier trusts the bridged root, whose authenticity
is the bridge's responsibility. **named; cross-layer 6b.**

---

## Bucket 4 / governance ceiling — the owner is the apex

The owner holds the real power (all `onlyOwner`):
- **`setIdentityOperator`** (`:648`) — chooses who can insert identities (initially `owner()`).
- **`setSemaphoreVerifier`** (`:580`) — **can swap the proof verifier.** A malicious/buggy verifier
  could accept invalid proofs; this is the single most powerful knob (it underpins Bucket 2).
- **`setRootHistoryExpiry`** (`:611`) — tunes the replay window.
- **Upgradeable** (`WorldIDImpl`/proxy) — the owner can replace the implementation wholesale (apex,
  "verified ≠ running", `AUDIT-GOVERNANCE-CEILING.md`).

So the on-chain ZK guarantees are **conditional on the owner** not swapping the verifier or
upgrading maliciously. The owner (a Worldcoin-controlled key/multisig — identity not in repo) is the
trust root; its key custody (multisig/timelock?) is the deployment fact that matters most.
**trust-boundary debt (by design).**

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 2 | Identity insertion ZK proof (tree transition) | **enforced invariant** — operator can't forge root/phantom members; binds exact commitments |
| 2 | Membership proof + root freshness | **enforced** — Semaphore verify; root must be ≤ `rootHistoryExpiry` (1h) old |
| 1 | Tree integrity | **ZK-enforced on-chain** |
| 1 | "One human = one membership" | **off-chain** — orb + identity operator (6b); chain proves tree correct, not member uniqueness |
| 1 | "One action = one nullifier" | **app-side** — identity manager is stateless re: nullifiers; integrators must dedup |
| 6 | L1→L2 state bridge root | **named** — cross-layer seam; L2 trusts the bridged root |
| ceiling | owner: upgrade + swap verifier + set operator + expiry | **trust-boundary debt (by design)** — ZK guarantees conditional on the owner |

## What this audit did NOT cover (coverage honesty)

- The **ZK circuits** themselves (`semaphore-rs`, the insertion/deletion verifiers `b10..b1200`,
  `SemaphoreVerifier.sol`) — soundness of the Groth16 verifiers/circuits is the foundation under
  Bucket 2 and was read only at the contract interface (the trusted setup is `smtb-ceremony`).
- The **identity deletion** path (`deletion/` verifiers) and `ImplV2`/`ImplV3` additions beyond the
  V1 insertion/verify core.
- The **state bridge** contracts (Optimism/Polygon) — the 6b counterpart, separate repos.
- The **signup-sequencer / semaphore-mtb** (off-chain tree manager that builds batches) — the
  operator-side software; the on-chain proof gate is what bounds it.
- The **orb** hardware/biometric pipeline — the off-chain personhood root, not on-chain.

## Nothing routed privately

No defect found. World ID's on-chain contracts are a strong, ZK-witnessed identity-tree manager:
insertions are proof-constrained (the operator cannot forge membership), membership proofs require a
fresh valid root, and the design is clean. The honest, methodology-level output is the **layering**:
on-chain ZK guarantees *tree integrity*, but **personhood is an off-chain orb+operator trust (6b)
and action-uniqueness is delegated to integrating apps** — so "one action per unique human" is *not*
a property of these contracts alone. And the whole ZK edifice is **conditional on the owner**, who
can swap the verifier or upgrade (the apex ceiling). A new §9/§11 data point: a **ZK
proof-of-personhood** where conservation = ZK tree-integrity + off-chain personhood + app-side
nullifier dedup. Cleaner than Humanity Protocol (`AUDIT-HUMANITY-HTOKEN.md`), which kept *all*
proof-of-humanity off-chain on vanilla EAS; World ID at least puts tree integrity under ZK on-chain.
Companion to `AUDIT-BASE-SIX-BUCKET.md` (the bridged-root seam) and `AUDIT-GOVERNANCE-CEILING.md`
(owner = apex; ZK conditional on it).
