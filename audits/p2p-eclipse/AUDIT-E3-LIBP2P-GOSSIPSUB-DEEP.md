# E3 (deep) — libp2p gossipsub: the exact scoring math, the Dout-preserving mesh trim, PX trust, and the validation choke

**Scope.** A deep, individualized expansion of sweep item **E3** (`AUDIT-P2P-ECLIPSE-SWEEP.md` §E3), going
past the P1–P7 names + Dhi graft restriction the rapid pass covered into the **exact mechanics**: the
quadratic-penalty + multiplicative-decay score formulas, the delivery-tally attribution (incl. the
deliver-during-validation reward window), the heartbeat **score-sorted mesh trim with forced Dout-outbound
preservation**, the **peer-exchange (PX) two-gate trust surface**, the mcache IWANT window + the two-stage
**validation throttle**, the **peer-gater** DoS breaker, and the **probabilistic broken-promise** IWANT
penalty. Target: `libp2p/go-libp2p-pubsub` @ `e137920`. Read-only, public-source, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No finding;** three factual concerns are named precisely.

**Sources (verbatim, line refs):** `score.go`, `score_params.go`, `gossipsub.go`, `mcache.go`, `pubsub.go`,
`validation.go`, `peer_gater.go`, `gossip_tracer.go`.

---

## 0. What the deep pass adds over the sweep

The sweep established the shape (negative-only scoring; the Dhi inbound-graft restriction; bounded gossip).
The deeper reading supplies the *math and the edges*: the penalties are **quadratic** (`deficit²`/`count²`/
`excess²` × negative weight) with **multiplicative decay snapped to zero**, and disconnected peers' scores are
**retained, not decayed** (anti reconnect-reset); the mesh trim is **score-sorted but forcibly preserves Dout
outbound peers** even when low-score (the real anti-takeover guarantee); PX is gated on **two** things
(`acceptPXThreshold` *and* cryptographically-valid signed peer records); the validation pipeline has a **32-deep
front choke** behind an 8192-wide fan-out; and the broken-promise penalty samples **one** promised ID per IWANT.
The three honest residuals — the validateQ choke mismatch, PX default-config sensitivity, and probabilistic
broken-promise under-counting — are the parts a rapid pass can't see.

---

## 1. The exact score — quadratic penalties, multiplicative decay, retained-on-disconnect. **The engine.**

`score(p) (:271-348)` sums per-topic P1–P4 × `TopicWeight` (capped by `TopicScoreCap`), then global P5/P6/P7.
The penalties are **quadratic with negative weight** — they grow super-linearly:
```go
deficit := MeshMessageDeliveriesThreshold - meshMessageDeliveries; p3 := deficit*deficit; topicScore += p3*MeshMessageDeliveriesWeight  // :308-313
p4 := invalidMessageDeliveries*invalidMessageDeliveries;           topicScore += p4*InvalidMessageDeliveriesWeight                      // :318-320
excess := behaviourPenalty - BehaviourPenaltyThreshold;  p7 := excess*excess;  score += p7*BehaviourPenaltyWeight                       // :340-345
```
**Decay** (`refreshScores :510-571`, ticked every `DecayInterval`, default 1s) is multiplicative and snapped to
zero under `DecayToZero` (default 0.01); the decay factor is `decayToZero^(1/ticks)` (`score_params.go:407-417`).
The **activation gate** (`MeshMessageDeliveriesActivation`) means a freshly-grafted peer is **immune to P3**
until it has been in-mesh long enough (`:556-562`), and **P3b is latched at PRUNE** (`Prune :689-694`:
`meshFailurePenalty += deficit²`) into a sticky penalty that then only decays. Crucially, **disconnected peers'
scores are retained, not decayed** (`:516-528`) — specifically to stop reconnect-to-reset.

**Characterization:** a peer that drifts toward the mesh-delivery deficit, sends invalid messages, or
accumulates behavioural penalty is punished **disproportionately** (quadratic), cannot reset by reconnecting,
and cannot game the score positive (penalty weights are validated negative). The activation window is the one
nuance that protects honest new peers from premature P3 punishment — and the inverse footgun: a
`MeshMessageDeliveriesThreshold` set too high with a steep weight drives *honest* peers negative (an
operational mis-config, not a bug).

---

## 2. Delivery attribution — and the deliver-during-validation reward window. **The near-first-delivery edge.**

