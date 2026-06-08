# Consensus-safety sweep — fork choice, the EL↔CL seam, equivocation

The agreement boundary under the threat model in [`README.md`](README.md): an adversarial
validator/proposer/peer/EL trying to cause a **safety violation**, a **reorg**, a **liveness stall**, an
**unjust slashing**, or an **EL↔CL split**. The lens: *does the code enforce exactly the safety/liveness
assumption (no weaker), and can one actor move fork choice / finality / slashing beyond their stake?* It is the
proven-vs-attested discipline turned inward — here the "summary" a node must not blindly trust is **another
participant's claim about the canonical chain.**

---

## C1. go-ethereum engine API — the EL↔CL seam: separation of authority + anti-poisoning invalid-block handling
**Target:** `ethereum/go-ethereum`, `eth/catalyst/api.go`. The **engine API** is the trust boundary between
the execution client (authority on *execution validity*) and the consensus client (authority on
*fork choice / head*). Post-Merge, an adversary's lever here is **optimistic-sync poisoning**: get a node to
follow a chain the EL will later reject, or get honest blocks wrongly invalidated. **Result: authority is
cleanly separated, the optimistic path is correct, and the invalid-block cache is bounded *and self-healing* —
the EL↔CL-split failure mode is forced safe. No finding.**

**`newPayload` — validate, but never choose the head (verified myself):**
1. **block-hash binding** — the payload's claimed `blockHash` must equal the computed `block.Hash()` (checked
   in the `ExecutableData → block` conversion before processing); a known-`VALID` block short-circuits
   (`:70-71`).
2. **invalid-ancestor check first** — `checkInvalidAncestor(block.Hash(), block.Hash())` (`:74`): if this block
   is a known descendant of a previously-rejected block, return `INVALID` immediately (don't reprocess; also
   anti-DoS).
3. **parent unknown → `SYNCING` (the optimistic path)** — `parent := GetBlock(ParentHash); if parent == nil`
   (`:83-84`) → cache the block and return `SYNCING`. The EL can't validate without the parent, so it tells the
   CL "optimistic" rather than guessing — correct, and it can't be tricked into a `VALID`/`INVALID` it hasn't
   earned.
4. **`InsertBlockWithoutSetHead`** (`:109`) — the block is executed and validated **without** being made the
   head. *Head selection is the CL's job via `forkchoiceUpdated`* — the separation-of-authority that defines
   the seam. Success → `VALID` + the block hash as `latestValidHash` (`:136`); failure →
   `invalidTipsets[block.Hash()] = header` (`:115-116`) + `INVALID`.

**The subtle part — `checkInvalidAncestor` is anti-poisoning by construction (verified myself):** it maps a
descendant hash → its bad ancestor and returns `INVALID` with **`latestValidHash = invalid.ParentHash`**
(`:1043`) — the parent of the *first* invalid block, which was by definition already validated — so the CL
learns *exactly* where the valid chain ends and can reorg to it rather than discarding more than it must.
Three defenses make this robust:
- **Bounded cache** — `invalidTipsets` capped at `invalidTipsetsCap = 512` (old entries evicted, `:1035-1040`),
  so a peer/CL streaming endless bad-descendants **can't grow memory** (S defended).
- **Self-healing eviction** — `invalidBlocksHits[badHash]++`, and on `>= invalidBlockHitEviction` the bad hash
  **and all its cached descendants are evicted** and the block is re-tried (`:1022-1030`). This is the key
  anti-poisoning property: a block wrongly marked invalid by a **transient data race** does **not permanently
  poison** the honest chain — repeated honest attempts eventually clear it. A persistent real defect stays
  rejected; a transient false-positive self-heals.
- **Terminal-PoW special case** — if the bad block's parent is the terminal PoW block, return `0x0` as LVH
  (`:1041-1042`), per the engine-API spec.

**Verdict:** the seam is built on **separation of authority** (EL = execution validity, CL = head) with the
optimistic case answered honestly (`SYNCING`, not a guess), the invalid-block cache **bounded and
self-healing**, and `latestValidHash` pointing exactly at the last validated ancestor. **No finding.**
**Failure mode — EL↔CL split / optimistic-sync poisoning: forced safe.** The residual is the *correctness of
the consensus rules themselves* (the EL faithfully implements EVM/validity; the CL faithfully implements fork
choice) — i.e. C2+ below; the *seam* between them does not add an exploitable gap. **Residual trust:** that the
CL feeding the engine API is the operator's own (the engine API is authenticated by a JWT secret — a local
trust boundary, not a peer one).

---

## Sweep status (running)
| # | Target | Layer | (Q) enforces exactly the assumption? | Worst reachable failure mode |
|---|---|---|---|---|
| C1 | go-ethereum engine API | EL↔CL seam | **yes** — separation of authority; bounded + self-healing invalid cache; correct LVH | EL↔CL split / optimistic poisoning **forced safe** |
| _C2…_ | _ETH fork choice, CometBFT, Solana/DAG — landing as sweeps complete_ | | | |
