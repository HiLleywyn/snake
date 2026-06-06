# zk Audit Methodology — Cross-Ecosystem Retrospective

A review of whether the [audit methodology](./AUDIT-METHODOLOGY.md) produced
*signal* — i.e. whether it located where trust actually concentrates in each
architecture — across four very different systems: Zcash/Orchard, Namada MASP,
Penumbra, and Aztec.

> **Thesis.** A bad methodology finds the same bug everywhere. A good one
> identifies *where trust concentrates* in each architecture. The value of this
> exercise is not another critical finding; it is the evidence that the same
> nine phases / small set of buckets kept leading to the right place in
> codebases that share almost no structure.

---

## 1. The evidence

| System | Architecture | Primary finding class | Grounding |
|---|---|---|---|
| **Zcash / Orchard** | halo2, single-asset shielded | **Witnessed-point / soundness** | BCTV14 counterfeiting (CVE-2019-7167); halo2 query-collision; 2026 Orchard disclosure (halo2-based) |
| **Namada MASP** | Groth16/bellman, multi-asset shielded | **Dual-representation / governance constraint debt** | Convert `assets↔generator` enforced host-side (`convert.rs:149-158`), not in-circuit; `UncheckedAllowedConversion` read at `conversion.rs:638`, fed by governance migrations only |
| **Penumbra** | Groth16/BLS12-377, decaf377, asset-heavy shielded DEX | **Arithmetic hardening** | rounding pool-favorable & circuit-enforced (`trading_function.rs`), batch pro-rata round-down enforced (`swap_claim/proof.rs:269-275`), VCB backstop (`circuit_breaker/value.rs`); residual = `overflow-checks` flag |
| **Aztec** | Noir kernel→rollup recursion + AVM + L1 bridge | **Cross-layer settlement seams** | Outbox leaf-id stability L1 cannot verify (`Outbox.sol:39-47`); AVM-deferred uniquification (`reset_output_validator.nr:52-63`) |

Four architectures, four *distinct* loci. That distribution — not a repeated
finding — is the result worth documenting.

---

## 2. Predictions that succeeded

**S1 — Conservation equations reliably point at value-critical code.**
Phase 4 ("hunt conservation equations") landed on the load-bearing mechanism
every time, even when the mechanism differed wildly:
- MASP: the RedJubjub **binding signature** over `Σ cv − value_balance`
  (`verifier.rs:173-203`) — conservation lives at the transaction layer, not the
  circuit.
- Penumbra: the **binding signature** over `Σ balance_commitment + fee`
  (`transaction.rs:586-607`) plus the per-component **Value Circuit Breakers**.
- Aztec: conservation is a **composition** — app checked arithmetic × protocol
  note/nullifier integrity × L1 public-input binding — and the phase still routed
  to each piece (`balance_set.nr:67-68`, `tree_snapshot_builder.nr:53`,
  `tx_base_public_inputs_composer.nr`).
*The question "where is `inputs = outputs` actually enforced, and in which
layer?" never returned noise.*

**S2 — Dual representations reliably expose trust assumptions.**
Phase 5 ("are these representations forced equivalent everywhere?") surfaced the
single most important MASP finding (the Convert path's host-enforced
`assets↔generator` equivalence) and structured the entire Aztec Pass 1
(`inner → siloed → unique` note hashes; `inner → siloed` nullifiers). Even where
it returned *negative* (Penumbra), the negative was informative (see F2).

**S3 — Witnessed cryptographic objects remain high-yield review targets.**
The historical record (Zcash/halo2 query-collision, the Frozen-Heart family) and
the live code agreed: MASP's `expose_value_commitment` **witnesses** the asset
generator and leans on tree membership; Penumbra deliberately **re-derives** it
in-circuit (`r1cs.rs:47-54`) and is tighter for it. "Is this witnessed point
constrained on-curve / bound to its preimage?" consistently separated tight code
from loose code.

**S4 — In a multi-layer system, cross-layer boundaries dominate local circuit
correctness.** In Aztec the circuits themselves were tightly constrained; *every*
open item was at a seam (AVM deferral, L1↔proving-system trust). The methodology's
instinct to "enumerate where data crosses trust boundaries" (Phase 2) was, for
Aztec, the whole game.

