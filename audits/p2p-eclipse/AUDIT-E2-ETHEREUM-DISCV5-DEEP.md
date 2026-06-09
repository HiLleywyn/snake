# E2 (deep) — Ethereum discv5/discv4: the full table lifecycle, revalidation, and the handshake anti-spoof core

**Scope.** A deep, individualized expansion of sweep item **E2** (`AUDIT-P2P-ECLIPSE-SWEEP.md` §E2), going
past the FINDNODE bond-gating + per-/24 limits the rapid pass covered into the **full discovery
lifecycle**: the Kademlia bucket + replacement-list structure, the revalidation eviction state machine,
the iterative lookup, the discv5 WHOAREYOU→handshake→AES-GCM session core in detail, add-time IP
enforcement at *every* insertion point, and seeding/bootstrap. Target: `ethereum/go-ethereum` @ `1f87331`,
`p2p/discover/` + `p2p/netutil/`. Read-only, public-source, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No finding;** two environment-assumption residuals are characterized factually.

**Sources (verbatim, line refs):** `discover/{table, table_reval, lookup, v5_udp}.go`,
`discover/v5wire/{encoding, crypto, session}.go`, `netutil/{net, iptrack}.go`.

---

## 0. What the deep pass adds over the sweep

The sweep established the two headline properties (FINDNODE is liveness/session-gated; the table caps per
/24). The deeper reading shows *why an attacker who satisfies those gates still cannot take the table*: a
**replacement-list** structure means a live node is *never displaced by flooding new records*; eviction is
a **divide-by-3 liveness-decay** state machine, not a single miss; the discv5 **handshake binds table
insertion to a signed ECDH exchange** the spoofed victim must actually complete; and the per-/24 IP cap is
enforced at *every* insertion path (live, replacement, and IP-change). The two honest residuals — a LAN
IP-limit bypass and the absence of an explicit packet rate limiter — are named precisely.

---

## 1. Bucket + replacement list — a live node is never displaced by flooding. **The structural anti-eclipse.**

`table.go`: 17 buckets (`nBuckets = hashBits/15`), `bucketSize=16`, `maxReplacements=10`,
`bucketIPLimit=2`/`tableIPLimit=10` over /24. The core is `handleAddNode (:552-590)`: a node already present
is only `bumpInBucket`-updated; **if the bucket is full the newcomer goes to a 10-slot replacement list,
never displacing a live entry**, and only then is the IP limit checked:
```go
n, _ := tab.bumpInBucket(b, req.node, req.isInbound)
if n != nil { return false }                       // already in bucket: update only
if len(b.entries) >= bucketSize { tab.addReplacement(b, req.node); return false }  // full -> replacements
if !tab.addIP(b, req.node.IPAddr()) { return false }                              // then IP-limit gate
```
Promotion of a replacement happens **only** in `deleteInBucket (:638-663)` (i.e. when a live node is
evicted by revalidation), and it picks a **random** replacement, not most-recently-seen. `bumpInBucket
(:667-704)` blocks discv4 records (which "always have seq=0") from overwriting a live entry's endpoint —
non-inbound updates **require `Seq()` to advance**. Inbound contacts are dropped while the table is still
initializing (`:560-562`), and `handleTrackRequest (:706-733)` only drops a node after `maxFindnodeFailures
= 5` *and* only if the bucket is ≥1/4 full (keeps small nets stable).

**Characterization:** eclipse-resistance is *structural*, not just rate-based — an attacker flooding new
node records cannot evict a responsive incumbent; newcomers sit in a 10-slot replacement list and only win
a slot when an incumbent **fails revalidation**, and even then selection is random (so the attacker can't
time which replacement is promoted). The seq-advance gate closes the discv4-record-overwrite path.

---

## 2. Revalidation — divide-by-3 liveness decay, not a single miss. **The eviction state machine.**

`table_reval.go` runs two lists — `fast` (3s) and `slow` (×3 = 9s) — every node starting in `fast`
(`:58-60`). `run (:79-94)` picks a due node at random (excluding in-flight), pings, and reschedules. The
eviction core is `handleResponse (:133-184)`:
```go
if !resp.didRespond {
    n.livenessChecks /= 3                       // decay, not a single-miss eviction
    if n.livenessChecks <= 0 { tab.deleteInBucket(b, n.ID()) }  // only zero evicts (-> promotes a replacement)
    else { tr.moveToList(&tr.fast, n, now, ...) }               // demote to fast scrutiny
    return
}
n.livenessChecks++; n.isValidatedLive = true     // success -> live, move to slow list
```
Seeds are persisted to the node DB only after `livenessChecks > 5` (`:150-154`); a node removed mid-check is
detected (`revalList == nil`) and skipped.

**Characterization:** liveness uses **integer divide-by-3 decay**, so a long-lived responsive node survives
a transient outage but a never-responding attacker entry degrades to eviction fast; **only `deleteInBucket`
evicts, and it immediately pulls a replacement**, keeping the bucket full of *validated* nodes. The
fast/slow split caps PING volume while keeping fresh-endpoint nodes under tight scrutiny.

---

## 3. Iterative lookup — closest-16, dedup-guarded. **The walk can't be stalled.**

`lookup.go`: `newLookup (:44-63)` seeds from the local table's closest 16; `startQueries (:114-130)` keeps
`alpha=3` queries in flight, asking only **unasked** nodes from the sorted front; `addNodes (:94-103)` dedups
via a `seen` map and keeps only the closest 16. discv5 FINDNODE requests distances adjacent to
`logdist(target,dest)` capped at `lookupRequestLimit=3` (`v5_udp.go:384-399`). Every query feeds
success/failure into the §1 failure counter.

