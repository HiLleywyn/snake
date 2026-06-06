# Bridges Through the Six-Bucket Lens — The Generalization Test

**Targets:** Wormhole (`wormhole-foundation/wormhole`), LayerZero v2
(`LayerZero-Labs/LayerZero-v2`), Hyperlane (`hyperlane-xyz/hyperlane-monorepo`),
all @ latest default branch. **The question:** bridges should be *almost pure
bucket 6*. If the six-bucket model (and the 6a/6b split) classifies them cleanly
and **explains their design space**, then this is no longer a "zk methodology" —
it is a general **high-assurance systems review heuristic**. **No exploit
search.** Verdicts: enforced (in-contract) / trusted-by-architecture /
trusted-by-implementation.

---

## Result

**The model generalizes — and bridges are the *limiting case* of bucket 6.** A
bridge connects two systems that, by construction, **cannot observe each other**:
the destination chain has no access to source-chain state. So "what happened on
the source" must be *imported* by a third party. That makes bucket 6 not merely
present but **definitional**, and — because there is no single system deferring to
another within itself — it is **pure 6b** (interpretation/equivalence), with **no
6a** to retire. The on-chain contract enforces representation-equivalence,
threshold, and replay; the **irreducible core** ("did the attesters correctly
observe the source?") is delegated by trust.

---

## The three protocols are structurally identical at the core

All three are: *a configurable/trusted set of off-chain attesters observes the
source and signs a commitment to the message; the destination contract verifies a
threshold of attestations against that set and re-derives the message hash.*

| Protocol | Attester set | Destination verify | File |
|---|---|---|---|
| **Wormhole** | 19 Guardians (governance-rotated) | recompute `keccak256(keccak256(body))`, require `≥quorum` guardian sigs | `Messages.sol:50-98` |
| **Hyperlane** | per-domain Validator m-of-n, **chosen by the recipient's ISM** | recompute `digest`, require `≥threshold` validator sigs | `AbstractMultisigIsm.sol:95-123`; `Mailbox.sol:221,410-416` |
| **LayerZero v2** | DVN set (required + optional), **chosen by the OApp** | all required DVNs + `≥optionalThreshold` optional DVNs attested `(headerHash, payloadHash)` | `ReceiveUlnBase.sol:90-116` |

---

## Concentration-by-concentration classification

### C1 — Message representation equivalence (source body ↔ signed commitment ↔ destination)
**Bucket 3/6b · Enforced in-contract.**
The destination **re-derives** the committed hash and binds the attestation to it:
Wormhole recomputes `keccak256(keccak256(body))` and rejects on `!= vm.hash`
(`Messages.sol:50-66`, with the comment flagging this as *critical*); Hyperlane
recomputes `digest(metadata, message)` (`AbstractMultisigIsm.sol:99`); LayerZero
keys verification on `keccak256(packetHeader)` + `payloadHash`
(`ReceiveUlnBase.sol:43-44,90`). **Enforced** — but note this binds representation
*within the attestation*, not to source truth (see C4).

### C2 — Attestation threshold verification
**Bucket 6 · Enforced in-contract.**
Signature/attestation recovery + threshold counting against the configured set:
Wormhole `quorum` + `verifySignatures` ordered ecrecover (`Messages.sol:90-98`);
Hyperlane two-pointer m-of-n match (`:109-121`); LayerZero "all required + optional
threshold" (`ReceiveUlnBase.sol:96-116`). **Enforced.**

### C3 — Replay / single-delivery (the conservation analog)
**Bucket 1 · Enforced in-contract.**
Each message is consumed once: Wormhole `completedTransfers[vm.hash]` /
`require(!isTransferCompleted)` (`NFTBridge.sol:113-114`; same in the token
bridge) and `consumedGovernanceActions[hash]` (`Setters.sol:30`); Hyperlane
`require(delivered(_id) == false)` (`Mailbox.sol:217`); LayerZero strictly-ordered
`lazyInboundNonce[receiver][srcEid][sender]` (`MessagingChannel.sol`,
`EndpointV2.sol:154`). **Enforced.**

### C4 — Source observation (the actual security)
**Bucket 6b · Trusted by architecture — IRREDUCIBLE, and dominant.**
The destination can verify the message is internally consistent (C1) and was
signed by ≥threshold of the trusted set (C2) — but it **cannot verify the message
reflects a real source-chain event.** That binding is delegated entirely to the
attesters' off-chain observation. This is the whole security of the bridge, and
it is **not on-chain.** Verdict: **trusted by architecture.**

### C5 — Trusted-set governance / configuration
**Bucket 6 · Trusted by architecture/configuration.**
The trust ultimately bottoms out in *who picks the attester set*: Wormhole rotates
the Guardian set via a governance VAA signed by the current Guardians
(`Setters.sol:9`, guardian-set upgrade); Hyperlane lets the **recipient app**
choose its ISM (`Mailbox.sol:221` `recipientIsm`); LayerZero lets the **OApp**
choose its `UlnConfig` DVNs. The contract enforces verification *given* the set;
the **choice of set is the trust root.** Verdict: **trusted by
architecture/configuration.**

---

## Why this is the sharpest confirmation of the 6a/6b model

Recall the AVM result: *proving converts 6a into 6b; it does not abolish bucket 6.*
Bridges are the clean limit of that statement.

- A **committee bridge** (all three here) discharges the irreducible C4/6b by
  **trust** — a threshold of a trusted set vouches for source-truth.
- A **light-client / zk bridge** discharges the *same* C4/6b by **proof** — but per
  the AVM result, the light-client circuit is *one encoding of the source chain's
  consensus rules*, which must still **agree with the source chain's actual
  rules**. That is exactly 6b ("does the encoding match intent"), now between the
  verifier circuit and the source's consensus.

> **You cannot make a bridge trustless; you can only choose how to discharge the
> irreducible 6b** — trust a committee, or trust that a light-client/zk encoding
> faithfully represents the source. Proof *relocates* the agreement (committee →
> circuit-vs-consensus); it does not remove it. The destination chain's inability
> to observe the source is a hard information boundary, and 6b is the name for what
> lives on it.

This is why the lens *explains* the bridge design space rather than merely
labeling it: the entire committee-vs-light-client-vs-zk taxonomy is "different
discharges of the same irreducible C4/6b."

---

## Comparative table

| Protocol | Dominant bucket | C4 discharge | Enforced in-contract | Trust root |
|---|---|---|---|---|
| **Wormhole** | 6b | trust (19 Guardians, ≥13) | hash-bind, quorum sigs, VAA-hash replay | Guardian set + governance VAA |
| **Hyperlane** | 6b | trust (recipient-chosen m-of-n validators) | digest, m-of-n, `delivered` id | recipient's ISM choice |
| **LayerZero v2** | 6b | trust (OApp-chosen DVNs) | payloadHash match, required+optional threshold, ordered nonce | OApp's `UlnConfig` |

All three: **C1/C2/C3 enforced in-contract; C4/C5 trusted by
architecture/configuration.** Identical shape; they differ only in *who configures
the trusted set* (a global governance vs. the recipient vs. the application).

---

## Conclusion — it's no longer a zk methodology

The six-bucket model classified three non-(primarily-)zk protocols cleanly,
located their dominant concentration (bucket 6b) without a single exploit
question, and the **6a/6b split was explanatory**: it pinpointed *why* bridges
cannot be made trustless and *what* the committee/light-client/zk choice actually
is (alternative discharges of one irreducible interpretation seam). Combined with
the six chains, the framework now spans pure-zk, hybrid, and committee-based
high-assurance systems with the same vocabulary.

> **The frontier of high-assurance systems is not "prove more." It is "manage the
> agreements you cannot prove away."** Bucket 6 — specifically 6b — is the
> permanent residue, and a review heuristic that locates it is a general systems
> tool, not a zk-specific one.

## Disclosure posture
Defensive, structural reading of public code at the default branches; no exploit,
no PoC, no vulnerability claimed or disclosed. The "trusted by architecture" items
are the **documented, intended security model** of each protocol (a trusted
attester set), not a defect.

## Files reviewed
Wormhole `ethereum/contracts/{Messages.sol, Setters.sol, nft/NFTBridge*.sol}`;
Hyperlane `solidity/contracts/{Mailbox.sol, isms/multisig/AbstractMultisigIsm.sol}`;
LayerZero `evm/messagelib/contracts/uln/ReceiveUlnBase.sol`,
`evm/protocol/contracts/{EndpointV2.sol, MessagingChannel.sol}`.
