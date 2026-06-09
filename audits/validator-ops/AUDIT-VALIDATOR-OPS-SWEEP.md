# Validator-ops sweep — MEV/PBS, randomness, key management

> **Deep dives:** each item now has an individualized deep audit reading the *full mechanism* (past the headline
> the sweep covers): **V1 →** [`AUDIT-V1-MEVBOOST-PROPOSER-DEEP.md`](AUDIT-V1-MEVBOOST-PROPOSER-DEEP.md) (relay
> fan-out + bid gauntlet + getPayload redundancy + the 204 escape; honest corrections) · **V2 →**
> [`AUDIT-V2-MEVBOOST-RELAY-DEEP.md`](AUDIT-V2-MEVBOOST-RELAY-DEEP.md) (the 17-step submission gauntlet, the
> floor-bid + its non-atomic RMW, the optimistic post-hoc trust window) · **V3 →**
> [`AUDIT-V3-RANDAO-SHUFFLE-VRF-DEEP.md`](AUDIT-V3-RANDAO-SHUFFLE-VRF-DEEP.md) (swap-or-not shuffle, the
> balance-weighted proposer loop, Algorand's binomial sortition + two-phase lookback) · **V4 →**
> [`AUDIT-V4-SLASHING-PROTECTION-DEEP.md`](AUDIT-V4-SLASHING-PROTECTION-DEEP.md) (the surround SQL, raise-only
> import, GVR binding, doppelganger, the advisory lock).

The validator's trust surface beyond consensus, under the threat model in [`README.md`](README.md):
**MEV-theft, slashing, leader-election bias/prediction, key compromise, invalid-block.** The lens: *what must
the validator trust, is that trust minimized (verified) or assumed, and can a single counterparty rob/slash/
single it out?* This is the proven-vs-attested axis at the operational layer — and the MEV relay is the honest
answer to *"where is Ethereum's one genuinely trusted intermediary?"*

---

## V1. mev-boost (proposer side) — the canonical trusted intermediary, with the trust *minimized* exactly where it can be
**Target:** `flashbots/mev-boost`, `server/get_header.go` + `server/get_payload.go`. In Proposer-Builder
Separation, the proposer asks relays for the best *blinded header*, signs a commitment to it, and only then
receives the body. The relay is trusted. **The audit question is the honest one: what does the proposer
actually *verify* before signing, and what is irreducibly *trusted*?** **Result: the verifiable parts are all
verified — relay signature, parent coherence, value, and (critically) the body-can't-be-swapped binding — and
the single-blinded-header-per-slot design means the relay *cannot get the proposer slashed*. The irreducible
trust (block validity, payment, revelation) is the PBS design, not a defect. No finding.**

**What the proposer verifies at `getHeader` (verified myself):**
- **Relay signature** — `checkRelaySignature(bid, builderSigningDomain, relay.PublicKey)` (`get_header.go:423`):
  the bid must be signed by the relay's *known* public key (the relay is **accountable** for every bid it
  serves), and the bid pubkey must match the configured relay (`:416`).
- **Parent-hash coherence** — `bidInfo.parentHash == proposer's requested parentHash` (`:435`): the relay can't
  serve a bid building on a *different* head than the proposer's.
- **Value & min-bid** — empty/zero-value/empty-tx-root bids dropped (`:401/:444`); bids below the proposer's
  configured **`relayMinBid`** are ignored (`:459`) — below the floor, the proposer **builds locally** rather
  than trust a relay for a trivial bid. Highest-value bid wins, deterministic blockHash tie-break (`:486`).

**What the proposer verifies at `getPayload` — the body can't be swapped (verified myself):** `verifyPayload`
→ **`verifyBlockHash`**: the revealed execution payload's block hash **must equal** the block hash inside the
blinded header the proposer already signed — `if requestBlockHash != responseBlockHash → error`
(`get_payload.go:395`), plus `verifyBlobsBundle` binding the blobs/KZG. Because the block hash commits to the
*entire* execution payload (txRoot, stateRoot, …), a matching hash means **the body is exactly what was
committed** — a relay cannot reveal a different block than the one signed.

**Why the relay cannot *slash* the proposer (the catastrophic mode, closed by design):** mev-boost has the
proposer sign **exactly one blinded header per slot** (getHeader → sign → getPayload is serialized per slot),
and the signed object is a *commitment to one specific block hash*. A relay serving two payloads can't induce
a double-sign, because the proposer signs once, to one block. **SLASH: prevented.**

