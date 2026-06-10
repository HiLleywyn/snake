# C2 (deep) — CometBFT: the full round state machine, WAL crash-recovery double-sign prevention, POL integrity, and light-client-attack evidence

**Scope.** A deep, individualized expansion of sweep item **C2** (`AUDIT-CONSENSUS-SWEEP.md` §C2), going past
the strict `>2/3` quorum + the PoLC unlock line into the **full Tendermint state machine**: the `enterX`
transitions + the prevote/lock-unlock core, timeout escalation, the **WAL write-before-sign crash-recovery**
that makes double-signing structurally impossible, POL-round integrity (`isProposalComplete` as the anti-lying
check), the **light-client-attack evidence** (lunatic/equivocation/amnesia), and the **privValidator HRS
double-sign guard**. Target: `cometbft/cometbft` @ `a81ee50`, `consensus/{state,wal,replay}.go`,
`types/evidence.go`, `evidence/verify.go`, `privval/file.go`. Read-only, public-source,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** the prevote-rule variant and the
signer-state-durability residual are characterized factually.

> **Variant note (honest):** this checkout implements the **classic** Tendermint prevote rule (prevote the
> locked block if locked; unlocking driven reactively by polkas in `enterPrecommit`), **not** the
> Tendermint-2 "prevote a block with a valid POL from a later round" rule. The sweep's cited unlock line
> (`state.go:2314-2317`) lives in the `addVote`/classic path and is consistent with this; the deeper reading
> just makes the *prevote* side explicit.

---

## 0. What the deep pass adds over the sweep

The sweep established the strict `>2/3` arithmetic and the correct PoLC unlock. The deeper reading shows the
*whole machine that enforces it*: every `enterX` transition guards its safety invariant with a **defensive
panic** (POLInfo consistency, +2/3-any presence, step==Commit); liveness is **linearly-escalating per-round
timeouts** plus vote-tally round-skipping; **double-signing is prevented in depth** — the WAL `FlushAndSync`s
every self-signed message *before* it is acted on (panic on failure) and the privValidator's HRS guard
*refuses* a second distinct signature at an already-signed height/round/step; POL integrity is enforced both
structurally and **semantically** (a proposer can't claim a polka the node doesn't locally observe); and the
**light-client-attack evidence** path reconstructs and cross-checks the culprit set at the common height, with
an explicit pubkey-swap defense.

---

## 1. The round state machine — defensive panics at every safety invariant. **enterPropose→Prevote→Precommit→Commit.**

`enterNewRound (state.go:1086-1152)` bumps proposer priority by the round delta, resets the proposal on
`round != 0`, and sets `Votes.SetRound(round+1)` to allow round-skipping. `enterPropose (:1177-1235)` schedules a
propose timeout and fires `enterPrevote` immediately if `isProposalComplete()`. The **prevote rule**
(`defaultDoPrevote :1382-1440`, classic): **prevote the locked block if locked**; else prevote nil **unless** the
proposal block exists AND passes consensus `ValidateBlock` AND ABCI `ProcessProposal`:
```go
if cs.LockedBlock != nil { signAddVote(Prevote, LockedBlock.Hash(), ...); return }   // :1387
if cs.ProposalBlock == nil { signAddVote(Prevote, nil, ...); return }                // :1394
if ValidateBlock(...) != nil { prevote nil }                                         // :1400
if !ProcessProposal(...) { prevote nil }                                             // :1428
signAddVote(Prevote, ProposalBlock.Hash(), ...)                                      // :1439
```
The lock/unlock core is `enterPrecommit (:1479-1598)`: no polka → precommit nil; **`polRound < round` →
panic** (POLInfo invariant, `:1518`); +2/3 **nil** → **unlock** (`LockedRound=-1`); +2/3 for our locked block →
**relock**; +2/3 for the proposal → **lock it** (with a `ValidateBlock` re-check that *panics* on fail); +2/3 for
a block we don't have → **unlock + reset parts to fetch it**, precommit nil. `enterPrevoteWait`/`enterPrecommitWait`
each **panic** if there isn't +2/3-any (a safety assertion). `tryFinalizeCommit (:1703-1718)` requires a +2/3
majority for a **non-nil** block *and* that we have it; `finalizeCommit` requires `Step == RoundStepCommit`.

