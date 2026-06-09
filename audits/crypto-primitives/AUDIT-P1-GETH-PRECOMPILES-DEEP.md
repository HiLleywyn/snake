# P1 (deep) — go-ethereum precompiles: the per-fork dispatch, gas-before-run, ecrecover/blake2F, and the bn256 pairing internals

**Scope.** A deep, individualized expansion of sweep item **P1** (`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P1), going
past modexp + bn256 decode the rapid pass covered into the **full precompile set + the curve internals**: the
per-fork dispatch table + the gas-before-run invariant, the complete ecrecover validation, the hash/identity
word-rounding, blake2F's parse + G-mixing, the **bn256 Miller-loop + final-exp + the pairing-product-==1** test,
and the per-fork gas formulas (EIP-1108 bn256; EIP-198/2565/7883/7823 modexp). Target: `ethereum/go-ethereum` @
`1f87331`, `core/vm/contracts.go`, `crypto/bn256/cloudflare/`, `crypto/blake2b/`. Read-only, public-source,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No finding;** the fork-gated length cap and the
gas-bounded-not-structural blake2F rounds are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established modexp's gas-saturation + the bn256 subgroup check (the famously self-corrected
`IsOnCurve`-also-checks-subgroup). The deeper reading covers the *rest of the layer*: the **gas-before-run
invariant** that pre-charges every metered cost before any computation; ecrecover's exact validation (the
high-31-byte-zero check, the *no-low-s-here* rule, the soft `(nil,nil)` failure); blake2F's 213-byte parse +
the SIGMA `rounds%10` G-mixing; the **bn256 pairing internals** (accumulate `∏ miller` into one `gfP12`, *one*
final exponentiation, `IsOne()`); and the full per-fork gas ladder with its `MaxUint64`-saturation overflow
handling.

---

## 1. The per-fork dispatch + the gas-before-run invariant. **Metering precedes computation.**

`contracts.go` holds static per-fork `PrecompiledContracts` maps that grow newest-first: Frontier (0x1–0x4),
Byzantium (+modexp `eip2565:false`, bn256 `*Byzantium`), Istanbul (bn256 `*Istanbul` EIP-1108, +blake2F),
Berlin (modexp `eip2565:true`), Cancun (+KZG 0xa), Prague (+BLS12-381 0xb–0x11), Osaka (modexp
`eip7823:true,eip7883:true`, +p256Verify 0x100). `RunPrecompiledContract (:265-282)` is the invariant:
```go
gasCost := p.RequiredGas(input)
prior, ok := gas.Charge(...)
if !ok { gas.Exhaust(); return nil, gas, ErrOutOfGas }   // full gas charged BEFORE Run; insufficient -> exhaust + short-circuit
output, err := p.Run(input)
```
**Characterization:** gas is computed as a **pure deterministic function of input length/content** and **charged
in full before `Run`** — insufficient gas exhausts the budget and returns before any computation. `RequiredGas`
is pure except for blake2F (reads `rounds`) and modexp (reads exp-head + lengths), both of which saturate on
overflow (§5). This pre-charge is the layer's central DoS-safety property.

---

## 2. ecrecover — exact validation, no-low-s-here, soft failure.

`ecrecover.Run (:291-320)`, fixed `EcrecoverGas = 3000`: right-pads input to 128 = `(hash‖v‖r‖s)`, sets
`v := input[63] - 27` (so **only v∈{27,28} map to recovery id {0,1}**), and:
```go
if bitutil.TestBytes(input[32:63]) || !crypto.ValidateSignatureValues(v, r, s, false) { return nil, nil }
```
**`bitutil.TestBytes(input[32:63])` enforces the high 31 bytes of the v-word are zero** (v must fit one byte),
and the **`false` arg means homestead low-s enforcement is NOT applied** (the in-code comment says so — low-s is
a *tx-signature* rule, not this precompile). On recover failure → **`(nil, nil)` (empty output, no error — gas
still consumed)**; success → `keccak256(pubKey[1:])[12:]` left-padded to 32.

**Characterization:** the validation is exactly r,s∈(0,N) + v∈{27,28} + the v-word-fits-one-byte check, and
**soft-fails to empty output** — callers must check for emptiness; gas is consumed regardless. The deliberate
*absence* of low-s here is a spec-matching detail a divergence-hunter must confirm (revm agrees — P3).

---

## 3. Hash/identity + blake2F — word-rounding and the G-mixing.

Hash/identity gas is `(len+31)/32 · perWord + base` (integer ceiling-division to words; sha256 60/12, ripemd160
600/120, identity 15/3) — no overflow check because `len` is memory-bounded on 64-bit. **blake2F**: gas ==
`rounds` (1 gas/round, big-endian, `:856-863`); `Run (:876-913)` strictly requires the **213-byte layout** (4
rounds-BE ‖ 64 h-LE ‖ 128 m-LE ‖ 16 t-LE ‖ 1 final-flag), rejects a final flag not in `{0,1}`
(`errBlake2FInvalidFinalFlag`), and calls `blake2b.F`. The generic mixing (`blake2b_generic.go:47-55`) maps
`final → 0xFF…FF`, sets up `v0..v15`, and loops the ARX **G-mixing with `SIGMA = precomputed[i%10]`**.

**Characterization:** strict length + strict `f∈{0,1}` reject malformed inputs hard; `rounds` is a full **uint32,
uncapped structurally but gas-bounded** at 1/round (reaching ~4.29e9 rounds needs ~4.29e9 gas, far above any
block limit), and `i%10` SIGMA cycling for rounds>10 is per EIP-152. A classic divergence-magnet, here
spec-exact.

---

## 4. The bn256 pairing internals — accumulate, one final-exp, IsOne. **The forgery-critical path's interior.**

`PairingCheck (bn256.go:322-333)` is the heart the sweep only named:
```go
acc := new(gfP12); acc.SetOne()
for i := range a {
  if a[i].p.IsInfinity() || b[i].p.IsInfinity() { continue }   // infinity contributes identity, skipped
  acc.Mul(acc, miller(b[i].p, a[i].p))                          // accumulate ∏ miller
}
return finalExponentiation(acc).IsOne()                          // ONE final exp, then test == 1
```
The precompile (`:791-818`) builds the (G1,G2) lists from 192-byte chunks (`len%192 != 0 → errBadPairingInput`)
and returns `true32Byte`/`false32Byte`. `miller (optate.go:122-206)` iterates the `sixuPlus2NAF` (NAF of 6u+2)
high-to-low — `lineFunctionDouble` + `Square` + `mulLine`, conditional `lineFunctionAdd` on NAF ±1 — then two
extra Frobenius line-functions for Q1/−Q2. `finalExponentiation (:211-260)` is the standard easy-part
(p⁶-Frobenius × inverse) + hard-part (Frobenius chains + `Exp(_, u)`).

**Characterization:** the pairing check is `∏ e(a_i,b_i) == 1` computed as a single accumulated `gfP12` with
**exactly one** final exponentiation and an `IsOne()` test — points at infinity correctly skipped (they're the
pairing identity). This is the interior the precompile's correctness rests on, read at the line level.

---

## 5. The per-fork gas ladder — saturating, fork-gated, floored.

**bn256** (EIP-1108 Istanbul reductions): Add 500→150, ScalarMul 40000→6000, Pairing base 100000→45000 +
per-point 80000→34000 (metered `base + (len/192)·perPoint`). **modexp** multComplexity is fork-laddered:
Byzantium EIP-198 piecewise (with `bits.Mul64`/`Add64` overflow → **`MaxUint64`**), Berlin EIP-2565
`ceil(x/8)²`, Osaka EIP-7883 (`x≤32 → 16`, else `2×Berlin`); the iteration count is `(expLen−32)·multiplier +
expHead.BitLen()−1` floored at 1; the final gas is `multComplexity·iterationCount / {20|3|1}` with **floors**
(200 Berlin, 500 Osaka). **`Run (:614-656)`** caps base/exp/mod length at **1024 only under Osaka (`eip7823`)**
and special-cases zero base/mod.

**Characterization:** every gas path **saturates to `MaxUint64` on overflow** (a huge exponent → out-of-gas, not
unbounded work), and the formulas are fork-gated by the `eip2565`/`eip7883`/`eip7823` flags. **Honest note:** the
1024-byte length cap is **fork-gated to Osaka** — pre-Osaka forks have *no hard length cap* and rely solely on
the saturating gas formula to price oversized operands out (which it does, but it's a "priced-out" not a
"rejected" defense pre-Osaka).

---

## 6. Verdict & residual

the full precompile layer is sound: gas is pre-charged before any computation, ecrecover validates exactly
(v-word-fits + r,s∈(0,N), no-low-s-here, soft-fail), blake2F is strict-length + gas-bounded, the bn256 pairing is
the correct `∏ e == 1` with one final-exp, and the gas ladder saturates + floors + fork-gates. **No finding.**
**Residuals / honest details**, named: (a) the **dominant risk at this layer is DIVERGE, not FORGE** — the
crypto is correct; the question is cross-client agreement on edges (P3); (b) ecrecover **soft-fails to empty
output** (callers must check; gas consumed) and deliberately **omits low-s** (spec-matching); (c) blake2F
`rounds` is **uncapped structurally, bounded only by gas** (DoS resistance rests entirely on the pre-charge);
(d) the **modexp 1024-byte cap is Osaka-only** — earlier forks rely on saturating gas, not rejection; (e) the
bn256 **G2 subgroup check lives inside `IsOnCurve`** (the sweep's corrected fact) and G1 needs none (cofactor 1).
The primitive computes the truth or out-of-gases; the residual is precisely cross-client agreement on every
edge, which P3 tests.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P1.*