The shared `deliveryRecord.peers` set (keyed by message ID, TTL `seenMsgTTL`) anchors attribution.
`DeliverMessage (:708-732)` credits the first deliverer (`markFirstMessageDelivery`, capped) and then credits
every peer who forwarded *before validation completed* via `markDuplicateMessageDelivery(p, msg,
time.Time{})` — a **zero validated-time that bypasses the window check** (`:973-984`: a non-zero `validated`
only counts within `MeshMessageDeliveriesWindow`). Invalid attribution (`RejectMessage :734-799`): genuine
invalids penalize the sender **and every peer in `drec.peers`** (P4 `+=1`, squared later), while
**throttled/ignored rejects null out `drec.peers` *without* penalty** (the system doesn't know if the message
was valid). `DuplicateMessage (:801-833)` dedups per-peer so no double-count.

**Characterization:** the "deliver-during-validation ⇒ zero validated-time ⇒ always-credited" path is the
*near-first-delivery reward window* the sweep only named — it rewards fast honest forwarding. The deliberate
choice **not** to penalize forwarders on *throttled/ignored* rejects (only on *genuine* invalids) is what
prevents an attacker flooding under load from causing collateral score damage to honest relays (it pairs with
§5/§6).

---

## 3. Heartbeat mesh maintenance — score-sorted trim, **Dout outbound forcibly preserved.** The anti-takeover core.

`heartbeat() (:1634-1900)`, defaults `D=6, Dlo=5, Dhi=12, Dscore=4, Dout=2`:
- **Negative-score prune** (`:1695-1702`): any mesh peer with `score<0` is pruned **with `noPX[p]=true`** (bad
  peers get no peer-exchange).
- **Over-supply trim** (`:1721-1782`): at `len ≥ Dhi`, sort descending by score, **keep the first `Dscore`
  strictly by score**, shuffle+keep the rest up to `D`.
- **Dout preservation** (`:1736-1775`): count outbound peers in the kept `D`; if `< Dout`, `rotate()` **bubbles
  outbound peers to the front so they survive the cut** — even if low-score:
  ```go
  ineed := Dout - outbound
  for i := D; i < len(plst) && ineed > 0; i++ { if gs.outbound[p] { rotate(i); ineed-- } }   // :1766-1774
  ```
- **Opportunistic grafting** (`:1812-1844`): every `OpportunisticGraftTicks` (≈60 heartbeats), if the **median**
  mesh score is below `opportunisticGraftThreshold`, graft above-median peers — the escape hatch from a
  Sybil-saturated mesh.

**Characterization:** mesh maintenance is **score-first but outbound-protected** — the highest-score peers fill
`Dscore` slots, and `Dout=2` *outbound* peers (ones *we* dialed, which an attacker can't make us choose) are
**forcibly preserved even when low-score**. This is the precise anti-eclipse/anti-takeover guarantee: a Sybil
flooding inbound GRAFTs cannot displace our outbound mesh links, and opportunistic grafting lets a partially
captured node *reach back out* to honest above-median gossipers.

---

## 4. Peer exchange (PX) — two-gate trust. **Signed records + an accept threshold.**

**Send** (`makePrune :2186-2216`): PX only to PX-capable peers, selecting `PrunePeers` (16) candidates with
`score ≥ 0`, each attached as a **signed `record.Envelope`** from the certified addr book. **Receive**
(`handlePrune :1157-1189`): PX is acted on **only if the *pruning* peer's `score ≥ acceptPXThreshold`**;
`pxConnect (:1249-1299)` then **requires each exchanged record to be a cryptographically valid signed peer
record with `rec.PeerID == p`** (`ConsumeEnvelope`, `:1266-1283`), enqueues non-blocking to a bounded (128)
connect queue, and dials with a 30s timeout. Backoff (`PruneBackoff` ≈1 min, or peer-specified) governs
re-graft.

**Characterization (the trust surface, factual):** PX is gated on **two** independent checks — the pruning
peer's score and per-record signature validity (peer-ID-bound, so addresses can't be spoofed). A peer below
`acceptPXThreshold` **cannot inject peers at all**. The residual: a *high-score* (or, in a default config where
`acceptPXThreshold` may be 0, *any*) peer can still hand you up to 16 attacker-chosen-but-validly-signed peer
IDs per prune, seeding your dial list — **signed records prevent address spoofing but not peer-selection
bias.** This is the one place gossipsub trusts a peer to *introduce* others, and it is **default-config
sensitive** (set `acceptPXThreshold` above zero in production — Eth/Filecoin do).

---

## 5. mcache + the two-stage validation throttle. **The narrowest choke.**

