# E1 (deep) — Bitcoin Core addrman: the test-before-evict lifecycle, IsTerrible gating, and connect-time group diversity

**Scope.** A deep, individualized expansion of sweep item **E1** (`AUDIT-P2P-ECLIPSE-SWEEP.md` §E1), going
past the group-bucketing (`GetNewBucket`/`GetTriedBucket`, already covered) into the **full address
lifecycle**: the Add/Good/Attempt flow, the **test-before-evict collision protocol**, the `IsTerrible`
displacement-gating thresholds, `Select`'s tried-vs-new draw, the **connect-time per-network-group dedup +
feeler/anchor** logic, the addr-relay token-bucket limiter, and the load-time asmap-consistency re-bucket.
Target: `bitcoin/bitcoin` @ `5f33da9`, `src/{addrman,net,net_processing,netgroup}.cpp`. Read-only,
public-source, recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** the weakest
point of the anti-eviction discipline is named factually.

**Sources (verbatim, line refs):** `addrman.cpp` (+ `addrman.h`/`addrman_impl.h`), `net.cpp`,
`net_processing.cpp`, `netgroup.cpp`.

---

## 0. What the deep pass adds over the sweep

The sweep established that the address tables are *bucketed by network group* (ASN/16), forcing eclipse from
"many IPs" to "many groups." The deeper reading shows the **dynamics that protect an already-honest tried
peer**: a new entry **never directly evicts a tried entry** — a tried-slot collision triggers a
*test-before-evict* protocol where the incumbent is actively probed and replaced only when *proven dead*;
`IsTerrible` (the displacement predicate) has a deliberate 1-minute floor and a future-timestamp guard;
`Select` draws tried-vs-new at **50/50** so the attacker-fillable new table can't dominate; the **connect-time
group dedup** (built from *outbound* peers only, inbound excluded by design) enforces diversity at the socket;
**anchors** give restart-time eclipse resistance; the **addr-relay token bucket** throttles injection to 0.1
addr/s; and **peers.dat is treated as untrusted** — every placement is recomputed from the node's own secret
key on load.

---

## 1. Add / Good / Attempt — and the test-before-evict collision protocol. **The core anti-eviction.**

`AddSingle (:530-604)` only ever inserts into the **new** table; an occupied new slot is overwritten *only*
if the incumbent `IsTerrible()` or is weakly-referenced (`:584-588`), and a stochastic refcount damper makes
each additional new-bucket reference `2^nRefCount` times harder (`:569-573`) — flooding the same address into
many new buckets is exponentially throttled.

The decisive mechanism is in `Good_ (:606-659)`: promotion to **tried** when the target tried slot is
occupied does **not** evict — the challenger's id is parked in `m_tried_collisions` (capped at 10) and the
function returns, leaving the incumbent untouched:
```cpp
if (test_before_evict && (vvTried[tried_bucket][tried_bucket_pos] != -1)) {   // :640
    if (m_tried_collisions.size() < ADDRMAN_SET_TRIED_COLLISION_SIZE) m_tried_collisions.insert(nId);
    return false;                                                             // incumbent kept
} else { MakeTried(info, nId); }
```
`MakeTried (:471-528)` is also **non-destructive**: a displaced tried entry is **demoted back into the new
table** (`:496-521`), never deleted. The deferred decision is `ResolveCollisions_ (:892-953)`, run each
`ThreadOpenConnections` loop: the incumbent is evicted **only** if it has had no success in
`ADDRMAN_REPLACEMENT = 4h` *and* a probe was made-and-failed >60s ago, **or** the collision sits unresolved
past `ADDRMAN_TEST_WINDOW = 40min`:
```cpp
if (now - info_old.m_last_success < ADDRMAN_REPLACEMENT) erase_collision = true;        // :921 old still good -> drop challenger
else if (now - info_old.m_last_try < ADDRMAN_REPLACEMENT) { if (now-info_old.m_last_try>60s) Good_(info_new,...); }  // :923 old proven dead -> promote
else if (now - info_new.m_last_success > ADDRMAN_TEST_WINDOW) Good_(info_new,...);      // :933 stalemate timeout -> force-promote
```
`SelectTriedCollision_ (:955-981)` returns the *incumbent* so a feeler actually probes it — **that probe is
the "test."**

**Characterization:** new entries cannot destroy tried entries; a tried-slot collision starts a
*test-before-evict* protocol where the would-be evictor waits while a feeler probes the incumbent, and the
incumbent is replaced **only after it is proven unreachable** (no success in 4h + a failed probe) or a 40-min
stalemate. This is the primary defense against flooding fresh addresses to displace honest tried peers — far
stronger than the static bucketing the sweep covered.

---

## 2. IsTerrible — the displacement-gating predicate. **Deliberately hard to weaponize.**

`IsTerrible (:49-72)` is the single predicate gating *displacement* (`AddSingle:585`) and *exclusion from
GETADDR* (`GetAddr_:825`). Exact thresholds: **never terrible if tried in the last 1 min** (`:51` — blocks
an attacker getting a just-attempted honest entry classified terrible); terrible if timestamp >10 min in the
future (`:55` — blocks timestamp-stuffing to keep stale entries alive), unseen for `ADDRMAN_HORIZON = 30d`,
`ADDRMAN_RETRIES = 3` attempts with zero success, or `ADDRMAN_MAX_FAILURES = 10` over `ADDRMAN_MIN_FAIL = 7d`.
`GetChance (:74-87)` is the soft companion: ×0.01 if tried in the last 10 min, ×0.66^min(nAttempts,8).

**Characterization:** the two guards (1-minute floor, future-timestamp reject) are precisely the
anti-weaponization details a rapid pass misses — they stop an attacker from *manufacturing* terribleness to
displace honest entries or from keeping stale attacker entries alive by timestamp-stuffing.

