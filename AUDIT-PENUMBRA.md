# Penumbra — Asset Identity → Value Generator → Balance Commitment → Nullifier / Action Binding

**Target:** `github.com/penumbra-zone/penumbra` @ `36a31c1` (HEAD 2026-01-24).
Groth16 over **BLS12-377**, group **decaf377** (prime-order — *no cofactor*),
Poseidon (`poseidon377`) hashing.
**Question (same method as MASP/Namada):** trace asset identity into the value
generator, balance commitment, nullifier, and action/transaction binding; for
each representation name the **exact** constraint or deterministic derivation
forcing equivalence; mark anything assumed by type/comment/test rather than a
circuit constraint as **constraint debt**.
**Verdicts (strict):** *enforced by constraint X* / *deterministically derived
at Y* / *unclear, needs human review* / *not enforced in reviewed path*. "Safe"
only with an exact constraint. **No exploit code.**

---

## Headline

Penumbra is **structurally tighter than MASP** on exactly the axis MASP carries
debt. The value generator `G_v` is **re-derived inside every circuit from the
witnessed `asset_id`** by the identical hash-to-group used on the host — it is
**never witnessed as a free point**. Combined with decaf377 being prime-order
(no cofactor / small-order subtleties), the asset-identity dual representation
has **no constraint debt in the reviewed chain**. Conservation is the RedDSA
binding signature over the sum of per-action balance commitments.

| Representation | decaf377 / Penumbra |
|---|---|
| R1 canonical asset ID | `Id(Fq)` — a single field element (`asset/id.rs`) |
| R2 value generator `G_v` | `encode_to_curve(Poseidon(domain_sep, asset_id))` — **derived**, never a stored/witnessed point |
| (no R3) | decaf377 is prime-order; there is no cofactor-cleared second generator |

---

## Edge-by-edge trace

### R1 → R2 (asset ID → value generator)
- **Host:** *deterministically derived at* `asset/id.rs:137-142`:
  `Element::encode_to_curve(poseidon377::hash_1(VALUE_GENERATOR_DOMAIN_SEP, id.0))`,
  domain sep `id.rs:131-133` (NUMS: `blake2b("penumbra.value.generator")`).
- **Circuit:** *deterministically derived at* `asset/r1cs.rs:47-54`:
  `ElementVar::encode_to_curve(poseidon377::r1cs::hash_1(cs, domain_sep_const,
  self.asset_id))`. The in-circuit derivation **mirrors the host exactly** and
  takes the **witnessed `asset_id` FqVar** as input — no free generator is
  allocated. *This is the key difference from MASP's `expose_value_commitment`,
  which witnesses the generator.*

### amount range (anti-overflow on the scalar mul)
- *enforced by constraint* `num/amount.rs:204` and `:222`
  (`bit_constrain(inner_amount_var, 128)`), which calls
  `num/fixpoint.rs:717-737`. Although the caller drops the returned bits
  (`let _ =`), `bit_constrain` **internally** enforces
  `constructed_fqvar.enforce_equal(&value)` (`fixpoint.rs:734`), so the 128-bit
  range constraint is added to the CS regardless. Amounts cannot exceed 2¹²⁸−1,
  preventing scalar-field-wrap cross-asset cancellation.

### R1 → note commitment
- *enforced by constraint* `note/r1cs.rs:94-…` (Poseidon note commit under
  `NOTECOMMIT_DOMAIN_SEP`, `note.rs:88`) binds `value.asset_id` into the
  commitment; in the spend circuit `note_var.commit()` is enforced equal to the
  public claimed note commitment at `spend/proof.rs:181-182`.

### R1 → balance commitment, using the *same* witnessed asset_id
- *enforced by constraint* `spend/proof.rs:212-213`: the balance commitment is
  `note_var.value().commit(v_blinding)` and `enforce_equal`-ed to the public
  `claimed_balance_commitment_var`. `value().commit` is `balance.rs:403-434`,
  which builds `G_v = asset_id.value_generator()?` (`balance.rs:423` →
  `r1cs.rs:47-54`) and a **constant** blinding generator
  (`VALUE_BLINDING_GENERATOR`, `balance.rs:417`).
- **Equivalence is by construction:** the *same* `note_var` supplies `asset_id`
  to **both** the note commitment (`:181`) and the balance commitment (`:212`).
  There is no second representation to drift.

### note commitment → nullifier
- *enforced by constraint* `spend/proof.rs:185-186`:
  `NullifierVar::derive(nk, position, claimed_note_commitment)` enforced equal to
  the public nullifier. The nullifier therefore binds the note commitment (hence
  `asset_id`).

### note ∈ state-commitment tree
- *enforced by constraint* `spend/proof.rs:193-199` (Merkle path to the public
  anchor), short-circuited only for zero-value dummy spends
  (`is_not_dummy`, `:192`).

