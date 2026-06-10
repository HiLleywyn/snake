# V1 (deep) — mev-boost (proposer side): the relay fan-out, the full bid gauntlet, getPayload redundancy, and the 204 escape

**Scope.** A deep, individualized expansion of sweep item **V1** (`AUDIT-VALIDATOR-OPS-SWEEP.md` §V1), going
past the getHeader signature/parent checks + the getPayload blockHash binding the rapid pass covered into the
**full proposer-side server**: the getHeader timeout budget + parallel relay fan-out + deterministic selection,
the complete bid-sanity gauntlet, the getPayload **fan-out-to-all-relays redundancy** + retry + V2→V1 fallback,
per-fork version dispatch + blob (KZG) binding, `registerValidator` opaque forwarding, and the
**204-to-beacon-node** escape (mev-boost builds nothing itself). Target: `flashbots/mev-boost`, `server/`.
Read-only, public-source, recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** several
honest corrections to the sweep's assumptions and a few operator footguns are characterized factually.

---

## 0. What the deep pass adds over the sweep (incl. honest corrections)

The sweep established the core safety (blockHash body-swap binding, one-sign-per-slot → no slashing, relay-sig
accountability). The deeper reading adds the *operational machine* and **corrects three assumptions**: (a) there
is **no gas-limit or timestamp/slot-genesis bid check** in mev-boost — those are relay/builder responsibilities;
(b) the "local-build fallback" is **not** inside mev-boost — it returns **204 No Content** to the beacon node,
which then builds locally; (c) the **relay-monitor is deprecated** to a hidden no-op flag. What *is* there and
deep: a timeout-budgeted parallel fan-out with **total error isolation**, a deterministic post-join selection,
a getPayload that **broadcasts to all relays** for missed-slot redundancy, and per-fork + blob handling whose
attestation boundary is precisely nameable.

---

## 1. getHeader — timeout budget, parallel fan-out, error isolation, deterministic selection.

getHeader is bounded by the **minimum** of the configured `timeoutGetHeaderMs` and the time remaining to the
late-in-slot deadline, optionally clamped further by a caller `X-Timeout-Ms` header; past the deadline it
returns an **empty bid, no error** (`get_header.go:86-121`). It then fans out **one goroutine per relay** with
results collected under a mutex (`:124-158`), and **error isolation is total** — `sendGetHeaderRequest` swallows
*every* error path (`return nil, ""`), so a failing/slow/malformed relay contributes nothing and never blocks
`wg.Wait()`. Selection runs **serially after the join** (`processBid :474-499`), so it's deterministic
regardless of goroutine race ordering: highest value wins, equal value breaks toward the **lexicographically
smaller block hash** (`:486`).

**Characterization:** clean parallel fan-out with **strong error isolation** (one bad relay can't stall or fail
the others) and a deterministic winner chosen in a post-join serial pass. Honest notes: the hash tiebreak is
builder-influenceable (a builder can grind a smaller block hash to win equal-value ties — benign for the
proposer); and an optional **timing-games** mode delays the first request and re-polls at intervals, keeping the
*latest* bid (trades latency-to-deadline for a fresher bid).

---

## 2. The full bid-sanity gauntlet — and what's *not* in it.

`processBid (:383-499)` runs the ordered gauntlet: (1) field-completeness per fork (`parseBidInfo`); (2)
empty-block-hash drop; (3) **builder-pubkey == configured relay pubkey** (`:416`); (4) relay BLS signature
(`:421`, *skippable* via `SKIP_RELAY_SIGNATURE_CHECK=1`); (5) parent-hash coherence; (6) **zero-value /
empty-tx-root sentinel** drop:
```go
isEmptyListTxRoot := bidInfo.txRoot.String() == "0x7ffe241ea60187fdb0187bfa22de35d1f9bed7ab061d9401fd47e34a54fbede1"
if isZeroValue || isEmptyListTxRoot { return }   // :443-449  the SSZ HTR of an empty tx list — rejects empty-block bids
```
(7) the **global min-bid floor** (`:459-463`, `relayMinBid`, bounded 0..1,000,000 ETH).

**Characterization (honest correction):** the sanity set is field-completeness, non-empty block, builder-key
match, relay signature, parent coherence, empty-block sentinel, and a min-bid floor — **there is NO gas-limit
check and NO timestamp/slot-genesis bid validation in mev-boost** (the genesis arithmetic is used only for
timing/budget logging; gas-limit/timestamp are relay/builder responsibilities). The `relayMinBid` is a **single
global floor**, not per-relay. Footgun: `SKIP_RELAY_SIGNATURE_CHECK=1` accepts **unsigned** bids (default off).

---

## 3. getPayload — fan-out to ALL relays for missed-slot redundancy. **The deep liveness mechanism.**

