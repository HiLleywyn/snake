# Mina — Six-Bucket Trust-Concentration Classification

**Target:** `MinaProtocol/mina` @ `d046482` (HEAD 2026-06-03). **Task:** apply the
[six-bucket model](./AUDIT-METHODOLOGY-RETROSPECTIVE.md); identify the **top three
trust concentrations**, classify each into **exactly one bucket**, and grade each
as **enforced invariant**, **constraint debt**, **trust-boundary debt**, or
**hardening debt**. Focus areas (per request): recursive-proof verification,
public-input binding, state-transition interpretation, ledger/proof
synchronization. **No exploit search.**

Buckets: 1 Conservation · 2 Witnessed cryptographic objects · 3 Dual
representations · 4 Dependency/fork lineage · 5 Arithmetic/bounds · 6 Cross-layer
settlement seams.

> **One-line read:** Mina is the most **bucket-6-concentrated** architecture in
> this series. A fully-succinct recursive chain *is* a stack of agreements
> (step↔wrap, native↔circuit, staged↔snarked), so two of its three top
> concentrations are layer-agreement seams.

---

## TC1 — Pickles recursive verification + deferred values + public-input binding
**Bucket: 2 (witnessed cryptographic objects). Grade: enforced invariant.**

The entire chain's validity reduces to **one recursive proof**: each blockchain
proof recursively verifies the previous proof and the transaction proof in-circuit
(`src/lib/crypto/pickles/{step_verifier.ml, wrap_verifier.ml, step_main.ml,
wrap_main.ml}`). Two soundness-critical pieces:
- **Witnessed inner proof:** the in-circuit verifier constrains the witnessed
  group elements / evaluations of the proof being recursed.
- **Deferred values:** because Mina uses a 2-cycle (Tick/Vesta ↔ Tock/Pallas),
  scalar-field checks are *deferred* from one half to the other and must be
  re-expanded and checked
  (`src/lib/crypto/pickles/wrap_deferred_values.ml:expand_deferred`, taking the
  evals, `old_bulletproof_challenges`, and the
  `Messages_for_next_proof_over_same_field.Wrap` passthrough).
- **Public-input binding:** the statement / protocol-state hash is carried through
  the recursion via that "messages for next proof" passthrough, and the verifier
  binds the inner proof's public input to it.

- **Why #1:** if the recursion or the deferred-values expansion were
  under-constrained, the whole chain's succinct guarantee collapses — every other
  invariant inherits from this proof.
- **Grade — enforced invariant:** this is the foundational soundness mechanism;
  the deferred handoff and public-input passthrough are explicit, constrained
  steps. *(Note: the step↔wrap deferred-values handoff also has a bucket-6
  character — two proof halves agreeing on what each has checked — but the
  dominant trust object is the correctly-constrained witnessed proof, so it
  classifies as bucket 2.)*

---

## TC2 — Native ↔ in-circuit transaction-logic agreement (state-transition interpretation)
**Bucket: 6 (cross-layer settlement seams). Grade: trust-boundary debt.**

The transaction-application logic must produce **identical** results when run
(a) **natively** to advance/validate the staged ledger
(`src/lib/transaction_snark/transaction_validator.ml:apply_user_command,
apply_transactions`) and (b) **in-circuit** to produce the transaction SNARK
(`src/lib/transaction_snark/transaction_snark.ml`). Mina mitigates divergence by
writing the logic **once** as a functor over abstract interfaces
(`src/lib/transaction_logic/zkapp_command_logic.ml` — `Amount_intf`,
`Balance_intf`, `Bool_intf`, … with a `module Checked` at `:316`) and
instantiating it for both the snark (`Checked`) and the native (unchecked) modes;
`mina_transaction_logic.ml` is the native instantiation.

- **Why it's a concentration:** correctness depends on two independent execution
  modes agreeing on the interpretation of the same transaction. A primitive-level
  divergence (field/range/hash behavior differing between native and circuit)
  yields a state the node *applies but cannot prove* (a liveness stall in the
  scan state) or, worse, *proves differently than it applied*.
