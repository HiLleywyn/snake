# Cryptographic primitives — where every client must agree, bit-for-bit

The bottom of the stack. Every sweep so far trusted *something* it could verify with a primitive — a
signature, a Merkle proof, a KZG opening, a pairing. This one audits **the primitives themselves**: the EVM
precompiles (ecrecover, modexp, bn256, blake2F, point-evaluation/KZG, BLS12-381) and the curve/field/pairing
operations underneath. Here the threat model inverts one more time: it is not *"does the code trust an
unverified summary"* — it is *"does the verifier itself compute the right answer, the same answer on every
client, and reject every malformed input the same way."*

## The threat model (what a crafted input to a primitive is trying to cause)

| # | Failure mode | Severity | The classic cause |
|---|---|---|---|
| **DIVERGE** | two clients compute the **same primitive differently** → consensus split | **catastrophic** | a field/curve edge case (point-at-infinity, exponent overflow, gas rounding) one client handles differently |
| **FORGE** | an **invalid** signature / proof / pairing is **accepted** | **catastrophic** | a **missing subgroup check** (point on curve but not in the prime-order subgroup), a point-at-infinity bypass, malleability |
| **DoS** | a small input forces **unbounded** computation | severe | modexp with a huge exponent, a pairing with many points, mis-metered gas |
| **MALLEABLE** | a **non-canonical** encoding is accepted (two encodings → one value, or worse, → two) | severe | a field element `>= modulus`, a non-reduced scalar, a high-`s` ECDSA signature |

The defining constraint of this layer: **the EVM and the consensus layer are *deterministic by requirement* —
every client must produce the identical output (or the identical rejection) for every input, or the chain
splits.** So a crypto bug here is the MemeCore lesson at its most acute: the substrate gives the primitives no
slack at all.

## The lens (adapted to the primitive layer)

> **(Q1) Is every malformed input *rejected*, deterministically and identically — on-curve, in-subgroup,
> canonical-encoding, length-exact?** (the forgery/malleability question)
>
> **(Q2) Is the computation *bounded* (gas-metered to its real cost) and *bit-for-bit reproducible* across
> clients?** (the DoS / divergence question)

Per-primitive checklist:
- **Subgroup membership** — for bn256/BLS12-381, is every input point checked to be in the **prime-order
  subgroup**, not merely on the curve? (the single most dangerous omission in pairing-based crypto)
- **Point/field validity** — on-curve check, field elements `< modulus` (canonical), point-at-infinity handled
  per spec, exact input length / zero-padding rules.
- **ECDSA** — `ecrecover` rejects `v`/`r`/`s` out of range and (where required) high-`s` malleability; recovers
  `0` correctly rejected.
- **Gas vs cost** — modexp (EIP-2565), bn256 pairing (per-point), BLS (per-pairing) — does the gas formula
  bound the worst case, with the exact rounding every client shares?
- **KZG / EIP-4844** — the trusted-setup load, `verify_kzg_proof`, the canonical field-element check on the
  evaluation point/claimed value, the versioned-hash binding.
- **Cross-client determinism** — geth (Go) vs reth/revm (Rust) vs the spec: do they agree on every edge case
  (the only way to *know* is to compare the rejection conditions)?

## Posture
Defensive; read-only; public source only. No exploit, no PoC. A genuinely exploitable defect (a forgery via a
missing subgroup check, a cross-client divergence) → **stopped and reported privately**, redacted here. The aim
is **characterization**: confirm each primitive rejects the malformed-input classes, is gas-bounded, and
matches across clients — because at this layer "trust" has nowhere left to go: the primitive either computes
the truth or it doesn't.

## Index
*(populated as the sweep runs — geth precompiles, BLS12-381, KZG/4844, reth/revm cross-check)*
| File | What it is |
|---|---|
| _PX entries land here_ | |
