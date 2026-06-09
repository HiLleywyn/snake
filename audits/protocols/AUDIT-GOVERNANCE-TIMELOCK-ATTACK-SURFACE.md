# Governance & timelock — the mechanism behind the "governance ceiling" coordinate (OZ + Compound)

**Scope.** The two canonical on-chain governance stacks: OpenZeppelin `Governor` +
`TimelockController` (`OpenZeppelin/openzeppelin-contracts` @ `48ab75f`, post-v5.6.0) and Compound
`GovernorBravo` + `Timelock` (`compound-finance/compound-protocol` @ `a3214f6`). This audit
characterizes the **governance-ceiling** coordinate that every prior report in this corpus *named
but deferred to* — here it is, dissected. Public source, read-only, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No exploitable defect found**; known attack classes
described factually with their in-code defenses.

**Sources read (verbatim, line refs against those checkouts):** OZ `Governor.sol`,
`TimelockController.sol`, `utils/Votes.sol`, `extensions/{GovernorVotes, GovernorTimelockControl,
GovernorProposalGuardian}.sol`; Compound `GovernorBravoDelegate.sol`, `Comp.sol`, `GovernorAlpha.sol`,
`Timelock.sol`.

---

## 0. The one-paragraph result

Across ~40 prior audits the dominant residual, again and again, was a **governance ceiling** —
"whatever the admin/upgrade key can do." This audit opens that box. On-chain governance is the
mechanism that *implements* the ceiling, and it reduces to a single, remarkably clean equation: **the
security ceiling of an entire protocol equals the security of its token-weighted vote, plus the
timelock's minimum-delay exit window.** There is no privileged action above that line; conversely, an
attacker who wins the vote inherits the timelock's *full authority over every downstream contract*,
bounded only by the delay during which guardians and users can react. Two structural defenses make
this tolerable: **(1) vote weight is read at a *past snapshot block***, not live — which is the
complete and sufficient answer to flash-loan vote-borrowing (borrowed-and-repaid tokens create no
checkpoint at the already-past snapshot, so they carry zero weight); and **(2) the timelock's
`minDelay` is a *user exit window*** — a floor that governance cannot retroactively shorten on an
already-scheduled operation. The remaining attack surface is almost entirely **configuration, not
logic**: `votingDelay == 0` collapsing the snapshot gap (OZ allows it; Compound hard-floors it at 1),
open executor/extra-proposer timelock roles, and cancel-griefing. So the governance law: *the ceiling
is real, total, and irreducible — every protocol's worst case is "governance is captured" — and the
engineering is entirely about (a) making vote-capture expensive via snapshots and thresholds, and (b)
making capture *survivable* via a delay long enough for users to leave.*

---

## 1. The proposal FSM — content-addressed, monotonic, reentrancy-safe

OZ `Governor`: `hashProposal = keccak256(abi.encode(targets, values, calldatas, descriptionHash))
(:121-128)` — proposals are **content-addressed and self-deduplicating**. (Deliberate property,
flagged: chainId and governor address are **not** in the id (`:116-119`), so the same actions share an
id across instances — a cross-domain identity fact to track in multi-deployment setups.) `state()
(:141-178)` is a strict monotonic FSM (Pending → Active → Succeeded/Defeated → Queued → Executed, with
Canceled/Expired branches) enforced by a bitmap validator (`_validateStateBitmap :731`). `execute`
sets `executed = true` **before** the external `call{value}` loop (`:405,442-446`) — reentrancy-safe,
and notably **`call`, not `delegatecall`** (no code-injection-into-governor vector; same in Compound's
`Timelock.executeTransaction :100`).

Compound `GovernorBravo` is the same FSM with sequential integer ids (no content-hash),
**one-live-proposal-per-proposer (`:83-88`)**, an explicit **Expired** state past
`eta + GRACE_PERIOD (:224)`, and `proposalMaxOperations = 10`.

