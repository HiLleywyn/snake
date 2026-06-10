# C3 (deep) — Lighthouse fork choice: attestation processing, the unrealized-justification pull-up, weight propagation, and prune

**Scope.** A deep, individualized expansion of sweep item **C3** (`AUDIT-CONSENSUS-SWEEP.md` §C3), going past
the proposer-boost-can't-compound + FFG-grace the rapid pass covered into the **full LMD-GHOST + Casper FFG
machinery**: `on_attestation` validity gates + the latest-message rule, `on_block` checkpoint update, the
**unrealized-justification pull-up** at epoch boundaries, `compute_deltas` + `apply_score_changes` (bottom-up
weight propagation + the boost swap), `find_head` + the viability filter, and `maybe_prune`. Target:
`sigp/lighthouse` @ `176cce5` (v8.1.3), `consensus/fork_choice/src/fork_choice.rs` +
`consensus/proto_array/src/{proto_array, proto_array_fork_choice}.rs`. Read-only, public-source,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** five design details are
characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established the four foci (boost can't compound, FFG grace is spec-exact, equivocators removed once,
deterministic tie-break). The deeper reading shows the *engine those properties live in*: the **latest-message
rule** is strict (`>`, so the first vote in an epoch wins and same-epoch flips are dropped before they reach
weights); the **unrealized-justification pull-up** is the mechanism that makes a block viable for head based on
what it *will* justify, not what it had justified when produced; weight is a **single bottom-up sweep** whose
correctness depends on a `parent-index < child-index` invariant that **prune must preserve**; `find_head` is
**O(1)-ish** (reads a precomputed `best_descendant`, not a live walk); and the boost swap is a
**subtract-previous-then-add-current** recomputed from live balances every call.

---

## 1. on_attestation — validity gates + the latest-message rule. **Newer vote wins, first-in-epoch sticks.**

