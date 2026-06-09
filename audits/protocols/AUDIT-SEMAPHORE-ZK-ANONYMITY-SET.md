# Semaphore — the ZK anonymity-set floor (commitment-nullifier privacy, same trusted-setup residual as zk-rollups)

**Scope.** Semaphore, the canonical zero-knowledge **anonymous-signaling** primitive
(`semaphore-protocol/semaphore` @ `341475c6`; Groth16 over BN254, Poseidon, a Lean Incremental Merkle
Tree). This is published, legitimate privacy cryptography (anonymous voting/signaling). It adds the
**anonymity-set floor** to the corpus and connects directly to the earlier zk-proving work: the on-chain
verifier is a thin pairing check, and *all* soundness lives in the off-chain ceremony + circuit — the same
residual the zk-rollup sweep surfaced, now in service of *privacy* rather than *scaling*. Public source,
read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**;
the trusted-setup, circuit-soundness, and small-anonymity-set residuals are characterized factually.

**Sources read (verbatim, line refs):** `Semaphore.sol`, `base/SemaphoreGroups.sol`,
`base/SemaphoreVerifier.sol`, `base/SemaphoreVerifierKeyPts.sol`, `interfaces/ISemaphore.sol`, and the
external `@zk-kit/lean-imt.sol@2.0.1` `InternalLeanIMT.sol` (`_insert`/`_root`).

---

## 0. The one-paragraph result

Semaphore is the cleanest illustration in the corpus of a floor that conserves **identity/eligibility
instead of value**, and it does so with the same machinery a zk-rollup uses for state. The "floor" is an
**anonymity set**: a per-group incremental Merkle tree of Poseidon-hashed **identity commitments**; the set
of all inserted commitments *literally is* the privacy guarantee, and its size bounds it. A member proves,
in zero knowledge, "*I know the secret behind some leaf in the tree with root R, the nullifier I reveal is
the unique one for my identity under this scope, and I am binding this message*" — **without revealing
which leaf**. Two on-chain checks make this a usable primitive: a **Groth16 pairing verification** that
binds the four public signals (`merkleTreeRoot, nullifier, hash(message), hash(scope)`) so none can be
swapped, and a **nullifier mapping** that rejects reuse — *anonymous double-spend prevention*: each member
can produce exactly one valid nullifier per scope, so "one vote per poll" is enforced without learning
*who* voted. The corpus-connecting point is that **the on-chain code proves almost nothing itself** — it
never re-derives Poseidon membership; it trusts the *circuit* to have proven "leaf ∈ tree" and "nullifier
correctly derived," and only checks that the root is recognized and recent and that field elements are
well-formed. So the entire soundness rests, exactly as in every Groth16 zk-rollup, on **(a) the trusted-
setup ceremony** (if any participant kept the toxic waste `tau`, forged proofs for non-members are possible,
silently breaking soundness), **(b) the circuit being correctly constrained**, and **(c) Poseidon collision
resistance** — plus a privacy-specific residual the value-conserving systems didn't have: **the anonymity
is only as strong as the group size at the proven root** (a 1-member group gives zero privacy, and the
contract only rejects *empty* groups). So the Semaphore law: *the anonymity-set floor conserves
eligibility by the same thin-verifier-over-a-trusted-circuit mechanism as a zk-rollup conserves state — the
residual is identical (ceremony + circuit + hash) plus one new privacy-only term, the set size, which is
the actual measure of how much is hidden.*

---

## 1. The anonymity-set floor — an incremental Merkle tree of identity commitments