---

## 2. The flash-loan defense — vote weight at a past snapshot. **Complete and sufficient.**

This is the single most important property, and both implement it identically in spirit:

- **OZ:** `_castVote` reads `_getVotes(account, proposalSnapshot, params) (Governor.sol:637)` →
  `token().getPastVotes(account, timepoint) (GovernorVotes.sol:57-63)` → `Votes.getPastVotes
  (:91-93)`, which calls `_validateTimepoint` that **reverts `ERC5805FutureLookup` if `timepoint ≥
  clock()` (:70-74)**. You can only read *historical, finalized* delegate checkpoints.
- **Compound:** `castVoteInternal` reads `comp.getPriorVotes(voter, proposal.startBlock)
  (Delegate:276)` → `Comp.getPriorVotes` which **`require(blockNumber < block.number) (:190)`** and
  binary-searches checkpointed delegate balances.

**Why flash loans fail, precisely:** voting power is the delegated-checkpoint value at a block that is
*already in the past* when voting opens. A flash loan acquires and repays tokens within one
transaction; it cannot retroactively write a checkpoint at the past snapshot block. **Borrowed tokens
contribute exactly zero votes.** The residual exposure is *acquire-and-hold across the snapshot block*
— a real, capital-intensive cost, which is the point. This is the textbook example of the corpus's
"recompute, don't trust" applied to *time*: the system trusts a value it can prove was true at a
fixed past moment, not a value an attacker can momentarily manufacture.

**The one genuine weakening — `votingDelay == 0`:** OZ sets `snapshot = clock() + votingDelay()
(Governor.sol:320)`, and `votingDelay` is overridable to **0**, collapsing the snapshot to the propose
block — so just-acquired-then-delegated votes count, shrinking the community's reaction window.
**Compound structurally avoids this with `MIN_VOTING_DELAY = 1` (Delegate:24).** This is the
highest-value flag for any OZ-based deployment: *never deploy with `votingDelay == 0`.*

---

## 3. The timelock — the minDelay *is* the user exit window. **The survivability layer.**

OZ `TimelockController`: roles `PROPOSER`/`EXECUTOR`/`CANCELLER (:25-27)`; `_schedule` rejects
duplicates and **requires `delay ≥ minDelay` (:319-321)**; `updateDelay` is **self-call only
(:447-454)** — minDelay can only change by routing an op back through the timelock, and a delay
*reduction* itself takes the full current delay to land. Compound `Timelock`: `MINIMUM_DELAY = 2 days`,
`MAXIMUM_DELAY = 30 days`, `GRACE_PERIOD = 14 days`; `setDelay`/`setPendingAdmin` are **self-call only
(:37-38,54-55)**.

**Characterization (the contract says it itself, OZ `:13-16`):** the delay "gives time for users …
to exit before a potentially dangerous maintenance operation." The minDelay is not anti-attacker — a
captured governance *will* pass its proposal — it is **anti-irreversibility**: it guarantees a public,
fixed window between a proposal becoming executable and it executing, during which honest users can
withdraw and guardians can cancel. **This is why every prior audit's "governance ceiling" was tolerable
rather than fatal: the ceiling is total, but the delay makes it *observable and escapable*.**

---

## 4. The circular admin trust + the ultimate-ceiling property

Compound makes the structure explicit: **protocol contracts' admin = Timelock; Timelock's admin =
Governor** (`Timelock.executeTransaction` requires `msg.sender == admin (:81-82)`, and that admin is
Bravo). A closed loop: the Governor is the *only* driver of the Timelock, and the Timelock is the
*only* toucher of privileged protocol functions. OZ codifies the same via `_executor() ⇒ timelock`
and `onlyGovernance` whitelisting self-calls only during execution (`Governor.sol:215-224`).

