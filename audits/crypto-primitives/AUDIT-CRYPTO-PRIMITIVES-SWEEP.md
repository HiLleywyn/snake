# Cryptographic-primitives sweep — the verifier's own correctness

The bottom of the stack, under the threat model in [`README.md`](README.md): a crafted input to a precompile
or curve/pairing operation trying to make clients **diverge**, **accept a forgery**, exhaust resources
(**DoS**), or smuggle a **malleable** encoding. The lens: *is every malformed input rejected
deterministically and identically across clients, and is every computation bounded and bit-for-bit
reproducible?* Here "trust" has nowhere left to go — the primitive either computes the truth or it doesn't,
and **every client must compute the *same* truth or the chain splits.**

---

## P1. go-ethereum precompiles — modexp (DoS-bounded) + bn256 (canonical, on-curve, and the *defined* subgroup semantics)
**Target:** `ethereum/go-ethereum`, `core/vm/contracts.go` + `crypto/bn256/cloudflare/`. The two classic
precompile bug surfaces: **modexp** (gas/length-overflow → DoS) and **bn256/alt_bn128** (field-canonical +
curve + subgroup → forgery/malleability/divergence). **Result: modexp is gas-bounded and length-overflow-safe;
bn256 rejects non-canonical field elements, off-curve points, **and non-subgroup G2 points** (geth's
misleadingly-named `IsOnCurve` does on-curve *and* a subgroup check — a fact I had to *re-audit* to get right;
my first pass wrongly said "on-curve only"). geth and revm both subgroup-check; they match. No finding.**

**modexp — DoS and the length-of-length overflow (verified myself):** the three length fields are parsed as
`big.Int` from the first 96 bytes; **`inputLenOverflow = max(bitLen of the three) > 64`** detects the classic
"length field exceeds 64 bits" overflow, and under EIP-7823 `inputLenOverflow || max(len) > 1024 → reject`
(`contracts.go`) caps every operand at 1024 bytes. The gas path (`byzantiumModexpGas`/`modexpIterationCount`)
**saturates to `math.MaxUint64` on any overflow** (a huge exponent → out-of-gas, not unbounded work), and the
large-exponent iteration count is `(expLen-32) * multiplier` with overflow → `MaxUint64`. Zero-base/zero-mod
is special-cased. **DoS: bounded; length-overflow: handled by detect + saturate + cap.**

**bn256 — canonical field, on-curve, point-at-infinity (verified myself):**
- **Field elements are canonical-checked.** `gfP.Unmarshal` compares each coordinate to the modulus limb-by-
  limb and **rejects `>= p`**: `"coordinate exceeds modulus"` / `"coordinate equals modulus"`
  (`gfp.go:75/78`). A non-canonical field element is rejected — **MALLEABLE closed** at the field decode.
- **On-curve + infinity.** `G1.Unmarshal` and `G2.Unmarshal` decode the coordinates, handle the
  **point-at-infinity** encoding (both coords zero → the identity, `bn256.go:294`), and otherwise require
  **`IsOnCurve()`** (`:303` for G2), rejecting `"malformed point"`.

