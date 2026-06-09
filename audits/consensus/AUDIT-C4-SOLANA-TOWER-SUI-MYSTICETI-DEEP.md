# C4 (deep) — Solana Tower BFT & Sui Mysticeti: the lockout simulation, switch/threshold math, the DAG commit rule, and halt-on-invariant

**Scope.** A deep, individualized expansion of sweep item **C4** (`AUDIT-CONSENSUS-SWEEP.md` §C4), going past
the lockout/0.38-switch headline + the Sui 2f+1 panic into the **full mechanics** of two non-EVM consensus
families: Solana's `is_locked_out` simulation, the depth-8 2/3 threshold + 0.38 switch-proof accumulation, the
heaviest-subtree fork choice + the 0.52/0.38/0.10 partition; and Sui's direct/indirect commit rule, the
linearizer's committed-set dedup, the reputation leader schedule, and the 2f+1-ancestor block verification.
Targets: `anza-xyz/agave` @ `bfe243d` (`core/src/consensus*`), `MystenLabs/sui` @ `d36a3637`
(`consensus/core/src/`). Read-only, public-source, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No finding;** the pervasive halt-on-invariant posture and two determinism-adjacent
details are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established the headlines (Solana lockout+0.38-switch prevents two-fork voting; Sui 2f+1 intersection
→ a safety break *halts*). The deeper reading supplies the **simulation and the math**: `is_locked_out` is a
*clone-push-pop* of the 31-deep lockout stack requiring every still-locked vote to be an *ancestor* of the
candidate; the switch proof is a **filtered, deduped, gossip-overlaid stake accumulation** past 0.38; the
heaviest fork is a stake-weighted subtree with a deterministic **low-slot tiebreak** and a **tight 0.52/0.38/0.10
threshold partition summing to 1**; Sui's commit rule is a **symmetric 2f+1-certs/2f+1-blames** direct decide
with an **anchor-certificate indirect** resolver; and — the deepest finding — **both systems are pervasively
halt-on-invariant** (panic when a BFT-assumption breach is reached), the fail-safe-substrate law at the
agreement layer, read at the line level.

---

## 1. Solana — `is_locked_out` is a full simulation. **Two live forks can't both be voted.**

`is_locked_out (consensus.rs:827-856)` **clones** the vote state, **pushes** the candidate via
`process_next_vote_slot` (which pops expired lockouts), and then **requires every still-locked tower vote to be
an ancestor of the candidate**:
```rust
let mut vote_state = self.vote_state.clone();
vote_state.process_next_vote_slot(slot);
for vote in &vote_state.votes {
    if slot != vote.slot() && !ancestors.contains(&vote.slot()) { return true; }   // :848 still-locked vote on a different fork -> locked out
}
```
The lockout windows are exponential: `lockout() = 2^confirmation_count`, `MAX_LOCKOUT_HISTORY = 31`
(`solana-vote-interface`). Local-tower **regression is a hard `panic!`** (`record_bank_vote_and_update_lockouts
:706-714`, `VoteError::VoteTooOld`), and `last_voted_slot` monotonicity blocks re-voting.

**Characterization:** the lockout simulation is the **slashing-safety core** — equivocation is *prevented at
vote construction*, not merely detected: a candidate on a fork that isn't an ancestor of any still-locked vote
is rejected, so a validator **cannot vote two live forks** unless their lockouts expired or it carries a valid
>0.38 switch proof. Regression is a process abort, not a soft reject.

---

## 2. Solana — the depth-8 2/3 threshold + the 0.38 switch-proof accumulation. **Two independent stake gates.**

`check_vote_stake_threshold (:1331-1367)`: `lockout = fork_stake/total_stake` passes if an optimistic bypass
applies (the vote is already in tower at the same slot+conf, `:1316-1328`) **or** `lockout > 2/3`
(`VOTE_THRESHOLD_DEPTH = 8`, enforced; depths 4/5 log-only). The **switch proof** (`:1182-1268`) iterates
`lockout_intervals` whose `end >= last_voted_slot`, **dedups by vote account**, requires each interval start to
be a **non-ancestor of the last vote and > root**, accumulates stake, and returns `SwitchProof` once
`locked_out_stake/total_stake > 0.38` — with a **second pass folding in gossip votes**. Several
invariant-violation paths are `panic!`/`assert!` ("Should never consider switching to ancestor of last vote",
`:1104`).

**Characterization:** two independent stake gates — the **2/3 depth-8 ancestor-stake threshold** to vote
in-fork, and the **0.38 locked-out-stake switch proof** to abandon a fork — each with non-trivial filtering
(ancestry, root, dedup, gossip overlay), consistent with the halt-on-inconsistency posture.

---

## 3. Solana — heaviest fork + the tight 0.52/0.38/0.10 partition. **Deterministic, documented safety margin.**

`select_vote_and_reset_forks (fork_choice.rs:410-491)` resets-only on a failed switch and otherwise takes the
heaviest candidate; `can_vote_on_candidate_bank` gates voting on `!is_locked_out && threshold_passed &&
propagation_confirmed && switch_decision.can_vote()`. The heaviest engine (`heaviest_subtree_fork_choice.rs
:856-948`) is `stake_voted_subtree = stake_voted_at + Σ children`, best child by greater subtree stake,
**tie-broken by lower slot key** (`:904`); duplicate-unconfirmed children **keep their weight but can't be the
best_slot**. The thresholds partition tightly: `DUPLICATE_THRESHOLD = 1 − 0.38 − 0.10 = 0.52`, and
**`0.52 + 0.38 + 0.10 = 1` is asserted** (`slot_supporters.rs:27`), with the code documenting that **below this
partition liveness is not guaranteed** (`fork_choice.rs:243-246`).