- **Grade — trust-boundary debt:** strongly mitigated by single-source
  functorized logic, but the equivalence of the `Checked` and unchecked
  instantiations is upheld by **construction, convention, and testing — not by a
  proof of equivalence**. The native↔circuit boundary is the residual trust seam.
  This is the most informative non-enforced item for Mina.

---

## TC3 — Staged-ledger ↔ snarked-ledger synchronization (the scan state)
**Bucket: 6 (cross-layer settlement seams). Grade: enforced invariant.**

Mina applies transactions to the **staged ledger before they are proven**; SNARK
workers produce transaction proofs asynchronously, aggregated in a **bounded
parallel scan state**; the blockchain proof only certifies the **snarked ledger**,
which lags (`src/lib/staged_ledger/README.md:1-67`;
`src/lib/transaction_snark_scan_state/transaction_snark_scan_state.ml`;
`src/lib/parallel_scan/`).

Synchronization rests on protocol-enforced rules:
- every applied transaction is **natively validated** at apply time (TC2);
- a block's diff must **include valid snark work** for prior pending jobs, and
  `apply` checks scan-state invariants and **rejects the block** otherwise
  (`README.md:197-223`);
- the **fee-excess** invariant: the ledger proof emitted by each scan-state tree
  must have **zero fee excess** (fees debited from payer == credited to
  recipient), enforced during diff creation (`README.md:115-171`);
- the scan state has a **fixed compile-time capacity**, bounding how far the
  staged ledger can run ahead of the snarked ledger.

- **Why it's a concentration:** the applied (staged) and proven (snarked) ledgers
  must stay consistent across an asynchronous lag — the defining ledger/proof
  synchronization seam.
- **Grade — enforced invariant:** the coupling is consensus-checked (no advance
  without the required, valid snark work; fee-excess nets to zero per tree; lag is
  bounded). *Residual (hardening, not a gap): value is spendable on the staged
  ledger before it is proven, so economic finality trails proof finality by the
  scan-state depth — a documented, bounded property.*

---

## Summary

| # | Trust concentration | Bucket | Grade |
|---|---------------------|--------|-------|
| TC1 | Pickles recursion + deferred values + public-input binding | 2 — witnessed cryptographic objects | **enforced invariant** |
| TC2 | native ↔ in-circuit transaction-logic interpretation | 6 — cross-layer settlement seams | **trust-boundary debt** |
| TC3 | staged ↔ snarked ledger synchronization (scan state) | 6 — cross-layer settlement seams | **enforced invariant** |

**Read against the model.** Across the series the sixth bucket has been the axis
that *distinguishes* architectures, and Mina is the extreme case: being fully
succinct and recursive, it concentrates risk in **layer agreement** more than any
other system reviewed — recursion handoff (TC1's bucket-6 shadow), native↔circuit
agreement (TC2), and staged↔snarked synchronization (TC3). Its single
non-enforced item (TC2) is a **trust-boundary debt** of exactly the bucket-6
shape: *two independently-correct systems must agree on a shared interpretation*,
and that agreement is maintained by single-source code rather than proven
equivalent. Compared to Aleo (which *replicates* its public layer under consensus)
and Aztec (which *proves* its public VM), Mina **recursively proves the whole
state** — moving essentially all residual risk onto the correctness of, and
agreement between, its proof layers. That bucket 6 keeps being where the
architectures genuinely differ is continued evidence the bucket is real and
load-bearing.

## Disclosure posture
Defensive architectural classification of public code at a named commit; no
exploit, no PoC. Findings are an enforced-invariant map plus one trust-boundary
(native↔circuit) item that is mitigated by design, not a demonstrated break.

## Files reviewed
`src/lib/crypto/pickles/{step_verifier,wrap_verifier,step_main,wrap_main,wrap_deferred_values}.ml`;
`src/lib/transaction_logic/{zkapp_command_logic,mina_transaction_logic}.ml`;
`src/lib/transaction_snark/{transaction_snark,transaction_validator}.ml`;
`src/lib/transaction_snark_scan_state/transaction_snark_scan_state.ml`;
`src/lib/staged_ledger/README.md` (+ `staged_ledger.ml`); `src/lib/parallel_scan/`.