**Characterization:** a textbook locked-coin PoLC machine where **every safety invariant is a panic**, not a
silent branch — POLInfo consistency, +2/3-any presence, step==Commit, and the lock-time `ValidateBlock` re-check
all halt the node rather than proceed on a violated assumption (the fail-safe-substrate law at the agreement
layer).

---

## 2. Timeouts — linear escalation + vote-tally round-skip. **Liveness past a withholding minority.**

Per-round timeouts grow **linearly** (`config.go:1322-1340`): `Propose(round) = TimeoutPropose +
TimeoutProposeDelta·round` (defaults 3000ms + 500ms/round; prevote/precommit 1000ms + 500ms/round). `handleTimeout
(:999-1047)` advances: propose-timeout → prevote-nil; prevoteWait → precommit; **`precommitWait` →
`enterPrecommit` then `enterNewRound(round+1)`** (`:1041-1042` — the canonical "no decision, escalate" path).
`addVote (:2301-2407)` adds vote-tally round-skipping: a future-round +2/3-any → `enterNewRound(vote.Round)`;
current-round +2/3 → `enterPrecommit`/`enterCommit`.

**Characterization:** liveness is linearly-escalating timeouts + vote-driven round-skip — a sub-1/3 minority can
neither force-advance (skip needs +2/3-any) nor force-commit (needs +2/3 majority), and a withholding minority is
escalated past by the growing timeouts. (Honest note: the `*Delta` values are operator-tunable and unbounded;
config validation only rejects negatives — a self-inflicted-liveness footgun, not an attack surface.)

---

## 3. WAL crash-recovery — fsync-before-sign makes double-signing structurally impossible. **The deep durability backbone.**

