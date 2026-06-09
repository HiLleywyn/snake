# P3 (deep) — revm precompiles, the full differential vs geth: per-fork registry, feature-gated backends, and every edge consensus-equivalent

**Scope.** A deep, individualized expansion of sweep item **P3** (`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P3), going
past the alt_bn128 G2 reconciliation the rapid pass covered into the **full revm precompile crate as an
edge-by-edge differential vs geth**: the per-fork registry, the feature-gated crypto backends, the modexp
error-vs-gas-saturate equivalence, the empty-pairing convention, and the blst/c-kzg delegation. Target:
`bluealloy/revm` @ `cfcf038`, `crates/precompile/src/`. Read-only, public-source, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No exploitable divergence found;** a few feature-gate/doc-staleness
observations are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep confirmed the alt_bn128 G2 edge lands on "both subgroup-check." The deeper reading does the **whole
differential**, and surfaces the structural fact that underpins consensus-equivalence: every revm Eth-precompile
error becomes a **`PrecompileHalt` that consumes the full forwarded gas** (`interface.rs:372-381`) — the *same*
consensus model as geth ("a failing precompile consumes all gas"). On top of that it maps the **per-fork
registry**, the **feature-gated backends** (and the important fact that revm's *default* bn254 backend is now
**arkworks**, not substrate-bn), and confirms every edge — ecrecover, modexp, blake2, hashes, bn128, BLS, KZG —
is consensus-equivalent.

---

## 1. The per-fork registry — additive, reprice-by-overwrite. **Consensus-equivalent to geth's active set.**

`init_precompiles (lib.rs:271-329)` is monotonic-additive, gated by `is_enabled_in` (a `u8 >=` on
`PrecompileSpecId`): Homestead 0x01–0x04, Byzantium +modexp/bn254, Istanbul reprices bn254 + blake2, Berlin
reprices modexp (EIP-2565), Cancun +KZG 0x0A, Prague +BLS 0x0B–0x11, Osaka reprices modexp (EIP-7823/7883) +
P256 0x100. Later forks **reprice by re-inserting at the same address** (`extend` overwrites).
**Characterization:** a clean additive model consensus-equivalent to geth's per-fork map; the only revm-specific
wrinkle is an `optimized_access` lookup array (a perf optimization, no semantic change). **Honest flag:** the
`cancun()` doc-comment claims KZG is feature-gated out of *registration* without `c-kzg`, but the code registers
it **unconditionally** — the feature-gating actually lives inside `verify_kzg_proof` (§6). Stale doc; default
build (with `c-kzg`) is correct.

---

## 2. The feature-gated backends — and the default-is-arkworks subtlety.

`bn254.rs:9-19`: default features are `["std","secp256k1","blst","c-kzg","portable"]` — **`bn` is NOT default, so
arkworks is the default bn254 backend** (substrate-bn is opt-in via `--features bn`). The subgroup paths:
- **arkworks**: `new_g1_point`/`new_g2_point` subgroup-check **both** G1 and G2
  (`is_in_correct_subgroup_assuming_on_curve`).
- **substrate-bn**: `AffineG::new` subgroup-checks **only if `P::check_order()`** — `G1Params::check_order()
  = false` (no G1 check), `G2Params::check_order() = true` (G2 checked, `NotInSubgroup`).

**Characterization (the consensus-equivalence argument):** BN254 has **G1 cofactor h=1**, so every on-curve G1
point is trivially in the prime-order subgroup — arkworks' extra G1 check is a **tautology** that cannot reject
anything substrate accepts. For G2 (cofactor≠1) **both** backends enforce the check. So the two bn254 backends are
mutually consistent **and** match geth's bn256 (which likewise only meaningfully subgroup-checks G2). KZG default
= `c-kzg`, BLS default = `blst` — the *same upstream libraries geth uses*, so those checks are identical by
construction. **Honest flag for a differential harness:** "revm uses substrate-bn" is now a **wrong assumption**
(default is arkworks); the *only* place a feature-gate could differ for bn254 is the G1 subgroup check, which the
cofactor argument closes.

---

## 3. modexp — error-vs-gas-saturate is consensus-equivalent.

Gas formulas match geth (EIP-198/2565/7883). Length handling (`modexp.rs:206-223`): a huge base/mod length that
exceeds `usize` returns `Err(ModexpEip7823LimitSize)` → a **halt consuming all forwarded gas**; `exp_len`
saturates to `usize::MAX` and blows up the gas calc → **OOG**. **Both outcomes are "the call fails and consumes
its gas"** — consensus-equivalent to geth (where such a length makes the computed gas vastly exceed any limit →
OOG). The 1024-byte cap is **Osaka-only** (`eip7823::INPUT_SIZE_LIMIT`), matching geth.
**Characterization:** geth saturates gas → OOG; revm errors → halt-consuming-all-gas. **Same observable result:
a rejected call, not a state split.** Honest note: `ModexpEip7823LimitSize` is *reused* for two conditions (the
Osaka >1024 rule and the pre-Osaka `usize` overflow guard) — behaviorally indistinguishable from geth in both.

---

## 4. ecrecover / blake2 / hashes — every edge matches.

**ecrecover (`secp256k1.rs:35-56`):** right-pad to 128, require bytes[32..63] all zero **and** `input[63] ∈
{27,28}` else empty, `recid = v−27`, recover-failure → empty; **no low-s** (the k256 backend `normalize_s`'s high-s
to accept it; the libsecp256k1 backend recovers directly — both reach geth's accept-high-s result). **blake2F
(`blake2/mod.rs`):** exact 213-byte, rounds = first-4-BE, gas = `rounds·1` **uncapped (gas-bounded)**, `f ∈ {0,1}`
strict. **hashes:** sha256 (60,12), ripemd160 (600,120), identity (15,3), `ceil(len/32)·word + base` — all
constants match geth.
**Characterization:** every edge condition (v-range, high-byte-zero, recover-0→empty, no-low-s, blake2
213/flag/uncapped-rounds, hash gas) is **consensus-equivalent to geth**.

---

## 5. bn128 edges — including the empty→true convention (opposite of BLS).

Both bn254 backends: field `< p` (canonical, `Bn254FieldPointNotAMember`), on-curve, `(0,0)→infinity`, pairing
input `%192==0` (`Bn254PairLength`), and — the deliberate convention — **empty pairing input → returns `1` (true)**
(the loop never runs; `pairing_check(&[])` = `Ok(true)`), with infinity-pairs skipped.
**Characterization:** bn254's **empty→true** (and infinity-skip) **exactly matches geth's bn256Pairing**, and is
the deliberate **opposite** of BLS pairing (§6), which *rejects* empty — both clients match *their respective
spec convention*. A client that "fixed" either would cause a split.

---

## 6. BLS12-381 + KZG — delegation makes them identical by construction.

**BLS (blst, default):** canonical field (`is_valid_be < MODULUS_REPR`), on-curve (`blst_p*_affine_on_curve`),
**subgroup gated by `subgroup_check`** — `read_g1`/`read_g2` set it true, **ADD uses
`read_*_no_subgroup_check`** (EIP-2537: ADD on-curve-only, MSM/pairing subgroup), 16-byte top-pad-must-be-zero,
**empty input rejected** (`Bls12381PairingInputLength`). Gas constants all verified. **KZG
(`kzg_point_evaluation.rs`):** exact 192-byte + gas-first fail-closed, **versioned-hash binding**
(`0x01 ++ sha256(commitment)[1..]`), proof verify ends in `.unwrap_or(false)` (error → clean false, no panic).
**Characterization:** BLS and KZG delegate to **blst and c-kzg — the same libraries geth uses** — so subgroup,
on-curve, and canonical-encoding checks are **identical by construction**; the ADD-no-subgroup / MSM-pairing-
subgroup split, the 16-byte pad, the empty-input rejection, and the versioned-hash binding all match geth/EIP.

---

## 7. Verdict & residual

across the full revm precompile crate, **every edge examined is consensus-equivalent to geth** — ecrecover,
modexp (error-vs-gas-saturate both = halt-consuming-gas), blake2, hashes, bn128 (incl. empty→true), BLS, KZG —
and the structural reason is that every Eth-precompile error becomes a gas-consuming halt, exactly geth's model.
**No exploitable divergence.** **Residuals / honest flags** (defensive, factual, none a finding): (a) **revm's
default bn254 backend is arkworks, not substrate-bn** — a differential harness must model this (consensus-
equivalent by the G1-cofactor-1 argument); (b) the **`cancun()` doc-comment is stale** vs unconditional KZG
registration (default build correct); (c) `ModexpEip7823LimitSize` is **reused** for the Osaka rule and the
`usize` guard (behaviorally identical to geth); (d) ecrecover **accepts high-s** by normalization/direct-recover
(spec-matching). The layer's safety rests on **cross-implementation recomputation** (the consensus test suite) —
the same discipline as this differential — and the one edge the corpus re-audited (alt_bn128 G2) lands on **both
subgroup-check**, the cleanest possible consensus-equivalence.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-CRYPTO-PRIMITIVES-SWEEP.md` §P3.*
