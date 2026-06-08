# State-synchronization security — the sync seam, audited

A new sweep, a different seam. Bridges (`../bridges/`) are where a chain trusts a **summary of another
chain**. **State sync is where a node trusts a summary of its *own* chain's history** — a snapshot, a
checkpoint, a range of accounts — served by **peers it does not trust**, often under time pressure, written
toward **persistent storage** before (or instead of) full cryptographic verification. It is the same
*proven-vs-attested / recompute-vs-trust-the-summary* axis (`../methodology/AUDIT-REASONER-EPISTEMOLOGY.md
§9`), pointed at the most operationally dangerous moment in a node's life: **bootstrapping state from the
network.**

## The threat model (what an adversarial peer is trying to cause)

A malicious peer (or a malicious snapshot/checkpoint provider) serving sync data wants to drive an **honest
node** into one of four end states. They are ranked by severity the same way the corpus ranks everything —
by whether the substrate lets the failure go **unsafe**:

| # | Failure mode | Severity | Why it matters |
|---|---|---|---|
| **D — Divergence** | honest nodes reconstruct **different** states from the same chain | **worst (unsafe)** | a consensus split with no misbehaving validators — the MemeCore class, but at the sync layer |
| **A — Invalid acceptance** | node commits **invalid** state as canonical | **unsafe** | accepts forged balances/storage; security collapse |
| **C — Corruption** | **persistent storage** left corrupted / inconsistent | severe | un-recoverable without resync; can brick a node or silently rot the DB |
| **S — Stall** | sync **never completes** (or wedges) | liveness | griefable DoS; node can't catch up, falls out of consensus |

## The two questions (the lens, adapted from the bridge sweep)

> **(Q1) What is the root of trust for the synced state?** A checkpoint/snapshot hash supplied out-of-band, the
> chain's own state root reached via consensus, or merely *a peer's word*? (the trust anchor)
>
> **(Q2) Is network-supplied data verified *before* it can influence persistent local state?** Is each chunk/
> range/node proven against the trusted root *before* it's written — or written-then-verified, or never? (the
> verification ordering — the single most important question for failure modes A and C)

Plus the sync-specific checklist the failure modes demand:
- **Verification ordering** — does untrusted bytes → disk happen *before* a Merkle/range/hash check? (any
  "write then verify" is a corruption/acceptance risk)
- **Chunk assembly & ordering** — can a peer reorder, omit, duplicate, or splice chunks/ranges and still pass?
  (the boundary-proof / range-proof completeness question — geth's "no extra leaves to the right" class)
- **Determinism of reconstruction** — given the same verified inputs, do all honest nodes build the *same*
  state? (iteration order, map nondeterminism, dust/rounding — the MemeCore lesson at the DB layer)
- **Partial / corrupted snapshots** — is a truncated or tampered download detected and *rejected*, or partially
  committed? Is there a clean abort + retry, or does it wedge / poison the DB?
- **Rollback / recovery & reorg-during-sync** — if a reorg lands mid-sync, or sync aborts, does unwind restore
  a consistent DB, or leave a half-written hybrid? Are pivot changes handled?
- **Resource exhaustion** — can a peer force unbounded memory/disk/CPU with a crafted snapshot (decompression
  bomb, huge proof, pathological trie, unbounded queue)?
- **Serialization/deserialization** — does decoding untrusted bytes bound lengths/recursion/allocations before
  trusting them?
- **Cache coherence & concurrent updates** — can live block processing and the sync writer race on the same
  state, leaving an inconsistent view?
- **fast/snap/warp vs full** — what safety does the fast path *give up* vs full replay, and is that gap
  cryptographically closed (proof) or socially assumed (trusted checkpoint)?

## Posture
Defensive; read-only; public source only. No exploit, no PoC. Real exploitable defects in live software →
**stopped and reported privately**, redacted placeholder here only. The aim is **characterization**: name the
trust anchor, locate the verify-before-persist boundary, and check whether each failure mode is forced **safe**
by the substrate (abort/retry/re-request) or left **unsafe** (commit/diverge/corrupt).

## Index
*(populated as the sweep runs — geth snap sync, reth/erigon staged sync, beacon checkpoint sync, Cosmos/
CometBFT state-sync, Solana snapshots, Substrate warp sync, …)*
| File | What it is |
|---|---|
| _SX entries land here_ | |