---

## 3. Predictions that failed — and how they refine the model

These matter more than the successes, because they recalibrate the buckets.

**F1 — Penumbra did not yield a conservation failure, despite being the obvious
target.** An asset-heavy shielded DEX is exactly where the model says to dig — and
the dig found correct, pool-favorable, circuit-enforced rounding with a VCB
backstop. *Refinement:* when a codebase exhibits **structural defenses**
(prime-order group → no cofactor class; explicit Value Circuit Breakers; checked
`Balance` types that panic rather than wrap), the classic conservation/dual-rep
buckets should be **down-weighted a priori**. The presence of these defenses is
itself a strong prior that those buckets are closed. The model should *score the
defenses*, not just the surface area.

**F2 — MASP asset-generator derivation was stronger than first suspected.** The
initial hypothesis (a witnessed multi-asset generator is under-constrained) was
wrong: the mint side binds it bit-for-bit to `blake2s(asset_id)`
(`circuit/sapling.rs:475-483`) and the spend side inherits correctness
transitively via the note tree. The real debt was **one layer over**, in
Convert/governance. *Refinement:* "witnessed point" and "dual representation"
findings must be **traced to the layer that actually closes them** before
grading; the first suspicious site is often constrained downstream.

**F3 — Several apparent "host-side assumptions" were constrained elsewhere.**
Penumbra's `bit_constrain` discards its return value (`let _ = …`) — a footgun —
but the range constraint is enforced *inside* it (`fixpoint.rs:734`). Namada's
`UncheckedAllowedConversion` read looks dangerous but is fed **only** by
governance migrations, with no transaction/WASM path (`conversion.rs:638`).
*Refinement:* "looks unchecked / host-trusted" is a hypothesis, not a finding.
The verdict requires tracing the **writer and its trust boundary**. This is why
the strict verdict vocabulary (`checked/fail-closed`, `capped/unreachable`,
`trusted-input-not-validated`, `untrusted-input-not-validated`, …) earned its
keep: it forced each candidate to resolve to a trust boundary before being
called a bug.

*Net effect of the failures:* the model is most useful not as a bug detector but
as a **trust-boundary locator** with a disciplined grading step that frequently
*downgrades* its own candidates. The discipline of recording the downgrades is
what keeps it from manufacturing criticals.

---

## 4. The sixth bucket: cross-layer settlement seams

Aztec surfaced a failure mode the original five buckets do not cleanly name:

> **Cross-layer settlement seam:** correctness depends on *multiple
> independently-correct systems agreeing on a shared interpretation* of the same
> data. No single layer is wrong in isolation; the bug lives in the *agreement*.

It is not quite conservation (no value equation is violated within a layer), not
quite dual representation (the representations are equal; the *positions* or
*interpretations* diverge), and not quite a witnessed point. Evidence:

- **Aztec Outbox leaf-id** (`Outbox.sol:39-47`): L1 keys its double-consume
  bitmap on a `leafId` it *documents it cannot verify* is stable across two
  epoch proofs; stability is the **proving system's** obligation. L1 and the
  rollup must agree on message *position*.
- **Aztec AVM deferrals** (`reset_output_validator.nr:52-63`,
  `public_tx_base_inputs_validator.nr:273-280`): the private kernel/rollup defer
  uniquification and public-data-write correctness to the **AVM**.
- **Retroactive support:** the **Frozen-Heart** class (weak Fiat-Shamir) is a
  cross-layer seam *within a single proof system* — prover and verifier
  disagreeing on what entered the transcript. And MASP's Convert tree is a mild
  seam (the circuit trusts a tree built by host/governance). The bucket was
  *latent* in earlier findings; Aztec made it dominant and explicit.

This is a genuinely distinct review target with its own questions (Section 5,
bucket 6).

### 4b. The 6a/6b split (from the AVM falsification test)

Applying the model to four public-layer strategies — Aleo (*re-execute* under
consensus), Mina (*recursively prove the whole state*), and Aztec (*prove the
public VM*) — and then running the cleanest falsification (does proving the
public VM **eliminate** bucket-6 debt, or move it?) forced bucket 6 to split:

