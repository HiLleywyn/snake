# Auditing a High-Usage, Lightly-Audited zk-Chain

A field methodology for a busy, probably-messy chain with little to no audit
budget. Treat it like an **archaeological dig**, not a traditional top-down
audit: follow the value, find where assumptions are buried, and dig there.

> Historically, more money has been lost to **accounting bugs** than to broken
> elliptic-curve math. Spend your attention accordingly.

---

## TL;DR — Where the bodies are buried

If you were dropped into a random busy chain tomorrow with no budget, spend the
first week almost entirely on these five areas. They have an unusually high
concentration of *"how did nobody notice this for years?"* bugs:

1. **Conservation equations** (`inputs = outputs`)
2. **Witnessed elliptic-curve points**
3. **Forked zk code**
4. **Dependency versions**
5. **Multiple representations of asset identity**

---

## Phase 1 — Map the Money

Don't start with cryptography. Start with value.

> **Ask:** Where does value enter, move, and leave the system?

Build a value-flow graph covering every source and sink:

- Native token minting
- Staking rewards
- Bridges
- Wrapped assets
- Shielded assets
- DEX pools
- Lending protocols
- Governance-controlled mint paths

You are looking for the places where **accounting invariants must hold**. Those
are your dig sites.

---

## Phase 2 — Find the Trust Boundaries

> **Ask:** Enumerate all locations where data crosses trust boundaries.

Typical boundaries:

- L1 → L2
- Bridge → chain
- Wallet → prover
- Prover → verifier
- Oracle → contract
- Consensus → execution

Then, for each boundary:

> **Ask:** What assumptions are made about this data *before* validation?

This is where hidden assumptions live — data trusted before it has earned trust.

---

## Phase 3 — Search for Witnessed Things

In a zk circuit, witnessed values are attacker-influenced until constrained.
Grep for the vocabulary of witnessing:

```
assign_advice
AssignedCell
witness
Advice
Value::known
Option<Point>
Point
NonIdentityPoint
generator
base
asset_base
```

> **Ask:** Which witnessed values eventually influence balances, commitments,
> minting, supply, or state transitions?

You don't care about every witness. You care about **witnesses that touch
money**.

---

## Phase 4 — Hunt Conservation Equations

Find every equation that asserts value is conserved:

```
inputs = outputs
sum(in) - sum(out) = 0
cv_net = 0
```

…or any equivalent balance check.

> **Ask:** Trace every variable participating in conservation. Show where each
> variable becomes constrained.

An unconstrained (or under-constrained) participant in a conservation equation
is where **counterfeiting bugs** emerge.

---

## Phase 5 — Search for "Dual Representations"

The highest-ROI check in this entire methodology.

Look for any concept that exists in **two forms at once**:

```
asset_id
asset_base
token
generator
pubkey
point
amount
commitment
```

> **Ask:** Are these representations forced to remain equivalent *everywhere*?

Many zk bugs occur when two representations of the same concept are allowed to
**drift apart** — the circuit binds one but not the other.

---

## Phase 6 — Review Dependency History

Don't look only at current code. Look at *when* the code was frozen.

> **Ask:** Which cryptographic libraries are pinned? Which pinned commits
> predate major security disclosures?

Usual suspects:

- `halo2`
- `arkworks`
- `bellman`
- `plonky2`
- `gnark`
- `circom`

Compare pinned versions against known bugfixes. **Many projects pin old
versions indefinitely** and never pick up the security patch.

---

## Phase 7 — Look for Forks

The dangerous code is often not original — and a tiny local edit can silently
invalidate an upstream audit.

> **Ask:** Which files are copied from upstream projects?

Common upstream sources:

- Zcash
- Aztec
- PSE
- Scroll
- Polygon zkEVM
- StarkWare examples

Then:

> **Ask:** Which local modifications changed constraints?

A single changed or removed constraint can break a circuit that was "audited"
upstream.

---

## Phase 8 — Rank Findings

Don't chase every anomaly. Score each finding and let the score nominate it for
scarce human review.

| Property                  | Score |
| ------------------------- | :---: |
| Touches money             |  +5   |
| Touches conservation      |  +5   |
| Witnessed point           |  +3   |
| Cryptographic primitive   |  +3   |
| Old dependency            |  +2   |
| No audit nearby           |  +2   |
| Hidden behind abstraction |  +2   |

The highest-scoring items deserve human eyes first.

---

## Phase 9 — Ask Defensive Questions Only

Stay on the defensive side of the line. The same bugs surface without crossing
into exploit development.

**Avoid:**

> Can I exploit this?

**Instead ask:**

> What invariant would fail if this assumption were false?

and

> Can the circuit *prove* that assumption?

These questions tend to uncover the same bugs — from the defender's seat.

---

## Appendix — The First-Week Plan

| Priority | Focus area                              | Why it pays off                         |
| :------: | --------------------------------------- | --------------------------------------- |
|    1     | Conservation equations                  | Counterfeit / inflation bugs            |
|    2     | Witnessed elliptic-curve points         | Under-constrained, money-touching       |
|    3     | Forked zk code                          | Upstream audit silently invalidated     |
|    4     | Dependency versions                     | Known, already-patched disclosures      |
|    5     | Multiple representations of asset ID    | Representation drift → value bugs        |

Follow the money first. The cryptography can wait.

---

> **Update — six buckets.** After applying this methodology across Zcash/Orchard,
> Namada MASP, Penumbra, and Aztec, the "first-week five" were refined into six,
> promoting **arithmetic / bounds** to a first-class bucket and adding
> **cross-layer settlement seams** (correctness that depends on independent
> layers agreeing on a shared interpretation). See
> [`AUDIT-METHODOLOGY-RETROSPECTIVE.md`](./AUDIT-METHODOLOGY-RETROSPECTIVE.md) for
> what predictions succeeded, which failed, and the scoring refinement
> (down-weight buckets 1–3 when structural defenses are present; up-weight 5–6).
