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

## C2. CometBFT consensus — the BFT state machine enforces *exactly* 1/3, no weaker
**Target:** `cometbft/cometbft`, `consensus/state.go`, `types/vote_set.go`, `evidence/verify.go`. The Tendermint
state machine: the audit question is whether a sub-1/3 minority can break **safety** (two blocks committed at
one height), wedge **liveness**, or evade double-sign **slashing**. **Result: the >2/3 assumption is enforced
*exactly* — strict quorum, the correct PoLC unlock rule, and complete in-round equivocation detection. No
finding.**

- **Quorum is strict `>2/3` (verified myself).** `quorum := TotalVotingPower()*2/3 + 1` (`vote_set.go:308`) —
  the `*2/3 + 1` form lands *strictly above* 2/3 under integer truncation; `HasTwoThirdsAny: sum >
  TotalVotingPower()*2/3` (`:459`, strict `>`). `TwoThirdsMajority` latches the first-seen 2/3 BlockID and is
  immutable thereafter — **no late flip**. The safety bar is exactly 1/3 Byzantine; nothing rounds it down.
- **The PoLC unlock rule is correct — the one safety-critical line (verified myself).** A locked validator
  unlocks only on a genuine later-round polka: `cs.LockedBlock != nil && cs.LockedRound < vote.Round &&
  vote.Round <= cs.Round && !cs.LockedBlock.HashesTo(blockID.Hash)` (`state.go:2314-2317`). Unlock requires a
  **real +2/3 prevote** (via `TwoThirdsMajority`) at a round **strictly later** than `lockedRound`, for a
  *different* block — the exact proof-of-lock-change condition. No path unlocks on sub-+2/3 evidence, and a
  Byzantine proposer can't induce a prevote for a block lacking a genuine polka (`isProposalComplete` requires
  `Prevotes(POLRound).HasTwoThirdsMajority()`, with `POLRound ∈ [0, Round)`). **Below 1/3 Byzantine, two
  conflicting commits are impossible.**
- **Every in-round double-signer is caught, with strictly-verifiable evidence.** Conflicting-vote detection in
  `vote_set.go` (an existing vote for a validator with a different BlockID → `ErrVoteConflictingVotes`, and
  *memory-bounded* — conflicting votes are only stored for peers that prove a real conflict, anti-DoS),
  surfaced to the evidence pool; `evidence/verify.go` re-checks same H/R/type, same validator, different
  BlockID, both sigs valid. (Cross-round/standalone equivocation is the evidence-pool / light-client-attack
  path by design.)
- **No minority wedge / no unbounded work.** Future-round skip requires `HasTwoThirdsAny` (`state.go:2362/2404`)
  and commit requires `TwoThirdsMajority` (`:2390`) — a sub-1/3 minority can neither force-advance nor
  force-commit; per-round timeout escalation + nil-precommit-on-no-polka guarantee progress past a withholding
  minority; block parts are bounded by `MaxBytes` and the proposal's fixed `PartSet.Total` (no amplification).

**Verdict: canonical Tendermint, enforced exactly.** **No finding.** This is the *agreement-layer* analog of
the corpus's recurring result: the protocol's stated assumption (>2/3 honest stake) is the *actual* bar — the
arithmetic is strict, the safety-critical unlock is the textbook PoLC rule, and equivocation is always
detected. The residual is the design assumption itself (≥1/3 stake can halt; ≥1/3 colluding can — by the BFT
bound — break safety and be slashed for it), which the code neither weakens nor strengthens.

## C3. Ethereum fork choice (Lighthouse, Prysm) — proposer boost that can't compound, an FFG filter that can't be weakened
**Target:** `sigp/lighthouse` (`consensus/proto_array/`, `fork_choice.rs`), `OffchainLabs/prysm`
(`beacon-chain/forkchoice/doubly-linked-tree/`). LMD-GHOST + Casper FFG: the audit question is whether a
**single proposer** can reorg honest blocks beyond the designed proposer-boost resistance, or **split** honest
views (a balancing attack). **Result: both enforce the spec rules exactly; the reorg lever is capped at one
committee's 40% boost and the head is a deterministic pure function — no finding.**