`innerGetPayload (get_payload.go:74-336)` deliberately broadcasts the signed blinded block to **every**
configured relay (`AllRelayConfigs()`), not just the one that served the winning bid (`:147-166`), using each
relay's recorded encoding preference only to pick SSZ/JSON. Each request is wrapped in `retry(ctx,
requestMaxRetries, 100ms, ...)` with **automatic V2→V1 endpoint fallback** on 4xx/5xx (`:261-267`). A background
goroutine pushes an **empty sentinel** into the buffered channel after the full timeout (`:156-160`), and the
**first relay to return a *verified* payload wins** the `received.CompareAndSwap` race (`:325-331`); the rest
keep running for broadcast redundancy. Crucially each payload is independently `verifyPayload`'d (version
match, non-empty, **block-hash binding**, blob bundle) **before** it can win (`:312-319`) — a malicious relay
cannot win with a mismatched payload. Total failure → the sentinel → `502 Bad Gateway` + a withholding log.

**Characterization:** getPayload maximizes the chance *some* relay broadcasts (minimizing missed slots) via
fan-out-to-all + per-attempt retry + V2→V1 fallback + first-correct-wins + a timeout sentinel so the handler
always returns. The body-swap safety holds because every candidate is block-hash-bound *before* it can win —
the redundancy is pure liveness, never a safety relaxation.

---

## 4. Version dispatch + blob (KZG) binding — and the attestation boundary.

Bid/payload decode branches per fork (bellatrix/capella/deneb/electra/**fulu**) with **no silent fallthrough**
(missing version on SSZ → `ErrMissingEthConsensusVersion`; unknown content type → error). `verifyBlobsBundle
(:405-486)`, gated by `Version >= Deneb`, checks blob/commitment/proof **counts** and asserts **exact
commitment equality index-by-index** (`:448-456`), with **Fulu cell-proof multiplicity** (`len(commitments) *
CellsPerExtBlob`) vs pre-Fulu one-proof-per-commitment.

**Characterization (the boundary, named honestly):** versioning is explicit per-fork; blob verification **binds
the relay's returned commitments to the commitments the proposer signed over** — but it verifies **commitment
equality + lengths only**, it does **not** re-run KZG pairing of blob↔commitment↔proof. That is correct by
design (the proposer signs over the commitments in the blinded block, and the block hash is independently bound;
an inconsistent blob is rejected by the consensus layer), but it is precisely the *edge of what mev-boost itself
attests* — worth naming in a deep audit.

---

## 5. registerValidator — opaque forwarding; mev-boost validates nothing here.

The handler reads the raw registration bytes once and **forwards them verbatim** (preserving the node's original
encoding), fanning out one goroutine per relay and returning OK as soon as **any one** relay responds 200
(`register_validator.go:31-93`), with a buffered `respErrCh` preventing goroutine leaks. **Characterization:**
mev-boost does **not** parse, signature-check, or rate-limit registrations — it trusts the (local, operator-run)
beacon node and lets relays validate. Honest note: the body is `io.ReadAll`'d with no explicit size cap beyond
the HTTP server's header limit (low concern — the caller is the operator's own node).

---

## 6. The escape hatch is a 204, not a local build. **mev-boost multiplexes; the beacon node builds.**

There is **no local block-building path inside mev-boost** — it is a relay multiplexer. When no relay returns an
acceptable bid (all failed/empty, past the deadline, or all filtered by the gauntlet incl. the min-bid floor),
getHeader returns an empty bid and the handler answers the beacon node with **`204 No Content`**
(`service.go:338-343`), which makes the **consensus client build a local block**. So the min-bid floor + the full
sanity gauntlet are effectively a **circuit breaker into local building**. The relay-monitor reporting feature
is **deprecated to a hidden no-op flag** (`cli/flags.go:158-164`); the only live relay-health surface is the
on-demand `CheckRelays`/`/eth/v1/builder/status` probe (`service.go:509-550`) and per-relay Prometheus metrics
— there is **no background relay-reputation or auto-disable logic.**

**Characterization:** the proposer is **never forced** onto a relay — a 204 hands control back to the CL for a
local build — which is the structural guarantee behind "the relay is trusted only for the MEV upside, never for
liveness-of-last-resort." Honest note: relay health is *operator-polled*, not auto-managed.

---

## 7. Verdict & residual

mev-boost minimizes the proposer's trust across the *whole* server: timeout-budgeted parallel fan-out with total
error isolation, a deterministic post-join winner, a complete bid gauntlet (empty-block sentinel + min-bid floor),
a getPayload that broadcasts to all relays for missed-slot redundancy while keeping the block-hash body-swap
binding, explicit per-fork + blob handling, opaque registration forwarding, and a 204 escape to local building.
**No finding.** **Residuals / honest details**, named: (a) the irreducible PBS trust (validity / payment /
revelation) is the *relay*, unchanged from the sweep; (b) **no gas-limit/timestamp bid check** in mev-boost
(relay-side responsibility — a corrected assumption); (c) the blob check is **commitment-equality, not KZG
pairing** (the attestation boundary); (d) operator footguns — `SKIP_RELAY_SIGNATURE_CHECK` (default off),
unbounded registration body read, operator-polled (not auto-managed) relay health; (e) the equal-value **hash
tiebreak is builder-grindable** (benign for the proposer). MEV-theft (body swap) and SLASH stay closed; the
residual is liveness (a bad relay costs a slot, mitigated by the all-relay getPayload fan-out + the 204 local
build) and payment-honesty (trusted, relay-simulated on the V2 side).

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-VALIDATOR-OPS-SWEEP.md` §V1.*