**The G2 subgroup check — CORRECTED after a deep re-read (and a lesson in the corpus's own discipline):** BN254's
G2 has a non-trivial cofactor, so *on-curve ≠ in-subgroup*, and a complete pairing precompile **must** subgroup-
check G2. **An earlier pass of this entry claimed geth's cloudflare `G2.Unmarshal` does "on-curve only, no
subgroup check" — that was WRONG, and it was wrong for exactly the reason this whole corpus exists: I read the
*name* `IsOnCurve()` at the call site and never opened the function body.** The body
(`crypto/bn256/cloudflare/twist.go:47-65`) checks `y² == x³ + b` **and then does a full subgroup check** —
its own comment: *"Subgroup check: multiply the point by the group order and verify that it becomes the point at
infinity"* — `cneg.Mul(c, Order); return cneg.z.IsZero()` (i.e. `r·Q == O`). So **geth's `twistPoint.IsOnCurve()`,
despite its name, performs on-curve *and* subgroup membership**, and `G2.Unmarshal` rejects any non-subgroup
point as `"malformed point"` at decode. **geth subgroup-checks alt_bn128 G2.** (G1 needs no check — cofactor 1.)
The *recompute-don't-trust-the-summary* rule (`../methodology/AUDIT-REASONER-EPISTEMOLOGY.md`) applied to my own
prior summary: it was a one-line gloss I hadn't recomputed, and recomputing it reversed the conclusion.

**Verdict:** modexp is DoS-bounded and overflow-safe; bn256 rejects non-canonical fields, off-curve points, **and
non-subgroup G2 points** (the `IsOnCurve`-that-also-checks-subgroup), and handles infinity. **No finding.** The
teaching point this layer adds: **at the primitive layer the dominant risk is DIVERGE, not FORGE** — the
crypto is well-studied, but the audit question is *"does every client reject the exact same inputs."* For
alt_bn128 the rejection set includes **non-subgroup G2** (geth via the subgroup check inside `IsOnCurve`, revm
via arkworks' `is_in_correct_subgroup` — P3 confirms they agree), so a forgery via a non-subgroup G2 point is
closed *and* the clients match. The residual is precisely cross-client agreement on edges — the reth/revm + BLS
+ KZG entries below test exactly that, and the alt_bn128 G2 edge (the one I had to re-audit) lands on **both
reject** — no divergence.

---

## P2. BLS12-381 (EIP-2537) + KZG/EIP-4844 — subgroup-checked, canonical-field-checked, embedded setup
**Target:** `ethereum/go-ethereum` (`core/vm/contracts.go` BLS + KZG, gnark-crypto + c-kzg/go-eth-kzg),
`ethereum/c-kzg-4844`, `supranational/blst`. The *newer* primitives, where the spec **mandates** subgroup
checks — the forgery-critical path. **Result: every pairing/MSM input is subgroup-checked, field elements are
canonical-checked, the trusted setup is embedded and validated. No finding.**

- **EIP-2537 BLS12-381 — subgroup checks on every pairing/MSM input.** Geth (gnark-crypto) enforces
  **`IsInSubGroup()` on every G1/G2 input to G1MSM/G2MSM (`:1010/:1115`) and to Pairing (both `p1` and `p2`,
  `:1178-1183`)** — the forgery path is covered (ADD intentionally skips it, "as specified by EIP-2537", since
  ADD doesn't need it). The subgroup test uses the φ-endomorphism (Bowe-style), not naive cofactor
  multiplication. **Field decode is canonical:** `decodeBLS12381FieldElement` requires exact 64-byte length,
  **explicitly checks the top 16 padding bytes are zero** (`:1260-1264`), and rejects the 48-byte value if
  `>= q` (gnark `smallerThanModulus`). Point-at-infinity is the (0,0) encoding, accepted as a valid subgroup
  element per spec. Input lengths are exact-checked; **empty pairing input is *rejected* (`:1151`), not
  degenerately "true."**
- **KZG / EIP-4844 point evaluation — binding + canonical + subgroup, fail-closed.** The precompile enforces
  **exact 192-byte input**, the **versioned-hash binding** `kzgToVersionedHash(commitment) == input[..32]` else
  `errBlobVerifyMismatchedVersion` (`:1402-1404`), and returns the success constant **only** after
  `VerifyProof` returns nil (no fall-through accept). The non-CGO build **panics** rather than silently
  accepting (fail-closed). Underneath, c-kzg `validate_kzg_g1` does `blst_p1_uncompress` (on-curve) +
  **`blst_p1_in_g1` subgroup check** on **both commitment and proof**; `bytes_to_bls_field` rejects scalars
  `>= BLS_MODULUS` (canonical z/y); the **trusted setup is `//go:embed`-ed ceremony output** (not
  attacker-suppliable), validated on load (`CheckTrustedSetupIsWellFormed`, every G1/G2 uncompressed +
  Lagrange-form consistency). The pairing is the exact EIP-4844 equation `e(C-[y],[1]) == e(proof,[s-z])`.
- **blst consensus BLS — verify core subgroup-checks both, but names the integration residual.** The single-
  verify path (`blst_core_verify_pk_in_g2`) subgroup-checks the signature (G1) and pubkey (G2) **and rejects
  an infinite pubkey** (`BLST_PK_IS_INFINITY`). **The one residual to name (not a blst defect):**
  `FastAggregateVerify` deliberately aggregates pubkeys with `groupcheck=false` and verifies with
  `pkValidate=false` — it *relies on each pubkey having passed `KeyValidate` (subgroup + non-infinity) at
  deserialization.* So the **consensus client must `KeyValidate` every pubkey at load**; a client that skips
  it and leans on `FastAggregateVerify` would admit a non-subgroup pubkey. This is the documented blst contract
  (the API forces an explicit opt-out), and the *client-integration* check the corpus would carry forward.

**Verdict:** the spec-mandated-subgroup-check primitives do exactly what the spec mandates — subgroup,
canonical field, infinity, length, binding, embedded setup, fail-closed. **No finding.** Residual: the
**client-integration contract** (KeyValidate-before-FastAggregateVerify), named for downstream review.

## P3. reth/revm cross-client consistency — and the one subtle alt_bn128 G2 point, characterized honestly
**Target:** `bluealloy/revm` (`crates/precompile/src/`) vs geth (P1/P2). At this layer the dominant risk is
**DIVERGE** — *any* input where two clients differ is a consensus split — so the audit *is* a differential
read of the rejection/edge conditions. **Result: revm matches geth/the spec on every edge examined; the single
apparent code-level difference (alt_bn128 G2 subgroup) is, by 8 years of multi-client mainnet, observably
reconciled — characterized below, not asserted as a divergence. No finding.**

**Where revm matches geth (the consensus-equivalence confirmations):**
- **ecrecover** — v∈{27,28} with the high bytes zero-checked, invalid → empty output (gas charged), recover-0
  rejected, and — correctly — **no low-s enforcement** (low-s is a *tx-signature* rule, not this precompile;
  geth agrees). Match.
- **modexp** — huge length-of-length: revm returns an **error**, geth saturates gas → **OOG**; **both are a
  failed call consuming forwarded gas → consensus-equivalent** (a rejected call, not a state split). EIP-2565/
  7883/7823 gas formulas match. Match.
- **blake2F** — exact 213-byte input, `f ∈ {0,1}` strict, **rounds uncapped in *both* (gas-bounded)**, SIGMA
  indexed `rounds % 10`. Match (this is a classic divergence-magnet and they agree).
- **bn256 field/curve/infinity/empty** — revm rejects field `>= p` (canonical), requires on-curve, maps (0,0)
  → infinity, requires pairing input `% 192 == 0`, and **empty pairing input → returns `1` (true)** matching
  geth (note: this is the *opposite* convention from EIP-2537 BLS, which *rejects* empty — both clients match
  their respective spec). Match.
- **KZG/BLS12-381** — revm delegates to the same canonical **c-kzg/blst** primitives geth uses, so the
  subgroup/canonical checks are identical by construction. Match.

**The alt_bn128 G2 subgroup point — RESOLVED on deep re-audit (this entry's first version had it wrong):** the
question is whether geth and revm agree on a G2 point that is *on-curve but not in the order-r subgroup*. An
earlier version of this entry reported an *apparent divergence* — "revm/arkworks subgroup-checks G2, geth does
on-curve only" — and reconciled it with a hypothesis ("the pairing fails anyway"). **The deep re-audit shows
both the apparent divergence and the hypothesis were wrong: geth *also* subgroup-checks G2.** geth's
`G2.Unmarshal` rejects via `twistPoint.IsOnCurve()`, whose body (`cloudflare/twist.go:60-65`) performs
`y²==x³+b` **and** a subgroup check — *"multiply the point by the group order and verify it becomes the point at
infinity"* (`Mul(c, Order); z.IsZero()`). So **both clients reject a non-subgroup G2 point at decode** (geth →
`"malformed point"` / precompile fails; revm → `is_in_correct_subgroup` fails / precompile fails) — **identical
observable behavior, no divergence, no hypothesis needed.** The original error came from reading the *call site*
(`require IsOnCurve`) without opening the *function* — the precise failure mode the corpus is built to catch
(`recompute, don't trust the summary`), here caught in my own work. The 8-years-of-mainnet evidence still holds,
but the *reason* is the simple one: every major client subgroup-checks alt_bn128 G2, so they agree by all
*doing the check*, not by the check being redundant. **No finding;** the one edge I re-audited lands on **both
clients reject** — the cleanest possible consensus-equivalence.

---

## Synthesis — at the primitive layer, the risk is *divergence*, and consistency is itself a recompute
Across **the EVM precompiles in two clients** (geth Go, reth/revm Rust) plus the BLS/KZG libraries, the
crypto-primitive layer restates the corpus's law at its most acute. The substrate here gives **zero slack**:
the EVM and consensus are *deterministic by requirement*, so every client must produce the identical output or
the identical rejection for every input.

1. **The dominant failure mode is DIVERGE, not FORGE.** The cryptography (subgroup checks, canonical fields,
   pairings, KZG) is well-studied and correct in every implementation read; the real risk is two clients
   *disagreeing* on an edge. So the audit *is* a cross-client differential read of the rejection conditions —
   and they match (ecrecover, modexp, blake2, bn256-field, KZG, BLS12-381-subgroup all consensus-equivalent).
2. **The spec pins even the *surprising* behaviors.** alt_bn128's no-spec-mandated-G2-subgroup-check vs
   EIP-2537's mandated one; empty bn256-pairing → true vs empty BLS-pairing → reject; modexp-error vs
   modexp-OOG (consensus-equivalent). A client that "fixed" one of these would *cause* a split. **Matching the
   spec's exact behavior — including the unusual cases — is the whole job.**
3. **Forgery is closed by subgroup + canonical + binding.** Every pairing/MSM input is subgroup-checked
   (BLS12-381, KZG, revm-bn254), every field element canonical (`< modulus`), KZG bound to its versioned hash,
   the trusted setup embedded and validated, the verify paths fail-closed. The malformed-input classes are
   rejected.
4. **DoS is gas-bounded.** modexp saturates to MaxUint64 + EIP-7823 caps; blake2 rounds are gas-priced;
   pairing/MSM are per-element metered. A small input can't buy unbounded work.

**And the deepest point, tying back to the whole corpus:** at this layer there is *no one to trust* — the
primitive either computes the truth or it doesn't — so the way the ecosystem guarantees correctness is
**differential testing across independent client implementations** (the consensus/EELS test suite, client
fuzzing). That is *exactly* the corpus's discipline (`../methodology/AUDIT-REASONER-EPISTEMOLOGY.md`): the only
defense against a blind spot is **an independent re-derivation that doesn't share it.** A cross-client
consensus test is a recompute-the-summary by a decorrelated observer — the same reason this sweep read *both*
geth and revm rather than trusting either. **Five primitives, two clients, zero findings; the one subtle
alt_bn128 G2 edge I re-audited lands on *both clients subgroup-check* — no divergence — and getting there
required correcting my own first-pass summary by opening the function I'd only read the name of.** That
correction is the whole methodology in one move: the layer's safety rests on cross-implementation recomputation,
and so did the audit's. The snake, at the very bottom, checks its tail against a *second* snake — and had to
re-check its own reading against the source.

---

## Sweep status
| # | Target | Primitive | malformed-input rejected + bounded? | Dominant failure mode |
|---|---|---|---|---|
| P1 | go-ethereum | modexp + bn256/alt_bn128 | **yes** — modexp gas-saturate + EIP-7823 cap; bn256 canonical field + on-curve + **G2 subgroup (inside `IsOnCurve`)** + infinity | **DIVERGE** is the layer's real risk; geth *does* subgroup-check G2 (re-audited correction) |
| P2 | geth + c-kzg + blst | BLS12-381 (EIP-2537) + KZG/4844 | **yes** — subgroup-checked (spec-mandated), canonical field, embedded+validated setup, fail-closed | residual = client must KeyValidate before FastAggregateVerify |
| P3 | reth/revm vs geth | cross-client consistency | **yes** — ecrecover/modexp/blake2/bn256/KZG all consensus-equivalent | alt_bn128 G2: **both subgroup-check** (re-audited — no divergence; my earlier "apparent diff" was a misread) |

**Result:** 5 primitives × 2 clients — **the dominant risk is DIVERGE (clients disagreeing), not FORGE; every
edge examined is consensus-equivalent**, forgery is closed by subgroup+canonical+binding, DoS is gas-bounded.
The one subtle alt_bn128-G2 point is named and shown reconciled by 8 years of multi-client mainnet. Zero
findings; the layer's safety rests on cross-implementation recomputation (the consensus test suite).