### Conservation / action binding (`inputs = outputs`)
- **Not in any circuit** (as in Sapling). *enforced by constraint* at the
  transaction layer: `transaction.rs:586-607` computes
  `bvk = Σ_actions action.balance_commitment() + fee_commitment`; stateless
  verification `app/.../transaction/stateless.rs:6-14` verifies the RedDSA
  **binding signature** against `bvk` over the auth hash. The signature validates
  iff the per-asset value terms cancel to the declared public fee — i.e. each
  asset conserves.
- **Uniformity:** every action circuit forms its balance commitment via
  `Value/Balance::commit()` (spend `:212`, output `output/proof.rs:56`, swap
  `swap/proof.rs:127-135`, swap_claim, `delegator_vote/proof.rs:216`,
  `undelegate_claim/proof.rs:135`). No action constructs a `BalanceCommitmentVar`
  by witnessing it; `BalanceCommitmentVar::new_input` is only the *claimed
  public* value the derived one is checked against. So the derived-`G_v` property
  holds across the whole action set.

### Foundational assumption
- Per-asset `G_v` mutual DL-independence: *deterministically derived at*
  `id.rs:137-142` (NUMS Poseidon → encode_to_curve), relied upon under the DL /
  random-oracle assumption. Not a circuit constraint (cannot be).

---

## Findings

### P1 — `let _ = bit_constrain(...)` is a footgun, currently sound. **No debt; harden for safety.**
`num/amount.rs:204,222` discard the return of `bit_constrain`. It is *enforced by
constraint* today only because `bit_constrain` performs its own
`enforce_equal` (`fixpoint.rs:734`). If a future refactor moved the
`enforce_equal` out to the (discarded) return path, amounts would silently become
unconstrained — a counterfeiting vector.
- **Remediation (defensive):** bind the result (`let _bits = …` used, or
  `?`-propagate into the value) or add a comment + test asserting an
  out-of-range amount makes the circuit unsatisfiable, so the range constraint
  cannot be refactored away unnoticed.

### P2 — In-circuit hash-to-group equivalence depends on external libraries. **Unclear, needs human review (dependency).**
The R1→R2 equivalence holds only if `decaf377-r1cs` `ElementVar::encode_to_curve`
and `poseidon377::r1cs::hash_1` compute **bit-identically** to their native
counterparts. This is outside Penumbra's own circuit code.
- **Verdict:** *deterministically derived at* `r1cs.rs:47-54` **conditional on**
  the pinned `decaf377` / `poseidon377` versions being correct — *unclear, needs
  human review* at the dependency boundary.
- **Remediation:** confirm the pinned versions, check their changelogs/audits for
  any `encode_to_curve` / Poseidon-parameter fixes post-pin (Phase 6 of the
  methodology), and keep the host-vs-circuit equivalence proptests in CI.

### P3 — Coverage scope. **Not enforced in reviewed path (out of scope, not a defect).**
This review covered the asset-identity → value-generator → balance-commitment →
nullifier/action-binding chain via the **spend** circuit and the shared
`asset`/`balance` gadgets, plus a uniformity sweep across action circuits. It did
**not** exhaustively re-derive every constraint of the DEX swap arithmetic,
staking penalty/exchange-rate math, or IBC asset minting. Those reuse the same
derived-`G_v` API (so dual-representation holds) but their *amount* arithmetic
(rates, penalties) warrants its own conservation pass.

---

## Bottom line

On the dual-representation axis, **Penumbra carries no constraint debt in the
reviewed chain**: `G_v` is derived in-circuit from the witnessed `asset_id`
(`r1cs.rs:47-54`), the *same* `asset_id` feeds both the note and balance
commitments (`spend/proof.rs:181` & `:212`), amounts are 128-bit range-checked
(`fixpoint.rs:734`), the nullifier binds the note commitment (`:185-186`), and
conservation is the binding signature over `Σ` balance commitments
(`transaction.rs:586-607` + `stateless.rs:12-13`). decaf377's prime order removes
the cofactor/small-order class entirely. The residual risks are a refactor
footgun (P1) and a dependency-equivalence assumption (P2) — both *hardening*
items, not live exploit paths. **No untrusted-input, not-validated path was
found; nothing to route privately.**

## Disclosure posture
Defensive constraint-level reading of public code at a named commit; no
counterfeiting path demonstrated, no exploit code. P1/P2 are "add a
comment/test/version-pin check" hardening suggestions. Were a concrete break ever
found, it would go to Penumbra's security channel under coordinated disclosure,
not a public PR.

## Files reviewed
`crates/core/asset/src/asset/id.rs`, `asset/r1cs.rs`, `balance.rs`,
`balance/commitment.rs`; `crates/core/num/src/amount.rs`, `fixpoint.rs`;
`crates/core/component/shielded-pool/src/note.rs`, `note/r1cs.rs`,
`spend/proof.rs`, `output/proof.rs`; `crates/core/component/{dex,governance,stake}`
(uniformity sweep); `crates/core/transaction/src/transaction.rs`;
`crates/core/app/src/action_handler/transaction/stateless.rs`.
