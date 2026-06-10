# P2 (deep) — BLS12-381 (EIP-2537) + KZG/4844: the 9-precompile matrix, the Pippenger discount, the φ-endomorphism subgroup test, and the c-kzg internals

**Scope.** A deep, individualized expansion of sweep item **P2** (`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P2), going
past "subgroup-checked on every input" the rapid pass covered into the **full EIP-2537 suite + the curve/KZG
internals**: the per-precompile length/subgroup matrix, the MSM Pippenger discount, the map-to-curve
cofactor-clear, the **gnark φ/ψ-endomorphism subgroup test** (not naive cofactor mul), and c-kzg's
`validate_kzg_g1` + the pairing equation + the trusted-setup load. Targets: `ethereum/go-ethereum` @ `1f87331`
(`core/vm/contracts.go` + gnark-crypto v0.18.1), `ethereum/c-kzg-4844` @ `e1c5705`. Read-only, public-source,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** one genuinely new factual
observation (c-kzg does not subgroup-check the *trusted-setup* points) is named.

---

## 0. What the deep pass adds over the sweep

The sweep established "every pairing/MSM input is subgroup-checked." The deeper reading supplies the
*mechanism and the matrix*: ADD **intentionally** skips the subgroup check (spec-correct — ADD is closed on the
full curve, and PAIRING re-checks independently); the subgroup test is the **fast φ/ψ-endomorphism (Bowe/Scott)
check**, not a cofactor multiply; map-to-curve outputs are **in-subgroup by construction** (cofactor clear); and
c-kzg's untrusted-input gate (`validate_kzg_g1`) subgroup-checks commitment+proof while the **trusted-setup load
does *not*** (by trust model).

---

## 1. The per-precompile length/subgroup matrix. **ADD skips it, by spec.**

| Precompile | Addr | Length | On-curve | Subgroup |
|---|---|---|---|---|
| G1ADD | 0x0b | `==256` | yes | **none** (`:953` "as specified by EIP-2537") |
| G1MSM | 0x0c | `%160, !=0` | yes | **yes** `IsInSubGroup` per point (`:1010`) |
| G2ADD | 0x0d | `==512` | yes | **none** (`:1057`) |
| G2MSM | 0x0e | `%288, !=0` | yes | **yes** (`:1115`) |
| PAIRING | 0x0f | `%384, !=0` | yes | **yes, both G1 & G2** (`:1178,1181`) |
| MAP_FP→G1 | 0x10 | `==64` | output in-G1 by cofactor clear | n/a |
| MAP_FP2→G2 | 0x11 | `==128` | output in-G2 by cofactor clear | n/a |

**Characterization:** the ADD precompiles **deliberately omit** the subgroup check — spec-correct because ADD is
closed on the full curve `E(Fp)`, so a non-subgroup input just yields a non-subgroup result; it **cannot forge a
pairing** because PAIRING subgroup-checks independently. The two-stage validation (on-curve at `decodePointG1`,
subgroup at the call site) is the deep structure. Field decode (`decodeBLS12381FieldElement :1255-1269`) requires
**exact 64 bytes, top-16-bytes-zero, and value < q**. (Honest note: PAIRING silently maps a `PairingCheck`
*error* to a `0` result — a false-negative only, benign.)

---

## 2. The MSM Pippenger discount. **A pricing model, not the runtime bucket count.**

`G1MSM`/`G2MSM` gas: `k = len/{160|288}`; `discount = DiscountTable[min(k, 128)-1]`; gas =
`(k · {12000|22500} · discount) / 1000` (`:970-985, 1075-1090`). The discount tables are `[128]uint64`
**monotonically decreasing** (G1 1000→519, G2 1000→524) — modeling Pippenger's sub-linear cost as pairs grow —
clamped at 128 (linear past that, at the floor discount). The actual compute calls gnark `MultiExp` whose window
`c` is chosen at runtime to minimize `bits/c · (n + 2^c)`.
**Characterization:** the gas is a **fixed closed-form per-pair discount, independent of the runtime window** the
Pippenger bucket method actually picks — a conservative pricing model, not tied to the real bucket count; no DoS
lever (pricing is conservative vs the asymptotic, and `k≥1` before the multiply rules out underflow).

---

## 3. Map-to-curve — output in-subgroup by cofactor clear. **Why MAP needs no subgroup check.**

gnark `MapToG1 (hash_to_g1.go:14-20)`: `MapToCurve1` (SSWU onto the isogenous curve) → `G1Isogeny` (11-isogeny
back to E) → **`ClearCofactor`** (forces the result into `G1[r]`); `MapToG2` is the analogous SSWU → `G2Isogeny`
→ `ClearCofactor`. G1's `ClearCofactor` uses the efficient `[x]P + P` (eprint 2019/403) rather than a full
cofactor scalar-mult.
**Characterization:** **the cofactor clear guarantees in-subgroup output**, which is exactly why the map
precompiles need no separate `IsInSubGroup` call — the φ/ψ test would pass by construction. The standard, correct
reason map outputs feed straight into a pairing.

---

## 4. The φ/ψ-endomorphism subgroup test — the deep mechanism. **Bowe/Scott, not cofactor mul.**

gnark **G1** `IsInSubGroup (g1.go:196-208)` tests the GLV short vector `(1, x²)`: `P + x²·φ(P) = O`, where
`φ` is just `X ← X·thirdRootOneG1` (multiply the x-coordinate by a cube root of unity — **O(1) field mult, no
scalar mult**):
```go
res.phi(&_p).mulBySeed(&res).mulBySeed(&res).Neg(&res)   // -x²·φ(P)
return res.Equal(&_p)                                    // == P  ⟺  P + x²·φ(P) = O
```
**G2** `IsInSubGroup (g2.go:203-213)` tests `ψ(P) == [x₀]P` (`ψ` = untwist–Frobenius–twist), citing eprint
2021/1130 / 2022/352.
**Characterization:** both are the **fast endomorphism-based membership checks** — one short ~64-bit seed-scalar
mult plus a constant-time endomorphism, **dramatically cheaper than a full cofactor multiply** — and they are the
basis for every geth BLS subgroup gate. The genuinely deeper mechanism the rapid pass glossed; no correctness
concern.

---

## 5. c-kzg verify — validate, then one pairing equation. **Fail-closed on untrusted input.**

`verify_kzg_proof` validates **all four untrusted inputs before any group op** (commitment, z, y, proof). The
gate is `validate_kzg_g1 (common/bytes.c:81-95)`:
```c
if (blst_p1_uncompress(...) != BLST_SUCCESS) return BADARGS;   // encoding + on-curve
if (blst_p1_is_inf(out)) return OK;                            // infinity ACCEPTED (4844 allows it)
if (!blst_p1_in_g1(out)) return BADARGS;                       // explicit subgroup check
```
(both commitment and proof route through it; `bytes_to_bls_field` enforces scalar < `BLS_MODULUS`). The equation
`verify_kzg_proof_impl` is the EIP-4844 `e(C−[y],[1]) == e(proof,[s−z])` via `pairings_verify` (two miller loops,
one shared `blst_final_exp`, `fp12_is_one`). The batch path is a random-linear-combination (Fiat-Shamir
`r_powers`) reduced to **one** `pairings_verify`.
**Characterization:** untrusted commitment/proof are **subgroup-checked + on-curve + canonical-scalar** before
the single-final-exp pairing; the infinity acceptance is spec-mandated (4844 permits an infinity commitment/
proof); the batch reduction is the standard sound RLC.

---

## 6. The trusted-setup load — the one genuinely new factual observation.

`load_trusted_setup (setup/setup.c:392-505)` validates lengths, then **deserializes every G1/G2 point via
`blst_p*_uncompress` only** (encoding + on-curve), runs `is_trusted_setup_in_lagrange_form` (a *pairing* that
rejects monomial-form setups), `compute_roots_of_unity`, bit-reversal, and FK20 init.
**Factual flag (defensive, not exploitable here):** the setup-load loops perform **no `blst_p1_in_g1`/`blst_p2_in_g2`
subgroup check** on the trusted-setup points (confirmed — no such call in `src/setup/`), in deliberate contrast
to `validate_kzg_g1` which *does* subgroup-check *untrusted* commitments/proofs. This is **by design** — the
trusted setup is ceremony-produced, not attacker-controlled, and `is_trusted_setup_in_lagrange_form` + the
ceremony provide integrity — **but** a *corrupted/non-canonical setup file* with on-curve-but-not-in-subgroup
points would **not** be caught at load by a subgroup test (only the Lagrange-form pairing runs, which checks
*form*, not *subgroup membership*). Worth naming for any consumer that loads setups from a less-trusted channel.

---

## 7. Verdict & residual

the spec-mandated-subgroup-check primitives do exactly what the spec mandates, across the *full* suite: the
ADD/MSM/PAIRING/MAP subgroup matrix is spec-correct (ADD omits by design, PAIRING re-checks), the field decode is
canonical + zero-padded, the subgroup test is the fast φ/ψ-endomorphism check, map outputs are in-subgroup by
cofactor clear, and c-kzg validates untrusted inputs (subgroup + on-curve + canonical) before a single-final-exp
pairing. **No finding.** **Residuals / honest details**, named: (a) the **client-integration contract** from the
sweep (`KeyValidate` before `FastAggregateVerify`) is unchanged; (b) **c-kzg does not subgroup-check the
trusted-setup points at load** (acceptable under the trust model — relevant only if a setup arrives from an
untrusted channel; the Lagrange-form pairing checks form, not subgroup); (c) PAIRING's `PairingCheck`-error→0 is
a false-negative only. The forgery classes (non-subgroup, non-canonical, off-curve) are rejected on *untrusted*
inputs; the one trust boundary is the setup file itself.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P2.*