`validate_on_attestation (fork_choice.rs:979-1056)` is a gate stack: target must be current/previous epoch;
**both the target block and the head block must be known** (unknown → *dropped, not queued* — "reduce DoS
attack surface", `:1008`); `block.slot > attestation.slot → AttestsToFutureBlock`; and time-of-flight is
checked **only** when `is_from_block == false` (block-replayed attestations skip the wall-clock gate, `:995-997`).
`on_attestation (:1075-1124)` splits on timing: votes for the current/future slot are **queued** for later
replay; past-slot votes update the tracker. The latest-message update is strict (`process_attestation`,
`proto_array_fork_choice.rs:487-501`):
```rust
if target_epoch > vote.next_epoch || *vote == VoteTracker::default() {   // :495 strict > 
    vote.next_root = block_root; vote.next_epoch = target_epoch;
}
```
**Characterization:** LMD's "latest message" — a vote is recorded only if its `target_epoch` **strictly
exceeds** the stored one, so an older or *same-epoch* vote cannot override a newer; same-epoch re-votes are
**dropped here, before the weight machinery**. The queued path defers future-slot attestations until their slot
is in the past, so an attestation can't influence fork choice early.

---

## 2. on_block — monotonic FFG checkpoint update. **Post-Capella simplified; only advances.**

`on_block (:660-918)` gates: known→no-op, future-slot→reject, `slot <= finalized_slot`→reject, and the
**finalized-descendant check** (`get_ancestor(parent, finalized_slot) == finalized_root` else
`NotFinalizedDescendant`, `:721-728`). `update_checkpoints (:921-941)` is **strict epoch-monotonic** — justified
and finalized **only ever advance, on a strictly-higher epoch**:
```rust
if justified_checkpoint.epoch > store.justified_checkpoint().epoch { set_justified_checkpoint(...) }   // :928
if finalized_checkpoint.epoch > store.finalized_checkpoint().epoch { set_finalized_checkpoint(...) }   // :936
```
**Characterization (a notable deepening):** this is the **post-Capella simplified rule** — the legacy
`should_update_justified_checkpoint` "safe-slots-into-epoch" guard is **gone from the code**; the *only*
condition is strict epoch monotonicity. Justified/finalized never regress. The realized checkpoints are applied
here; the unrealized ones drive the pull-up (§3).

---

## 3. The unrealized-justification pull-up — the deep mechanism. **Viable for what it *will* justify.**

`on_block (:752-823)` computes what the block *will* justify/finalize: if the parent's unrealized checkpoints
already reach `block_epoch` it inherits them (an optimization, `:765-770`); else it runs
`process_justification_and_finalization` on the post-state, storing the result as best-known if strictly higher.
**The pull-up at the epoch boundary (`:825-838`):** if the block is from a *past* epoch, `pull_up_store_checkpoints`
immediately promotes unrealized → realized. The payoff is in head selection (`node_is_viable_for_head,
proto_array.rs:933-947`):
```rust
let voting_source = if current_epoch > node_epoch {
    node.unrealized_justified_checkpoint.unwrap_or(node_justified_checkpoint)   // :938 pulled-up source
} else { node_justified_checkpoint };
let correct_justified = ... || voting_source.epoch + 2 >= current_epoch;        // :947 the FFG grace
```
**Characterization:** a block from a prior epoch is judged on its **unrealized (will-justify) checkpoint**, so
it becomes viable for head based on what it will justify, not what it had justified when produced — the
mechanism that closes the pre-pull-up reorg/bouncing window. The `unwrap_or(realized)` fallback is safe; the
`+2 >= current_epoch` clause is the unweakened spec grace (sweep). Honest note: the parent-inheritance
optimization **trusts** the parent's stored unrealized checkpoints rather than recomputing, predicated on three
monotonicity invariants stated only in comments.

---

## 4. compute_deltas + apply_score_changes — bottom-up weight, boost swap, equivocator zeroed once.

`compute_deltas (proto_array_fork_choice.rs:1003-1094)`: per validator, **subtract old vote from `current_root`,
add new vote to `next_root`**, advance `current_root = next_root` (`:1062-1090`); a newly-slashed validator's
balance is subtracted once then **`current_root` permanently zeroed** so it never contributes again (`:1026-1049`);
off-tree/unknown roots silently ignored (`:1063-1064`). `apply_score_changes (proto_array.rs:154-298)` iterates
nodes in **reverse index order** (children before parents) so weights aggregate bottom-up, with the boost swap:
```rust
if previous_proposer_boost.root == node.root ... node_delta -= previous_proposer_boost.score   // :204-211 remove last slot's boost
if proposer_boost_root == node.root ... proposer_score = calculate_committee_fraction(new_justified_balances, ...); node_delta += proposer_score  // :218-227 add this slot's, recomputed from live balances
*parent_delta += node_delta;   // :257-265 back-propagate (reverse order => parent sees all descendants)
```
**Characterization:** boost is **non-compounding and self-cancelling** (last slot's subtracted before this
slot's added, boosted node identified by root each call, magnitude **recomputed from live justified balances**),
equivocators are removed exactly once and permanently, and weight is a **single bottom-up sweep** whose
correctness rests on `parent-index < child-index`.

---

## 5. find_head + viability — O(1)-ish read of a precomputed best-descendant. **GHOST amortized.**

`find_head (:635-692)` does **not** walk the tree — it reads the justified node's precomputed `best_descendant`
and runs **one viability sanity-check** (`:666-689`); an invalid-execution justified node aborts entirely
(consensus failure). The heaviest-child comparison is maintained incrementally
(`maybe_update_best_child_and_descendant :776-874`): viability **dominates weight**, equal weight → root
tie-break `child.root >= best_child.root` (`:843`), else heavier wins. The viability gate
(`node_is_viable_for_head :917-954`): not invalid-payload, **correct_justified** (grace-windowed) AND
**correct_finalized** (`is_finalized_checkpoint_or_descendant`).
**Characterization:** GHOST descent is amortized into incremental `best_child`/`best_descendant` updates during
`apply_score_changes`/`on_block`, so head-finding is a lookup + a viability check. **Viability dominates weight**
— a heavier subtree that isn't a finalized descendant, or whose justification is >2 epochs stale, is excluded
from the head even if it wins by weight. Honest note: the equal-weight root tie-break is deterministic but
root-value-dependent.

---

## 6. maybe_prune — prune-to-finalized + index remap that preserves the weight invariant.

`maybe_prune (proto_array.rs:707-762)`: gated by `prune_threshold` (trade memory for fewer remaps), it removes
everything below the finalized node and **re-bases the array** — `nodes = split_off(finalized_index)` (finalized
becomes index 0), then **every `indices` entry, `parent`, `best_child`, `best_descendant` is shifted down by
`finalized_index`** (`:732-757`), the pruned parent of the finalized root becoming `None` via `checked_sub`.
**Characterization:** the tree is anchored at finalization (can't grow unbounded), and crucially the remap
**preserves the `parent-index < child-index` invariant** that §4's reverse-iteration back-propagation depends on
— the prune and the weight sweep are coupled correctness, a coupling a rapid pass wouldn't surface.

---

## 7. Verdict & residual

Lighthouse fork choice is spec-exact across the *whole* machinery: strict latest-message, monotonic FFG
checkpoints, the unrealized-justification pull-up, non-compounding boost recomputed from live balances,
equivocators zeroed once, viability-dominates-weight head selection read from a precomputed best-descendant, and
a finalized-anchored prune that preserves the weight invariant. **No finding.** **Residuals / honest details**,
named: (a) **from-block attestations skip the wall-clock gate** (rely on prior block validation, documented
intentional); (b) **latest-message is strict `>`** so same-epoch re-votes are dropped (first-in-epoch wins);
(c) the **inherited-unrealized-checkpoints optimization trusts the parent** rather than recomputing (predicated
on comment-stated invariants); (d) **off-tree/unknown-root votes are silently ignored** (by design for
pre-finalization, but votes referencing pruned roots vanish without error); (e) the **equal-weight root
tie-break** is deterministic but root-value-dependent. All are design choices, not defects — and each is the
precise spot where the head is a deterministic pure function of (votes + boost + viability + root tie-break),
the property that forbids honest splits.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CONSENSUS-SWEEP.md` §C3.*