- **Proposer boost is spec-sized and *cannot compound* (verified myself).** The boost is `committee_fraction =
  total_balance / slots_per_epoch * 40 / 100` (`proto_array.rs:1112`), applied only to the `proposer_boost_root`
  — and crucially the **previous** boost is **subtracted before** the current one is applied
  (`proto_array.rs:204-211`, `previous_proposer_boost`), recomputed fresh on *every* head computation, and
  **zeroed at the slot boundary** in `on_tick`. So a stale boost can never persist or accumulate across slots —
  the property that turns proposer boost from a reorg *enabler* into a reorg *resister*. It's set only for the
  current-slot, timely, first block. Prysm mirrors this exactly (`proposer_boost.go`, reset in `NewSlot`).
- **FFG filter is justified-checkpoint-rooted with the exact spec grace.** `node_is_viable_for_head` requires
  `correct_justified` (the pulled-up **unrealized** justified checkpoint, with `voting_source.epoch + 2 >=
  current_epoch` — the *exact* spec grace, not loosened) and `correct_finalized` (descendant of the finalized
  checkpoint); head-finding starts at the justified node and re-verifies viability. A weakened grace would
  open a bouncing/reorg attack; both clients use the spec value.
- **Equivocators removed exactly once.** `compute_deltas` applies one negative delta then **sets the
  equivocator's `current_root` to zero and `continue`s** (`proto_array_fork_choice.rs:1016-1021`, verified) —
  removed a single time, never re-added; normal votes net old/new balance once; `node.weight` back-propagates
  once. No double-count.
- **Deterministic tie-break.** Equal weight → **highest block root** (`child.root >= best_child.root`,
  `proto_array.rs:843`, verified; Prysm `bytes.Compare(child.root, bestChild.root) > 0`). So all honest nodes
  pick the *same* head from the same messages — no balancing-attack foothold, the head is a deterministic pure
  function of (votes + boost + root tie-break).

**Verdict:** spec-exact on all four foci; **REORG bounded to the 40% boost** (can't accumulate), **SPLIT not
reachable** (deterministic head), **SAFETY/LIVENESS** governed by the unweakened FFG filter. **No finding.**
The residual is the protocol's own designed reorg-resistance (a timely proposer-boost can still re-org a *late*
block — by design, not a bug) and the >2/3 honesty assumption the FFG filter encodes.

## C4. Solana Tower BFT + Sui Mysticeti (DAG-BFT) — equivocation prevented at construction; the "impossible" *halts*, not forks
**Target:** `anza-xyz/agave` (`core/src/consensus.rs`, `runtime/src/commitment.rs`), `MystenLabs/sui`
(`consensus/config/src/committee.rs`, `consensus/core/src/`). Two non-Ethereum families, same audit question:
does a single/minority validator get more leverage than their stake? **Both enforce the supermajority strictly;
neither lets a sub-threshold validator break safety, reorg, or escape equivocation. No finding.**

- **Solana Tower BFT — equivocation prevented at *vote construction*.** Vote threshold is strict `> 2/3`
  (`VOTE_THRESHOLD_SIZE = 2/3`, the depth-8 ancestor must exceed it before a vote is allowed); switching forks
  requires a **switch proof** that `locked_out_stake/total_stake > SWITCH_FORK_THRESHOLD (0.38)`, else
  `FailedSwitchThreshold` (verified the decision logic). `is_locked_out` simulates the new vote, pops expired
  lockouts, and **rejects any vote on a slot that isn't an ancestor of a still-locked tower vote** — so a
  minority validator *cannot vote two live forks* (the second is rejected unless lockouts expired or it carries
  a valid >0.38 switch proof). Lockout doubling is exact 2^n geometric; `last_voted_slot` monotonicity blocks
  re-voting. Equivocation is **prevented, not merely detected.**
- **Sui Mysticeti — 2f+1 intersection, and a safety break becomes a *halt* (verified myself).**
  `fault_tolerance = (total_stake-1)/3`, `quorum_threshold = total_stake - fault_tolerance` (= 2f+1), and the
  committee constructor **asserts quorum intersection**: `2*quorum_threshold - fault_tolerance > total_stake`
  (`committee.rs:56`) — any two quorums share `>f` validators, i.e. `>0` honest. Every step is gated at 2f+1
  (certificate, commit, skip, round-advance), each authority counted once via a `BTreeSet`. The beautiful part:
  a Byzantine leader producing two blocks at one slot is **explicitly anticipated** — at most one can gather a
  2f+1 certificate under the intersection invariant, and the decider **`panic!`s if it ever sees >1 certified**
  (`try_direct_decide`, `decide_leader_from_anchor`). **That converts a would-be silent fork (a 2f+1
  intersection break) into a node halt** — the *fail-safe-substrate law at the consensus layer*: when the
  impossible happens, stop, don't diverge.

