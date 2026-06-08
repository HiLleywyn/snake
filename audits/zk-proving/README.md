# Proving-system soundness — does the verifier accept only the truth?

One layer below the precompiles (`../crypto-primitives/`). Those audited whether a *given* primitive computes
the right answer; this audits the **proving systems** that decide whether an entire *computation* was done
correctly — the zkVMs (SP1, RISC Zero, Jolt) and the proof backends (Plonky3/FRI, Halo2, Groth16/Plonk) that
roll up a whole execution into one proof a chain can verify cheaply. The threat model is the most fundamental
one in the stack: **can a malicious prover convince an honest verifier of a *false* statement?**

## What's honestly auditable here (and what isn't)

Full **soundness** — "no prover can forge a proof of a false statement except with negligible probability" —
is a *cryptographic* property established by security proofs and, increasingly, formal verification. A source
read cannot re-derive that. **But the historical breaks were never the deep math** — they were
**implementation gaps in well-understood, checkable places.** This sweep audits exactly those:

| # | Failure mode | Severity | The historical cause (real, named) |
|---|---|---|---|
| **SOUNDNESS** | a proof of a **false** statement is accepted | **catastrophic** (forge any state transition) | — |
| **FROZEN-HEART** | Fiat-Shamir challenge **not bound to all commitments/public inputs** → forge | catastrophic | the 2022 "Frozen Heart" class (PlonK/Bulletproofs/etc.) — a challenge squeezed *before* a commitment is absorbed |
| **UNDER-CONSTRAINED** | a constraint is **missing**, so a malicious witness is free | catastrophic | the #1 ZK bug class (Tornado, countless Circom audits) |
| **INPUT-BINDING** | the proof isn't tied to the **claimed public values / vkey / journal** | catastrophic | a verifier that checks a valid proof but of the *wrong* statement |
| **PARAM** | too-few FRI queries / wrong soundness parameter | severe | a security-parameter set below the target bits |

## The lens (adapted to proof systems)

> **(Q1) Is the Fiat-Shamir transcript *honest*** — is **every** commitment, every prior message, and **every
> public input** absorbed into the transcript **before** the challenge that depends on it is squeezed? (the
> Frozen-Heart / weak-Fiat-Shamir question — the most common real break)
>
> **(Q2) Is the proof *bound to the exact statement*** — the vkey/program-image, the public values/journal, the
> claimed output — so a valid proof of a *different* computation can't be passed off? (the input-binding
> question)

Per-target checklist:
- **Fiat-Shamir / the challenger** — observe-before-sample: are commitments observed into the duplex sponge
  *before* challenges are drawn? are public values and the vkey hashed in? is the transcript domain-separated?
- **Public-input / vkey / journal binding** — the verifier ties the proof to the committed program and the
  claimed I/O (SP1 `programVKey` + `publicValuesDigest`; RISC Zero `imageID` + journal; Groth16 public inputs).
- **FRI / low-degree test** — the number of queries (soundness bits), the proof-of-work grinding bits, the
  folding-challenge derivation, the final-polynomial degree check.
- **Constraint completeness (where readable)** — boundary + transition constraints, the lookup/permutation
  arguments, the quotient identity — is anything an honest reading shows *unconstrained*?
- **Recursion** — the recursive verifier circuit faithfully re-checks the inner proof; the aggregation vkey.

## Posture
Defensive; read-only; public source only. No exploit, no PoC. A genuinely exploitable soundness defect (a
weak-Fiat-Shamir forge, an unbound public input, an under-constrained gate) in live software → **stopped and
reported privately**, redacted here. The aim is **characterization** of the implementation-level
soundness-critical properties — *honest about the line between what a source read can confirm (the transcript
absorbs everything before it samples; the proof is bound to the statement) and what only a security proof can
(the scheme is sound).*

## Index
*(populated as the sweep runs — Plonky3/FRI Fiat-Shamir, SP1, RISC Zero, …)*
| File | What it is |
|---|---|
| _ZX entries land here_ | |
