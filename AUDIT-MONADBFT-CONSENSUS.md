# MonadBFT (consensus safety) — Six-Bucket Trust Audit

**Target:** `category-labs/monad-bft` (the consensus client, separate from the execution client
audited in `AUDIT-MONAD-PARALLEL.md`), cloned `/tmp/mbft`. Focus: the **voting safety module**
(`monad-consensus/src/validation/safety.rs`) — the rules that prevent two conflicting blocks from
both being certified (a fork).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe." Nothing routed
privately — none found. First **BFT-consensus-safety** target in the corpus (prior chains were about
*validity*/*execution* conservation; this is about *agreement*).

**The conservation analogue here:** consensus "conservation" is **safety** — no two conflicting tips
get finalized in a way that forks the chain. MonadBFT is a HotStuff/Jolteon-family pipelined BFT with
a **no-endorsement (NE/NEC)** extension for *tail-fork resistance*. The safety module is the stateful
per-validator discipline that makes that hold.

---

## Bucket: safety (no conflicting finalization) — the voting rules, enforced

`Safety` tracks per-validator monotonic state: `highest_vote`, `highest_no_endorse`,
`highest_propose`, `high_certificate_qc_round`, `maybe_high_tip`. Three invariants stand out:

### 1. One vote per round, strictly monotonic (anti-equivocation)
`is_safe_to_vote` requires `round > self.highest_vote` (`:141`); `vote` sets
`self.highest_vote = round` (`:151`). So a validator **votes at most once per round and never in a
past round.** Combined with QC = 2f+1 votes and quorum intersection, this is the classic guarantee
that **two conflicting QCs cannot form in the same round** (any two quorums share an honest validator,
who voted only once). **enforced.**

### 2. NE/NEC vs QC same-round conflict prevention (MonadBFT tail-fork resistance)
The novel part. `is_safe_to_vote` adds (`:132-140`): if `round == highest_no_endorse.round` and the
proposal's `last_round_tc_tip` is **not** the tip I no-endorsed, **refuse to vote** — *"once a TC is
NE'd, we must only vote on proposals including that TC; otherwise a QC and NEC can be formed in the
same round between conflicting tips."* And `timeout` (`:173-185`) only lets a validator include its
`Vote(r)` in `Timeout(r)` if it hasn't NE'd round r, **or** its `high_tip.round == r` — *"to ensure
that NEC(r) and QC(r) don't form for conflicting tips in the same round."* `is_safe_to_no_endorse`
requires `round > max(highest_no_endorse.round, highest_vote)` (`:164`), so a validator cannot both
vote-for-A and no-endorse-B in the same round. Together these are the formalized invariant that
**`QC(r)` and `NEC(r)` are mutually exclusive for conflicting tips** — the heart of the no-tail-fork
property. **enforced (the published safety argument, in code).**

### 3. Safety checks are enforced, not swallowed (correct failure philosophy)
`vote`/`no_endorse`/`propose`/`recovery_request` each begin with `assert!(self.is_safe_to_…())`
(`:150`,`:168`,`:192`,`:201`). A safety-rule violation **halts the validator** rather than emitting an
unsafe vote. This is the same halt-over-divergence discipline verified in `AUDIT-SUI-SIX-BUCKET.md`
Pass 6 and `AUDIT-MONAD-PARALLEL.md` — and it is exactly the discipline **MemeCore's swallowed
system-call error lacked**. For a consensus client, "crash rather than sign something that could fork
the chain" is the correct choice. **enforced.**

### State hygiene
`process_certificate` (`:118`) advances `high_certificate_qc_round` monotonically and clears a stale
`maybe_high_tip` once a QC supersedes it (`:122-128`), keeping `timeout.high_tip_round >
timeout.high_qc_round` (the invariant the timeout/NE logic relies on). Monotonic round state
throughout; no map-iteration into safety decisions (the MemeCore determinism class is N/A here — these
are scalar round comparisons). **enforced.**

---

## What this audit did NOT cover (coverage honesty)

### Pass 2 — cross-round lock safety (OPENED): coherency gate + QC-of-QC commit

The other half of safety — that a *committed* block can't be reverted by a later conflicting one — is
enforced not in `safety.rs` but in the vote-gating sequence (`monad-consensus-state/src/lib.rs`) plus
`monad-blocktree`. Opened, and it is sound HotStuff-family safety:
- **Coherency gate (the lock rule).** Before `is_safe_to_vote`, the proposal must pass
  `pending_block_tree.is_coherent(block_id)` (`consensus-state:1676`). A blocktree entry "is coherent
  if there is a path to root from the entry" (`blocktree/tree.rs:239`) — it chains back through
  ancestors to the **committed root**. So a validator **won't vote for a block on a branch that forks
  off a pre-committed block** — the structural equivalent of HotStuff's locked-QC rule.
- **Commit rule.** `blocktree.rs:142`: *"the commit rule stating a QC-of-QC commits the block"* — the
  **two-chain** (Jolteon / HotStuff-2) rule: a block commits when a QC certifies a QC on it.
- **Root = committed = immutable.** The tree roots at the last committed block (`:55`,`:117`); `prune`
  (`:132-145`) advances the root to the newly-committed block and drops non-descendants — **finalized
  blocks leave the mutable tree** and cannot be reorged.

**Together = full BFT safety:** *within* a round, one-vote-per-round + quorum intersection ⇒ no two
conflicting QCs; *across* rounds, two-chain commit + coherency ⇒ a committed block can't be reverted
(honest validators won't vote a conflicting non-coherent branch, so no competing QC forms after
commit). NE/NEC adds tail-fork resistance on top. **enforced.**

### Pass 3 — the quorum foundation (OPENED): >2/3 distinct stake, dup-guarded, invalid-sigs removed

The foundation invariant #1 leans on — *a QC genuinely represents a supermajority of distinct
validators* — opened (`vote_state.rs`, `monad-validator/src/validator_set.rs`):
- **Votes aggregated by author** — `round_pending_votes.insert(author, sig)` (`vote_state.rs:130`):
  a map keyed by author, so a validator's vote is stored once (re-votes overwrite). First-supermajority
  forms the QC; one QC per round (`:36`).
- **Supermajority = stake-weighted, strictly > 2/3** — `has_super_majority_votes` thresholds at
  `total_stake * 2 / 3 + 1` (`validator_set.rs:262`); the threshold is by **stake** (PoS), `voter_stake
  >= threshold` (`:280`). Correct BFT bound (tolerates < 1/3 Byzantine stake).
- **Duplicate guard** — `calculate_current_stake` returns `Err(DuplicateValidator)` if any voter
  appears twice (`:287-288`): explicit anti-double-count, belt-and-suspenders with the map aggregation.
- **Invalid signatures removed before the count** — invalid voters are dropped and stake recomputed;
  the QC forms only if the *remaining valid distinct stake* is supermajority (`vote_state.rs:204`,
  tests `:490-509`). A forged vote can't inflate a QC.

So **QC = > 2/3 distinct, valid, stake-weighted votes.** By quorum intersection, two such sets overlap
in > 1/3 stake ⇒ contain an honest validator (since < 1/3 Byzantine) ⇒ who voted once per round
(`safety.rs`) ⇒ **no two conflicting QCs in a round.** The full safety chain is now traced through
actual code: vote aggregation → quorum threshold → per-round discipline → cross-round lock/commit.
**enforced.**

### Remaining (read only at interface)
- **BLS/certificate crypto** (`monad-crypto/certificate_signature.rs`) — that an aggregate signature
  genuinely proves the claimed validators signed (the soundness under the quorum count).
- **Pacemaker / view-change** (`pacemaker.rs`) — *liveness* (progress under partial synchrony);
  orthogonal to the safety rules above.
- **Leader election** (`leader_election.rs`), **equivocation detection/slashing**, and the **crypto**
  (`monad-crypto/certificate_signature.rs` — BLS aggregation soundness).
- The execution client (separate; `AUDIT-MONAD-PARALLEL.md`).

## Nothing routed privately

No defect found. MonadBFT's safety module correctly enforces the per-round voting discipline:
strictly-monotonic one-vote-per-round (anti-equivocation; with quorum intersection ⇒ no conflicting
same-round QCs), the NE/NEC-vs-QC mutual-exclusion that gives tail-fork resistance (the invariant
written verbatim in the code), and **safety checks backed by `assert!` so a validator halts rather
than signs an unsafe message** — the right failure philosophy and the exact discipline MemeCore
lacked. The decisive remaining safety surface is the **cross-round "extends-high-QC" rule in proposal
validation** (where HotStuff-family lock safety lives), which is the natural next read. A new corpus
data point: **consensus safety as a substrate — "conservation" = no conflicting finalization,
enforced by monotonic voting rules + quorum intersection + halt-on-violation.** Companion to
`AUDIT-MONAD-PARALLEL.md` (the execution half) and `AUDIT-MEMECORE-POSA.md` (the failure mode this
design's enforced-assert discipline avoids).
