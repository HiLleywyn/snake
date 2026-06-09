# The coordination layer — admission gates: interop messaging, data availability, and governance

**Why this hunt exists.** Three live systems that are each a **gate admitting an external claim into privileged
action** — a cross-chain message that moves value, a data-availability claim a rollup builds on, a governance
proposal that can upgrade contracts or move a treasury. The bug class is "admit a claim that should be rejected":
**forge a message, forge availability, or execute an unvoted/unauthorized action.** Distinct from the
verification-layer hunt (which *verifies a proof of external truth*); this is about what gets to *act*.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute the admission
logic from source and ask "what stops an illegitimate claim from passing this gate?" Anything real and live would be
stopped and routed for private disclosure (redacted here). **All three came back clean — no live finding** — and
each had its historically-sensitive spot or freshest code confirmed handled.

| Target | The gate | "Illegitimate claim admitted" = | Verdict |
|---|---|---|---|
| **Hyperlane** (HEAD `70b7da4`) | ISM/Mailbox cross-chain message verification | forge any message → drain any app | **clean** (in-order-distinct signers; replay set before interactions) |
| **Celestia** (NMT/share/rsmt2d/app HEADs) | NMT + DA proofs (data-availability admission) | prove a blob available/included when it isn't | **clean** (GHSA-r9fq completeness bypass present-and-patched) |
| **Arbitrum DAO** (HEAD `ae6cf85`) | Governor + timelock + cross-chain upgrade path | execute an unvoted / unauthorized governance action | **clean** (cross-chain sender doubly-authenticated; fresh DVP/cancel sound) |

---

## 1. Hyperlane — admitting a cross-chain message (a bug forges any message)

**Repo:** `hyperlane-xyz/hyperlane-monorepo`, HEAD `70b7da4`. Live on many mainnets; the highest-historical-loss
category (cross-chain). The gate is the ISM `verify` + the Mailbox replay guard.

- **ISM verify + anti-double-count (highest) — clean.** The `AbstractMultisigIsm.verify` loop uses a single
  monotonic `_validatorIndex` that only ever advances, so the `threshold` signatures must form a **strictly
  increasing subsequence of the validator array** — a duplicate or out-of-order signature fails
  `_validatorIndex < _validatorCount`. The classic below-threshold-forge defense, correct; OZ `ECDSA.recover` blocks
  `s`-malleability and `v ∉ {27,28}`.
- **Digest binding — clean.** `CheckpointLib.domainHash = keccak256(origin ‖ merkleTreeHook ‖ "HYPERLANE")` binds a
  checkpoint signature to the exact origin domain **and** the specific merkle-tree-hook address (no cross-domain
  *or* cross-mailbox replay); the message-id additionally binds version+nonce+origin+sender+destination+recipient+body.
- **Mailbox replay — clean.** `process` records `deliveries[_id]` in the **effects block before** `ism.verify` /
  `recipient.handle`, so a reentrant `handle` re-hits `delivered() == true` and reverts.
- **Aggregation / routing — clean.** Aggregation iterates unique sub-ISM positions and *underflows the uint8
  threshold → reverts* if over-supplied (fails closed); routing keys on the id-bound `origin`, so an attacker can't
  route to a weaker ISM.
- **By-design trust (named, not a bug):** the validator set + duplicates are deployer/governance config — an
  attacker can't influence the set, and a duplicate only weakens that deployer's own ISM.

**No live finding.**

---

## 2. Celestia — admitting a data-availability claim (a bug forges availability/inclusion)

**Repos:** `celestiaorg/{nmt, celestia-app, go-square(v4), rsmt2d}` (main HEADs). Live mainnet securing rollup DA.
The gate is the namespaced-merkle-tree proof system + the data-root binding — a taxonomy that exists nowhere else.

- **NMT proofs (highest) — clean.** Every inner node commits `min(left.minNID) ‖ max(right.maxNID)` **inside the
  hash preimage** (`hasher.go`), with `HashNode` rejecting malformed lengths, intra-node disorder
  (`maxNID < minNID`), and out-of-order siblings (`right.Min < left.Max`) — so a forged namespace range cannot
  survive root recomputation. Absence proofs require the leaf belong to a strictly larger namespace; `ignoreMaxNs`
  only *narrows* the upper bound, never widens (can't forge inclusion).
- **The historical CVE is present-and-patched.** The NMT truncated-proof **completeness bypass
  (`GHSA-r9fq-g486-v8pg`)** — where the right-side completeness check was silently skipped when the left traversal
  exhausted `proof.nodes` — is fixed at HEAD with an explicit guard + reference comment. Known, not novel.
- **Share encoding — clean.** Continuation shares must match the prior sequence's namespace (no cross-namespace
  smuggling); blob namespaces can't be version-≠{0,255} or collide with the parity (`0xFF`) / reserved namespaces.
