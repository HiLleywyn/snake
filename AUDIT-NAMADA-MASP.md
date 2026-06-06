# Namada MASP — Dual-Representation & Conservation Review

**Target:** `github.com/anoma/masp` @ `b2b0f61` (HEAD 2026-03-26), crates
`masp_primitives` and `masp_proofs`. This is the multi-asset, Sapling-descended
shielded pool used by Namada (Groth16 / bellman over BLS12-381 / Jubjub).
**Question asked:** trace asset identity from the canonical asset ID into note
commitments, value commitments, nullifiers, and the balance/conservation
equation; for each representation, name the **exact** constraint or deterministic
derivation that forces equivalence; mark anything assumed by type/comment/test
rather than a circuit constraint as **constraint debt**.
**Conclusions use only this vocabulary:** *enforced by constraint X* /
*deterministically derived at Y* / *unclear, needs human review* / *not enforced
in reviewed path*. The word "safe" is not used unless tied to an exact
constraint.
**No exploit code.** Remediation suggestions only. See [Disclosure
posture](#disclosure-posture).

---

## 1. Asset identity exists in three representations

| # | Representation | Type | Where it is used |
|---|----------------|------|------------------|
| R1 | canonical asset ID (32 bytes) | `AssetType.identifier` | `asset_type.rs:21` |
| R2 | asset generator, cofactor **not** cleared | `jubjub::ExtendedPoint` | note commitment + cv base witness |
| R3 | value-commitment generator, cofactor **cleared** | `jubjub::SubgroupPoint` | homomorphic value commitment + value balance |

The conservation system depends on these three never drifting apart, and on the
per-asset R3 generators being mutually discrete-log-independent.

---

## 2. Edge-by-edge trace (with exact conclusions)

### R1 → R2 (ID to uncleared generator)
- **Host:** *deterministically derived at* `asset_type.rs:70-102`
  (`hash_to_point` = `ExtendedPoint::from_bytes(BLAKE2s(id,
  VALUE_COMMITMENT_GENERATOR_PERSONALIZATION))`, rejecting off-curve and
  small-order images).
- **Output circuit:** *enforced by constraint* `circuit/sapling.rs:475-483` — the
  witnessed generator's compressed encoding is bit-for-bit `enforce_equal` to the
  in-circuit `blake2s(asset_identifier)` image (`circuit/sapling.rs:452-456`),
  and the witnessed point is forced on-curve by `EdwardsPoint::witness`
  (`circuit/ecc.rs:130-143`). Net: in an Output, R2 is the unique on-curve point
  whose encoding equals `BLAKE2s(R1)` — matches the host map exactly.

### R2 → R3 (cofactor clearing)
- **Host:** *deterministically derived at* `asset_type.rs:129-131`
  (`clear_cofactor`) and `sapling.rs:214` (cv uses `clear_cofactor(asset_generator)`).
- **Circuit:** *deterministically derived at* `circuit/sapling.rs:88-93` (three
  in-circuit doublings = ×8) inside `expose_value_commitment`, with the cleared
  base forced non-identity by `circuit/sapling.rs:99-101`
  (`assert_nonzero` on `u`). Since clearing is linear, the same witnessed R2
  feeds both the note (R2 bits) and the cv (R3) — no drift within a circuit.

### R2 → note commitment
- **Host:** *deterministically derived at* `sapling.rs:804-832` (`cm_full_point`
  hashes `asset_generator().to_bytes()` ‖ value ‖ g_d ‖ pk_d under a Pedersen
  hash).
- **Circuit:** *enforced by constraint* — the same `asset_generator_bits` used in
  cv are placed into `note_contents` (`circuit/sapling.rs:266` for Spend,
  `:486` for Output) and Pedersen-hashed (`:287` / `:564`). The note therefore
  binds R2, and the cv uses R3 derived from that same R2.

### R3 → value commitment (the homomorphism)
- *deterministically derived at* `sapling.rs:212-216`:
  `cv = clear_cofactor(asset_generator)·value + H·rcv`. In-circuit the identical
  relation is built in `expose_value_commitment` (`circuit/sapling.rs:110-131`)
  and the resulting `cv` is exposed as a public input (`:134`), so the `cv`
  later summed by the verifier is exactly the circuit-validated one.

### asset ID → nullifier
- *deterministically derived at* `sapling.rs:836-853`: `nf = BLAKE2s(nk ‖ rho)`,
  `rho = cm_full_point + position·G`. The nullifier binds the asset only
  transitively through `cm_full_point` (which binds R2). In-circuit the nullifier
  is recomputed from the same note contents (`circuit/sapling.rs:390-415`).
  *Conclusion:* asset identity is bound into the nullifier *enforced by
  constraint* via the note-commitment preimage, not as an independent field.

### Conservation (`inputs = outputs`)
- **Not located in any circuit.** *enforced by constraint* at the transaction
  layer: `verifier.rs:54 / :117 / :148` accumulate
  `cv_sum = Σcv_spend + Σcv_convert − Σcv_output`; `verifier.rs:173-203`
  (`final_check`) computes `bvk = cv_sum − Σ_asset R3(asset)·value_balance(asset)`
  (`sapling/mod.rs:14-38`) and verifies the RedJubjub **binding signature**
  against `bvk`. The signature validates iff every asset's value nets to the
  declared public `value_balance`. Small-order `cv` is rejected up front
  (`verifier.rs:49 / :112 / :143`).
- *This reduces conservation to one unprovable-in-circuit assumption:* the
  per-asset R3 generators are mutually DL-independent — *deterministically
  derived at* `asset_type.rs:70-102` (NUMS BLAKE2s hash-to-curve), relied upon
  under the DL/random-oracle assumption. It is **not** (and cannot be) a circuit
  constraint.

---

## 3. Findings (constraint debt & items for human review)

### F1 — Convert: assets↔generator equivalence is enforced off-circuit. **Constraint debt. (High attention)**
The Convert circuit (`circuit/convert.rs`) witnesses a value commitment whose
generator is an **`AllowedConversion` generator** = `Σ value_i · R2(asset_i)`
(`convert.rs:87-118`). In-circuit, that generator is bound **only** by
membership in the allowed-conversion Merkle tree:
`pedersen_hash(asset_generator_bits)` must equal a tree leaf
(`circuit/convert.rs:54-58`, `:117-122`). The equivalence *"this generator
actually equals the claimed value-preserving combination of per-asset
generators"* is **not enforced in the reviewed circuit path** — it is enforced at
tree-construction time, on the host, by `AllowedConversion`'s checked Borsh
deserializer (`convert.rs:146-159`, which recomputes the generator from `assets`
and rejects mismatches).
- **Conclusion:** conversion correctness is *deterministically derived at*
  `convert.rs:87-118` and *enforced by constraint* `convert.rs:149-158` **at the
  host/tree-construction layer**, and **not enforced in the reviewed circuit
  path**. Circuit soundness of conversions therefore rests entirely on every
  leaf admitted to the convert tree being well-formed.
- **Remediation (defensive):** treat convert-tree construction as
  consensus-critical; assert that every leaf is produced by the *checked*
  `AllowedConversion` path and gated by governance; add a regression test that a
  malformed (assets≠generator) conversion cannot enter the tree; document the
  invariant at the circuit boundary.

### F2 — `UncheckedAllowedConversion` is a deliberate equivalence bypass. **Unclear, needs human review.**
`UncheckedAllowedConversion` (`convert.rs:217-232`) deserializes the `generator`
field **without** checking it corresponds to `assets` ("Assume that the
generator just read corresponds to the value sum", `convert.rs:222-223`). Within
`masp` it is only consumed by the *checked* deserializer (`convert.rs:149-158`),
which re-validates — so inside this repo the drift is closed. But the type and
its `generator` field are `pub`.
- **Conclusion:** the assets↔generator equivalence is *not enforced in this
  path*; whether that path ever reaches a trust-bearing surface is *unclear,
  needs human review*.
- **Remediation:** grep the Namada repo for `UncheckedAllowedConversion` and for
  direct construction/mutation of `AllowedConversion.generator`; confirm none
  feed the on-chain conversion tree, `value_commitment`, or `value_balance`.
  Consider `#[doc(hidden)]` / a more alarming name / a debug-assert.

### F3 — Spend does not re-derive the generator from R1; it trusts the note tree. **Enforced by constraint (transitive) — flagged for documentation.**
Unlike Output, the Spend circuit never recomputes `blake2s(asset_id)`; the
generator is witnessed and bound only by note-commitment membership in the anchor
(`circuit/sapling.rs:377-382`, the `(cur − rt)·value = 0` gate) plus Pedersen
binding of R2 into the note.
- **Conclusion:** *enforced by constraint* transitively — Output's R1→R2 binding
  (`circuit/sapling.rs:475-483`) **plus** Spend tree-membership
  (`circuit/sapling.rs:377-382`). Sound **iff** the note commitment tree only
  ever ingests Output/Convert-produced commitments.
- **Remediation:** document this as a load-bearing invariant; if any future code
  path can insert externally-supplied leaves into the note tree, this transitive
  guarantee breaks and Spend would accept attacker-chosen generators.

### F4 — Foundational DL-independence assumption is implicit. **Deterministically derived; flagged.**
Per-asset R3 generators are independent only because they are NUMS hash-to-curve
outputs (`asset_type.rs:70-102`). Nothing in-circuit prevents a future
asset-onboarding path from registering a generator with a *known* relation to
existing ones (which would let value migrate between assets through the binding
equation).
- **Conclusion:** *deterministically derived at* `asset_type.rs:70-102`; relied
  upon, **not enforced in reviewed path** as a runtime check on new assets.
- **Remediation:** ensure all asset registration flows derive the generator via
  `AssetType::{new,from_identifier}` only; add a test asserting no onboarding API
  accepts an externally supplied generator point.

---

## 4. Edges that ARE enforced by an exact constraint (no debt)

- R1→R2 in Output: *enforced by constraint* `circuit/sapling.rs:475-483`.
- cv base non-small-order: *enforced by constraint* `circuit/sapling.rs:99-101`.
- On-curve witnessing of every point: *enforced by constraint*
  `circuit/ecc.rs:130-143` (`witness`→`interpret`).
- Spend note∈tree when value≠0: *enforced by constraint*
  `circuit/sapling.rs:377-382`; Convert leaf∈tree: `circuit/convert.rs:117-122`.
- Small-order `cv`/`rk`/`epk` rejected at verify: *enforced by constraint*
  `verifier.rs:49 / :112 / :143`.
- Per-asset value range (u64) in cv: *enforced by constraint*
  `circuit/sapling.rs:104-107`; host `value_balance` bounds *deterministically
  derived at* `sapling/mod.rs:17-29`.
- Net conservation: *enforced by constraint* `verifier.rs:173-203` (binding
  signature over `bvk`).

---

## 5. Bottom line

The asset-identity dual representations (R1/R2/R3) are **forced into equivalence
on the mint side by an exact circuit constraint** (`circuit/sapling.rs:475-483`)
and **on the spend side transitively** through note-tree membership, while
end-to-end conservation is **enforced by the transaction-layer binding
signature** (`verifier.rs:173-203`). The concentration of **constraint debt is in
the Convert / `AllowedConversion` machinery (F1, F2)**: there, the
assets↔generator equivalence is a *host-side, tree-construction* guarantee, not a
circuit constraint, and an explicit unchecked bypass exists. That is the right
place for human review, and it matches exactly where a multi-asset Sapling
descendant concentrates its trust. Next targets per your ordering: **Penumbra,
then Aztec.**

---

## Disclosure posture
This is a defensive, constraint-level reading of public open-source code at a
named commit. It identifies **trust boundaries and constraint debt**, not a
live, exploitable break — no counterfeiting path was demonstrated and **no
exploit code is included**. F1–F4 are design observations whose remediation is
"add/confirm a constraint or an invariant test." If deeper review of the Convert
tree-construction path in Namada were to reveal a concrete, exploitable break, it
would go to the Namada/MASP security channel under coordinated disclosure — not a
public PR — with a defensive description only.

## Files reviewed
`masp_primitives/src/asset_type.rs`, `convert.rs`, `sapling.rs`;
`masp_proofs/src/circuit/sapling.rs`, `circuit/convert.rs`, `circuit/ecc.rs`,
`sapling/verifier.rs`, `sapling/mod.rs`.
