# Aztec — Pass 1: Representation Equivalence

**Target:** `AztecProtocol/aztec-packages` @ `32207bf` (HEAD 2026-06-05),
`noir-projects/noir-protocol-circuits` (Noir). **Question:** for every path where
an asset/note identifier, nullifier, commitment, public input, or generator
appears in more than one representation, determine how equivalence is enforced —
circuit constraint, deterministic derivation, host validation, protocol
assumption, or comments/types. **Read-only.** No exploit construction.
**Report fields:** location · invariant · enforcement mechanism · verdict.

---

## Architecture note (why the buckets relocate)

Aztec has **no protocol-level value-conservation circuit** (unlike MASP's
binding signature or Penumbra's). The protocol guarantees only: (1) correct
**siloing** (every note/nullifier is scoped to its contract), (2) **note-hash
uniqueness** (anti-faerie-gold), and (3) **nullifier uniqueness** (anti-double-
spend). Per-asset value conservation is delegated to **application** circuits
(the token contract) — covered in Pass 2. So Pass 1's risk concentrates exactly
where the methodology predicts for a multi-representation system: the
inner→siloed→unique transitions and the contract-address binding.

---

## Representation transitions

### T1 — inner note hash → siloed note hash
- **Location:** `types/src/hash.nr:54-59` (`compute_siloed_note_hash`); applied/checked in `private-kernel-lib/.../reset_output_validator.nr:46,64-68`.
- **Invariant:** `siloed = H(DOM_SEP__SILOED_NOTE_HASH, contract_address, inner_note_hash)` — binds the emitting contract so notes can't intermingle across contracts.
- **Enforcement:** **circuit constraint** — the reset circuit recomputes `siloed` from first principles and `assert_eq`s it to the output (`:64-68`); double-siloing is blocked (`:388-393`), and the output's `contract_address` is asserted `== 0` post-silo (`:431-434`).
- **Verdict:** **enforced by circuit constraint.**

### T2 — siloed note hash → unique note hash (anti-faerie-gold)
- **Location:** `hash.nr:98-119` (`compute_unique_note_hash`, `compute_note_nonce_and_unique_note_hash`); checked at `reset_output_validator.nr:47-48`.
- **Invariant:** `unique = H(DOM_SEP__UNIQUE, note_nonce, siloed)`, `note_nonce = H(first_nullifier, note_index_in_tx)` — injects global uniqueness so two identical notes can't collide (only one would be nullifiable otherwise).
- **Enforcement:** **deterministic derivation, circuit-constrained** — recomputed and `assert_eq`'d; index and `first_nullifier` are both constrained inputs (tests at `:672-717` confirm both alter the output).
- **Verdict:** **enforced by circuit constraint.**

### T3 — note_nonce seed ← first/protocol nullifier
- **Location:** `hash.nr:103-110,128-134`; uniqueness seed validated unchanged at `reset_output_validator.nr:222-225`.
- **Invariant:** every tx has ≥1 nullifier (a `protocol_nullifier = tx_request.hash()` is created by the init circuit if none arises), guaranteeing a non-zero uniqueness seed.
- **Enforcement:** **protocol invariant + circuit constraint** (init circuit forces the protocol nullifier; reset pins `claimed_first_nullifier` to the previous kernel).
- **Verdict:** **enforced by circuit constraint** (relies on the init-circuit protocol-nullifier guarantee — verified by construction here, init circuit not separately re-derived).

### T4 — inner nullifier → siloed nullifier
- **Location:** `hash.nr:121-126`; checked at `reset_output_validator.nr:79,81-84`.
- **Invariant:** `siloed_nullifier = H(DOM_SEP__SILOED_NULLIFIER, contract_address, inner_nullifier)` — a contract can only nullify its own notes.
- **Enforcement:** **circuit constraint** — recomputed and `assert_eq`'d; double-silo guard (`:445-450`); output address zeroed (`:479-482`).
- **Verdict:** **enforced by circuit constraint.**

### T5 — contract-address binding (the identity that all siloing depends on)
- **Location:** `private_kernel_circuit_output_composer.nr:373-374,387,398-399,411-412` — note hashes / nullifiers / msgs / logs are `.scope(private_call.public_inputs.call_context.contract_address)`.
- **Invariant:** the address used for siloing is the **executing contract's** address from the verified call context, not an attacker-chosen value.
- **Enforcement:** **circuit constraint** — the scoped address is the call context bound to the verified private-function proof.
- **Verdict:** **enforced by circuit constraint** (binding of `call_context.contract_address` to the called contract's class/address derivation is the standard kernel call-validation; not separately re-derived in this pass — see Open Items).

### T6 — note-hash uniqueness at settlement (tree insertion)
- **Location:** `rollup-lib/.../tree_snapshot_builder.nr:45-50` (`append_only_tree::insert_subtree_root_to_snapshot`).
- **Invariant:** the unique note hashes are appended into the note-hash tree; uniqueness (T2) makes leaves globally distinct.
- **Enforcement:** **circuit constraint** (rollup tx-base append-only subtree insert).
- **Verdict:** **enforced by circuit constraint** at the settlement layer.

### T7 — nullifier uniqueness at settlement (double-spend prevention) — **cross-layer**
- **Location:** `rollup-lib/.../tree_snapshot_builder.nr:53-62` (`indexed_tree::batch_insert_no_update`).
- **Invariant:** each new siloed nullifier is proven **non-member** of the nullifier tree (via its low-leaf predecessor witness) before insertion; `_no_update` makes a duplicate fail.
- **Enforcement:** **circuit constraint at the rollup (settlement) layer.** The private kernel only checks nullifier reads against a *historical anchor* snapshot and tx-local duplicates; authoritative global uniqueness (across txs in a block and across blocks) lives in the rollup indexed-tree insert.
- **Verdict:** **enforced by circuit constraint — cross-layer (settlement-authoritative).** This split is sound by design (the sequencer cannot forge a valid rollup proof that inserts a duplicate), but it is a genuine cross-layer dependency to keep in view (Pass 2 traces the rollup/sequencer side).

### T8 — revertible note-hash uniquification deferred to the AVM — **cross-layer assumption**
- **Location:** `reset_output_validator.nr:52-63` and `hash.nr:79-90` (comment).
- **Invariant:** for txs with public execution (`is_private_only == false`), **revertible** note hashes are siloed but **not** made unique in the private kernel — the AVM is expected to uniquify them later (once `note_index_in_tx` is known after public execution).
- **Enforcement:** **cross-layer** — private kernel enforces siloing only; the uniqueness (anti-faerie-gold) of these specific note hashes is the **AVM's** responsibility.
- **Verdict:** **unclear needs human review (cross-layer)** — the AVM-side uniquification was not verified in this pass. This is precisely the "circuit says one thing, another layer assumes the rest" pattern flagged for Aztec; it is the single most interesting Pass-1 item to confirm on the AVM/public side.

### T9 — private-log first-field siloing (impersonation prevention)
- **Location:** `hash.nr:140-154`; checked at `reset_output_validator.nr:94-123`.
- **Invariant:** a log's first field is siloed with the contract address so one contract can't emit a log impersonating another (e.g. copying a tag).
- **Enforcement:** **circuit constraint** (recomputed + `assert_eq`; remaining fields copied verbatim and length checked).
- **Verdict:** **enforced by circuit constraint.**

### T10 — L2→L1 message hash (bridge representation)
- **Location:** `hash.nr:171-196` (`compute_l2_to_l1_message_hash`).
- **Invariant:** the cross-domain message commits to `contract_address ‖ rollup_version_id ‖ recipient ‖ chain_id ‖ content` (sha256) — binding the emitting L2 contract, the rollup version, and the L1 chain id to prevent cross-chain/cross-version replay.
- **Enforcement:** **deterministic derivation (in-circuit)**; the L1 side must recompute the same preimage (Pass 2 / bridge).
- **Verdict:** **enforced by deterministic derivation** on the L2 side; **L1-side equivalence is a cross-layer item for Pass 2** (the L1 outbox must hash identically).

---

## Bottom line (Pass 1)

The note-hash and nullifier representation transitions are **uniformly enforced
by in-circuit recomputation + `assert_eq`**, with the contract-address identity
bound to the **verified executing call context** and double-siloing explicitly
blocked. Note-hash uniqueness (faerie-gold) and nullifier uniqueness
(double-spend) are real and circuit-enforced — the latter authoritatively at the
**rollup settlement layer** (indexed-tree non-membership), not the private
kernel.

**Two genuine cross-layer items** (consistent with the Aztec-specific risks
flagged up front):
- **T8** — uniquification of *revertible* note hashes in txs with public calls is
  **deferred to the AVM**; not verified here → **needs human review**.
- **T10/T7** — the L2→L1 message hash and nullifier uniqueness both depend on a
  second layer (L1 outbox / rollup+sequencer) recomputing/inserting identically
  → traced in Pass 2.

No representation transition in the reviewed private-kernel/reset path is
enforced merely by comments or types; all are constraint-backed. The two
cross-layer deferrals are the place a "circuit says X, another layer assumes Y"
bug would live, and are the priority for follow-up.

## Disclosure posture
Defensive constraint-level reading of public code at a named commit; no exploit,
no PoC. The cross-layer items are "confirm the second layer matches," not a
demonstrated break.

## Files reviewed
`types/src/hash.nr`; `private-kernel-lib/src/components/reset_output_validator.nr`,
`private_kernel_circuit_output_composer.nr`;
`rollup-lib/src/tx_base/components/tree_snapshot_builder.nr`.