**Verdict:** both strict and exact. **SAFETY** — Solana's lockout + 0.38 switch + Sui's 2f+1 intersection make
sub-threshold conflicting commits impossible; **REORG** — a minority leader's equivocating block simply fails
to be certified / fails the switch proof; **SLASHING/equivocation** — Solana prevents it at construction, Sui
makes it non-certifiable and detectable. **No finding.**

---

## Synthesis — the agreement layer enforces *exactly* its assumption, and fails safe when the impossible happens
Across **four consensus families** (Ethereum LMD-GHOST + Casper FFG, Tendermint BFT, Solana Tower BFT, Sui
DAG-BFT) **plus the EL↔CL engine-API seam**, the result is the corpus's thesis at the agreement layer, and it
is uniform:

1. **The safety assumption is enforced *exactly* — never weaker.** `>2/3` is *strict* (CometBFT `*2/3+1`,
   Solana `> 2/3`, Sui `2f+1` with an asserted intersection); the FFG grace is the *spec* value, not loosened;
   proposer boost is the *spec* size and **cannot compound**; equivocators are removed/counted *exactly once*.
   No bug in any of the read paths lowers the designed Byzantine bar (1/3 stake).
2. **One actor can't exceed their stake.** No single proposer reorgs beyond the 40% boost (ETH); no minority
   votes two live forks (Solana lockout) or wedges the round machine (CometBFT >2/3-gated advancement); no
   equivocating leader gets two certificates (Sui intersection). The reorg/split lever is always ≤ the stake
   the protocol designs for.
3. **Determinism forbids honest splits.** Head selection is a **deterministic pure function** — ETH's
   highest-root tie-break, CometBFT's latched first-seen 2/3, Sui's single-certification — so the same messages
   yield the same chain on every honest node. (The MemeCore lesson, inverted: well-engineered consensus is
   *deterministic by construction*, which is exactly what MemeCore's unsorted-map reward path was not.)
4. **When the impossible happens, it *halts* — it doesn't diverge.** Sui's `panic!`-on-double-certification is
   the sharpest example: a 2f+1 intersection break (which requires >1/3 Byzantine) is turned into a **liveness
   halt, not a silent fork** — the *fail-safe-substrate law* (`../methodology/AUDIT-CAPSTONE.md §5b`) at the
   consensus layer. The engine API (C1) does the same at the EL↔CL seam: an unresolvable disagreement yields
   `SYNCING`/`INVALID` and a *bounded, self-healing* invalid cache, never a guess.

**This is the proven-vs-attested / recompute-vs-trust axis pointed at agreement:** an honest node never *trusts*
another participant's claim about the canonical chain — it **recomputes** the fork choice from the messages
against the protocol's exact rules, and where it cannot resolve, it **stops rather than guesses.** **Five
agreement mechanisms, zero exploitable findings, the Byzantine bar enforced exactly, and the failure mode of
last resort is a halt, not a fork.** The snake refuses to swallow a tail it didn't verify is its own.

---

## Sweep status
| # | Target | Layer | (Q) enforces exactly the assumption? | Worst reachable failure mode |
|---|---|---|---|---|
| C1 | go-ethereum engine API | EL↔CL seam | **yes** — separation of authority; bounded + self-healing invalid cache; correct LVH | EL↔CL split / optimistic poisoning **forced safe** |
| C2 | CometBFT | Tendermint BFT | **yes** — strict `>2/3` (`*2/3+1`), correct PoLC unlock, complete double-sign detection | sub-1/3 can't break safety/liveness/slashing |
| C3 | Lighthouse · Prysm | ETH LMD-GHOST + FFG | **yes** — spec-exact boost (no compounding), unweakened FFG filter, single-removal equivocation, deterministic tie-break | REORG ≤ 40% boost; SPLIT not reachable |
| C4 | Agave · Sui Mysticeti | Tower BFT · DAG-BFT | **yes** — Solana lockout+0.38 switch (equivocation prevented at construction); Sui 2f+1 intersection asserted | safety break → **halt** (Sui panic), not fork |

**Result:** 4 consensus families + the EL↔CL seam — **every one enforces its Byzantine assumption *exactly*
(never weaker), head selection is deterministic (no honest split), and the failure mode of last resort is a
*halt*, not a fork.** Zero exploitable findings.
