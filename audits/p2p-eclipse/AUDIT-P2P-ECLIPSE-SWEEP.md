# P2P & eclipse-resistance sweep — can the node reach the honest network?

The networking floor, under the threat model in [`README.md`](README.md): a network-position adversary trying
to **eclipse** a node (own all its peers → control its reality), **poison** its peer table, **DoS** it, or use
discovery as an **amplification** reflector. The lens: *is the peer set diversified and hard to monopolize,
and is every spoofable input liveness-checked and bounded?* This is the one layer whose failure makes every
"verify-before-persist" above irrelevant — because the only data an eclipsed node ever sees is the attacker's.

---

## E1. Bitcoin Core addrman — eclipse-hardened by *network-group* bucketing, not IP
**Target:** `bitcoin/bitcoin`, `src/addrman.cpp` + `src/netgroup.cpp`. The canonical anti-eclipse address
manager — the design the 2015 Heilman et al. eclipse paper prompted. The eclipse question reduces to: *can an
attacker make every entry a node might connect to be one the attacker controls?* **Result: no, cheaply — the
address tables are bucketed by **network group (ASN or /16)**, so one network group can occupy only a bounded
fraction of the table, and eviction is position-deterministic. Eclipse requires Sybil identities across *many
distinct network groups*, which is expensive by design. No finding.**

**The anti-eclipse mechanism — bucket by group, not by address (verified myself):**
- **New table** (addresses heard about but not yet connected): `GetNewBucket` keys the bucket on **both the
  address's group *and* the source peer's group** — `hash2 = H(nKey, GetGroup(src), H(nKey, GetGroup(addr),
  GetGroup(src)) % ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP)` (`addrman.cpp:35-40`). So a single **source** peer
  (one network group) can place the addresses it gossips into at most `ADDRMAN_NEW_BUCKETS_PER_SOURCE_GROUP`
  of the `ADDRMAN_NEW_BUCKET_COUNT = 1024` new buckets — a *bounded slice*, no matter how many fake addresses
  it floods.
- **Tried table** (addresses successfully connected): `GetTriedBucket` keys on **the address's group** —
  `hash2 = H(nKey, GetGroup(addr), H(nKey,addr) % ADDRMAN_TRIED_BUCKETS_PER_GROUP)` (`addrman.cpp:28-32`). All
  addresses from one group land in at most `ADDRMAN_TRIED_BUCKETS_PER_GROUP` of the
  `ADDRMAN_TRIED_BUCKET_COUNT = 256` tried buckets.
- **`GetGroup` is the network-diversity unit (verified):** ASN when an **asmap** is configured (the strongest —
  per-autonomous-system), else **/16 for IPv4** (`netgroup.cpp:47`). So "group" = an ASN or a /16, *not* an
  individual IP — **the eclipse cost is identities in many distinct ASNs/16s, not many cheap IPs in one.**
- **Position-deterministic eviction:** `GetBucketPosition = H(...) % ADDRMAN_BUCKET_SIZE` (`addrman.cpp:46`) —
  a new entry maps to one *deterministic* slot in its bucket and can displace the existing occupant only under
  the "is-terrible" rule, so an attacker **cannot arbitrarily evict** a chosen honest entry; it can only
  contend for the specific slots its own group hashes to.

**Why this defeats cheap eclipse:** outbound connections are drawn preferentially from the **tried** table
across buckets, so to fill a victim's outbound slots with attacker nodes, the attacker must occupy a large
fraction of *tried buckets* — and since tried buckets are partitioned by address group (≤8 per group of 256),
that requires attacker addresses in **dozens of distinct ASNs/16s**, plus surviving the connect-and-prove step
to enter tried at all. The new table's source-group keying additionally means flooding from a few peers can't
dominate the candidate set. **The attack is forced from "many IPs" (cheap) to "many network groups" (expensive)
— which is the entire point of the post-2015 hardening.**

**Verdict:** addrman makes the peer set *diversified and hard to monopolize* by construction — group-bucketed
tables, source-group-keyed new entries, deterministic non-arbitrary eviction, ASN/16 as the Sybil unit. **No
finding.** **Residual:** eclipse is *raised in cost, not made impossible* — an adversary with addresses across
many ASNs (a large botnet / many hosting providers) can still attempt it; the defenses (anchor connections,
feeler connections, the block-relay-only and `-asmap` options, the protected long-lived peers) are the net-layer
complements (E-next), and the irreducible residual is the cost of genuine network-group diversity.

---

