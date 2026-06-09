# V2 (deep) — mev-boost-relay: the full submission gauntlet, the floor-bid, demotion bookkeeping, and the optimistic trust window

**Scope.** A deep, individualized expansion of sweep item **V2** (`AUDIT-VALIDATOR-OPS-SWEEP.md` §V2), going past
block-simulation + the atomic one-body-per-slot + the optimistic-collateral path the rapid pass covered into the
**full relay internals**: the 17-step `handleSubmitNewBlock` gauntlet, the floor-bid / top-bid Redis machinery
(and its non-atomic read-modify-write), the builder demotion + getPayload async-sim block, the housekeeper
proposer-duties, and the simulation rate-limiter. Target: `flashbots/mev-boost-relay` @ `31fda11`,
`services/api/`, `datastore/`, `services/housekeeper/`. Read-only, public-source, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No exploitable finding;** several factual concerns (non-atomic floor
RMW, the optimistic post-hoc trust window, silent drops) are characterized — none is a confidentiality/
fund-loss defect; each is a *named operational property*.

---

## 0. What the deep pass adds over the sweep (incl. an honest correction)

The sweep established the three pillars (synchronous block-sim, atomic one-body-per-slot, collateral-bounded
optimism). The deeper reading adds the *whole pipeline and its edges*, and **corrects one assumption: there is
no optimistic-V2 / header-payload split** — the relay is **V1 only** (one full-body submission route), with
"optimism" being async simulation of that full body, not a header/payload split. What's deep: the complete
17-step submission gauntlet ordering, the floor-bid mechanic (cancellable bids can't lower the floor) **and its
non-atomic read-modify-write** (the documented substrate of the latest-wins latency race), the demotion
bookkeeping with its post-hoc trust window, and the FIFO-unaware sim rate-limiter.

---

## 1. The submission gauntlet — 17 ordered rejection points.

`handleSubmitNewBlock (service.go:2208)` runs a builder body through, in order: (1) cancellation flag vs
feature-flag; (2) **gzip + `io.LimitReader(apiMaxPayloadBytes)`** (default 15 MiB); (3) content-type/fork
resolution — **missing `Eth-Consensus-Version` is *tolerated*, the slot is sniffed from raw bytes** (`:2293`);
(4) decode + non-empty field validation; (5) slot/timing — rejects past slots and **exact genesis-derived
timestamp mismatch** (`checkSubmissionSlotDetails`); (6) **builder entry** — blacklisted/low-prio-disabled →
`time.Sleep(200ms)` then a **silent `200 OK` no-body drop**; (7) fee-recipient + gas-limit from
`proposerDutiesMap[slot]` (missing duty → 400, mismatch → 400); (8) zero-value/no-tx short-circuit; (9)
`SanityCheckBuilderBlockSubmission`; (10) payload-attributes (`prev_randao` + post-Capella `withdrawals_root`);
(11) **builder BLS signature** over the bid trace; (12) **floor-bid check**; (13) deferred DB save (waits up to
10s on `simResultC`); (14) top-bid read → `fastTrackValidation = IsHighPrio && bidIsTopBid && !isLargeRequest`;
(15) **simulation dispatch** — optimistic (async) iff `IsOptimistic && collateral >= bidValue && slot ==
optimisticSlot`, else **synchronous** `simulateBlock` (timeout → 504, validation error → 400); (16) cancellation
**latest-wins recheck**; (17) Redis bid update.

**Characterization:** the gauntlet validates *everything cheap and structural before simulation* (size, timing,
duty, fee-recipient, signature, floor) and only then spends an EL simulation — and the synchronous default means
a bid is **never stored/served until it passes sim**. Honest notes: blacklisted-builder rejections are **silent
200-OK drops after a fixed 200ms sleep** (timing-observable, indistinguishable from acceptance without body
inspection); and **a missing version header is tolerated** by sniffing — a parser/sniffer-divergence surface
worth naming.

---

## 2. The floor-bid — cancellable bids can't lower it; but the read-modify-write isn't atomic.

`SaveBidAndUpdateTopBid (redis.go:582)`: the floor gate (`:605-616`) aborts a *non-cancellation* bid that is
below the floor, and floor-*promotion* (`:699-727`) `COPY`s a non-cancellable above-floor bid into
`keyFloorBid`. `_updateTopBid (:739)` makes the **floor outrank the live top bid** (`:763-767`). The
cancellation-below-floor path (`service.go:2119-2129`) `DelBuilderBid`s and returns 202 without simulating.
```go
isBidAboveFloor := submission.BidTrace.Value.ToBig().Cmp(floorValue) == 1
if !isCancellationEnabled && !isBidAboveFloor { return state, nil }   // redis.go:613-615  cancellable bids never lower the floor
```
**Characterization:** the floor = the highest *non-cancellable* bid, so a builder using cancellations can never
*reduce* what a proposer is served — the anti-cancellation-griefing guarantee. **Honest concern (factual, not an
exploit):** the floor/top read-modify-write is **not transactionally isolated** — `SaveBidAndUpdateTopBid` calls
`pipeliner.Exec` multiple times mid-function (`:707,730`) rather than one MULTI/EXEC, and `GetFloorBidValue`/
`GetTopBidValue` return `0` on `redis.Nil`. This is the **substrate of the network-latency race the code itself
documents** (`service.go:2569-2572`): a high bid can be clobbered by a later low bid under concurrent
submissions for the same `(slot, parent, proposer)`. It's a *bid-quality/MEV-efficiency* property, not a proposer
-safety hole (the block-hash binding + atomic one-body-per-slot still hold).

---

## 3. Demotion + the optimistic post-hoc trust window.

`processOptimisticBlock (service.go:711)` runs the sim async (registered on `optimisticBlocksWG`), and on any
error `demoteBuilder (:669)` flips the in-DB optimistic flag and **writes a demotion row** (`InsertBuilderDemotion`)
for an **off-chain collateral claim**. `handleGetPayload` **blocks on `optimisticBlocksWG.Wait()` (`:1605-1606`)**
then checks `GetBuilderDemotion` — so the async sim (and any demotion write) is guaranteed to land before the
refund decision; `prepareBuildersForSlot` also `Wait()`s before advancing `optimisticSlot`.

**Characterization (the trust window, named honestly):** an optimistic block is **served from getHeader and
proposable *before* its async sim completes** — integrity rests entirely on **collateral sizing**
(`collateral >= bidValue`) plus a successfully-written demotion row. Factual concerns: the shared builder-cache
`IsOptimistic` flag is mutated **without a lock** (`:735`); and a **failed `InsertBuilderDemotion` is only
logged** (`:700-706`) — so a DB-write failure means no off-chain claim record for a bad block already served.
This is exactly the sweep's "bounded by collateral" relaxation, now seen with its bookkeeping edges: the bound is
only as good as the collateral *and* the demotion-row durability.

---

## 4. Housekeeper — proposer duties = beacon-node duties filtered by registrations.

`updateProposerDuties (housekeeper.go:174)` runs twice/epoch, fetching **current + next epoch** duties from the
beacon node, joining each against DB validator registrations, and keeping **only duties with a registration**
(`:238-247`), written to Redis as `SetProposerDuties`. There is **no on-chain known-validator-set refresh here**;
`updateValidatorRegistrationsInRedis` bulk-copies the latest registrations from Postgres to Redis.
**Characterization:** the relay's notion of "who the slot's proposer is" — which **fee-recipient enforcement
depends on** — is purely the **beacon node's `GetProposerDuties` filtered by self-reported registrations**. An
unregistered proposer simply gets no duty entry. The trust here is the relay's own beacon node (local), not a
peer.

---

## 5. The simulation rate-limiter — capped, but FIFO-unaware.

`blocksim_ratelimiter.go`: `maxConcurrentBlocks = BLOCKSIM_MAX_CONCURRENT` (default **4**), `simRequestTimeout =
BLOCKSIM_TIMEOUT_MS` (default **10s**). `Send (:63)` gates via a `sync.Cond` — increment `counter`, `cv.Wait()`
if over cap, deferred decrement + `cv.Signal()` one waiter. The EL call is version-dispatched
`flashbots_validateBuilderSubmissionV2/V3/V4/V5` with `X-High-Priority`/`X-Fast-Track` headers.
**Characterization (factual concern):** the limiter is **FIFO-unaware** — `cv.Wait()`/`Signal()` give no
ordering, so under load a high-prio/fast-track submission has **no local scheduling priority** over queued
low-prio ones (the flags only become *EL request headers*, not local queue priority). Optimistic submissions
bypass the synchronous path but still consume one of the 4 concurrent slots. This is a *fairness/latency*
property under load, not a safety gap.

---

## 6. Optimistic-V2 — not present (honest correction).

The only builder-submission route is `pathSubmitNewBlock = "/relay/v1/builder/blocks"` (V1). There is **no
`handleSubmitNewBlockV2`, no header-payload split, no `/relay/v2/`** in the tree. Optimism = async full-block sim
+ collateral + demotion bookkeeping (§3, §5), **not** a header/payload split. (A correction to the sweep's open
question.)

---

## 7. Verdict & residual

the relay closes the proposer-facing safety modes the sweep named: synchronous default block-sim (so a served
bid passed validation), atomic one-body-per-slot (proposer-equivocation protection), HTR header→body binding,
and a collateral-bounded optimistic relaxation. **No exploitable finding.** **Residuals / factual concerns**,
named precisely: (a) the **floor/top Redis read-modify-write is non-atomic** (multiple mid-function `Exec`s) —
the documented substrate of a latest-wins bid-clobber race (bid-quality, not proposer-safety); (b) the
**optimistic trust window is post-hoc** — a block is proposable before its async sim completes, bounded only by
collateral *and* a durable demotion row (the in-cache flag is mutated lock-free; a demotion-write failure is only
logged); (c) **blacklisted builders get silent 200-OK drops after a 200ms sleep** (timing-observable); (d) a
**missing version header is tolerated by byte-sniffing** (parser-divergence surface); (e) the **sim limiter is
FIFO-unaware** (no local priority under load); (f) **V1 only** — no optimistic-V2. The relay remains Ethereum's
one trusted intermediary, trusted for validity (except the bonded optimistic window), payment (EL-simulated),
and revelation — and the deep read locates exactly where each of those trusts is *bounded* vs *assumed*.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-VALIDATOR-OPS-SWEEP.md` §V2.*