The WAL has two write modes (`wal.go`): `Write` (buffered) for peer msgs/timeouts, and **`WriteSync` (fsync'd)
for our own messages** — "so that we write to disk before sending signed messages." `receiveRoutine
(:835-905)` orders **write-before-act**, and `writeInternalMsgToWAL (:881-905)` **panics the node** if it can't
durably persist a self `VoteMessage`/`ProposalMessage` before processing it. Before signing, both
`decideProposal` and `signVote` call `wal.FlushAndSync()` first (`:2423-2427`), with the comment that otherwise
the privValidator would "refuse to sign anything." On restart, `catchupReplay (replay.go:94-166)` re-drives the
**exact** message sequence back through the *same* `handleMsg`/`handleTimeout` paths, asserting replayed
RoundState steps match, with `replayMode=true` suppressing signing errors — *"the votes will be replayed and
we'll get to the next step."*

**Characterization:** the WAL is the durability backbone — **every vote/proposal is fsync'd before broadcast
(panic on failure)**, and on restart the validator deterministically **re-enters the precise H/R/step it crashed
at**. A crash between signing and broadcasting is safe: replay re-feeds the same vote and the signer's HRS guard
(§6) reuses the stored signature rather than minting a second one. This is *record-before-sign* (the
validator-ops law) at the consensus layer, read end-to-end.

---

## 4. POL integrity — the anti-lying check. **A proposer can't fabricate a polka.**

`defaultSetProposal (:1940-1987)` validates structurally: **`POLRound ∈ [-1, round)`** (`:1952-1955`), the
proposer signature against `Validators.GetProposer().PubKey`, and the part count against `MaxBytes`. The
*semantic* check is `isProposalComplete (:1296-1307)`:
```go
if cs.Proposal.POLRound < 0 { return true }
return cs.Votes.Prevotes(cs.Proposal.POLRound).HasTwoThirdsMajority()   // :1306
```
**Characterization:** a proposer claiming `POLRound = r` only counts as "complete" if the node **locally
observes +2/3 prevotes at round r** — it cannot fabricate a polka that doesn't exist; the local node simply won't
prevote and the round times out. Block parts are **Merkle-proof-validated incrementally** (`addProposalBlockPart
:1992-2081`, with `MaxBytes` bounding), so a malicious proposer can neither forge a polka nor blow up memory.

---

## 5. Evidence — light-client-attack reconstruction + the pubkey-swap defense.

`DuplicateVoteEvidence` (`types/evidence.go:36-145`) canonicalizes its two votes by lexicographic BlockID.
`LightClientAttackEvidence (:210-390)` carries a `ConflictingBlock` + `CommonHeight`, and `GetByzantineValidators
(:253-300)` discriminates the three attack classes: **lunatic** (header hashes — ValidatorsHash/AppHash/etc. —
differ from the trusted header; culprits = common-set signers of the bogus header), **equivocation** (same round,
valid header; culprits = double-signers), **amnesia** (different rounds; **not attributable → empty set**).
`evidence/verify.go` independently re-derives the set: `VerifyLightClientAttack (:111-160)` does the trusting jump,
verifies 2/3+ of the **conflicting** set signed, cross-checks `TotalVotingPower` against `commonVals`, and a
forward-lunatic monotonic-time check; `validateABCIEvidence (:232-291)` requires the submitted byzantine list to
**match the re-derived one exactly** and — the notable guard — **rejects evidence where `evByz.Address !=
evByz.PubKey.Address()`** to *"prevent pubkey-swap attacks that would redirect ABCI misbehavior to an innocent
validator"* (`:276-288`).

**Characterization:** light-client-attack detection reconstructs *which* of the three attacks occurred purely from
header-hash divergence vs commit-round equality, re-derives the culprits, and validates them **at the common
height where the attackers were provably bonded**. Two honest details: **amnesia is explicitly non-attributable**
(an acknowledged accountability gap), and the **pubkey-vs-address consistency check** is a deliberate
anti-framing guard.

---

## 6. The signer HRS guard — double-signing structurally impossible. **And its one residual.**

The privValidator persists `FilePVLastSignState{Height, Round, Step, Signature, SignBytes}` (`privval/file.go:75-83`).
`CheckHRS (:100-131)` rejects any height/round/step **regression**, and `signVote (:307-367)` is the actual
guard:
```go
sameHRS, _ := lss.CheckHRS(height, round, step)
if sameHRS {
    if bytes.Equal(signBytes, lss.SignBytes) { vote.Signature = lss.Signature }        // identical -> reuse
    else if checkVotesOnlyDifferByTimestamp(...) { ...reuse with new ts... }            // ts-only -> reuse
    else { err = "conflicting data" }                                                  // DIFFERENT block @ same H/R/step -> REFUSE
}
... saveSigned(height, round, step, signBytes, sig)   // :362 persist new HRS BEFORE releasing the signature
```
**Characterization:** double-signing is **structurally impossible from the signer** — at an already-signed
H/R/step it returns the *identical* prior signature (or a timestamp-only variant) or a hard `"conflicting data"`
error; it **never mints a second distinct signature**. Combined with the WAL fsync-before-sign (§3) and
`saveSigned`-before-release, a crash between signing and broadcasting is safe. **Residual (the real one):** safety
rests entirely on the `LastSignState` file being **durable and co-located with the key** — a restored/rolled-back
state file, or a **key shared across instances without shared HRS state** (the tmkms multi-validator case flagged
in-code at `state.go:2159-2161`), reintroduces double-sign risk; the optional `DoubleSignCheckHeight` scan
(`:2544-2566`) is a best-effort secondary backstop.

---

## 7. Verdict & residual

CometBFT enforces its Byzantine assumption *exactly* across the whole machine: PoLC with panics at every safety
invariant, linearly-escalating timeouts that can't be force-advanced sub-2/3, WAL fsync-before-sign +
deterministic replay, semantic POL integrity, full light-client-attack evidence with an anti-framing guard, and a
signer that structurally cannot double-sign. **No finding.** **Residuals**, named: (a) this build uses the
**classic prevote/unlock rule** (not Tendermint-2 "valid POL for a later round") — a correct, well-understood
variant; (b) **amnesia evidence is non-attributable** (acknowledged accountability gap); (c) the
double-sign guarantee depends on **`LastSignState` durability + non-shared keys** — a restored/rolled-back state
file or a shared key without shared HRS state defeats it (operational, with a best-effort `DoubleSignCheckHeight`
backstop); (d) `*TimeoutDelta` is operator-tunable/unbounded (self-inflicted liveness only). The code neither
weakens nor strengthens the >2/3 assumption; the residual is the design assumption + the operational durability
of the signer state.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CONSENSUS-SWEEP.md` §C2.*
