# State-sync sweep — verify-before-persist, audited across clients

The sync seam under the threat model in [`README.md`](README.md): a malicious peer serving snapshot/checkpoint/
range data tries to drive an honest node to **diverge (D)**, **accept invalid state (A)**, **corrupt storage
(C)**, or **stall (S)**. The two questions: *(Q1) what is the root of trust for synced state, and (Q2) is
network-supplied data verified before it can influence persistent local state?* This is the
proven-vs-attested / recompute-vs-trust-the-summary axis (`../bridges/AUDIT-BRIDGES-SWEEP.md` coda) at the node
bootstrap layer.

---

## S1. go-ethereum snap sync — the proven end: every untrusted byte recomputed against the trusted root before it persists
**Target:** `ethereum/go-ethereum`, `eth/protocols/snap/sync.go` + `trie/proof.go`. Snap sync downloads the
state as **account/storage ranges** from untrusted peers and reconstructs the trie. It is the canonical
"network data influencing local state" path, and it is built exactly the way the corpus says it should be:
**recompute, don't trust the summary.** **Result: failure modes D/A/C are structurally forced *safe*; only S
(stall) remains, and it is mitigated by peer rescheduling.**

**(Q1) Root of trust:** `s.root` — the **state root from the (consensus-verified) block header**. The synced
state is never trusted on a peer's word; it is verified against the chain's own canonical root. (As the chain
advances during sync the **pivot** root moves, and the **healing** phase re-downloads missing trie nodes and
re-verifies them against the current root.)

**(Q2) Verify-before-persist: yes, and it gates everything.** In `OnAccounts` (`sync.go:2524`) the peer's
`hashes/accounts/proof` are checked by **`trie.VerifyRangeProof(root, req.origin, keys, accounts, proof)`
(`:2593`) *before* the response is ever delivered to the processing pipeline**. On failure →
**`scheduleRevertAccountRequest(req)` + return err** (`:2596-2598`) — the request is reverted and **rescheduled
to another peer**; nothing touches the database. `OnStorage` (`:2735`) is identical (`VerifyRangeProof` at
`:2845/:2856`). Untrusted bytes reach disk **only after** a proof against the trusted root succeeds.

**Why the range proof closes the omission/splice/reorder attacks (`trie/proof.go VerifyRangeProof :478`):** a
peer cannot cheat the *set* of keys in a range, because the proof enforces, before persistence —
- **monotonically increasing keys** (`keys[i] < keys[i+1]`, `:488`) → no reorder, no duplicates;
- **no path-prefix expansion** (`!HasPrefix(keys[i+1], keys[i])`, `:491`) → no structural trie attack;
- **no deletions** (`len(values[i]) != 0`, `:495`);
- **left boundary** (`firstKey <= keys[0]`, `:525`) → no keys spliced in before the requested origin;
- **reconstructed root must equal `rootHash`** — both the no-edge-proof case (rebuild via `StackTrie`, hash
  must match, `:506`) and the two-edge-proof case (`proofToPath` ×2 then root compare); and
- **`hasRightElement`** (the `cont` return, `:518/:542`) → the boundary proof reveals whether more elements
  exist to the right, so a peer **cannot falsely claim a range is empty or omit a trailing leaf** — the empty-
  range case must *prove* `!hasRightElement` (`:513-521`).

**Failure-mode analysis:**
- **D (divergence): structurally impossible.** The state root is the **unique** Merkle preimage commitment;
  any set of ranges that verifies against it reconstructs the *identical* state on every honest node. There is
  no iteration-order or nondeterminism freedom — the root pins the state exactly. (This is the MemeCore lesson
  inverted: here the substrate *forces* determinism.)
- **A (invalid acceptance): forced safe.** Nothing is accepted that doesn't verify against the trusted root; a
  forged balance/slot fails `VerifyRangeProof` → revert.
- **C (corruption): forced safe.** Verify happens *before* the write; a bad/partial/tampered range is rejected
  before it can be committed, so the DB is never left holding unverified bytes.
- **S (stall): the only residual.** A malicious peer can *refuse* or feed bad proofs — but each failure
  **reschedules to another peer** (`scheduleRevert*`), and bad peers are dropped. Liveness rests on ≥1 honest
  serving peer (a 1-of-N honest-availability assumption), not on safety.

**Verdict: the proven end of the sync taxonomy.** Snap sync is, in effect, a **light client for your own
state history** — it recomputes every peer-supplied byte against the consensus root before persistence, with
a range proof complete enough to defeat omission/splice/reorder, and a clean revert-and-reschedule on any
failure. **No finding.** **Residual:** the header's state root (i.e. consensus itself — the irreducible
anchor) and **≥1 honest peer for liveness**. This is what "verify-before-persist" looks like done right, and
it is the bar the rest of this sweep is measured against.

---

## Sweep status (running)
| # | Target | Layer | (Q2) verify-before-persist? | Worst reachable failure mode |
|---|---|---|---|---|
| S1 | go-ethereum snap sync | EVM exec-client state ranges | **yes** — `VerifyRangeProof` vs header root before any write | only **S** (stall); D/A/C forced safe |
| _S2…_ | _reth/erigon, beacon checkpoint, Cosmos/CometBFT, Solana/Bitcoin — landing as sweeps complete_ | | | |