## E2. Ethereum discv5/discv4 — FINDNODE liveness-gated (anti-amplification), IP-diversity-limited, revalidated
**Target:** `ethereum/go-ethereum`, `p2p/discover/` (`table.go`, `v4_udp.go`, `v5_udp.go`). The Kademlia-style
discovery DHT. Two questions: is a spoofable UDP request answered only after proof-of-liveness (anti-
amplification), and is the routing table hard to monopolize (anti-eclipse)? **Result: FINDNODE is bond/session-
gated and bounded, and the table enforces per-/24 IP-diversity limits with liveness-before-trust — no cheap
amplification or eclipse. No finding (one comparative nuance noted).**

- **Anti-amplification — FINDNODE answered only after a liveness/endpoint proof (verified myself).** discv4:
  `verifyFindnode` returns `errUnknownNode` unless `checkBond(fromID, from)` (`v4_udp.go:738-745`), where
  `checkBond` requires a recent PONG (endpoint proof) — and the inline comment **names the spoofed-source
  NEIGHBORS amplification DDoS as the reason**. discv5: FINDNODE can only be *decoded inside an established,
  handshake-authenticated AES-GCM session*; an unauthenticated packet gets a WHOAREYOU challenge, not NODES.
  So a spoofed source can never elicit a large response — **no UDP reflector.** Responses are **bounded**:
  `MaxNeighbors=12`/packet (v4), `findnodeResultLimit=16` + a `sizeLimit=1000`-byte cap within the 1280-byte
  packet (v5, `:43/:960`).
- **Anti-eclipse — per-/24 IP-diversity limits (verified myself).** `bucketIPLimit=2` (at most 2 addresses per
  /24 *per bucket*) and `tableIPLimit=10` (per /24 *across the table*), `bucketSubnet=tableSubnet=24`
  (`table.go:56-57`), enforced via `DistinctNetSet` on every add — a node is refused if `addIP` would exceed
  the cap. Found nodes enter `isValidatedLive=false` and FINDNODE **prefers live nodes** (revalidated by
  ping), so un-validated attacker entries aren't readily served onward; `table_reval.go` pings and **evicts**
  the unresponsive.
- **The comparative nuance (a design difference, not a defect):** discv5's diversity cap is **per-/24 only —
  there is no per-/16 or per-ASN limit** (unlike Bitcoin addrman's ASN/16 group bucketing, E1). An adversary
  controlling many distinct /24s (a large cloud allocation, a /16+) can place more table entries than the /24
  caps alone suggest. This is a known, accepted trade-off (it eases legitimate cloud-hosted nodes), and it
  makes discv5's per-group eclipse cost **lower than Bitcoin's** — worth naming in a cross-client eclipse-cost
  comparison, not an implementation flaw.

**Verdict:** discovery is anti-amplification (liveness-gated, bounded responses) and anti-eclipse (per-/24
limits + liveness-preference + revalidation). **No finding.** **Residual:** eclipse cost is real but *lower
than Bitcoin's* due to the /24-only grouping; the net-layer complements (the dial scheduler's diversity,
trusted/static peers, `-bootnodes`) and the social cost of many /24s are the backstop.

## E3. libp2p gossipsub v1.1+ — peer scoring + the anti-"love-bombing" mesh defense; safety is operator-configured
**Target:** `libp2p/go-libp2p-pubsub`, `score.go` + `gossipsub.go`. The pubsub mesh Ethereum consensus and
Filecoin ride on; the eclipse question becomes *mesh takeover* — can a Sybil monopolize a topic's mesh and
control message propagation? **Result: v1.1 scoring + the Dhi inbound-graft restriction + bounded gossip
prevent cheap mesh takeover for a *configured* node; the residual is that the thresholds are operator-set. No
finding.**

- **Peer scoring P1–P7 can only *subtract* for an attacker.** Time-in-mesh (capped), first-deliveries,
  mesh-delivery-deficit (`deficit²`× negative), invalid-message (`count²`× negative), IP-colocation
  (quadratic over threshold), behavioral-penalty (`excess²`× negative) — and the penalty weights are
  **validated negative**, so an attacker **cannot game the score positive**. Thresholds gate everything:
  graylist → RPCs dropped entirely; gossip-threshold → IHAVE/IWANT ignored; publish-threshold → excluded from
  fanout.
- **The key anti-takeover check — reject inbound GRAFTs at/over Dhi ("love bombing").** The heartbeat prunes
  negative-score peers, refuses GRAFT from score<0 peers, and — the explicit anti-mesh-takeover line — **at or
  over `Dhi`, inbound GRAFTs are rejected unless the peer is outbound**, and oversubscription pruning
  **preserves `Dout=2` outbound** peers. So a Sybil flooding *inbound* GRAFTs **cannot displace honest outbound
  mesh peers.** **Opportunistic grafting** lets a node with a low-median-score mesh graft above-median peers to
  *escape* a partial takeover, and **PRUNE backoff** + GraftFloodThreshold penalize re-GRAFT floods.