- **6a — inter-layer deferral:** "layer A trusts layer B to enforce X."
  **Reducible by proving.** Aztec's AVM converts the Pass-2 deferrals (revertible
  note-hash uniquification; public-data-write correctness) from 6a into
  *proven-in-circuit*: the AVM's PIL relations constrain them
  (`pil/vm2/opcodes/emit_notehash.pil`, `sstore.pil`, …) and the rollup
  *recursively verifies the AVM proof* and binds the private↔AVM interface
  (`public_tx_base_inputs_validator.nr:80,105-224`).
- **6b — interpretation / equivalence:** "multiple encodings of the same
  semantics must agree." **Irreducible.** Proving *creates a new encoding* (the
  circuit/relations) that must now agree with (i) the intended spec — relation &
  opcode-table completeness (`precomputed.pil` is trusted, not proven canonical)
  — and (ii) the executor(s) that build blocks — the
  *simulation ↔ constraining ↔ TS-simulator* equivalence, which is structurally
  identical to Mina's native↔circuit seam.

> **Proving converts 6a into 6b; it does not abolish bucket 6.** A proof is *of a
> circuit*, and the circuit is *one encoding* of the intended semantics; something
> outside the proof must vouch that the encoding matches intent (completeness) and
> that the block-builder matches the encoding (equivalence). The more you prove,
> the more 6a you retire and the more 6b you create.

**Consequence for the model:** bucket 6 is **intrinsic** to any system complex
enough to separate "execution" from "proof/replication of execution" — it is the
one bucket that *survives maximal proving*. The three architectures differ only in
*which form of 6b* they carry (consensus replication vs. native↔circuit vs.
sim↔constrain↔reference). See `AUDIT-AZTEC-AVM-BUCKET6-TEST.md`.

---

## 5. The updated framework (six buckets)

The original "first-week five" — conservation, witnessed points, forks,
dependencies, dual representations — becomes six, with arithmetic/bounds promoted
to a first-class bucket (it carried Penumbra) and cross-layer seams added:

| # | Bucket | The question | Signal it produced | Where it dominated |
|---|--------|--------------|--------------------|--------------------|
| 1 | **Conservation** | Where is `inputs=outputs` enforced, and in which layer? | binding sigs, VCBs, composition | all four |
| 2 | **Witnessed cryptographic objects** | Is this point constrained on-curve & bound to its preimage? | query-collision, witnessed vs derived generator | Zcash, MASP |
| 3 | **Dual representations** | Are all representations forced equivalent *everywhere*? | MASP Convert; Aztec siloing | MASP, Aztec |
| 4 | **Dependency / fork lineage** | Which pinned commit predates which fix; what local edits changed constraints? | Frozen-Heart, RUSTSEC, fork drift | (ecosystem-wide) |
| 5 | **Arithmetic / bounds** | Checked vs saturating vs wrapping; is the bound enforced or assumed? | `overflow-checks`, capped-at-2^52, fail-closed `Balance` | Penumbra |
| 6 | **Cross-layer settlement seams** | Do independent layers agree on the *interpretation* of shared data? | Outbox leaf-id, AVM deferral, public-input binding | Aztec |

**Scoring refinement (from §3):** add **defensive priors** — when a target shows
a prime-order group, explicit circuit breakers, checked/panicking value types, or
in-circuit re-derivation of generators, *lower* the prior on buckets 1–3 and
*raise* it on buckets 5–6. Maturity moves risk from "is the equation right?" to
"do the bounds hold and do the layers agree?"

**Method note that held up:** Phase 9 ("defensive questions only") was sufficient
throughout. Every finding came from *"what invariant fails if this assumption is
false?"* — never from exploit construction. The strict verdict vocabulary did the
rest, repeatedly downgrading candidates to their true trust boundary.

---

## 6. Why it worked

The framework is, in effect, a **trust-cartography** tool. It does not predict
bugs; it predicts *where a system has chosen to place its trust*, and then asks
whether that trust is discharged by a constraint, a derivation, a bound, a host
check, a governance assumption, or another layer. Across four ecosystems the
*location* of trust was different each time — and the model found each location:
- value lives behind a **binding signature / VCB** (conservation);
- identity lives behind **siloing / hash-to-curve** (dual rep / witnessed);
- safety lives behind **bounds and checked types** (arithmetic);
- and, in a rollup, correctness lives behind **inter-layer agreement** (seams).

