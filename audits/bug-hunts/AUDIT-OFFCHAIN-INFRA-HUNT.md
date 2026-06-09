# Off-chain infrastructure bug-hunt — the engine layer: BFT consensus and PBS block-building

**Why this hunt exists.** Every prior bug-hunt — EVM contracts, the cross-VM round (Vyper/Solana/zk/Move/Cosmos-
module/ERC-4337) — was *application or contract* code where the worst case is a value leak. This hunt drops a layer:
**off-chain engine code in Go** that secures the network itself, where the worst case is a **chain fork/halt** (a
safety/liveness violation) or a **proposer being cheated by infrastructure** — taxonomies with no value-rounding,
no `msg.sender`, no shares. Two live, critical targets that between them secure most of two major ecosystems.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute-don't-trust in
each engine's native invariant model. Anything real and live would be stopped and routed for private disclosure
(redacted here). **Both came back clean — no live finding — and both had their recent CVEs confirmed patched at the
analyzed release.**

| Target | Layer / language | Worst case | Taxonomy hunted | Verdict |
|---|---|---|---|---|
| **CometBFT** (`v1.0.1`) | BFT consensus engine (Go) — secures Cosmos Hub, Osmosis, etc. | **chain fork or halt** (safety/liveness), not theft | locking/polka rules, vote double-count, +2/3 + voting-power overflow, block/part validation, light-client trust math, evidence | **clean** (ASA-2025-001/002, merkle GHSA, ASA-2024-001 all patched) |
| **mev-boost** (`v1.12.0`) | PBS block-building sidecar (Go) — runs on the majority of ETH mainnet validators | **proposer cheated** (payload swap / forged bid), within an inherent relay-trust model | getHeader/getPayload unblinding equality, bid signature/domain binding, bid selection, relay equivocation/withholding, timing/DoS | **clean** (the inherent PBS trust residuals correctly characterized, not called bugs) |

---

## 1. CometBFT — the consensus-safety taxonomy (a bug here forks the chain)

**Repo:** `cometbft/cometbft`, pinned to release tag **`v1.0.1`** (`d2229950`). Live: the current stable line of the
BFT engine securing Cosmos mainnets; program is Cosmos HackerOne / `security@interchain.io`. The method was to
recompute each invariant from source and **trace the Tendermint paper's prevote/precommit/lock rules (lines 22-32)
against the actual Go**, then label every historical advisory as fixed-or-open in this tag.

**Per-class, against the proven-safe spec:**
- **State machine / locking (safety, highest) — clean.** `enterPrevote`/`defaultDoPrevote` (`state.go:1380-1566`)
  implements lines 22-32 including the `POLRound < cs.Round` guard (`:1538`, i.e. `v_r < round_p`).
  `enterPrecommit` (`:1604-1703`) locks **only on a current-round polka** (`Prevotes(round).TwoThirdsMajority()`,
  `:1624`) — the corrected post-2022 locking rule, no stale-round unlock — and `LockedRound`/`ValidRound` move
  monotonically. **No path could be constructed where a Byzantine proposer/peer drives two honest validators to
  commit different blocks**; the locked-block-vs-POLRound invariant holds.
- **Vote validation / double-count — clean.** `vote_set.go:169-243` checks height/round/type, validator membership
  by index, address match, duplicate, and signature **before** counting; voting power is added only on the first
  vote per validator (`sum += votingPower`, `:281`); a conflicting vote surfaces `ConflictingVoteError` → evidence.
  The commit path uses a `seenVals` map to reject double-votes and a strict `> votingPowerNeeded`.
- **Quorum / voting-power math — clean.** `MaxTotalVotingPower = MaxInt64/8` (`validator_set.go:27`), enforced via
  `safeAddClip` + panic; `safeAdd/Sub/Mul/Clip` are correct; proposer-priority increment uses safe arithmetic with
  a rescaling bound. No int64 overflow, no sub-2/3-as-quorum path.
- **Block / header / part validation — clean.** Header hashes bind recomputed content; `part_set.go:294-330` verifies
  each part against the part-set-header root with index-bounds/duplicate/total-consistency checks; the merkle code
  (`crypto/merkle/proof.go`) is the **post-fix** version (nil-root rejected `:80`, domain-separated leaf/inner
  hashes, `index>=total`/negative guards, `MaxAunts=100`).
- **Light client — clean.** `VerifyNonAdjacent` does the trust check (`trustLevel ≥ 1/3`) then a full +2/3 of the new
  set, with the expensive untrusted-set check deliberately last (a documented DoS ordering); `VerifyAdjacent`
  requires `ValidatorsHash == trustedHeader.NextValidatorsHash`; `ValidateTrustLevel` enforces `[1/3, 1]` with a
  `safeMul` overflow guard.
- **Evidence — clean.** Duplicate-vote and light-client-attack evidence both verify membership, the H/R/T match,
  *different* BlockIDs, power match, and both signatures, with expiry checked first.

**Historical advisories — all confirmed patched in v1.0.1:** the synchrony-param overflow cap (`params.go:157`,
fixes the **ASA-2025-001/002** chain-halt), merkle nil-root rejection (GHSA), vote validator-index OOB, and the
VoteExtensionsEnableHeight validation (ASA-2024-001). None open in this tag.

