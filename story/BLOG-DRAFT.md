# Where Trust Concentrates: A Review Heuristic for zk Systems

*Draft. This is a methodology essay about a **review lens**, not a security audit
and not a certification of any system. Every system named below is used to
illustrate how the lens **predicts where to look** — not to make a security
claim. All observations are of public source code at a point in time, and all are
either enforced invariants, documented/accepted trust boundaries, or
hardening suggestions. No vulnerabilities are claimed or disclosed.*

---

## The claim

Most write-ups about reviewing zero-knowledge systems are bug lists. This is not
that. It's a single, small heuristic for answering a different question:

> **Where has this system chosen to place its trust, and is that trust actually
> discharged?**

A good lens shouldn't find the same bug everywhere. It should keep re-deriving
each system's *own* map of where correctness has to hold — and, ideally, tell you
something about how those maps change as an ecosystem matures.

## Six buckets

After reading across several mature zk codebases, the places trust concentrates
sort cleanly into six buckets:

1. **Conservation** — where `inputs = outputs` is enforced (and in which layer).
2. **Witnessed cryptographic objects** — is a witnessed point/proof bound to its
   preimage, or re-derived?
3. **Dual representations** — must two forms of the same thing (id ↔ commitment ↔
   nullifier ↔ generator) stay equal *everywhere*?
4. **Dependency / fork lineage** — stale pins; local edits that void an upstream
   audit.
5. **Arithmetic / bounds** — checked vs saturating vs wrapping; is a bound
   *enforced* or merely *assumed*?
6. **Cross-layer settlement seams** — correctness depends on *multiple
   independently-correct systems agreeing on a shared interpretation*.

The method is deliberately defensive: every question is *"what invariant fails if
this assumption is false?"*, never *"can I exploit this?"* And every candidate is
forced to a verdict — **enforced**, **constraint debt**, **trust-boundary debt**,
or **hardening debt** — which, in practice, *downgrades* most candidates. The
discipline of recording the downgrades is what keeps the lens honest.

## What the lens predicted

Used as a *predictor of where to look* (not a bug hunt), the lens kept landing on
each system's actual trust concentration — and the concentration was different
each time:

- A mature **shielded multi-asset pool**'s subtle point wasn't its asset-generator
  math (that was tightly constrained); it was one layer over, in a
  **governance-fed** path where an equivalence is enforced at tree-build time
  rather than in-circuit. *Dual representation → constraint debt, no untrusted
  path.* (Bucket 3.)
- A mature **shielded DEX** that looked like an obvious conservation target turned
  out to have pool-favorable, circuit-enforced rounding with an explicit value
  circuit breaker. The only residual was a build-profile **hardening** flag.
  (Bucket 5 — and a *negative* result, which is itself signal.)
- Three chains with radically different public-execution strategies — *re-execute
  under consensus*, *recursively prove the whole state*, and *prove the public VM
  as a circuit* — **all** concentrated their residual risk in **bucket 6**.

That last point is the interesting one.

## Maturity moves risk to the seams

Reading the dominant bucket across systems, oldest-and-simplest to
newest-and-most-proved, it migrates: **2 → 3 → 5 → 6.** Local cryptographic
correctness becomes table stakes. What's left is *agreement between layers and
between encodings.*

So we ran the sharpest test we could think of. One architecture *proves* its
public virtual machine as a circuit. If proving is what closes cross-layer seams,
this should have the least bucket-6 exposure of all.

**It didn't eliminate the seam — it moved it.** Proving the public VM genuinely
retired the *inter-layer deferrals* (the surrounding protocol no longer trusts an
unverified layer; it verifies a proof and binds the interface). But it created a
new obligation in their place: the proof is *of a circuit*, and the circuit is
*one encoding* of the intended semantics. Something outside the proof still has to
vouch that the encoding matches the intended spec (relation completeness) and that
the executor building blocks matches the encoding (implementation equivalence).

That forces bucket 6 to split:

- **6a — inter-layer deferral.** *Reducible by proving.*
- **6b — interpretation / equivalence.** *Irreducible* — proving adds an encoding
  that must agree with the spec and the executor.

> **Proving converts 6a into 6b. It doesn't abolish bucket 6.** The more you prove,
> the more 6a you retire and the more 6b you create.

Which yields the one durable conclusion: **cross-layer/cross-encoding agreement is
intrinsic to any system complex enough to separate *execution* from *proof or
replication of execution*.** It is the one bucket that survives maximal proving.

## Why this might not be a "zk" finding at all

If bucket 6 is really about *independent systems agreeing on a shared
interpretation*, it shouldn't be specific to zero-knowledge. The natural next test
is a domain that is **almost pure bucket 6**: cross-chain bridges and messaging
protocols, where security *is* the agreement between a source chain, a transport,
and a destination chain. If the same lens — 6a vs 6b, "who vouches the encoding,"
"does every value enter the transcript the next layer verifies" — keeps locating
the trust concentration there, then this stops being a zk methodology and becomes
a general **high-assurance systems review heuristic**.

That's an open question, not a result. Which is the right note to end on: the
useful artifact here isn't a finding about any one system. It's a lens, offered
for other reviewers to point at their own targets — and to falsify.

---

### What this is / isn't (please read)
- **Is:** a review heuristic, illustrated with public-code observations.
- **Isn't:** a security audit, a certification, or a claim that any named system
  is (or isn't) secure. Reviews were time-boxed and defensive; absence of a
  finding here means *the lens did not surface one*, not that none exists.
- **No vulnerabilities** are claimed or disclosed; the named items are enforced
  invariants, documented trust boundaries, or hardening suggestions.
- The most useful response to this post is to **try the lens and tell us where it
  fails.**
