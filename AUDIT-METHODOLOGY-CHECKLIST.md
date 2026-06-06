# How to Use This Methodology — One-Page Checklist

A reviewer's heuristic for locating **where a system places its trust**, and
whether that trust is discharged. It is a *lens*, not a security audit and not a
certification. It finds *trust boundaries*, not (necessarily) bugs.

---

## 0. Frame the run (5 minutes)
- [ ] Name the **value**: what is the scarce thing (token, note, message, state)?
- [ ] Set the **goal**: "locate the top 3 trust concentrations," not "find a bug."
- [ ] Commit to **defensive questions only**: *"what invariant fails if this
      assumption is false?"* — never "can I exploit this?"

## 1. Follow the money first (buckets 1–3)
- [ ] **Conservation (1):** find where `inputs = outputs` is enforced, and in
      *which layer* (circuit / protocol / sequencer / host). Binding signatures,
      value circuit breakers, and "checked-type" accounting are the usual homes.
- [ ] **Witnessed objects (2):** for every witnessed point / proof / key, ask
      *"is it constrained on-curve and bound to its preimage, or re-derived?"*
- [ ] **Dual representations (3):** list every object that exists in >1 form
      (id ↔ commitment ↔ nullifier ↔ generator). Ask *"are they forced equal
      **everywhere**?"* Trace to the layer that actually closes it.

## 2. Then the mechanics (buckets 4–5)
- [ ] **Dependency / fork lineage (4):** which pinned commit predates which fix;
      what local edits changed an upstream-audited constraint?
- [ ] **Arithmetic / bounds (5):** checked vs saturating vs wrapping; is each
      bound **enforced** or merely **assumed** (and where is it assumed)?

## 3. Then the seams (bucket 6 — usually where mature systems concentrate risk)
- [ ] **Enumerate trust boundaries:** L1↔L2, prover↔verifier, circuit↔sequencer,
      native↔circuit, simulation↔constraining, proof↔consensus.
- [ ] **6a — inter-layer deferral:** does layer A trust layer B to enforce X?
      (*Reducible by proving B and verifying B's proof.*)
- [ ] **6b — interpretation / equivalence:** do two encodings of the same
      semantics (native vs circuit; spec vs relations; builder vs prover) have to
      *agree*? (*Irreducible — proving adds an encoding that must agree.*)
- [ ] **Public-input binding:** does every value-bearing effect actually enter the
      transcript / public inputs the next layer verifies?

## 4. Grade every candidate (force a verdict)
Resolve each finding to **exactly one** label — this step *downgrades* most
candidates and is what stops the lens manufacturing criticals:
- [ ] **Enforced invariant** — point to the exact constraint / require / check.
- [ ] **Constraint debt** — equivalence/correctness assumed in-circuit but not
      constrained (often enforced one layer over — check before grading).
- [ ] **Trust-boundary debt** — correctness rests on a boundary (governance,
      another layer, a reference implementation) being honest/correct.
- [ ] **Hardening debt** — correct today; one authoring slip or bound regression
      from wrong; fixable by policy (e.g. enable overflow-checks).

Before calling anything a bug: **trace the writer and its trust boundary.**
"Looks unchecked / host-trusted" is a hypothesis, not a finding.

## 5. Triage & stop
- [ ] Down-weight buckets 1–3 when you see **structural defenses** (prime-order
      groups, value circuit breakers, checked/panicking value types, in-circuit
      re-derivation). Up-weight 5–6.
- [ ] **Route privately** only on `untrusted input → not validated` reaching
      value. Everything else (governance debt, hardening, documented boundaries)
      is safe to record openly.
- [ ] **Stop sampling.** Three to six systems is enough to see whether the model
      *predicts where risk concentrates*. A good run produces *proportional*
      signal, not a critical everywhere.

---

### The one-line test of a healthy review
> If every review "finds a critical," the lens is broken. The lens is working when
> it keeps re-deriving each system's *own* trust map — and the dominant bucket
> migrates toward **cross-layer/cross-encoding agreement (6)** as systems mature.
