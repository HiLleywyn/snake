# Validator operations — the trust surface beyond consensus

Three sweeps so far have walked inward: bridges (trusting *another chain's* summary), state-sync (trusting a
*peer's* summary of your own chain), consensus (trusting *no participant* — recompute the fork choice). This
one is the **operational and economic** surface a validator carries that the consensus rules don't cover:
**the MEV/PBS relay it trusts to build its blocks, the randomness that decides when it leads, and the keys it
must never let leak or double-sign.** Where consensus asked *"can the protocol be broken,"* this asks *"can
the validator be **exploited** — robbed of MEV, slashed, key-compromised, or have its leadership predicted."*

## The threat model (what an adversary — relay, builder, co-validator, or peer — is trying to cause)

| # | Failure mode | Severity | Who |
|---|---|---|---|
| **MEV-THEFT** | proposer's block is **unblinded/stolen** or the proposer is **not paid** the bid | severe | a malicious **relay** or **builder** |
| **SLASH** | validator is induced to **double-sign** (equivocate / get slashed) | catastrophic for that validator | a relay serving two payloads; a key/DB race; a doppelganger |
| **GRIND/BIAS** | leader election (RANDAO/VRF) is **biased or predicted**, enabling targeted DoS / MEV / reorg | severe | the **last revealer**; a grinding adversary |
| **KEY-COMPROMISE** | the signing key leaks or the **remote-signer** boundary is bypassed | catastrophic | a compromised signer / network position |
| **INVALID-BLOCK** | an **optimistic relay** forwards an unsimulated/invalid block the proposer signs | severe | a malicious builder + a relay that skipped validation |

## The lens (adapted to the validator's trust surface)

> **(Q1) What does the validator have to *trust*, and is that trust *minimized* (verified) or *assumed*?**
> (the relay is the canonical "trusted intermediary" — does the proposer verify anything, or just trust it?)
>
> **(Q2) Can a single counterparty (relay / builder / co-proposer / signer host) make the validator lose
> funds, get slashed, or be singled out?**

Per-target checklist:
- **PBS trust triangle** — proposer ↔ relay ↔ builder. The relay's job is to let a proposer commit to a
  *blinded* header and only reveal the body on a signed commitment. Audit: is the bid **signed by the relay**
  and checked? is the header→payload binding enforced at `getPayload`? does the relay **simulate** the block
  (or is it *optimistic*, trusting the builder)? what stops the proposer being shown a header whose body is
  invalid or unpayable?
- **Proposer-equivocation / unbundling** — can a relay/builder get the proposer to sign two blocks, or release
  the body to a competitor before the proposer is committed (MEV theft)?
- **Payment enforcement** — is the proposer-payment a *consensus-enforced* transfer in the block, or a relay
  *promise*? (the difference between trustless and trusted).
- **Randomness** — RANDAO last-revealer bias (a proposer can withhold to bias the next mix by 1 bit ×
  consecutive slots) and VRF leader election (Algorand sortition, Cardano Praos, Solana) — is leadership
  **unpredictable until the slot** and **un-grindable**? proof-verified, not self-asserted?
- **Key management** — slashing-protection DB (monotonic min-slot/min-epoch, import/export interchange),
  doppelganger detection, the remote-signer (web3signer) request authentication + the slashing-protection
  ordering (is protection recorded *before* the signature is returned?).

## Posture
Defensive; read-only; public source only. No exploit, no PoC. A genuinely exploitable defect that lets a relay
slash/rob a proposer, or makes leader election grindable, → **stopped and reported privately**, redacted here.
The aim is **characterization**: name what the validator trusts, and locate where that trust is *verified*
versus merely *assumed* (the relay is the honest answer to "where is Ethereum's one trusted intermediary").

## Index
*(populated as the sweep runs — MEV-Boost proposer, the relay, RANDAO/VRF, key management)*
| File | What it is |
|---|---|
| _VX entries land here_ | |
