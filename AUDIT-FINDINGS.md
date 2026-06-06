# Audit Findings — zk Ecosystem Referenced by the Methodology

**Targets:** the cryptographic libraries and forks named in
[`AUDIT-METHODOLOGY.md`](./AUDIT-METHODOLOGY.md) — `halo2`, `arkworks`,
`bellman`, `plonky2`, `gnark`, `circom`/`circomlib`, and forks descending from
**Zcash, Aztec, PSE, Scroll, Polygon zkEVM, StarkWare**.
**Lens:** the 9-phase methodology.
**Date:** 2026-06-06
**Nature of this report:** a **defensive review of already-public, disclosed,
and (mostly) patched vulnerabilities** — a literature-and-history audit, not a
live penetration test. See [Disclosure posture](#disclosure-posture) below.

---

## Headline

The methodology claims its five highest-ROI areas are conservation equations,
witnessed elliptic-curve points, forked zk code, stale dependencies, and dual
representations of asset identity. **The real disclosure history of these
libraries confirms the claim almost exactly.** Nearly every catastrophic,
real-world zk bug on record falls into one of those five buckets:

| Real bug | Project | Phase that catches it | Bucket |
|----------|---------|-----------------------|--------|
| BCTV14 counterfeiting (CVE-2019-7167) | Zcash/bellman-era | 4 + 6 | conservation / setup |
| Query-collision soundness bug | halo2 (Zcash, PSE, Axiom) | 3 + 9 | witnessed / soundness |
| Frozen Heart (weak Fiat-Shamir) | gnark, SnarkJS, Dusk plonk, bulletproofs | 2 + 9 | trust boundary |
| Groth16 multi-commitment unsoundness (CVE-2024-45039) | gnark | 3 + 5 | witnessed / dual-rep |
| Groth16 commitment not hiding (CVE-2024-45040) | gnark | 5 | dual-rep (ZK loss) |
| Num2Bits(254) aliasing | circomlib | 5 + 4 | dual-rep / range |
| `mul_by_inverse` unsound constraints (RUSTSEC-2021-0075) | arkworks (ark-r1cs-std) | 3 + 6 | witnessed / dep |
| Missing binary constraints, ROM/Storage SM | Polygon zkEVM | 4 | conservation |
| Missing range checks (RLP 0–255), Poseidon overconstraint | Scroll | 4 | conservation |
| Nondeterministic nullifier → double-spend | Aztec 2.0 | 5 | dual-rep |
| Verifier missing EC point validation (identity/zero) | Aztec Plonk verifier | 3 | witnessed point |

The pattern holds: **money is lost at accounting invariants and at witnessed
points, not at the elliptic-curve math itself.**

---

## Phase-by-phase findings

### Phase 1 — Map the Money
The high-value sinks in this ecosystem are: shielded-pool value commitments
(Zcash Sapling/Orchard, Aztec), bridge mint/burn (Polygon zkEVM, Scroll), and
proof-gated state roots. Every catastrophic bug below sits on one of these
paths. **Observation:** the bridges and shielded pools concentrate risk;
proof-system soundness is the single point whose failure mints unbacked value.

### Phase 2 — Trust Boundaries (the Fiat-Shamir frontier)
The prover→verifier transcript is the boundary that has failed most often.
- **Frozen Heart** (Trail of Bits, 2022): a "weak Fiat-Shamir" transform hashes
  only part of the prover's messages, **omitting public inputs/parameters**, so
  a malicious prover forges proofs for arbitrary statements. Confirmed in
  ConsenSys **gnark**, Iden3 **SnarkJS**, Dusk **plonk**, ING **zkrp**, SECBIT
  **ckb-zkp**, Adjoint **bulletproofs**. *Defensive question (Phase 9): "Does the
  challenge hash bind **every** public value before the prover commits?" If not,
  the boundary is broken.*

### Phase 3 — Witnessed Things (points that skip validation)
- **halo2 query-collision bug** (zksecurity): the same polynomial queried at the
  same point twice in the multipoint opening lets a prover forge evaluations.
  Disclosed to **Zcash, PSE, and Axiom**; patched. No production circuit known
  affected — but it lived in widely-forked code.
- **arkworks RUSTSEC-2021-0075**: `FieldVar::mul_by_inverse` in `ark-r1cs-std`
  permitted **unsound R1CS constraint systems**. A witnessed inverse not forced
  to be the true inverse is exactly the "witness touching money" case.
- **arkworks deserialization**: `deserialize_*_unchecked` skips
  subgroup/curve-membership checks. A witnessed point not constrained to the
  prime-order subgroup (`NonIdentityPoint`, cofactor) is a classic small-subgroup
  foothold.
- **Aztec Plonk verifier**: missing EC point validation allowed **proof forgery
  using zero/identity values** — the canonical "is this point actually on the
  curve and non-identity?" miss.

### Phase 4 — Conservation Equations (counterfeiting)
- **Zcash BCTV14 / CVE-2019-7167**: the trusted-setup key generation emitted
  **extra, unused elements**; their presence let a cheating prover bypass a
  consistency check and convert a proof of one statement into a valid-looking
  proof of another — i.e. **counterfeit shielded value**. Found by Gabizon
  (2019), remediated by the Sapling parameters. The exploit required the MPC
  transcript, which was pulled from public availability on discovery. ECC
  believes no counterfeiting occurred. **This is the textbook conservation
  failure.**
- **Polygon zkEVM**: Verichains found a critical bug allowing **counterfeit
  proofs and state manipulation** (fixed on mainnet Dec 2023); the FreeVer tool
  later found 6 soundness + 1 completeness issues; Hexens found criticals rooted
  in **missing binary constraints** in the Storage state machine and ROM.
- **Scroll**: missing range checks (e.g. RLP input bytes not constrained to
  0–255) and a Poseidon overconstraint — the unconstrained-variable family that
  breaks `inputs = outputs`.

### Phase 5 — Dual Representations (the highest-ROI bucket, confirmed)
- **gnark CVE-2024-45040**: the Groth16 commitment is **binding but not
  hiding** — two representations (commitment vs. underlying witness) that were
  supposed to stay opaque don't, letting an attacker **recover private
  witnesses**. ZK property broken; fixed in 0.11.0 (Zellic).
- **gnark CVE-2024-45039**: with ≥2 commitments the prover can fix the first
  commitment **independently of the witness**, learning the in-circuit challenge
  before choosing assignments — a dual-representation/ordering drift that breaks
  soundness. Fixed in 0.11.0.
- **circomlib Num2Bits aliasing**: a value `u` and `u + p` produce the **same bit
  array** under the default 254-bit prime, so two field elements share one
  representation. `Num2Bits(254)`/`Bits2Num` without `AliasCheck`
  (`*_strict`) lets a malicious witness forge a colliding representation.
- **Aztec 2.0 nondeterministic nullifier**: an unconstrained note index makes the
  nullifier (the "already spent" representation of a note) **non-unique**,
  enabling **double-spend**.

### Phase 6 — Dependency History (stale pins)
- The arkworks `mul_by_inverse` flaw (RUSTSEC-2021-0075) is exactly the "pinned
  pre-fix commit" risk: any downstream chain pinning `ark-r1cs-std` below the fix
  inherits unsound constraints.
- bellman-era Groth16/BCTV14 lineage is the genealogical root of Zcash's
  counterfeiting bug — **forks that never re-ran the setup carried the flaw**.
- *Action for any live target:* diff pinned `Cargo.toml`/`go.mod` commits of
  `halo2`, `arkworks`, `gnark` against each library's published security fix
  dates above.

### Phase 7 — Forks (upstream audit invalidated)
- The **halo2 query-collision** bug demonstrates the fork hazard directly: it
  rode along in Zcash's halo2, **PSE's fork**, and Axiom's circuits
  simultaneously. An audit of one fork did not cover the others.
- Polygon zkEVM and Scroll are independent halo2/Plonkish reimplementations;
  each grew **its own** missing-constraint bugs in copied gadget patterns
  (modulo, shift, SMT inclusion) — see the
  [0xPARC zk-bug-tracker](https://github.com/0xPARC/zk-bug-tracker).
- *Action:* identify which gadget files were copied vs. modified, and re-verify
  only the modified constraints (the methodology's exact prescription).

### Phase 8 — Ranking (applied to the real findings)
Using the methodology's scoring table:

| Finding | Money | Conserv. | Witn. pt | Crypto | Old dep | Score |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| Zcash BCTV14 counterfeiting | +5 | +5 | — | +3 | +2 | **15** |
| Polygon zkEVM counterfeit proofs | +5 | +5 | — | +3 | — | **13** |
| gnark CVE-2024-45039 soundness | +5 | +5 | +3 | +3 | +2 | **18** |
| halo2 query collision | +5 | — | +3 | +3 | +2 | **13** |
| circomlib Num2Bits aliasing | +5 | +5 | — | +3 | — | **13** |

The scoring faithfully floats the counterfeiting/soundness bugs to the top —
which is where the real-world impact actually landed.

### Phase 9 — Defensive Questions Only
For every item above, the bug surfaces from a defensive question, never an
exploit:
- *"Does the Fiat-Shamir hash bind all public inputs?"* → Frozen Heart.
- *"Is this witnessed point constrained on-curve and non-identity?"* → Aztec
  verifier, arkworks subgroup checks.
- *"Is each commitment forced to depend on the witness before the challenge?"* →
  gnark CVE-2024-45039.
- *"Can two field elements share one bit representation?"* → circomlib aliasing.
- *"Does the trusted setup emit only the elements the prover needs?"* → Zcash
  BCTV14.

No exploit code is required to find any of them — and none is provided here.

---

## Note on the recent Zcash Orchard disclosure (June 2026)
Public reporting (Tech Times, Crypto Briefing) describes an **AI-assisted audit
that surfaced a multi-year Orchard bug**, prompting an emergency network upgrade
and a sharp ZEC drop. Orchard is halo2-based, which is consistent with the
witnessed-point / soundness families above. **It is already public and being
remediated by the project**, so it is referenced here only at a high level; this
report adds no technical exploitation detail.

---

## Disclosure posture
- **Everything above is already public and disclosed** (CVEs, vendor advisories,
  Trail of Bits / Zellic / zksecurity / Verichains write-ups, the 0xPARC
  tracker). Publishing it on this PR endangers no funds — these are patched or
  publicly known.
- **This pass surfaced no new, undisclosed, live-exploitable vulnerability**, so
  per your instruction there is **nothing being withheld**. The note exists so a
  null result isn't mistaken for an omission.
- **If a fresh catastrophic bug were ever found**, it would go through the
  project's security channel / coordinated disclosure (e.g. the
  bellman-suite, halo2, gnark, or chain bug-bounty programs) — **never a public
  PR** — and **no weaponized proof-of-concept would be written**. The deliverable
  in that case is the defensive description (which invariant fails, where to add
  the constraint), exactly as above.

---

## Sources
- Zcash counterfeiting (CVE-2019-7167): https://electriccoin.co/blog/zcash-counterfeiting-vulnerability-successfully-remediated/
- halo2 query-collision bug: https://blog.zksecurity.xyz/posts/halo2-query-collision/
- Frozen Heart (coordinated disclosure): https://blog.trailofbits.com/2022/04/13/part-1-coordinated-disclosure-of-vulnerabilities-affecting-girault-bulletproofs-and-plonk/
- Frozen Heart in PlonK: https://blog.trailofbits.com/2022/04/18/the-frozen-heart-vulnerability-in-plonk/
- gnark Groth16 advisory (CVE-2024-45039): https://github.com/Consensys/gnark/security/advisories/GHSA-q3hw-3gm4-w5cr
- gnark commitment bugs (Zellic): https://www.zellic.io/blog/gnark-bug-groth16-commitments/
- circomlib Num2Bits / AliasCheck: https://rareskills.io/post/circom-aliascheck
- Circom pitfalls (zksecurity): https://blog.zksecurity.xyz/posts/circom-pitfalls-1/
- 0xPARC zk-bug-tracker: https://github.com/0xPARC/zk-bug-tracker
- Polygon zkEVM critical bug (Verichains): https://blog.verichains.io/p/discovering-and-fixing-a-critical
- FreeVer automated soundness vetting (USENIX Security '25): https://www.usenix.org/system/files/usenixsecurity25-peng-xinghao.pdf
- arkworks RUSTSEC-2021-0075: https://rustsec.org/advisories/RUSTSEC-2021-0075.html
- SoK: Security Vulnerabilities in SNARKs: https://arxiv.org/pdf/2402.15293
- Zcash Orchard disclosure (June 2026, public reporting): https://www.techtimes.com/articles/317831/20260605/why-crypto-crashing-ai-assisted-audit-exposes-four-year-zcash-orchard-bug-zec-plummets-31.htm