**Characterization:** heaviest selection is pure stake-weighted-subtree with a deterministic low-slot tiebreak
(so honest nodes pick the same fork); duplicate-unconfirmed slots are demoted from "candidate" without starving
the parent fork; and the 0.52/0.38/0.10 split is the **documented, asserted safety margin** — the protocol
states its own liveness boundary.

---

## 4. Sui — the direct/indirect commit rule. **Symmetric 2f+1; halt on >1 certified.**

`universal_committer.try_decide (:42-111)` elects a leader per round and commits the **longest prefix of decided
leaders**. `base_committer.try_direct_decide (:86-117)`: **2f+1 blames → Skip** (`enough_leader_blame`: a voting
block blames if *none* of its ancestors are by the leader, `:337-366`), else **2f+1 certificates → Commit**
(`enough_leader_support` over certificates, where a *certificate* is a block whose ancestors contain 2f+1 votes
for the leader, `is_certificate :231-279`) — and a **hard `panic!` if >1 leader has enough support** ("BFT
assumption is broken", `:108-111`). `try_indirect_decide (:122-145)` resolves an undecided leader off a later
committed **anchor**: `decide_leader_from_anchor (:284-334)` commits iff a certificate for the target is an
*ancestor* of the anchor, else Skip — again **`panic!` if >1 certified** (`:322-326`).

**Characterization:** the direct rule is **symmetric** (2f+1 certs ⇒ commit, 2f+1 blames ⇒ skip, else
undecided), the indirect rule deterministically resolves undecided leaders by certificate-ancestry off a
committed anchor, and **multiple-certified / multiple-supported leaders are explicit panics** — a would-be
silent fork (which requires a 2f+1 intersection break, i.e. >1/3 Byzantine) becomes a **node halt**, the
sharpest example of the fail-safe-substrate law at the consensus layer.

---

## 5. Sui — the linearizer dedup + the reputation leader schedule. **Each block committed once.**

`linearizer.linearize_sub_dag (:156-218)`: a DFS from the leader pushing ancestors filtered by `round > gc_round
&& !is_committed`, with **dedup enforced by `set_committed` returning false → `assert!` "attempted to be
committed twice"** (`:171-175,198-202`), a post-check that nothing `<= gc_round` is committed, and a monotonic
stake-weighted-median commit timestamp. The leader schedule (`leader_schedule.rs:132-173`) is a **round-seeded
stake-weighted shuffle** (`StdRng::from_seed(round)`), with a **reputation swap table** (`:229-363`) demoting the
worst ≤33%-stake performers and swapping in a (seed=round) randomly chosen good node — deterministic and
reproducible from round + reputation scores.

**Characterization:** linearization is a **committed-set-deduped causal DFS** — each block enters exactly one
sub-dag (guaranteed by the `set_committed` asserts), GC-bounded in depth — and leader identity is a
**deterministic pure function of round + reputation**, so all honest nodes derive the same order and the same
leaders.

---

## 6. Sui — block verification + the equivocation-tolerance nuance. **2f+1 ancestors; equivocation handled in the commit rule.**

`block_verifier.rs:90-147` hard-requires: ancestors ≤ committee size and non-empty; ancestor[0] self-authored,
others not; **every ancestor round `< block.round`**; **per-authority dedup** (`seen_ancestors`,
`DuplicatedAncestorsAuthority`); and — the quorum rule — parent stakes from `round == block.round-1` must
**`reached_quorum` (2f+1)** (`:142-147`). The threshold clock advances rounds on the same 2f+1 stake quorum.
**The nuance:** `dag_state.accept_block (:292-351)` only asserts-against equivocation for the **node's own**
index (`:323-337`); **others' equivocating blocks are accepted into the DAG** and tracked separately — safety
rests **entirely on the commit-rule quorum math + the ≤1-certified-leader panic**, not on input rejection.

**Characterization:** block validity requires **2f+1 distinct previous-round ancestors** with strict
position/uniqueness rules, but Sui **does not reject others' equivocating blocks at acceptance** — it tolerates
them in the DAG and lets the commit rule's intersection invariant (panic on >1 certified) be the safety
backstop. This is a deliberate design choice (the DAG is permissive; the *commit* is strict), and the place to
understand *why* the Sui panic guard is load-bearing rather than redundant.

---

## 7. Verdict & residual

both families enforce their supermajority *exactly* across the full mechanism: Solana's clone-simulate lockout +
two independent stake gates (2/3 in-fork, 0.38 switch) + deterministic heaviest-subtree + the asserted
0.52/0.38/0.10 partition; Sui's symmetric 2f+1 direct/indirect commit + committed-set-deduped linearization +
2f+1-ancestor blocks + reputation-deterministic leaders. **No finding.** **Residuals / honest details**, named:
(a) **halt-on-invariant is pervasive** in both (Solana vote-regression/switch-ancestor/root asserts; Sui
>1-certified / double-commit / self-equivocation panics) — these encode genuine BFT-assumption breaches and turn
the impossible into a *halt, not a fork*, but are worth naming as a denial-of-availability surface if ever
legitimately reachable; (b) **Sui accepts others' equivocating blocks** (self-only acceptance check) — safety is
the commit-rule quorum + the ≤1-certified panic, not input rejection; (c) **Solana uses f64 thresholds**
(`0.38`, `lockout as f64 / total as f64`) — a determinism-adjacent detail vs Sui's integer `Stake` comparisons
(not a finding; stake comparisons cross the float boundary identically on every node); (d) Solana's **optimistic
threshold bypass** is a deliberate liveness optimization (worst case is a deferred re-check). The code neither
weakens nor strengthens the Byzantine bar; the residual is the design assumption and the documented liveness
partition.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CONSENSUS-SWEEP.md` §C4.*