That a single small framework keeps re-deriving each system's own trust map is
the result. It is more portable than any one finding.

---

## 7. Implications for the (deferred) AVM review

The AVM is expensive to review, so it should be entered as a **test of bucket 6**,
with a precise target list rather than open-ended exploration:
1. **Deferred invariants** — anything the kernel/rollup said "the AVM is
   responsible for" (revertible note-hash uniquification X1; public-data-write
   correctness X3).
2. **Imported assumptions** — values the AVM consumes as given from another layer.
3. **Public-input binding** — does every value the AVM produces enter the proof
   transcript the rollup/L1 verifies?
4. **Nullifier correctness** — AVM-side nullifier emission vs the rollup's
   uniqueness insert.
5. **State-transition interpretation** — does the AVM interpret note indices /
   positions / tree state identically to the circuits that consume its output
   (the leaf-id class)?

If bucket 6 is real, the AVM's risks will cluster on 1, 2, and 5 — *deferred and
imported correctness* — not on local opcode arithmetic. That is the falsifiable
prediction this retrospective sets up.

**Resolved (see `AUDIT-AZTEC-AVM-BUCKET6-TEST.md`):** the prediction held. Local
opcode arithmetic, gas, bytecode binding, and the deferred invariants (X1/X3) are
all *proven in-circuit*; the residual clustered exactly on **deferred/imported
correctness** in its 6b form — relation/spec completeness and
simulation↔constraining↔reference equivalence. Proving the public VM **retired 6a
and exposed 6b** (Section 4b).

---

## 8. Comparative table

| System | Dominant bucket | Debt type | Why it mattered | Outcome |
|--------|-----------------|-----------|-----------------|---------|
| **Zcash / Orchard** | 2 — witnessed objects | (historical) soundness | witnessed-point / setup soundness is where shielded value is forged or not | enforced today; the historical class that anchors bucket 2 |
| **Namada MASP** | 3 — dual representations | **constraint debt** (governance) | `assets↔generator` equivalence enforced host-side at tree-build, not in-circuit; `UncheckedAllowedConversion` | governance-level constraint debt; **no untrusted path** (fed only by migrations) → not routed |
| **Penumbra** | 5 — arithmetic / bounds | **hardening debt** | a mature shielded DEX: rounding pool-favorable & circuit-enforced, VCB-backstopped | residual = enable `overflow-checks`; a "round-once" precision nit; **no conservation failure** |
| **Aztec** | 6 — settlement seams | **trust-boundary debt → then proven** | Outbox leaf-id L1 can't verify; kernel→AVM deferrals (6a) | 6a **retired by proving the AVM**; 6b remains (relation completeness + sim↔circuit) |
| **Aleo** | 6 — settlement seams | enforced (+ bucket-5 hardening) | public state mutated by plaintext `finalize` re-executed under consensus, not proved | enforced by replication + future-binding; bucket-5 `.w` foot-gun at app level |
| **Mina** | 6 (+ some 2) | **trust-boundary debt** | fully-succinct recursive chain = a stack of agreements | native↔circuit equivalence (6b) upheld by single-source code, not proven equivalent |

Reading down the *Dominant bucket* column is the headline: as the systems get
newer and more thoroughly proved, the dominant bucket migrates **2 → 3 → 5 → 6**,
and within 6 the debt migrates **6a → 6b** (irreducible). Local cryptographic
correctness becomes table stakes; **cross-layer / cross-encoding agreement
becomes the frontier.**

---

## 9. Generalization beyond zk: the 6b residue (bridges)

Applying the lens to cross-chain bridges — Wormhole, LayerZero v2, Hyperlane,
which are *almost pure bucket 6* — closes the arc. A bridge connects two systems
that **by construction cannot observe each other**, so "what happened on the
source" must be imported by a third party. There is no 6a to retire; it is **pure
6b**. (See `AUDIT-BRIDGES-SIX-BUCKET.md`.) That makes the bridges the cleanest
statement of the whole investigation's thesis:

