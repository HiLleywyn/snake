# C1 (deep) — go-ethereum Engine API: forkchoiceUpdated, payload build, optimistic-sync resolution, version + blob gating

**Scope.** A deep, individualized expansion of sweep item **C1** (`AUDIT-CONSENSUS-SWEEP.md` §C1), going past
the `newPayload`/`checkInvalidAncestor` analysis the rapid pass covered into the **rest of the EL↔CL seam**:
the full `forkchoiceUpdated` (head-set + safe/finalized validation + reorg-depth bound), payload build +
`getPayload`, the optimistic-sync **resolution** state machine, per-version fork-timestamp + **blob
versioned-hash** binding, JWT auth, and the serialization locks/queue caps. Target: `ethereum/go-ethereum` @
`1f87331`, `eth/catalyst/{api,queue}.go` + `beacon/engine/types.go` + `node/jwt_handler.go`. Read-only,
public-source, recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** four
documented design trade-offs are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established `newPayload`'s separation-of-authority + the bounded, self-healing invalid cache. The
deeper reading covers the *other half of the seam*: `forkchoiceUpdated` is the CL's only lever to **set the
head**, and it independently validates the **safe and finalized** hashes (must be in the DB *and* on the
canonical chain) and **bounds reorg depth at 32**; payload building stamps the **fork version into the
PayloadID** so a payload can't be retrieved through the wrong version; the optimistic path **resolves** via
beacon-sync extension with a 128-hit self-healing eviction; each `newPayloadV2/V3/V4/V5` enforces an **exact
fork-window + presence matrix**, and V3+ **recomputes the block's blob hashes and requires them to equal the
CL-supplied `versionedHashes` in order**; and both entry points are **fully serialized** with every
unbounded surface hard-capped.

---

## 1. forkchoiceUpdated — head-set, safe/finalized validation, reorg bound. **The CL's head lever, gated.**

`forkchoiceUpdated (api.go:240)` is `forkchoiceLock`-serialized (`:244`). A zero head → `INVALID` (`:248-250`);
an **unknown head → optimistic SYNCING** after a `checkInvalidAncestor` short-circuit and a `BeaconSync`
trigger (`:258-295`). The head is set via `SetCanonical` **only after the block is locally present** (`:318-346`),
and crucially:
- **safe/finalized must be known AND canonical** (`:350-376`):
  ```go
  if rawdb.ReadCanonicalHash(db, finalBlock.NumberU64()) != update.FinalizedBlockHash
      return STATUS_INVALID, InvalidForkChoiceState("final block not in canonical chain")   // :356-358
  ```
  same for safe (`:370-372`) — a CL can't finalize a block that isn't on the node's own canonical chain.
- **reorg depth bounded at 32** (`maxReorgDepth`, `:332-335`): `depth >= maxReorgDepth → TooDeepReorg`.
- finalized-ancestor fcU is a silent no-op (`:328-330`) to avoid rewinding final history.

**Characterization:** the CL chooses the head, but the EL **independently verifies** every claim before acting
— the head must be locally validated, safe/finalized must be on the node's *own* canonical chain (recompute,
don't trust the CL's word), and reorgs deeper than 32 are refused. This is the *head-selection* half of the
separation-of-authority the sweep only saw from the `newPayload` side.

---

## 2. Payload build + getPayload — the version is baked into the ID. **No cross-version retrieval.**

A non-nil `payloadAttributes` triggers async construction via `Miner().BuildPayload`, keyed by a `PayloadID`
that is `SHA256(parent‖ts‖random‖feeRecipient‖withdrawals‖[beaconRoot]‖[slot])[:8]` with **byte 0 = the fork
version** (`miner/payload_building.go:54-71`); duplicate IDs short-circuit (`api.go:394-395`). `getPayload
(:518-531)` rejects an ID whose **embedded version doesn't match the endpoint** (`payloadID.Is(versions...)` →
`UnsupportedFork`), returns `UnknownPayload` if evicted, and **re-checks the payload timestamp's fork** against
the endpoint's allowed forks.

**Characterization:** the PayloadID is a content digest with the version stamped in, so `GetPayloadV3` can't
retrieve a V2-built payload and vice-versa — **the version binding is cryptographic, not advisory**, closing a
cross-version confusion seam a rapid pass wouldn't reach.

---

## 3. Optimistic-sync resolution — the SYNCING→VALID/INVALID closure. **Self-healing.**