---

## 3. Select — tried and new drawn at 50/50. **The attacker-fillable table can't dominate.**

`Select_ (:693-773)`: if both tables are populated, a **50/50 coin flip** chooses tried vs new (`:727`);
within a bucket it scans from a random position with **probabilistic acceptance** that escalates a
`chance_factor ×1.2` per retry (`:764-771`), and a `networks` filter confines selection to one network
(`:747-749`). **Characterization:** because outbound selection samples tried (proven peers) at **parity**
with the far-larger, attacker-fillable new table, an attacker flooding the new table does **not**
proportionally raise its odds of being dialed — the proven set is always a coin-flip away.

---

## 4. Connect-time anti-eclipse (net.cpp) — group dedup, feelers, anchors. **Diversity enforced at the socket.**

`ThreadOpenConnections` builds the diversity set from **outbound** peers only — **inbound/feeler/addr-fetch
are deliberately excluded** so an attacker's free inbounds can't poison group accounting (`:2702-2738`,
comment), counting Tor/I2P/CJDNS as separate random groups. Group enforcement at connect time for non-feelers
(`:2876-2879`):
```cpp
if (!fFeeler && outbound_ipv46_peer_netgroups.contains(m_netgroupman.GetGroup(addr))) continue;  // :2877 one group per outbound
```
Connect-type priority (`:2766-2817`): **anchors** (2 block-relay-only) first, then full-relay to capacity,
block-relay, stale-tip extra, an **exponential-timer extra-block-relay** rotation (eclipse hardening, comment
`:2782`), feeler, extra-network. **Feelers** (`:2847-2865`) first call `SelectTriedCollision()` (driving the
§1 test-before-evict probe). **Anchors** (`MAX_BLOCK_RELAY_ONLY_ANCHORS = 2`) are read at startup, re-checked
against the group set, and dumped only on clean shutdown (`anchors.dat`). `GetGroup (netgroup.cpp:19-80)` is
the mapped-AS under `-asmap`, else /16 (IPv4) / /32 (IPv6) / 4-bit (Tor/I2P).

**Characterization:** outbound slots are forced into **distinct network groups at connect time** (ASN under
`-asmap`, else prefix), with inbound excluded from accounting by design; anchors give **restart-time eclipse
resistance** (reconnect stickiness across reboots — the window the 2015 attack exploited), and the
exponential extra-block-relay rotation continually samples fresh header sources. This is the *connection*
half of the defense the address-table sweep didn't reach.

---

## 5. ADDR relay — response cap + token-bucket injection limiter. **Throttling the bias vector.**

Outbound: `GETADDR` is answered once per connection, capped at `MAX_PCT_ADDR_TO_SEND = 23%`/`MAX_ADDR_TO_SEND
= 1000` (`net_processing.cpp:187-197,4833-4851`), and each requester gets a **cache frozen for ~21–27h**
(`net.cpp:3771-3807`) — anti-scrape. Inbound: a **token bucket** (`net_processing.cpp:5651-5677`) refills at
`MAX_ADDR_RATE_PER_SECOND = 0.1`/s (one per 10s), burst `1000`; excess records are **silently dropped before
reaching addrman**; over-size ADDR (>1000) → `Misbehaving`. A `GETADDR` *we* send grants a one-time +1000
bypass (`:3767-3769`).

**Characterization:** an attacker pushing unsolicited addresses to bias bucketing is throttled to a long-run
**0.1 addr/s**, and excess is discarded *before* it can touch the tables; outbound, the frozen per-requester
cache prevents repeatedly scraping live addrman to infer topology/freshness. This caps the *rate* of the very
injection the bucketing defends against.

---

## 6. peers.dat treated as untrusted — re-bucket on load. **No disk-chosen layout.**

`Unserialize (:211-379)`: format/version gated (`:223-237`), counts bounds-checked against capacity
(`:248-260`), and **every tried/new placement is recomputed from the node's own secret `nKey`** on load
(`:275-294`) — so disk-supplied positions can't force an attacker-chosen bucket layout. An **asmap-version
mismatch or bucket-count change triggers a full re-bucket** rather than trusting stored positions
(`:313-356`), and a final `CheckAddrman()` aborts the load on any structural inconsistency (`:373-378`).

**Characterization:** a tampered or asmap-divergent `peers.dat` is **detected and normalized**, not silently
honored — the bucket layout is always re-derived from the node's secret key, closing a "poison the file to
pick the buckets" vector a rapid pass wouldn't check.

---

## 7. Verdict & residual

addrman makes the peer set diversified and hard to monopolize across the *whole* lifecycle: group-bucketed
tables (sweep) **plus** test-before-evict tried protection, IsTerrible's anti-weaponization guards, 50/50
tried-vs-new selection, connect-time per-group dedup with anchors + feelers, a 0.1-addr/s injection limiter,
and untrusted-file re-bucketing. **No finding.** **Residuals**, named: (a) eclipse is *raised in cost, not
impossible* — an adversary with addresses across **many distinct ASNs** (a large botnet / many hosting
providers) can still attempt it (the irreducible group-diversity cost); (b) the **40-minute stalemate
force-promote** (`:933`) is the *one* path where a tried entry unreachable-by-us (possibly honest, e.g. our
own connectivity loss) is evicted without a definitive failed probe — the weakest point of the anti-eviction
discipline, by design; (c) inbound is excluded from group accounting (acknowledged in-code) and a solicited
ADDR can deliver ~1000 records past the steady-state limiter. All are deliberate trade-offs, precisely
located.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-P2P-ECLIPSE-SWEEP.md` §E1.*