**The irreducible trust (named honestly — this is the PBS model, not a bug):** the proposer signs a header
**without executing the body**, so it trusts the relay for:
1. **Validity** — the block is valid. If it isn't, the network rejects it and the proposer *misses the slot*
   (a liveness cost), but is **not slashed**. Mitigated by the relay's own block **simulation** (relay side,
   V2) and the **local-build fallback**.
2. **Payment** — the bid value reflects a real payment to the proposer's fee recipient. The value is the
   relay's *signed claim*; the proposer can't see the payment tx in the unseen body (though the blockHash
   binding guarantees the revealed body *is* the committed one).
3. **Revelation / data availability** — the relay actually returns the body at `getPayload`. Withholding =
   *missed slot* (liveness), never theft of a committed block or a slashing.

**Verdict:** mev-boost **minimizes** the trust exactly where it can — relay-signature accountability, parent
coherence, the blockHash body-swap binding, one-sign-per-slot (no slashing), and a local fallback so the
proposer is *never forced* onto a relay — and **names** what remains (validity, payment, revelation), which is
the irreducible PBS trust in the relay. **No finding.** **Residual: the relay** — Ethereum's one genuinely
trusted intermediary, mitigated by relay reputation/accountability (the signature), the optimistic-relay bond
(V2), and the always-available local-build escape hatch. *MEV-THEFT (body swap) and SLASH are closed; the
residual is liveness (a bad relay costs you a slot) and payment-honesty (trusted).*

---

## V2. mev-boost-relay (relay side) — the trusted intermediary, with the one bounded place trust *isn't* verified
**Target:** `flashbots/mev-boost-relay`, `services/api/service.go`, `datastore/redis.go`. The relay's own
view of the V1 trust triangle: it accepts full blocks from builders, serves blinded bids to proposers, and
reveals bodies. **Result: the relay protects honest builders from proposer-equivocation, enforces the same
header→body binding, validates blocks by simulation — and the *one* place it relaxes verification (the
optimistic path) is a deliberate, collateral-bounded trust tradeoff, not a defect. No finding.**

- **Block simulation (INVALID-BLOCK).** The default path **simulates every submission against an EL**
  (`flashbots_validateBuilderSubmission`, concurrency-capped `BLOCKSIM_MAX_CONCURRENT=4`) *before* the bid is
  stored/served — on validation error the bid is **never stored** (`service.go:2534-2554`). This is what makes
  the proposer's V1 "validity" trust justified: the relay did the execution the proposer can't.
- **The optimistic path — the bounded trust relaxation (verified myself).** A bid is served *before*
  simulation **only** under three conjuncts: the builder is flagged `IsOptimistic` **AND** its posted
  `collateral >= bid.Value` **AND** `slot == optimisticSlot`. Simulation runs async; on failure the builder is
  **demoted** (`demoteBuilder:669` sets `IsOptimistic=false`, writes a demotions row for off-chain collateral
  claim) and `getPayload` blocks on the async sim before delivering. So invalid-block risk is **capped at the
  builder's collateral** — the relay trades a verification for latency, bounded by a bond. The residual is
  *operational* (is the posted collateral really backed?), not a code gap.