- **BEFP — clean.** `verifyEncoding` re-Reed-Solomon-encodes the original half and requires **every** parity share
  to byte-match — the exact "passes the roots but is unreconstructable" detector → `ErrByzantineData`.
- **Blob inclusion — clean.** The shares→row-root→data-root chain is cryptographically bound (per-row NMT inclusion
  + cometbft merkle with domain-separated leaves + `Index`/`Total` binding), so an unavailable blob can't be proven
  included; `StartRow/EndRow` are advisory, the binding lives in the merkle proof.
- **PFB hygiene — clean.** `ValidateBasic` enforces component-count/reserved-namespace/share-version/commitment
  rules, and `blob_tx` recomputes the blob commitment and byte-compares it to the PFB's `ShareCommitments`.

**No live finding.**

---

## 3. Arbitrum DAO — admitting a governance action (a bug executes the unauthorized)

**Repo:** `ArbitrumFoundation/governance`, HEAD `ae6cf85` (OZ `4.7.3`). Live, multi-billion treasury + chain
upgrades. The freshest surface (and the scrutiny focus) is the new DVP (Delegated Voting Power) quorum + a new
public `cancel()`, corroborated by the in-repo Oct-2025 cancel-upgrade audit.

- **Proposal lifecycle + DVP quorum (highest) — clean.** `quorum()` clamps the DVP estimate to
  `[_minimumQuorum, _maximumQuorum]` — the **floor means quorum can never be driven below the configured minimum**,
  defeating the manipulated-low-quorum passage class; `EXCLUDE_ADDRESS` (treasury) is subtracted in both the legacy
  and DVP paths. Vote counting is unoverridden OZ (double-vote guard intact), and the snapshot uses
  `getPastVotes(account, snapshot)` at a strictly-past block — **flash-delegation at the snapshot is impossible.**
- **Timelock payload binding — clean.** Only `updateDelay` is overridden (role-gated); the op-id
  `hashOperationBatch(targets, values, payloads, predecessor, salt)`, the `block.timestamp >= getTimestamp(id)`
  delay, and predecessor ordering are unmodified OZ — execute recomputes the id from supplied args, so voted ≠
  executed is unreachable.
- **Cross-chain execution (the Arbitrum-specific surface) — clean.** `L1ArbitrumTimelock.onlyCounterpartTimelock`
  enforces **both** `msg.sender == bridge` **and** `getL2ToL1Sender(inbox) == l2Timelock`, and PROPOSER_ROLE is
  granted only to the bridge — a non-governance party cannot forge the L2 sender or schedule an L1 op; the retryable
  sets `callValueRefundAddress = address(this)` so only the DAO can cancel the round-trip.
- **Security Council — clean.** The member-sync action re-applies the existing Safe threshold on add/remove (relying
  on the Safe `threshold ≤ owners` invariant), removes departed members as Safe owners (no retained signing power),
  and enforces nonce monotonicity; cohort roles block a member being in both cohorts.
- **New cancel — clean.** The new public `cancel()` is restricted to `ProposalState.Pending` **and**
  `msg.sender == proposers[id]` — Pending precedes Active/Queued and carries no votes/timelock op, so no escalation
  or griefing of others.

**No live finding.** Honest scope note: the OZ 4.7.3 base contracts and the separately-audited `UpgradeExecutor`
package are not vendored in this tree (reasoned from known behavior, flagged out-of-tree).

---

## Synthesis — admission gates

1. **One gate question, three admission systems.** "What stops an illegitimate claim from passing?" resolves to:
   in-order-distinct-signers-over-a-domain-bound-digest (Hyperlane), namespace-range-committed-in-the-hash +
   data-root-binding (Celestia), and quorum-floor + payload-hash-binding + doubly-authenticated-cross-chain-sender
   (Arbitrum). Each gate rejects the forged claim at a *specific* checked step.
2. **The historical-CVE-confirmation pattern held a third time.** Like DCAP's recomputed cert-chain bypass and
   tBTC's CVE-2012-2459, Celestia's NMT completeness bypass (`GHSA-r9fq`) was located and confirmed
   present-and-patched at HEAD — "deployed == audited" applied to the known-issue surface.
3. **Scrutiny weighted to the freshest code.** Arbitrum's hunt focused on the two genuinely-new pieces (DVP quorum,
   public cancel) and confirmed the high-value invariants are unmodified audited code — the right allocation of
   attention on a mostly-stable, heavily-audited contract.
4. **Config-trust vs forgeable-defect, kept distinct.** Hyperlane's duplicate-validator config and Celestia's
   advisory row indices were each characterized as operator-config / non-binding metadata, **not** attacker-reachable
   forge paths — the same defect-vs-design discipline the whole corpus runs on.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
