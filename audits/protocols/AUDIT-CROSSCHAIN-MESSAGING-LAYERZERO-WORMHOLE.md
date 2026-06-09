# Cross-chain messaging — configurable trust vs monolithic quorum (LayerZero v2 vs Wormhole)

**Scope.** The two dominant generic cross-chain messaging layers: LayerZero v2 (`LayerZero-Labs/
LayerZero-v2` @ `9c741e7`, the configurable DVN security stack) and Wormhole core (`wormhole-
foundation/wormhole` @ `6cc8db2`, the monolithic guardian set). This generalizes the cross-chain
*attestation residual* the corpus already saw in Across (optimistic) and connects directly to the §5g
oracle finding (Pyth *is* a Wormhole consumer). Public source, read-only, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No exploitable defect found**; the configurable-trust footguns
and the single-global-quorum concentration are characterized factually.

**Sources read (verbatim, line refs):** LayerZero `EndpointV2.sol`, `MessagingChannel.sol`, `GUID.sol`,
`uln/uln302/ReceiveUln302.sol`, `uln/ReceiveUlnBase.sol`, `uln/UlnBase.sol`; Wormhole `Messages.sol`,
`Implementation.sol`, `Governance.sol`, `Setters.sol`.

---

## 0. The one-paragraph result

A generic cross-chain message has the same irreducible residual as every bridge: **nothing on the
destination chain can *prove* what happened on the source chain — some off-chain party must attest it.**
Both protocols accept this and differ on exactly one axis, which defines the entire design space: **who
chooses the attestor.** Wormhole centralizes it — **one global ~19-member guardian set**; a message of
any kind is authentic iff **≥13** guardians signed its hash off-chain, and *the same quorum* governs
message attestation, guardian-set rotation, fee changes, **and core-contract upgrades**. Every consumer
(including Pyth, the token bridge, the NFT bridge) inherits *exactly* that 13/19, so a quorum compromise
forges arbitrary messages for **everyone at once** and can even self-upgrade the core. LayerZero v2
**decentralizes the choice to each application**: an OApp configures its own `UlnConfig` —
`requiredDVNs[]` (all must attest) plus `optionalDVNs[]` with a threshold — so trust is *per-app,
per-source-chain, heterogeneous*, with a LayerZero-Labs-set **default** (publicly, the LZ-Labs DVN +
Google Cloud DVN) that apps silently inherit until they override. The trade is sharp and is the whole
finding: Wormhole's risk is **systemic** (one quorum under everything, also its own upgrade authority);
LayerZero's risk is **per-app and self-inflicted** (the only protocol-enforced floor is "≥1 DVN," so an
app can legally configure 1-of-1 trust or hand its entire security stack to a single `delegate` key). So
the messaging law: *the cross-chain attestation residual is unavoidable; you can make it a fixed global
quorum (Wormhole — simple, uniform, catastrophically correlated) or an app-configurable stack
(LayerZero — flexible, heterogeneous, only as strong as each app's own config) — and this is the §5f
own-vs-delete dial applied to the attestor itself.*

---

## 1. The shared shape — emit on source, verify-attestation-then-deliver on destination

Both reduce to: source chain *emits* a message and does **no verification**; the destination chain
delivers it **only after** the configured off-chain attestor(s) have vouched for the exact payload hash.

**LayerZero** (`EndpointV2.sol`): `send()` (`:83-144`) just delegates to the app-selected send library
and emits `PacketSent` for off-chain DVNs/executors to observe (`:141`); the GUID binds
`(nonce, srcEid, sender, dstEid, receiver)` (`GUID.sol:10-18`). Delivery is gated by `verify()`
(`:151-161`, callable *only* by the app's configured receive library) which writes the verified
`payloadHash` into the channel, and `lzReceive()` (`:172-183`) re-hashes `keccak256(guid‖message)` and
**requires it to equal the stored verified hash** (`MessagingChannel.sol:145-147`, cleared-before-call
for reentrancy safety). Nonces are *unordered for verification* but *gapless/in-order for execution*
(`_clearPayload:126-151`).

**Wormhole** (`Implementation.sol`): `publishMessage (:15-26)` charges the fee and emits
`LogMessagePublished` — **the EVM core never verifies an outbound message; all attestation is off-chain
by the guardians.** Delivery (on the consumer side) calls `parseAndVerifyVM` → the guardian check.

**Characterization:** identical skeleton — *the contracts move the payload hash; an off-chain set vouches
for it.* Everything interesting is in *who that set is and who picks them.*

---

## 2. LayerZero — the app picks its own verifiers. **Configurable, heterogeneous trust.**

The heart is `_checkVerifiable` (`ReceiveUlnBase.sol:90-124`): the message is verifiable iff **every**
`requiredDVN` has attested the exact `(headerHash, payloadHash)` at sufficient `confirmations`, **and**
`optionalDVNThreshold`-many optional DVNs have:
```solidity
for (i in requiredDVNs)   if (!_verified(requiredDVNs[i], ...)) return false;  // ALL required must attest (:97-99)
for (i in optionalDVNs)   if (_verified(optionalDVNs[i], ...)) { threshold--; if (threshold==0) return true; } // :111-114
```
Each DVN attests independently (`ReceiveUlnBase._verify:43-46` writes `hashLookup[...][msg.sender]`). The
config (`UlnBase.sol:8-16`) is `{confirmations, requiredDVNCount, optionalDVNCount, optionalDVNThreshold,
requiredDVNs[], optionalDVNs[]}`, resolved per OApp per source-EID by `getUlnConfig (:74-118)`: a `0`
count means *inherit the owner-set DEFAULT*; a non-zero count *overrides*; `NIL_DVN_COUNT` lets an app
override down to none. **The only protocol-enforced floor is `_assertAtLeastOneDVN` (:117) — at least one
DVN, anywhere.**

**Characterization + factual flags:** trust is **app-configurable, not protocol-fixed** — the strongest
expression of "you choose your own security stack" in the corpus. But:
1. **Default-DVN inheritance:** an app that never sets a config inherits whatever the privileged owner put
   in DEFAULT (`setDefaultUlnConfigs`, `onlyOwner`) — publicly the LZ-Labs + Google Cloud DVNs. Apps
   *silently* inherit owner-controlled defaults.
2. **No diversity floor:** an app can legally configure **1-of-1** required DVN, collapsing security to a
   single verifier; there is no protocol-mandated minimum count or independence requirement.
3. **The delegate key:** `setDelegate (EndpointV2:327-330)` can reconfigure an app's entire DVN set — a
   single point of trust over that app's security. The configurability that is LayerZero's strength is
   also its footgun: *misconfiguration is an app-level vulnerability the protocol won't prevent.*

---

## 3. Wormhole — one global quorum for everything. **Monolithic, correlated, self-governing.**

`verifyVMInternal (Messages.sol:40-102)` keys off a single global guardian set by `vm.guardianSetIndex`
(`:42`); `quorum (:213-217)` is `floor(2N/3)+1` (N=19 → **13**); `verifySignatures (:111-141)` ecrecovers
each sig, rejects zero recovers, enforces strictly **ascending guardian index** (dedup), and requires an
exact key match (`:134`). The VM hash is a double-keccak of the body (`:51-65`).

The concentration is the finding: **the same guardian quorum governs everything.** `verifyGovernanceVM
(Governance.sol:190-220)` reuses `verifyVM` for guardian-set rotations (`submitNewGuardianSet:79-112`,
index must be exactly `current+1`) **and core-contract upgrades** (`submitContractUpgrade:27-49` →
ERC1967 `_upgradeTo` + `delegatecall initialize`). So 13/19 guardians can forge any message, rotate
themselves, and **swap the entire core implementation**.

**Characterization + factual flags:**
1. **Single global point of trust:** no per-app choice — *every* consumer (Pyth, token bridge, NFT
   bridge) inherits the same 13/19; a quorum compromise forges for **all downstream apps simultaneously**
   and can self-upgrade.
2. **24h overlap window:** after rotation the superseded set stays valid until `expirationTime = now +
   86400` (`Setters.sol:13-15`), so a compromised *old* set retains forging power for a day.
3. **Version not hashed:** `Messages.sol:152-157` self-documents that `vm.version` integrity is
   unprotected (safe today with one accepted version).

---

## 4. The contrast — the own-vs-delete dial applied to the attestor

| | LayerZero v2 | Wormhole |
|---|---|---|
| **Trust unit** | per-app, per-source-EID `UlnConfig` | one global guardian set |
| **Who picks verifiers** | the app / its `delegate` | protocol-fixed; no app choice |
| **Authenticity rule** | all required DVNs + N optional attest the payloadHash | ≥⌊2N/3⌋+1 guardians sign the VM hash |
| **Governance** | owner sets DEFAULT config / libs | **same quorum** signs price/rotation/upgrade |
| **Single-point risk** | **per-app**: a 1-DVN app or captured delegate | **systemic**: one quorum forges for all + self-upgrades |

LayerZero externalizes the trust decision to each app (configurable, heterogeneous, owner-set default
fallback); Wormhole centralizes it in one fixed global quorum that is simultaneously the attestor and its
own upgrade authority. **Neither removes the residual** — a cross-chain message *must* be vouched for off
-chain — they just locate the trust differently: LayerZero spreads it (and the risk of getting it wrong)
across apps; Wormhole concentrates it (and correlates the risk) in one set.

---

## 5. Where this sits in the corpus

This is the **bridge/cross-domain** residual (the sixth bucket) opened to its mechanism, and it closes a
loop with two earlier audits. Against **Across** (§5f): Across uses an *optimistic* attestation (a bonded
proposer + a UMA dispute window + the canonical bridge), Wormhole uses a *signed-quorum* attestation, and
LayerZero uses a *configurable-quorum* attestation — three points on the "who attests the remote event"
axis, mirroring the prediction-market oracle spectrum exactly (optimistic ↔ committee ↔ configurable).
Against the **oracle audit** (§5g): Wormhole *is* the quorum under Pyth, so the finding that "the oracle
residual is a multisig, often a *shared* one" is here shown to extend to *messaging* — the same 13/19
sits under Pyth prices **and** Wormhole-bridged assets, so a protocol that uses both has a *single*
correlated point, not two independent ones. And it confirms the own-vs-delete dial one more time, now at
the attestor: LayerZero **delegates** the trust choice to each app (flexible, only as safe as the app's
config), Wormhole **owns** it as a fixed quorum (uniform, correlated, self-governing). The honest
integrator statement: *your cross-chain message is authentic iff your chosen attestors say so — for
Wormhole that's a global 13/19 you don't control and that can upgrade itself; for LayerZero it's whatever
DVN set your app (or its delegate, or the default) configured, with no protocol floor beyond "at least
one."*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