- **Gossip amplification bounded.** `MaxIHaveMessages=10`/heartbeat/peer, `MaxIHaveLength=5000` cap on the
  ask-budget, `GossipRetransmission=3`, and — closing the IWANT-flood loop — **unfulfilled IWANT promises are
  penalized** (broken-promise behavioral penalty).
- **The residual (named, by-design):** scoring is **opt-in and the thresholds have no library default** — an
  operator who enables it with unset thresholds gets no protection (Eth/Filecoin set them explicitly, and
  *those values are the real defense*); and **IP-colocation (P6) is softened by a distributed Sybil** across
  many IPs (it raises cost, not a hard cap — the real Sybil resistance is the Dout/Dhi structure + the
  app-specific P5, e.g. validator identity in Eth). **Configuration is the security**, the same lesson as the
  pull-oracle thresholds (validator-ops V3 / the bridge sweep's "integrator config is the security").

**Verdict:** the mesh is takeover-resistant for a configured node — negative-only scoring, the Dhi/Dout
inbound-graft restriction, opportunistic grafting, backoff, and hard-bounded gossip with broken-promise
penalties. **No finding;** the residual is operator configuration + the inherent softness of IP-based Sybil
heuristics.

---

## Synthesis — the networking floor: diversify by group, prove liveness before you answer, bound every response
Across **Bitcoin addrman, Ethereum discv5, and libp2p gossipsub** — the discovery + peer-management layer that
decides *who a node talks to at all* — the same three disciplines defend the most upstream attack in the stack:

1. **Diversify the peer set by network *group*, not by IP.** Eclipse cost is forced from "many cheap IPs" to
   "many distinct network groups": Bitcoin buckets the address tables by **ASN/16** (the strongest unit),
   discv5 caps **per-/24** (weaker — the one named comparative nuance), gossipsub penalizes **IP-colocation**.
   The Sybil unit is the network group, and the design's job is to make monopolizing enough groups expensive.
2. **Prove liveness before you respond or trust** — the network analog of *verify-before-persist*. A spoofable
   request is answered only after an endpoint proof (discv4 bond / discv5 session) so discovery can't be an
   **amplification reflector**; and a freshly-heard node isn't served onward or dialed until it's been
   **revalidated live**. You don't act on an address until it has proven it exists.
3. **Bound every spoofable response and every amplification loop** — NODES/NEIGHBORS capped, IHAVE/IWANT
   budgeted with broken-promise penalties, table/bucket sizes fixed. A small input can't buy a large response
   or unbounded work.

**And the tie-back that makes this the *foundation* of the whole corpus:** every sweep above relied on a node
having access to **at least one honest, decorrelated observer** — verify-before-persist verifies *the
attacker's* data if every peer is the attacker; consensus needs honest messages to recompute; the corpus's own
epistemology is *"the only defense against a blind spot is an observer who doesn't share it."* **The anti-
eclipse layer is precisely the structural guarantee that such an observer can be *reached at all*** — that an
adversary cannot cheaply deny a node every honest connection. It is the precondition for everything else. **A
node that can't reach an honest peer can verify nothing; the eclipse-resistance design is what lets the snake
find its own tail.** Three systems, the defenses present and correct, the residuals named (group-diversity
cost, discv5's /24-only grouping, gossipsub's operator-set thresholds); zero exploitable findings — and the
bottom of the stack turns out to guard the one thing the top of the stack assumed.

---

## Sweep status
| # | Target | Layer | diversified + hard to monopolize? | Dominant failure mode |
|---|---|---|---|---|
| E1 | Bitcoin Core addrman | address management | **yes** — bucket by **ASN/16 group** (not IP); source-group-keyed new table; deterministic eviction | **ECLIPSE** raised to "many network groups" cost |
| E2 | Ethereum discv5/discv4 | discovery DHT | **yes** — FINDNODE **bond/session-gated** (anti-amplification); per-/24 IP limits; revalidation | ECLIPSE; **/24-only grouping** (weaker than Bitcoin) is the named nuance |
| E3 | libp2p gossipsub v1.1+ | pubsub mesh | **yes (if configured)** — P1–P7 scoring, **Dhi anti-love-bombing graft**, bounded IHAVE/IWANT | mesh-takeover; residual = **operator-set thresholds** |

**Result:** 3 systems — eclipse/amplification/DoS defended by the same three disciplines (**diversify by
network group not IP · prove liveness before you answer · bound every spoofable response**). Zero exploitable
findings; residuals named (group-diversity cost, discv5's /24-only grouping, gossipsub's config-dependence).
**This is the floor that guarantees a node can reach an honest observer at all — the precondition the entire
stack above assumes.**