- **Proposer-equivocation protection — atomic slot-uniqueness (verified myself).** `getPayload` verifies the
  proposer signature + duty + pubkey, then **atomically** records the delivered (slot, blockHash) via a Redis
  `WATCH` optimistic lock `CheckAndSetLastSlotAndHashDelivered` (`redis.go:272-309`): a *second* getPayload for
  the same slot with a **different** blockHash → `ErrAnotherPayloadAlreadyDeliveredForSlot` → 400 (`:294`).
  **The relay reveals exactly one body per slot** — so a proposer can't use the relay to obtain two bodies and
  play builders/relays off each other (the honest-builder protection, the mirror of V1's no-slashing).
- **Header→body binding + bid integrity.** `EqBlindedBlockContentsToBlockContents` requires
  `HashTreeRoot(signed ExecutionPayloadHeader) == HashTreeRoot(revealed payload)` + per-blob KZG equality (the
  relay-side twin of V1's `verifyBlockHash`); the builder's BidTrace is signature-verified against
  `DomainBuilder`, and `ProposerFeeRecipient` must match the registered duty (the *actual* last-tx payment is
  the EL simulator's check). **Builder DoS** bounded: `io.LimitReader(apiMaxPayloadBytes)`, sim concurrency
  cap, blacklist + 200ms tarpit, below-floor/zero-value short-circuit before sim.

**Verdict:** the relay closes MEV-THEFT (HTR binding), SLASH/equivocation (atomic one-body-per-slot), and
default INVALID-BLOCK (synchronous simulation); the optimistic path is a *named, collateral-bounded* relaxation
(the one spot it serves before verifying). **No finding.** **Residual: the relay is trusted** for validity
(except the bonded optimistic window), payment (EL-simulated), and revelation — Ethereum's one trusted
intermediary, exactly as V1 named it from the other side.

## V3. Consensus randomness (Ethereum RANDAO, Algorand VRF) — proof-verified, deterministic, only 1-bit grindable
**Target:** `ethereum/consensus-specs` (`process_randao`, `get_seed`), `algorand/go-algorand`
(`data/committee/credential.go`, `crypto/vrf.go`). Leader election is what consensus *and* PBS rest on: if it's
predictable or grindable, an adversary gets targeted DoS / MEV / reorg leverage. **Result: in both, the
randomness is cryptographically proof-verified before use, the proposer's contribution is *deterministic* (so
it can't be ground — only withheld, the accepted 1-bit bias), and leadership is unpredictable until the slot.
No finding.**

- **Ethereum RANDAO (verified myself).** `process_randao` **asserts `bls.Verify(proposer.pubkey, signing_root,
  body.randao_reveal)` (`beacon-chain.md:1917`) *before* `mix = xor(get_randao_mix(...), hash(randao_reveal))`
  (`:1919`)** — the contribution is a *BLS signature over the epoch*, so a proposer **cannot choose** its
  contribution, only **reveal or withhold**. The seed is read from `epoch - MIN_SEED_LOOKAHEAD - 1` (=N-2,
  `MIN_SEED_LOOKAHEAD=1`, `:266/1072`), giving the designed ~1-epoch lookahead. **Bias is exactly the accepted
  bound:** the last proposer of an epoch can withhold to skip its reveal, choosing between **two** mix outcomes
  = **1 bit per consecutive controlled tail slot** — the code sits *at* that bound, not worse.
- **Algorand VRF sortition (verified myself).** Membership is **VRF-proof-verified before sortition**:
  `selectionKey.Verify(cred.Proof, m.Selector)` (`credential.go:78`) → error if invalid (`:94`) → only then
  `sortition.Select(...)` (`:107`); the per-round **seed proof** is verified *and the seed recomputed*
  (`proposal.go:241/268`, so it can't be self-asserted), and the VRF primitive is IETF ECVRF via libsodium
  `crypto_vrf_verify` (`vrf.go:129`). Each seed is the *deterministic VRF output* of the prior seed under the
  key, so grinding again reduces to the **same 1-bit withholding choice**; leadership requires the secret VRF
  key → **unpredictable until the slot**; the address is hashed into the VRF output to decorrelate same-key
  accounts; stake/key lookback bounds mid-flight committee inflation.

**Verdict:** both are the *proven-not-asserted* discipline at the randomness layer — the entropy is verified
(BLS/VRF) before it influences selection, the contribution is deterministic (grinding-resistant by
construction), and predictability is exactly the designed lookahead. **No finding.** **Residual: the accepted
1-bit last-revealer bias** (RANDAO and VRF-with-withholding alike) — a known, bounded property the code neither
worsens nor pretends away; the deeper fix (VDFs / single-secret-leader-election) is a protocol upgrade, not a
client bug.

## V4. Slashing protection + remote signer (Lighthouse, Web3Signer) — record *before* you sign
**Target:** `sigp/lighthouse` (`validator_client/slashing_protection/`, `lighthouse_validator_store/`),
`Consensys/web3signer` (`slashing-protection/`, `Eth2SignForIdentifierHandler.java`). The last line of
defense against the catastrophic mode: a validator must **never double-sign**. The audit question is the
ordering — is the protection record **committed before the signature is released**? — plus the surround/
monotonic correctness. **Result: both commit-before-sign, both implement EIP-3076 correctly, and interchange
import is raise-only. No finding.**

- **Record-before-sign — the critical ordering (verified myself).** In Lighthouse,
  `check_and_insert_block_proposal(...)` (`lib.rs:471`) opens an **`Exclusive`** SQLite transaction, checks +
  inserts, and **`txn.commit()`s** (`slashing_database.rs:201`) — and only *then*, strictly after, is
  `get_signature(...)` invoked (`lib.rs:489`). Web3Signer does the same: `maySignBlock`/`maySignAttestation`
  `persist()` inside a `jdbi.inTransaction` (per-validator advisory lock) that commits **before**
  `respondWithSignature` releases the signature. **A crash between signing and recording is impossible —
  because the record is durable first.** This is the slashing-protection analog of S1's verify-before-persist:
  *commit the irreversible-action record before you take the irreversible action.*
- **Surround / monotonic correctness (EIP-3076).** Block double-proposal: same-slot/different-root →
  `DoubleBlockProposal`, lower bound `slot <= min_slot`. Attestation: surrounding (`source < ? AND target >
  ?`), surrounded (`source > ? AND target < ?`), double-vote (same target/different root), with min-source
  (`<`) and min-target (`<=`, strict) watermarks. Both clients match the spec exactly.
- **Interchange import is raise-only.** Lighthouse sets watermarks via `max_or(prev, imported)` and runs a
  post-import `monotonic()` consistency check that **rolls back the exclusive txn** if any watermark would
  regress (`NotSafe::ConsistencyError`); Web3Signer updates the low watermark **only when `imported >
  currentWatermark`**. A malicious or buggy interchange file **cannot lower a watermark** to re-open a
  double-sign window.

**Verdict:** the double-sign mode is closed by **ordering** (record commits before signature) plus
**raise-only** monotonic state — the same discipline as the rest of the corpus, applied to the validator's
most dangerous action. **No finding.** **Residual: operational** (the slashing-protection DB must be the
*single* authority for a key — running the same key against two independent DBs defeats it; this is the
doppelganger/duplicate-instance risk, a deployment property the code can't enforce).

---

## Synthesis — the validator's trust surface: minimize what's verifiable, record before the irreversible step
Across the validator's operational layer — **PBS relay (V1/V2), randomness (V3), key management (V4)** — the
result is the corpus's discipline pointed at *what a validator must trust and what it must never do twice*:

1. **Trust is minimized where verifiable, and named honestly where not.** mev-boost verifies everything it can
   (relay signature, parent coherence, the **blockHash body-swap binding**, one-sign-per-slot, a local-build
   fallback) and names the irreducible remainder (the relay is trusted for validity / payment / revelation).
   **The relay is the honest answer to "where is Ethereum's one trusted intermediary"** — and the audit's job
   was to confirm the trust is *minimized to exactly that*, which it is.
2. **Proven, not asserted.** Randomness is **BLS/VRF-verified before it influences selection** (RANDAO
   `bls.Verify` before the XOR-mix; Algorand `VrfPubkey.Verify` before `sortition.Select`), and the
   contribution is *deterministic* so it can't be ground — only withheld, the accepted 1-bit bias.
3. **The catastrophic mode is closed by the *same ordering discipline* everywhere — act-once, record-before-
   release.** One-blinded-header-per-slot (mev-boost), atomic one-body-per-slot at the relay
   (`CheckAndSetLastSlotAndHashDelivered`), and **record-before-sign** in slashing protection (`txn.commit`
   before `get_signature`) are *the same idea*: make the irreversible action idempotent-per-slot and durably
   record it **before** you release it. This is **verify-before-persist (S1) / bound-before-allocate (S6) /
   recompute-before-finalize (C-sweep)** wearing operational clothes.
4. **The residuals are bounded and named:** the relay (mitigated by signature + optimistic-builder collateral
   + the always-available local fallback), the 1-bit RANDAO/withholding bias (a known protocol property,
   fixable only by a protocol upgrade), and the operational single-authority requirement of the
   slashing-protection DB.

**Four operational mechanisms, zero exploitable findings.** It is the **proven-vs-attested axis at the
operational layer**: the validator *verifies* what it can (signatures, bindings, proofs), *records before it
releases* the one action it can never take twice, and *names* the one thing it must trust (the relay). The
snake doesn't sign a tail twice, and it checks the one it's handed before it swallows.

---

## Sweep status
| # | Target | Surface | trust *minimized* where verifiable? | Worst reachable failure mode |
|---|---|---|---|---|
| V1 | mev-boost (proposer) | PBS / relay trust | **yes** — relay sig + parent + **blockHash body-swap binding** + 1-sign/slot + local fallback | SLASH & body-swap **closed**; residual = liveness + payment trust |
| V2 | mev-boost-relay | PBS / relay internals | **yes** — synchronous block sim, atomic **1-body/slot**, HTR header→body binding | optimistic path = **collateral-bounded** invalid-block tradeoff |
| V3 | RANDAO · Algorand VRF | randomness / leader election | **yes** — BLS/VRF **verified before use**, deterministic contribution | only the accepted **1-bit** last-revealer bias |
| V4 | Lighthouse · Web3Signer | slashing protection / signer | **yes** — **record-before-sign** (commit before `get_signature`), raise-only import | double-sign closed by ordering; residual = single-DB-authority |

**Result:** 4 operational mechanisms — **trust minimized where verifiable, the catastrophic (double-sign) mode
closed by the same act-once / record-before-release ordering everywhere, residuals named and bounded** (the
relay, the 1-bit bias, the single-authority DB). Zero exploitable findings.