When `newPayload`'s parent is missing, `delayPayloadImport (:961-994)` stashes the block in `remoteBlocks`,
runs `checkInvalidAncestor(parent, block)` first, and **extends the beacon sync** (`BeaconExtend`) — returning
`SYNCING`/`ACCEPTED`, never a guess (`:901-924`). Resolution is *implicit*: once the parent arrives a later
`newPayload`/fcU re-imports to VALID/INVALID. Bad blocks found during async sync flow through the downloader
callback (`SetBadBlockCallback(api.setInvalidAncestor)`, `:153`) into `invalidTipsets`; `checkInvalidAncestor`
surfaces them as INVALID with `latestValidHash = invalid.ParentHash`, and on **`invalidBlockHitEviction = 128`
hits the bad hash + its descendants are evicted and re-tried** (`:1022-1030`) — so a transient false-positive
*self-heals* while a real defect stays rejected.

**Characterization:** the optimistic path is a *closed* state machine — a block can be SYNCING only while its
parent is genuinely unknown, the resolution is driven by real sync progress, and the invalid-tracking is
**ephemeral and self-correcting** (a documented correctness-over-strictness trade-off: a restart clears it).

---

## 4. Version gating + blob versioned-hash binding. **The CL can't smuggle a cross-fork payload.**

Each `newPayloadV2/V3/V4/V5` enforces a **strict presence matrix + exact fork window** via `checkFork (:1127-1135)`
(which resolves the *latest* fork at the timestamp and requires exact membership): V2 rejects post-Cancun and
requires withdrawals; V3 requires `withdrawals`+`excessBlobGas`+`blobGasUsed`+`versionedHashes`+`beaconRoot`
and **`checkFork(ts, Cancun)`** (`:749-765`); V4 gates Prague, V5 gates Amsterdam + requires `SlotNumber`. The
**blob binding** (`beacon/engine/types.go:289-300`) **recomputes the block's blob hashes from the decoded
transactions and requires count + order to equal the CL-supplied `versionedHashes`**:
```go
if len(blobHashes) != len(versionedHashes) ... error
for i { if blobHashes[i] != versionedHashes[i] ... error }   // :296-298
```

**Characterization:** a CL **cannot** push a Cancun payload through V2 or a pre-Cancun payload through V3 (exact
fork-window check), and the blob commitments are **recomputed from the EL block and bound to the CL's claimed
hashes in order** — recompute-don't-trust applied to the blob layer, a seam the sweep didn't cover.

---

## 5. JWT auth + the serialization/bounds floor. **Local trust boundary + no unbounded surface.**

The entire `engine` namespace is `Authenticated: true` (`:51-59`), routed onto the JWT port; the handler is
**HS256-only** with a **±60s `iat` freshness window** (rejects stale *and* future tokens, `jwt_handler.go:60-76`)
— bounding token replay. Both entry points are fully serialized (`forkchoiceLock`, `newPayloadLock`), the latter
with an explicit DoS rationale (collapse duplicate in-flight inserts under CL retries, `:820-832`). Every
unbounded surface is capped: `maxTrackedPayloads = 10` / `maxTrackedHeaders = 96` shift-evicting ring buffers
(`queue.go`), `invalidTipsetsCap = 512`, blob requests `> 128 → TooLargeRequest`, payload-bodies `> 1024 →
TooLargeRequest`.

**Characterization:** the seam's trust boundary is **local** (JWT shared secret, not a peer), concurrent fcU/
newPayload calls can't interleave (no concurrent-reorg race), and there is **no unbounded-growth surface** — a
malicious-or-buggy CL can't OOM the EL through the API.

---

## 6. Verdict & residual

the EL↔CL seam is sound across the *whole* surface, not just `newPayload`: the CL sets the head but the EL
independently verifies head/safe/finalized against its own canonical chain and bounds reorg depth; payload
retrieval is version-bound by a content digest; the optimistic path is a closed, self-healing state machine;
version + blob gating recompute and bind the CL's claims; auth is a local JWT boundary; every surface is capped.
**No finding.** **Residuals / documented trade-offs**, named: (a) **invalid-state is intentionally ephemeral
and in-memory** — a restart clears bad-block tracking and the 128-hit eviction re-admits previously-rejected
blocks to escape self-induced false positives (correctness-over-strictness, by design); (b) fcU V3/V4 evaluate
payload-attributes *before* head application despite an in-code `TODO` noting the spec wants the head applied
regardless (behavioral, not memory-safety); (c) JWT uses `WithoutClaimsValidation()` and re-checks freshness
manually (`exp` optional) — security rests on the ±60s `iat` window + the shared secret (spec-consistent);
(d) `maxReorgDepth = 32` refuses deeper reorgs via fcU (they must be driven through sync). The *seam* adds no
exploitable gap; the residual is the correctness of the consensus rules on either side (C2–C4).

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CONSENSUS-SWEEP.md` §C1.*
