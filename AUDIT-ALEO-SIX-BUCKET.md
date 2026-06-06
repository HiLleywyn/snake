# Aleo (snarkVM) — Six-Bucket Trust-Concentration Classification

**Target:** `ProvableHQ/snarkVM` @ `fad09d8` (HEAD 2026-06-04). **Task:** apply the
[six-bucket model](./AUDIT-METHODOLOGY-RETROSPECTIVE.md) to Aleo's current
architecture; identify the **top three trust concentrations**, classify each into
**exactly one bucket**, and grade each as **constraint debt**, **trust-boundary
debt**, **hardening debt**, or **enforced invariant**. **No exploit search.**

Buckets: 1 Conservation · 2 Witnessed cryptographic objects · 3 Dual
representations · 4 Dependency/fork lineage · 5 Arithmetic/bounds · 6 Cross-layer
settlement seams.

---

## TC1 — The private-execution → public-`finalize` settlement seam
**Bucket: 6 (cross-layer settlement seams). Grade: enforced invariant.**

Aleo splits every stateful call into a **private transition** (proven in ZK) and a
public **`finalize`** that mutates on-chain mappings (e.g. `credits.aleo`
`account`, staking). The proof attests to the transition and to the `Future`s it
emits; the public mutation is then performed by **plaintext, atomic,
deterministic re-execution** by every validator — *not* inside any SNARK
(`synthesizer/process/src/finalize.rs:95,251-258,292`; `atomic_batch_scope!`
makes the public effects all-or-nothing).

- **Why it's the #1 concentration:** the ZK guarantee *stops at the
  private/public boundary*. All public-state correctness rests on the VM's
  deterministic `finalize` semantics plus consensus replication — a different and
  much larger trust base than the proof itself.
- **Why "enforced," not debt:** the seam is discharged on both sides — the
  `finalize` arguments are bound to the verified execution (the `Future`s are part
  of the proven outputs, matched at `finalize.rs:251-258`), and the computation is
  atomically, deterministically re-executed under consensus. The proof↔finalize
  handoff has no unbound input.
- **Watch:** this is precisely where a future change (a `finalize` input not
  bound to the transition, or a non-deterministic command) would convert an
  enforced invariant into **trust-boundary debt**. It is the bucket-6 home and the
  thing to re-audit on every protocol change.

---

## TC2 — Serial-number (double-spend nullifier) derivation & uniqueness
**Bucket: 2 (witnessed cryptographic objects). Grade: enforced invariant.**

The serial number is the spend-once object. It is derived
(`console/program/src/data/record/serial_number.rs:20-35`) as:
`H = HashToGroup(sn_domain, commitment)`, `γ = sk_sig · H`,
`sn = Commit(commitment, Hash(cofactor·γ))`.

- **The witnessed object is `γ`** (a group element). It is bound in-circuit to the
  owner's signing key and the record commitment via the request verification
  (`console/program/src/request/verify.rs:128`, `input_id/mod.rs:147`): `γ` must
  equal `sk_sig·H(commitment)`, proven against the transition's signature.
- **Determinism + unforgeability:** exactly one serial number per
  (record, owner) — so a record cannot be re-derived to two different serial
  numbers (no double-spend by aliasing) — and only the owner (who knows `sk_sig`)
  can produce it (no nullifying others' records).
- **Uniqueness:** enforced at the ledger — a transaction whose serial number is
  already present is rejected (`ledger/src/contains.rs:80`
  `contains_serial_number`; `ledger/src/find.rs:142-151` `is_spent`).
- **Grade:** enforced — constrained derivation + signature binding (circuit) plus
  ledger-level uniqueness (consensus). This is Aleo's anti-counterfeit core and it
  is closed across the circuit/ledger boundary.

---

## TC3 — Public/program arithmetic: checked vs wrapping (`.w`) ops
**Bucket: 5 (arithmetic / bounds). Grade: hardening debt.**

Aleo's instruction set exposes **both** checked (`add`, `sub`, `mul` — halt on
over/underflow) and **wrapping** (`add.w`, `sub.w`, …) integer ops. Bounds-safety
of value-bearing public state is therefore a per-program authoring choice.

- **Native protocol is safe:** `credits.aleo`
  (`synthesizer/program/src/resources/credits.aleo`) uses **zero `.w` ops** — all
  microcredit arithmetic (transfer/fee/bond/unbond) is checked and halts on
  overflow. So the native token's conservation/bounds are **enforced**.
- **The architecture-level debt:** the broader token/DeFi ecosystem's
  public-balance safety rests on each program author choosing checked ops; the
  wrapping variants are freely available and silently wrap. Nothing in the
  protocol forces value-handling mappings to use checked arithmetic.
- **Grade:** hardening debt — the safe path exists and the protocol takes it, but
  the platform leaves a foot-gun in reach for application value accounting. (This
  mirrors Penumbra's `overflow-checks` finding: correct today, one authoring
  slip from wrong, fixable by policy rather than a soundness change.)

---

## Also enforced (considered, not in the top three)
- **Record dual representation (bucket 3):** the commitment binds
  `program_id || record_name || record` (owner, value, nonce) via BHP commit
  (`console/program/src/data/record/to_commitment.rs:26-48`), so a record cannot
  be spent by another program or re-owned — **enforced**.
- **Private value conservation (bucket 1):** enforced by each program's own
  circuit (e.g. `credits.aleo` `transfer_private` checked record arithmetic),
  backed by TC2 (no double-spend) and inclusion proofs — **enforced**.

---

## Summary

| # | Trust concentration | Bucket | Grade |
|---|---------------------|--------|-------|
| TC1 | private execution → public `finalize` seam | 6 — cross-layer settlement seams | **enforced invariant** |
| TC2 | serial-number (`γ`) derivation & uniqueness | 2 — witnessed cryptographic objects | **enforced invariant** |
| TC3 | checked vs wrapping (`.w`) public arithmetic | 5 — arithmetic / bounds | **hardening debt** |

**Read of Aleo against the model:** like Aztec, Aleo's defining concentration is a
**cross-layer seam** (bucket 6) — but Aleo discharges it differently: where Aztec
*proves* its public VM (AVM circuit), Aleo *re-executes* its public layer
(`finalize`) under consensus and binds only the inputs to the proof. Both are
enforced; the trust bases differ (a proof vs. deterministic replication). The
sole **debt** surfaced is bucket 5 (hardening) — and it is ecosystem-level, not in
the native protocol. No untrusted-input path or constraint/ trust-boundary debt
was found in the reviewed core. Consistent with the retrospective: a mature core
moves the residual risk to *bounds* and *layer agreement*, exactly buckets 5 and
6.

## Disclosure posture
Defensive architectural classification of public code at a named commit; no
exploit, no PoC. Findings are an enforced-invariant map plus one hardening
(policy-level) item.

## Files reviewed
`synthesizer/process/src/finalize.rs`;
`console/program/src/data/record/serial_number.rs`, `to_commitment.rs`;
`console/program/src/request/verify.rs`, `input_id/mod.rs`;
`ledger/src/contains.rs`, `find.rs`;
`synthesizer/program/src/resources/credits.aleo`.