> **Bucket 6b is the permanent residue in high-assurance systems: the place where
> one representation of truth must be accepted as equivalent to another, but that
> equivalence cannot be fully proven inside the system being verified.**

Every system reviewed differs only in **how it discharges that one equivalence**:

| System type | How 6b is discharged |
|-------------|----------------------|
| **Aleo** | deterministic consensus re-execution |
| **Aztec** | proven public VM — but spec/circuit equivalence remains |
| **Mina** | recursive proof stack — but native/circuit agreement remains |
| **Committee bridges** | attester threshold signs source-truth |
| **Light-client bridges** | destination verifies encoded source consensus |
| **zk bridges** | destination verifies a *proof* of encoded source consensus |

Read top-to-bottom, the discharge mechanism changes — re-execute, prove, recurse,
trust a committee, verify an encoding, verify a proof of an encoding — but the
*thing being discharged* never does: an equivalence between two representations of
truth that the verifying system cannot fully close on its own. Proving moves it
(6a → 6b); it never abolishes it.

Which yields the framing that makes this a general systems tool, not a zk one:

> **"Trustless" is usually a marketing term. The real question is *which
> equivalence relation* is trusted, proven, replicated, or socially governed.**

That question — *name the equivalence, then name who/what discharges it and how* —
is the entire methodology, compressed. It applies wherever one system must accept
another's account of reality, zk or not.

---

## 10. The Compression/Expansion Axis

*A correction surfaced by the reflexive test — applying the lens to the agent
system running it — not a new target. It does not add a seventh bucket.*

- It is **not a seventh bucket.** It is an **axis that cuts across all six**
  (`embedding ≡ document` is Bucket 2; `model ≡ training distribution` is Bucket 4;
  `summary ≡ evidence` is 6b — a pattern that appears in *every* bucket is an axis,
  not a bucket).
- **Compression** is large reality → smaller representation. It **fails by
  omission** (load-bearing detail dropped).
- **Expansion** is small representation → larger action/implementation. It **fails
  by invention** (unwarranted detail confabulated).
- A system's two boundaries are the two directions: **import = compression**
  (reality → witnessed text), **export = expansion** (intent → effects).
- **Scale-change without recomputation is the operational signature of 6b** — a
  granularity change that no consumer ever decompresses is a trust boundary you
  can locate *mechanically, before understanding the domain.*

> **A summary is a bridge. The producer saw the source state; the consumer sees
> only a commitment to it.**

**The three front-door questions** (ask before the buckets):

1. What equivalences must hold?
2. Who or what discharges each equivalence — and does the consumer recompute, or
   only trust?
3. Where does representation granularity change — compressed on import, expanded
   on export — and is that scale boundary verified?

---

## What this is and isn't
This is a defensive, public-information retrospective synthesizing reviews of
open-source code at named commits. It demonstrates **no** vulnerability; every
system finding was a documented/accepted trust boundary, a hardening item, or
constraint debt with no untrusted path. The artifact's purpose is methodological:
a written record that the framework generated proportional signal across
ecosystems, and a sharpened six-bucket model for the next target.

## Companion reports
`AUDIT-METHODOLOGY.md` (the nine phases) · `AUDIT-METHODOLOGY-CHECKLIST.md`
(one-page how-to) · `AUDIT-FINDINGS.md` (ecosystem/history) ·
`AUDIT-NAMADA-MASP.md`, `AUDIT-NAMADA-CALLSITES.md` · `AUDIT-PENUMBRA.md`,
`AUDIT-PENUMBRA-DEX-STAKE.md`, `AUDIT-PENUMBRA-AMOUNT-SWEEP.md` ·
`AUDIT-AZTEC-PASS1-REPRESENTATION.md`, `AUDIT-AZTEC-PASS2-CONSERVATION.md`,
`AUDIT-AZTEC-AVM-BUCKET6-TEST.md` · `AUDIT-ALEO-SIX-BUCKET.md`,
`AUDIT-MINA-SIX-BUCKET.md` · `AUDIT-BRIDGES-SIX-BUCKET.md` (generalization beyond
zk).
