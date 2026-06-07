# Large-cap bug-hunt — hunting the *delta*, not the base

The one real finding in this corpus (MemeCore) was in the **custom consensus delta a geth-fork added on
top of audited geth**, not in inherited code. So the highest-EV large-cap hunt is: take large-cap chains
that are **forks-with-custom-consensus** (or that ship **recent** consensus/feature code), and hunt the
*delta* for the failure classes that actually bite — the **MemeCore set**:
- **(B) swallowed errors** in consensus-critical paths (a reverting system call silently produces a
  "valid" block);
- **(C) non-deterministic iteration** (Go map ranged without sort) feeding a state-changing /
  consensus-critical call → divergent state roots;
- missing checks / unverified system-call replay in new code.

Cores (EVM, Move VM, …) are the most-audited code on earth — skipped. **Anything live + exploitable is
stopped-and-notified privately; only redacted placeholders appear here.** Defensive, no PoC.

---

## L1. BSC (BNB) — parlia consensus delta + fast-finality (clean; canonically-correct counterpart to MemeCore)
**Target:** `bnb-chain/bsc` HEAD `3cf9043`, `consensus/parlia/parlia.go`. BSC is the **largest
parlia-derived geth fork** — i.e. the real, top-5-cap sibling of MemeCore's lineage. I hunted the exact
MemeCore failure classes, focusing on the **newer fast-finality code** (`distributeFinalityReward`,
BEP-126/319), which is the least-audited consensus surface.

**Result: clean — and it is the canonically-correct version of the MemeCore bug.** Same code pattern
(map → validator list → consensus-critical system call), opposite handling:
- **Class C (non-determinism) — FIXED here.** `distributeFinalityReward` builds the validator list from a
  Go **map** (`for val := range accumulatedWeights`, non-deterministic — *exactly* like MemeCore), but
  then **`sort.Sort(validatorsAscending(validators))`** before packing the system call, and builds the
  parallel `weights` array in the sorted order. So the calldata is canonical across all nodes. *(This is
  the precise line MemeCore is missing.)*
- **Class B (swallowed error) — FIXED here.** Every system-call path **propagates errors** (`return
  err` throughout `distributeFinalityReward`, `slash`, `distributeIncoming`), and `Finalize` asserts
  **`len(*systemTxs) == 0`** at the end (`:1491-1492`, "the length of systemTxs do not match") — no
  extra/curtailed system txs.
- **System-call replay is verified, not trusted.** `applyTransaction` reconstructs the `expectedTx` from
  the system message, and in verification mode **requires the block's actual system tx to be present and
  its hash to byte-equal the expected** (`:22-32`, error on mismatch) — a verifier cannot be fed a
  different system tx than the producer deterministically computed. Errors propagate.

**Significance.** Hunting the highest-value MemeCore classes in the *largest* parlia chain's *newest*
consensus code returned clean — and BSC implements the exact pattern MemeCore got wrong, **correctly**
(sort + verify + propagate). This (a) clears BSC on this surface, and (b) **independently confirms the
MemeCore finding is a genuine deviation from canonical parlia practice** — the parent chain sorts the
map-derived validator list and verifies/propagates, MemeCore does neither. The contrast is the proof.
**Residual:** the rest of parlia (vote/BLS aggregation in `votepool`, snapshot/validator-set transition
at epoch, the stakehub/feynman staking delta) — large surfaces, partially read; the fast-finality reward
+ system-call path is the MemeCore-class core and it's clean. **No finding.**