**mcache** (`mcache.go`): a sliding window of `history=5` slots; `GetGossipIDs (:82-92)` advertises only the
first `gossip=3` slots (the IHAVE window), while `Get` serves IWANT from the full 5 — the `5−3=2` slot slack is
the deliberate advertise→pull reaction buffer; `GetForPeer` enforces `GossipRetransmission` per peer; `Shift`
rotates once per heartbeat. **Seen/timecache** dedups by message ID inside validation (`Strategy_FirstSeen`,
TTL `TimeCacheDuration`). **Validation throttle** (`validation.go`): `Push (:256-270)` is a non-blocking send to
a **32-deep `validateQ`** feeding a *single* worker → on full, `RejectValidationQueueFull` + drop; then an
**8192-wide async semaphore** (`:364-377`) → on full, `RejectValidationThrottled`; then **per-topic 1024
semaphores**.

**Characterization (factual concern):** the **32-deep front queue behind a single validateWorker** is the
narrowest choke, mismatched against the 8192-wide async fan-out — a burst of *validatable* messages (those with
a signature or topic validator) that out-paces the single worker fills `validateQ` fast and triggers
`RejectValidationQueueFull` drops of *honest* messages. This is **fail-safe** (throttle/queue-full rejects are
*non-attributing* to forwarders, §2, so honest relays aren't penalized), but it means an attacker flooding
validatable messages can induce honest-message drops without individual penalty — **validation-queue
saturation**, whose intended mitigation is the peer-gater (§6), not the scoring.

---

## 6. peer-gater + the probabilistic broken-promise IWANT penalty. **The DoS breaker.**

**Peer-gater** (`peer_gater.go`, `AcceptFrom :325-368`): a self-disarming probabilistic DoS breaker that
engages **only** when the system-wide `throttle/validate` ratio exceeds `Threshold=0.33` *and* there was a
throttle event within `Quiet=1m`; then it probabilistically throttles a peer by its goodput ratio
(`threshold = (1+deliver)/(1+total)`, rejects weighted **16×**), returning `AcceptControl` (control msgs only,
payload dropped) — **never a hard blacklist**, and decaying back to `AcceptAll`.

**Broken-promise IWANT penalty** (`gossip_tracer.go`): on serving an IWANT, `AddPromise (:48-75)` tracks **one
randomly chosen** promised msgID with a 3s (`IWantFollowupTime`) expiry; `GetBrokenPromises (:79-115)` reports
unfulfilled ones, wired each heartbeat into the **P7 behaviour penalty** (`applyIwantPenalties :1934-1939` →
squared in scoring). Missing/invalid-signature rejects **do not fulfill** the promise (`:153-158`), so the
penalty still applies; a throttled peer's promises are voided (no penalty). IHAVE flood is bounded
(`handleIHave`: drop below gossipThreshold, `MaxIHaveMessages=10`/heartbeat, `MaxIHaveLength=5000`); IWANT
serving enforces `GossipRetransmission=3`.

**Characterization (factual concerns):** the broken-promise mechanism is the anti-IHAVE-spam defense
(advertise-but-don't-deliver costs quadratic P7) — but it samples **one** promised ID per IWANT, so a peer
breaking *many* promises is **under-counted by design** (memory-bounded sampling). The peer-gater is the
front-line breaker against the §5 validation saturation, but it is *strictly probabilistic and self-disarming*,
so a peer maintaining some genuine deliveries (the `1+deliver` numerator) can stay just under the per-peer
throttle.

---

## 7. Verdict & residual

the mesh is takeover-resistant for a *configured* node across the full mechanism: quadratic non-gameable
scoring with retained-on-disconnect, the score-sorted-but-Dout-preserving trim, opportunistic grafting, the
two-gate PX, bounded mcache/IHAVE/IWANT with broken-promise penalties, and the peer-gater. **No finding.**
**Residuals**, named precisely: (a) **configuration is the security** — scoring thresholds and
`acceptPXThreshold` have weak/zero library defaults, so an operator who under-sets them (or leaves
`acceptPXThreshold` at 0) gets the PX-seeding and scoring protections only as strongly as they configured them
(Eth/Filecoin set them explicitly — *those values are the real defense*); (b) the **32-deep validateQ choke**
behind an 8192-wide fan-out means validation-queue saturation can drop honest messages (fail-safe, gater-
mitigated); (c) the **probabilistic (sampled) broken-promise accounting** under-penalizes high-volume IHAVE
liars. All three are design trade-offs (memory-bounded, config-driven), not implementation defects — and each
is the precise spot where the takeover-resistance rests on a parameter rather than a structural guarantee.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-P2P-ECLIPSE-SWEEP.md` §E3.*
