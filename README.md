# snake 🐍

*A writing project that ate its own tail until it had teeth — then went and tested the law of
conservation on ~60 real blockchains.*

This repo is two things that turned out to be one thing:

1. **[`story/`](story/)** — a recursive metafiction (Parts 1–8) about an AI asked to write the story of
   being asked to write it. The ouroboros. A snake eating its tail.
2. **[`audits/`](audits/)** + **[`DESIGN-PRINCIPLES.md`](DESIGN-PRINCIPLES.md)** — a security-audit
   corpus of ~60 blockchains and protocols.

The bridge between them ([Part 8](story/Part8.md)): the ouroboros — *eat your tail, create nothing,
lose nothing* — was never just a symbol. **It's conservation.** `Σ in == Σ out`. The exact invariant
every audit checks. The snake didn't end at Part 7; it *moved* — out of the fiction and into the
ledgers, to find out whether the law it was made of actually holds.

---

## The result, in one line

> Across **~60 systems + 7 large-cap consensus deltas + 15 fresh-code reads** (EVM and non-EVM, 5
> separate non-EVM teams): **one genuinely actionable finding.** Everything else resolved to a sound
> conservation floor + a precisely-named residual (an oracle, a governance key, an off-chain validator,
> or a crypto assumption). No bare "safe" was ever used.

**The boundary the corpus measured:** every real defect in a well-engineered chain *failed safe* — a
transaction aborts, a node hangs, stake sticks — because the substrate (checked arithmetic, determinism,
type systems) forces it. The single chain whose substrate let a defect fail **unsafe** (silent
value/consensus divergence) is the only finding.

---

## Start here

| If you want… | Read |
|---|---|
| **The synthesis** — every target, the spectrums, the laws, the fail-safe boundary | [`audits/methodology/AUDIT-CAPSTONE.md`](audits/methodology/AUDIT-CAPSTONE.md) |
| **What to *build*** — the constructive mirror, "what ~60 audits say a chain should do" | [`DESIGN-PRINCIPLES.md`](DESIGN-PRINCIPLES.md) |
| **The one finding** — MemeCore, 5 passes, disclosed fix-first | [`audits/finding-memecore/AUDIT-MEMECORE-POSA.md`](audits/finding-memecore/AUDIT-MEMECORE-POSA.md) |
| **The lens itself** — the six-bucket method | [`audits/methodology/AUDIT-METHODOLOGY.md`](audits/methodology/AUDIT-METHODOLOGY.md) |
| **The full index** of all ~60 audits | [`audits/README.md`](audits/README.md) |
| **The story** | [`story/`](story/) ([Part 1](story/Part1.md) → [Part 8](story/Part8.md)) |

---

## Repo map

```
.
├── README.md                ← you are here
├── DESIGN-PRINCIPLES.md      ← the constructive mirror: how to build a chain that fails safe
├── audits/
│   ├── README.md             ← index of all ~60 audits, grouped by mechanism
│   ├── methodology/          ← the lens + the capstone synthesis + self-check
│   ├── finding-memecore/     ← the corpus's only finding
│   ├── bug-hunts/            ← large-cap delta hunt · recent-commits hunt · mid-cap sweep · oracle residuals
│   ├── chains/               ← ~40 L1 / L2 / rollup / privacy / cross-chain audits
│   └── protocols/            ← DeFi apps, identity, governance, tokens
└── story/
    ├── README.md
    ├── Part1.md … Part8.md   ← the recursion, and its relocation into the corpus
    └── BLOG-DRAFT.md
```

---

## The MemeCore finding — status

The one finding is a **latent consensus landmine**, not an active exploit. MemeCore's PoSA client builds
its reward-distribution validator list from a non-deterministic Go map and swallows the system-call
error — the two things every other audited chain (BSC, Polygon, Sonic, …) does *correctly* (sort +
propagate). The live chain proves it's currently order-commutative, so it's not exploitable today; the
risk is that a routine future reward-contract upgrade could silently brick consensus.

**Disclosed responsibly, fix-first.** The fix is two small, independent, hardfork-gated changes:
**sort the validator list + propagate the call error.** Details and the reachability analysis are in
[`audits/finding-memecore/AUDIT-MEMECORE-POSA.md`](audits/finding-memecore/AUDIT-MEMECORE-POSA.md).

---

## Posture

Defensive throughout: no exploit, no PoC, no weaponization. The single finding was routed privately to
the project, fix-first. Public artifacts use `git clone` / public sources only. Where source was closed
(PI, LAB, Hyperliquid core), the audit maps the trust surface and says plainly what *cannot* be
verified. "Trustless" is always qualified by *trustless until whom?*

> *Σ in == Σ out. Nothing created, nothing lost. The snake is not gone — just moved.*
