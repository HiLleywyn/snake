# Peer-to-peer & eclipse resistance — can the node even reach the honest network?

The floor under every other sweep. State-sync, consensus, and the rest all assumed a node is connected to
*some* honest peers. This one audits that assumption: the **discovery + peer-management layer** that decides
*who a node talks to at all.* The threat model is the most upstream of all — **if an adversary controls every
one of a node's connections, it controls the node's entire reality**, and every "verify-before-persist" above
is moot because the only data the node ever sees is the attacker's.

## The threat model (what a network-position adversary is trying to cause)

| # | Failure mode | Severity | The mechanism |
|---|---|---|---|
| **ECLIPSE** | adversary owns **all** of a node's peers → controls its entire view (feeds a fake chain, censors, double-spends against it) | **catastrophic** *for the victim* | poison the peer table so every outbound + inbound slot is attacker-controlled |
| **TABLE-POISON** | fill the discovery table / addr DB with attacker nodes so honest peers are evicted/never tried | severe (enables eclipse) | flood with fake ENRs/addrs, abuse eviction, low-cost identity (Sybil) |
| **DoS** | exhaust connection/discovery/bandwidth resources | severe | connection floods, unsolicited messages, slot exhaustion |
| **AMPLIFICATION** | use the discovery protocol as a **DDoS reflector** against a third party | severe | spoofed-source request → large response to the victim (the classic UDP-reflection) |

## The lens (adapted to the network floor)

> **(Q1) Is the peer set *diversified and hard to monopolize*** — are outbound peers chosen across
> independent network groups (so one /16 or one ASN can't supply them all), is eviction resistant to flooding,
> is identity expensive enough to blunt Sybil?
>
> **(Q2) Is every unsolicited/spoofable input *bounded and liveness-checked*** — is a request answered only
> after a proof-of-liveness (anti-spoof / anti-amplification), are tables/queues capped, are ENRs/addresses
> verified before they influence the table?

Per-target checklist:
- **Address/table bucketing** — Bitcoin's `addrman` (tried/new tables bucketed by **source group**, so an
  attacker in one group can occupy only a few buckets); discv5's k-buckets by node-ID distance.
- **Outbound diversity** — choosing peers across distinct **/16 or ASN groups** (the anti-eclipse property);
  anchor/feeler connections; protected/long-lived peers immune to eviction.
- **Liveness / anti-spoof before response** — discv5's ping/pong (WHOAREYOU handshake) and the
  "endpoint-proof" before a FINDNODE is answered (anti-amplification); Bitcoin's no-reply-to-unverified.
- **Eviction policy** — is eviction protective (keep the most-useful/most-diverse, evict the most-replaceable)
  so an attacker can't churn out honest peers cheaply?
- **Sybil / identity cost** — what does one fake node cost (a key + an IP); how many does eclipse need.
- **Amplification ratio** — response size vs request size for any spoofable (UDP) message.

## Posture
Defensive; read-only; public source only. No exploit, no PoC. A genuinely exploitable eclipse/amplification
defect in live software → **stopped and reported privately**, redacted here. The aim is **characterization**:
confirm the peer set is diversified and hard to monopolize, and that every spoofable input is liveness-checked
and bounded — because this is the one layer whose failure makes *all the others irrelevant for the victim.*

## Index
*(populated as the sweep runs — Bitcoin addrman, Ethereum discv5, libp2p gossipsub)*
| File | What it is |
|---|---|
| _EX entries land here_ | |
