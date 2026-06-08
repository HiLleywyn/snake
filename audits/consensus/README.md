# Consensus safety — fork choice, the EL↔CL seam, equivocation

A new layer. State sync (`../state-sync/`) was the *ingress* boundary — untrusted bytes entering a node. This
sweep is the **agreement** boundary: the rules by which honest nodes converge on *one* canonical chain even
when a fraction of validators (and all the peers) are adversarial. Where the sync sweep asked *"is network
data verified before it persists,"* this one asks *"can an adversary make honest nodes disagree, revert,
stall, or punish each other."*

## The threat model (what an adversarial validator/proposer/peer is trying to cause)

| # | Failure mode | Severity | Who can cause it |
|---|---|---|---|
| **SAFETY** | two conflicting blocks **finalized** (a permanent split) | **catastrophic** | ≥1/3 stake (by design) — the audit question is *whether a bug lowers that bar* |
| **REORG** | adversary **reverts** honest blocks (ex-ante / ex-post / balancing / proposer-boost-evasion) | severe | sometimes a *single* malicious proposer or a small stake fraction, if fork choice is exploitable |
| **LIVENESS** | consensus **stalls** / can't finalize | severe | a withholding or equivocating minority, if the protocol wedges |
| **SLASHING** | an **honest** validator is slashed (or a malicious one escapes slashing) | severe | a peer feeding crafted votes; a bug in surround/double-vote detection |
| **EL↔CL split** | execution and consensus clients **disagree** on validity, so a node follows a wrong chain or halts | severe | a malicious payload + a mishandled `INVALID`/`SYNCING`/`ACCEPTED` status |

## The lens (adapted to the agreement layer)

> **(Q1) What is the safety/liveness assumption, and does the code *enforce exactly* that — no weaker?** (e.g.
> ">2/3 honest stake": is the quorum arithmetic strict, the equivocation counted once, the FFG filter
> correct?)
>
> **(Q2) Can a single adversarial actor (proposer / voter / peer / EL) move the fork choice, finality, or
> slashing further than their stake should allow?** (the reorg / split / unjust-slash question)

The per-target checklist this layer demands:
- **Fork-choice integrity** — LMD-GHOST weight accounting, **proposer boost** (sized right? cleared right?),
  **FFG filtering** (only descendants of the justified checkpoint are viable), unrealized justification,
  equivocating-validator weight removal, tie-breaking determinism.
- **Finality / quorum arithmetic** — strict `>2/3` (not `>=`), supermajority-link validity, no double-count of
  an equivocator, the `>1/3` slashable-safety bound actually being the bound.
- **Equivocation / slashing** — double-proposal and surround-vote detection correctness; can an *honest*
  validator be framed; can a *guilty* one evade; replay/uniqueness of slashing evidence.
- **The EL↔CL engine-API seam** — `newPayload`/`forkchoiceUpdated` validity, correct handling of
  `VALID/INVALID/SYNCING/ACCEPTED`, the **invalid-block (and `latestValidHash`) cache**, optimistic-sync
  poisoning, payload-vs-header binding.
- **Reorg resistance** — ex-ante reorg (withhold + release), balancing attack (split honest view), proposer-
  boost evasion, the "reorg the tip for MEV" single-proposer vector.
- **Determinism of the choice** — given the same messages, do all honest nodes pick the same head? (the
  tie-break + the message-ordering-independence question — the MemeCore lesson at the consensus layer)
- **Liveness / stall** — can a minority wedge the state machine (Tendermint locking/PoLC, the round/timeout
  logic), or force unbounded work per round.

## Posture
Defensive; read-only; public source only. No exploit, no PoC. A genuinely exploitable consensus defect in live
software (a sub-1/3 safety break, a single-proposer reorg beyond proposer-boost, an honest-validator framing) →
**stopped and reported privately**, redacted placeholder here only. The aim is **characterization**: state the
safety/liveness assumption, check the code enforces *exactly* it, and locate where (if anywhere) one actor
gets more leverage than their stake.

## Index
*(populated as the sweep runs — Ethereum fork choice, the engine-API seam, CometBFT, Solana/DAG consensus, …)*
| File | What it is |
|---|---|
| _CX entries land here_ | |