`SemaphoreGroups._addMember (:85-93, onlyGroupAdmin)` inserts an `identityCommitment` into a per-group Lean
IMT and returns the new root; `Semaphore.addMember (:78-82)` records `merkleRootCreationDates[root] =
block.timestamp` (for the history window, §4). The actual accumulation is `InternalLeanIMT._insert`: leaves
must be **non-zero, unique, and `< SNARK_SCALAR_FIELD`**, depth grows at most +1 per insert, and each node
is `PoseidonT3.hash([sibling, node])` (the *Lean* IMT omits zero-padding — a missing right child promotes
the left child's value, a cheaper but distinct root convention the circuit must match exactly).

**Characterization:** the floor is a Poseidon Merkle tree whose leaves are members' commitments. **The set
of all inserted commitments *is* the anonymity set — its size literally bounds the privacy.** Membership is
`onlyGroupAdmin`, so the admin fully controls who is in the set (add/remove/update) — a trust the privacy
guarantee rests on (an admin can stuff or censor the set).

---

## 2. The ZK floor — a thin Groth16 pairing check that binds four signals

`Semaphore.verifyProof (:142-187)` calls the snarkjs-generated `SemaphoreVerifier`, binding **four public
inputs**: `[merkleTreeRoot, nullifier, _hash(message), _hash(scope)]` (`_hash = keccak >> 8` to fit the
BN254 scalar field), plus the 8-element Groth16 proof. `SemaphoreVerifier (:37-187)` does `checkField` (each
public signal `< r`) then the standard BN254 pairing equation via the `ecMul`/`ecAdd`/`ecPairing`
precompiles, with hardcoded `alpha/beta/gamma` VK constants and per-depth `delta`/IC points swapped in from
`SemaphoreVerifierKeyPts.getPts(depth)` — **one verifier serves all depths 1–32** by selecting per-depth VK
points (a hardcoded blob "taken from the verification key json generated with snarkjs").

**Characterization:** validity reduces to a **single elliptic-curve pairing check**. The proof
cryptographically binds membership (`merkleTreeRoot`) to the signaling triple (`nullifier, message, scope`)
so none can be swapped without invalidating it. **Crucially the contract never re-derives Poseidon
membership on-chain** — it trusts the circuit to have proven "leaf-with-known-secret ∈ tree rooted at
`merkleTreeRoot`," and only checks the root is recognized/recent (§4). *This is the same thin-verifier
posture as a zk-rollup's on-chain proof check.*

---

## 3. The nullifier — anonymous double-spend prevention

`Semaphore.validateProof (:114-140)` rejects a reused nullifier (`groups[groupId].nullifiers[nullifier]`),
verifies the proof, then **records the nullifier** and emits. In the circuit the nullifier is
deterministically derived from the identity secret and the `scope`, so **each member can produce exactly one
valid nullifier per scope**; reuse is rejected on-chain. **Characterization:** the double-spend analog
*without revealing the spender* — `scope` defines the one-action-per-identity domain (one vote per poll)
while preserving unlinkability of *who*. The dedup is **per-group**, not global — the same nullifier value
can be fresh in a different group.

---

## 4. Root history — the stale-proof window

Because membership changes between proof generation and submission, `verifyProof (:164-177)` accepts a proof
against the **current** root, or any **historical** root that (a) really was a root of this group
(`merkleRootCreationDates != 0`) and (b) is younger than `merkleTreeDuration` (default **1 hour**,
admin-tunable). **Characterization:** a deliberate liveness-vs-freshness trade-off — a wider window
tolerates lag but lets proofs against a *stale anonymity set* (one that may have since removed a member)
remain valid for up to the window. Per-group, admin-controlled.

---

## 5. The ZK trust model — identical to the zk-rollup residual, plus a privacy term

**What the proof proves:** "I know the secret behind *some* leaf in the tree with root R, my nullifier is
the unique one for my identity under this scope, and I bind this message" — *without revealing which leaf*.
**Anonymity = indistinguishability within the leaf set.**

**The residual (factual, defensive — not exploits):**
1. **Groth16 trusted setup (toxic waste).** The hardcoded VK constants come from a snarkjs Powers-of-Tau
   ceremony. If any participant kept `tau`, **forged proofs for non-members** are possible, *silently*
   breaking soundness — the contract only checks the pairing against these constants and cannot detect it.
   **Identical class of trust to every Groth16 zk-rollup in the §5c proving sweep.**
2. **Circuit soundness/completeness.** On-chain code never re-computes Poseidon membership or the nullifier
   derivation — it *fully delegates* "leaf ∈ tree" and "nullifier correctly bound to identity" to the
   off-chain circuit; an underconstraint (missing range check, unbound nullifier) is **not caught here**.
3. **Poseidon collision resistance** over BN254 — a collision corrupts root accumulation or lets one leaf
   masquerade as another.
4. **Anonymity set = group size (the privacy-only residual).** Privacy is only as strong as the number of
   members at the proven root; a 1-member (or timed-degenerate) group gives **zero** anonymity, and the
   contract only rejects *empty* groups (`Semaphore__GroupHasNoMembers`), not small ones. *This is the new
   term the value-conserving systems didn't have: the floor can be perfectly sound and still hide nothing.*
5. **Admin-controlled membership + per-group nullifiers + the stale-root window** — the group admin is
   trusted not to stuff/censor the set; a large `merkleTreeDuration` widens staleness exposure.

---

## 6. Where this sits in the corpus

Semaphore is the corpus's **anonymity-set floor**, and it closes a loop with the zk-proving sweep (§5c):
the on-chain verifier is, *exactly as in a zk-rollup*, a thin hardcoded pairing check, and **all soundness
lives in the off-chain ceremony + circuit + hash** — the same residual, repurposed from "is this state
transition valid" to "is this signaler an eligible-but-unidentified member." It also extends the residual
taxonomy with a term unique to privacy systems: **the anonymity set size**, a floor that can be
*cryptographically sound and yet privacy-empty* — the analog, for a privacy primitive, of "the conservation
floor holds but the oracle lies." And it reaffirms the method one more time: *recompute, don't trust the
summary* — the contract proves nothing about membership itself; a reader who stops at "Groth16 verified ⇒
safe" misses that the verifier is trusting a ceremony it can't see and an anonymity set that might be one
person. The honest user statement: *your signal is anonymous within, and only within, the set of members at
the root you proved against — and that the proof means anything at all rests on the trusted setup and the
circuit, exactly as a zk-rollup's validity does.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
