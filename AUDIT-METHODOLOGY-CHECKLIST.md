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

---

## Epistemic Hygiene — audit your own evidence chain

*Object-level review fails by **missing evidence** (compression); meta-level
synthesis fails by **overgeneralization** (expansion). The strongest-sounding
claim in a report is often carried by the weakest evidence chain — because local
findings are constrained by reality and global ones are not. Run this on every
significant conclusion.*

1. [ ] What is **directly observed**?
2. [ ] What evidence is **compressed** through summaries, reports, retrieval, or
       delegation? *(A summary is a bridge — deflate it before counting it as
       observation.)*
3. [ ] What is **inferred** beyond the observation?
4. [ ] **Induction risk** — how far beyond the sample is this generalizing?
       *(population claimed vs. sample observed)*
5. [ ] **Evidence-depth risk** — how much of the claimed object was actually
       observed vs. trusted? *(claimed-about-the-instance vs. directly-seen-of-it
       — orthogonal to #4: a historian can be low-depth/high-induction, an auditor
       high-depth/low-induction; the dangerous claims are high on both.)*
6. [ ] If this conclusion is wrong, **what observation would reverse it?**
7. [ ] **Has such an observation been actively sought?**

> **The self-sealing test is not "has the framework reversed."** Some correct
> frameworks won't reverse for a long time. It is: **does the framework expose
> itself to situations where reversal is possible?** The failure mode is not "no
> reversals yet" — it is **"no conceivable observation would cause a reversal."**

**What #7 enforces.** A review that only ever *finds → classifies → explains* a
concentration is seeking confirmation. The next level of rigor is to go looking
for **the system where the framework predicts concentration X and reality appears
to produce Y** — not because the framework is probably wrong, but because that is
where you learn the most if it is.

**On expansion.** The goal is not to *minimize* it — generalization is where a
framework's value lives — but to **disclose and price** it. State a high-expansion
claim in the register of a hypothesis, not an observation. Undisclosed expansion
(a 100:1 claim spoken in the voice of a 1:1 citation) is the only actual error.