**Characterization:** standard 3-concurrent iterative Kademlia, but the `seen` dedup means **a malicious
node cannot re-inject the same IDs to stall the walk**, and results that don't improve closeness terminate
it — bounded work per lookup.

---

## 4. The discv5 handshake — table insertion bound to a signed ECDH exchange. **The anti-spoof/amplification core.**

This is the deep heart the sweep only named. An **unauthenticated/spoofed packet yields at most one small
WHOAREYOU**, never node data or a table entry:
- `decodeMessage (encoding.go:630-647)`: no session key (or GCM failure) → returns an `Unknown` placeholder,
  *not* any node data.
- `handleUnknown (v5_udp.go:831-853)`: responds **WHOAREYOU only**, echoing the request `Nonce` + a fresh
  random `IDNonce`; **no table mutation, no node-data leak**. The challenge's masking key is derived from the
  *requester ID* (`createMask` keys AES-CTR with `destID[:16]`, `encoding.go:683-688`) — so a spoofed source
  that never receives the WHOAREYOU cannot proceed.
- `decodeHandshake (encoding.go:543-574)`: requires a *matching stored* WHOAREYOU (`errUnexpectedHandshake`
  otherwise), **verifies the ID-nonce signature** over the challenge + ephemeral key, checks the ephemeral
  key is on-curve, then `deriveKeys` (HKDF-SHA256 over the ECDH secret, salted by the challenge, → two
  16-byte AES-GCM keys, `crypto.go:117-134`). **Only on full success is the node returned and added**
  (`handlePacket:756-759` calls `addInboundNode` *only* when the handshake produced a node).

**Replay / state bounding:** `matchWithCall (v5_udp.go:883-892)` requires a WHOAREYOU to match an in-flight
call by `Nonce` and rejects a second handshake (`errChallengeTwice`) — **exactly one handshake attempt per
call**; concurrent unknowns get the *same* existing challenge resent (bounded state); `handshakeGC`
(`session.go:139-147`) expires challenges after `handshakeTimeout = 1s`.

**Characterization:** **table insertion is gated on a signed, ECDH-authenticated handshake the claimed
source must actually complete** — a spoofed packet gets a ~request-sized WHOAREYOU (amplification ≈ 1) and
nothing else. One honest note: challenge state is keyed on the *claimed* `(SrcID, addr)`, but it cannot
*advance* without the real owner of `addr` answering — the masking key + required signature bind it.

---

## 5. IP-diversity enforced at every insertion point. **The principal anti-Sybil control.**

`DistinctNetSet.AddAddr (netutil/net.go:263-271)` is the primitive — refuse past the limit, **no eviction**.
`addIP (table.go:525-542)` enforces table-level (10/​/24) then bucket-level (2/​/24), rolling back the table
count if the bucket is full — and it is invoked from `handleAddNode`, `addReplacement`, **and** the
`bumpInBucket` IP-change path, so **both live entries and replacements are subnet-capped**, against the
*claimed record IP*. FINDNODE responses are bounded: `collectTableNodes (v5_udp.go:922-948)` dedups
distances, rejects `dist>256`, applies `CheckRelayAddr`, caps at `findnodeResultLimit=16`; `packNodes`
splits to ≤1000-byte packets.

**Characterization (the two honest residuals, defensive — not exploits):**
1. **LAN/loopback addresses bypass all IP limits** (`addIP:529-531` exempts `AddrIsLAN`). Correct on the
   public internet, but a peer classified as LAN that can spoof RFC1918 sources faces no per-subnet cap —
   an environment assumption, not a flaw.
2. **No explicit per-source packet rate limiter** in the discv5 path. Back-pressure is *structural*:
   `readLoop` processes one packet at a time on a single goroutine, re-arming the next read only after
   `handlePacket` returns (`v5_udp.go:598-601,705-723`). Per-packet cost is bounded (handshake-gated) but
   *unmetered* — DoS resistance rests on serial dispatch + the handshake gate, not a token bucket.

---

## 6. Seeding / bootstrap — bootnodes get no special table privilege

`loadSeedNodes (table.go:491-505)` mixes DB seeds with the nursery (bootnodes) and adds them through the
**same `handleAddNode` path** — non-inbound (bypassing only the init-done gate) but still subject to IP
limits, bucket-full→replacements, and seq gating. Bootnodes are validated (`ValidateComplete`, NetRestrict)
and must still pass revalidation; only seeds surviving >5 liveness checks are persisted. **Characterization:**
bootnodes are trusted *only as lookup entry points* — a poisoned local node DB cannot exceed the per-/24
caps on bootstrap, and seed nodes earn persistence only by proving liveness.

---

## 7. Verdict & residual

discovery is anti-amplification (handshake/bond-gated, ~1× responses, bounded), anti-eclipse (replacement
list so live nodes aren't displaced + divide-by-3 revalidation + per-/24 caps at every insertion + random
promotion), and the lookup can't be stalled. **No finding.** **Residuals**, named: (a) the **per-/24-only
grouping** is weaker than Bitcoin's ASN/16 (the sweep's comparative nuance — an adversary across many
distinct /24s places more entries than the /24 cap alone suggests); (b) **LAN addresses bypass IP limits**;
(c) **no explicit packet rate limiter** (serial single-goroutine dispatch instead). All three are
environment/design trade-offs, not implementation defects — and each is a precise statement of where the
anti-eclipse guarantee rests on an assumption rather than a hard cap.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-P2P-ECLIPSE-SWEEP.md` §E2.*
