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

---

## L2. Polygon (POL/MATIC) — bor consensus delta: state-sync + producer selection (clean)
**Target:** `maticnetwork/bor` HEAD `706b800`, `consensus/bor/bor.go`. Bor's custom delta over geth is
the **heimdall→bor state-sync** (a consensus-critical system call importing off-chain events) and the
span/producer selection — both prime MemeCore-class surfaces. Hunted classes B + C.
- **Class C (determinism) — clean.** Validator sets and selected producers are consistently
  **`sort.Sort(valset.ValidatorsByAddress(...))`** before use (`:650,677,842,1062`), so the producer
  ordering is canonical. The **state-sync** is applied in **strict sequential ID order**:
  `CommitStates` (`:1758`) sets `from = lastStateID+1` (read from on-chain state), and
  `validateEventRecord` (`:1892`) requires **`lastStateID+1 == eventRecord.ID`** (+ chainID + time
  bound); on any invalid/out-of-order event the loop **`break`s** (`:1860`), so only a strictly
  contiguous, validated prefix of events is ever applied — deterministic across nodes, no gaps, no
  reordering.
- **Class B (swallowed error) — clean.** The state-sync system call propagates: `gasUsed, err =
  CommitState(...); if err != nil { return nil, err }` (`:1875-1878`); `LastStateId` errors propagate
  (`:34,44`). No swallow.
- Per-block state-sync gas is bounded (`totalGas`), and `eventRecord.ID <= lastStateID` is skipped
  (idempotent replay guard).
**Result: clean** on the MemeCore classes. The bor↔heimdall boundary is the **cross-layer seam**
(bor trusts heimdall to supply correct, ordered state-sync events and the validator spans) — the
irreducible residual, same shape as the other settlement seams; but bor's *application* of heimdall
data is deterministic, strictly-ordered, validated, gas-bounded, and error-propagating. **No finding.**

---

### Large-cap delta-hunt status (2 of the biggest geth forks, both clean)
Applied the proven MemeCore lens (custom-consensus delta + the B/C failure classes) to the two largest
geth-fork large caps — **BSC** (parlia + fast-finality) and **Polygon** (bor state-sync + producer
selection). Both **clean**, and both implement the exact patterns MemeCore got wrong **correctly**
(sort the map-derived list; validate/order; propagate errors; verify system-tx replay). The honest
pattern: **well-resourced large-cap teams get the consensus delta right** — MemeCore is the exception
(a smaller, less-reviewed parlia descendant), which is precisely why it's the corpus's one finding. The
remaining large-cap delta surfaces (opBNB/Mantle op-stack deposit/derivation, Cronos, Sonic/Lachesis,
Gnosis posdao) are the next candidates, but the EV is declining: the failure class is rare at this tier.