**No live finding.** The load-bearing invariants that hold: current-round-only locking, per-validator single-count,
`MaxTotalVotingPower = MaxInt64/8`, and the merkle index/total/nil-root guards.

---

## 2. mev-boost — the PBS trust taxonomy (separate "inherent trust" from "code defect")

**Repo:** `flashbots/mev-boost`, tag **`v1.12.0`** (`c48dbe4`). Live: the sidecar on a large fraction of ETH
mainnet validators. The first job here was **framing the trust model honestly** — mev-boost is a *stateless relay
multiplexer*; it never holds the validator key and signs nothing. So two residuals are **inherent to PBS and out of
scope for mev-boost code**, not bugs:
- a relay can withhold the payload after unblinding (data-withholding) — mev-boost can only detect + log it;
- a relay is trusted to have validated the builder block body behind the header — mev-boost can verify the relay
  *signed* the bid, not independently re-execute the block.

**Per-class, distinguishing inherent-trust from actual defects:**
- **getHeader/getPayload flow (highest) — clean / by-design.** Before the proposer signs, `processBid`
  (`get_header.go:383-499`) validates the relay pubkey binding, the relay BLS signature over the bid (under the
  builder domain), parentHash coherence with the proposer's request, and rejects zero-value/empty-tx-root/below-min
  bids. On unblinding, `verifyPayload` (`get_payload.go:343-486`) enforces the **load-bearing anti-swap check**:
  version match, non-empty payload, **block-hash equality** between the returned payload and the header the proposer
  signed (`verifyBlockHash`), and element-by-element blob-KZG-commitment equality. The signed bid is cached by
  `bidKey(slot, blockHash)` and re-checked against the CL-submitted blinded block — **the payload-swap path is
  closed.**
- **Signature / domain binding — clean.** The builder domain is computed once with the correct domain type and an
  **empty genesis-validators-root** per builder-specs, correctly separated from the beacon-proposer domain — so a
  bid signature can't be replayed as a block signature or vice-versa. The relay pubkey is an allowlist by
  construction (parsed from the operator-supplied relay URL, BLS-infinity rejected); a bid is accepted only if
  signed by that pubkey. Cross-slot/cross-relay replay is blocked by the parentHash check + the per-slot `slotUID`
  and `bidKey` binding. (By-design knob: `SKIP_RELAY_SIGNATURE_CHECK=1` is an explicit opt-in test flag, default
  off.)
- **Bid selection — clean.** The loop strictly keeps the highest `value` with a deterministic lexicographic-blockHash
  tiebreak; invalid bids `return` early before comparison, so no stale/invalid bid can be selected.
- **Relay equivocation / withholding — inherent PBS trust, correctly handled.** On getPayload mev-boost fans the
  unblinded block to **all** relays for redundancy, returns the first valid response, and logs the withholding relay
  loudly (the bid cache exists specifically to attribute withholding). Equivocation detection is relay-monitor
  territory, out of mev-boost's scope. No code defect.
- **Timing / DoS — clean / robust.** getHeader is bounded by `min(timeoutGetHeaderMs, lateInSlotTimeMs − msIntoSlot)`
  and aborts past the late-in-slot deadline; getPayload uses a hard timeout as both a watchdog goroutine (always
  feeds the channel) and the request context, with the first valid relay winning via `CompareAndSwap` — a single
  stalling relay can't push the proposer past its signing deadline or leak goroutines.

**No live finding.** The two security-critical checks (payload-vs-header equality on unblinding; bid
signature+pubkey+parentHash binding under a separated builder domain) are present and correct; the remaining risks
are inherent PBS trust assumptions handled as well as a stateless multiplexer can.

---

## Synthesis — what dropping to the engine layer proved

1. **The worst case changes, so the taxonomy changes.** No value-rounding, no `msg.sender`, no shares appear in this
   round. The question became "could two honest validators commit different blocks?" (CometBFT) and "can the relay
   make the proposer sign one header and get a different payload?" (mev-boost). The method — recompute the invariant
   from source in the platform's native model — ports, but *what* the invariant is is entirely layer-specific.
2. **Against proven-safe code, the job is verifying the proof is faithfully implemented.** CometBFT's safety is
   proven at the spec level; a real bug would be an *implementation drift* from the spec (e.g. the pre-2022
   stale-round unlock). The hunt traced the paper's lines 22-32 against the Go and confirmed the corrected
   current-round-only locking — that's the consensus analogue of recomputing a rounding direction.
3. **"Inherent trust" is not "defect" — and saying so is the finding.** mev-boost's payload-withholding and
   block-validity-trust are *properties of PBS*, not mev-boost bugs; calling them out as trust assumptions (and
   confirming the code does the maximum a stateless multiplexer can) is more honest and more useful than inflating
   an architectural property into a "finding."
4. **CVE-patch confirmation is a first-class deliverable on live infra.** Both hunts confirmed from source that the
   recent advisories are closed at the analyzed release (CometBFT: ASA-2025-001/002 + merkle GHSA + ASA-2024-001;
   mev-boost: the post-Deneb blob-commitment equality) — the same "deployed == audited" discipline applied to known
   issues rather than novel ones.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