**The ultimate-ceiling property, stated exactly:** *the security ceiling of the entire protocol equals
the security of the token-weighted vote plus the minDelay exit window.* There is no privileged action
above that line; an attacker who wins the vote inherits the timelock's full authority over every
downstream contract (including, via a normal `call` to a proxy's `upgradeToAndCall`, arbitrary code —
the framework itself uses no `delegatecall`, but the timelock *is* the admin of upgradeable targets).
This is the precise, mechanized form of the "governance ceiling" residual named throughout the corpus.

**Guardian / veto surface (the only thing above a passed vote, and only downward):** OZ
`GovernorProposalGuardian` can cancel *any* proposal at *any* stage (`:51-58`); `CANCELLER_ROLE` can
cancel scheduled ops. Compound `whitelistGuardian` can cancel whitelisted proposers below threshold and
the legacy GovernorAlpha `guardian` could re-point the timelock's pending admin during bootstrap then
`__abdicate`. Guardians can only *subtract* (cancel/veto), never *enact* — a deliberate asymmetry.

---

## 5. The attack surface — almost entirely configuration, not logic

| Class | Defense in code | Residual / flag |
|---|---|---|
| **Flash-loan vote borrowing** | past-snapshot weight (`Votes:70-74`, `Comp:190`) | none — fully neutralized; cost is acquire-and-hold |
| **`votingDelay == 0`** | Compound `MIN_VOTING_DELAY = 1` | **OZ allows 0 — collapses snapshot gap; deployment flag** |
| **Proposal-threshold spam** | Compound `MIN_PROPOSAL_THRESHOLD = 1000e18` + one-live-proposal | OZ default `proposalThreshold() == 0 (:181)` — raise it |
| **Cancel-griefing** | (anti-stale-proposal feature) | Compound third-party cancel-when-below-threshold (`:157-179`) can kill a legit proposer whose delegated weight dips |
| **Timelock-delay bypass** | `delay ≥ minDelay` + self-only `updateDelay` | **role misconfig**: OZ open `EXECUTOR_ROLE = address(0)` (`:145-150`), or extra PROPOSER/CANCELLER (source WARNING `GovernorTimelockControl:19-22`) |
| **Malicious upgrade via proposal** | no `delegatecall` in framework | timelock is admin of every target; a normal proposal can reach `upgradeToAndCall` on a proxy |

**The honest summary:** the *logic* of both stacks is sound and the headline attack (flash-loan
borrowing) is structurally dead. The real-world breaks are **configuration** — `votingDelay == 0`,
`proposalThreshold == 0`, open executor role, extra timelock proposers/cancellers — exactly the
parameters a deploying team sets, and exactly what the source comments themselves warn about.

---

## 6. Where this sits in the corpus — closing the ceiling coordinate

Every prior audit ended at a governance ceiling and named it without dissecting it. This report *is*
the dissection, and it resolves the coordinate into a reusable, mechanized statement:

- **The ceiling is total and irreducible.** Every governed protocol's true worst case is "governance
  is captured," and capture grants the timelock's full authority. No amount of downstream code review
  changes this — it is structural.
- **It is made *expensive* by snapshots + thresholds** (vote-capture costs real held capital, not a
  flash loan) **and *survivable* by the minDelay exit window** (capture is observable and escapable
  before it executes). A governance audit therefore reduces to four questions, all answerable from
  config: *is `votingDelay > 0`? is `proposalThreshold` meaningful? is `minDelay` long enough to
  actually exit? are the timelock roles minimal (no open executor, no stray proposers)?*
- **This unifies the corpus.** The "governance ceiling" residual that dominated lending, perps,
  restaking, stablecoins, and bridges is, mechanically, *this* — a token-weighted vote plus a delay.
  Naming a protocol's ceiling now means naming its `votingDelay`/`proposalThreshold`/`minDelay`/role
  set, not hand-waving at "the admin multisig." The most-centralized-to-least spectrum from the
  capstone (§4c) is, at bottom, a spectrum of *these four parameters*.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
