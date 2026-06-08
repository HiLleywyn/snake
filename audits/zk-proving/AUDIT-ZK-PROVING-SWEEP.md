# Proving-system soundness sweep — does the verifier accept only the truth?

The deepest verifier layer, under the threat model in [`README.md`](README.md): a malicious prover trying to
get an honest verifier to accept a proof of a **false** statement. The historical breaks were never the deep
math — they were **implementation gaps in checkable places**: a Fiat-Shamir challenge squeezed before its
commitment was absorbed (Frozen-Heart), a public input left unbound, a missing constraint. This sweep audits
exactly those, and is **honest about the line** between what a source read can confirm (the transcript absorbs
everything before it samples; the proof is bound to the statement) and what only a security proof can (the
scheme is sound).

---

## Z1. Plonky3 — the Fiat-Shamir is *honest*: every commitment and public input is absorbed before its challenge
**Target:** `Plonky3/Plonky3`, `uni-stark/src/verifier.rs` + `fri/src/verifier.rs` + `challenger/`. Plonky3 is
the STARK/FRI foundation **SP1, Valida, and others build on**, so its challenger discipline is load-bearing for
a large fraction of the zkVM ecosystem. The Frozen-Heart question — *is every commitment and every public input
observed into the transcript before the challenge that depends on it is sampled?* — is the single most common
real soundness break, and it is fully checkable from source. **Result: the observe-before-sample ordering is
correct end-to-end, and the public values are bound before any challenge. No finding.**

**The STARK verifier transcript order (verified myself, `uni-stark/src/verifier.rs`):**
1. **AIR shape bound** — `observe(degree_bits)`, `observe(base_degree_bits)`, `observe(preprocessed_width)`
   (`:361-363`): the circuit *shape* is absorbed, so a proof can't be replayed against a different-shaped AIR.
2. **`observe(commitments.trace)`** (`:369`) + preprocessed commit (`:371`), **then `observe_slice(public_values)`**
   (`:373`) — the main-trace commitment **and the public values** are absorbed —
3. — **then `alpha = sample_algebra_element()`** (`:379`). The constraint-combination challenge `alpha` is
   drawn **after** the trace *and* the public values are committed. **This is the input-binding + Frozen-Heart
   property in one:** a prover cannot choose its trace or its public values after seeing `alpha`. (The opposite
   order — sample `alpha`, *then* let the prover pick public values — would be a forge; it isn't done.)
4. **`observe(commitments.quotient_chunks)`** (`:380`) + any randomized/logup commits (`:385`), **then `zeta =
   sample_algebra_element()`** (`:391`) — the out-of-domain evaluation point is drawn **after** the quotient
   commitment. Correct.

**The FRI low-degree test transcript order (verified myself, `fri/src/verifier.rs`):**
- **Each folding challenge is sampled after its commitment is observed** — the commit-phase loop
  `observe(comm)` (`:293`) → `check_witness(commit_proof_of_work_bits, witness)` (`:294`) → `sample_algebra_element()`
  (`:297`), with the code's own comment: *"Observe the commitment, check the PoW witness, then sample the
  folding challenge."* So no folding `beta` is ever drawn before the round it folds is committed.
- **`observe(final_poly)`** (`:310`), the arity schedule absorbed (`:320-322`), and **query indices sampled
  only at the end** (`sample_bits`, `:340`) after everything is in the transcript.
- **Grinding raises soundness at *both* phases** — proof-of-work witnesses are checked for the commit phase
  (`commit_proof_of_work_bits`, `:294`) **and** the query phase (`query_proof_of_work_bits`, `:326`); the
  grinding bits add directly to the FRI soundness parameter.

**Verdict:** the transcript is honest — **every commitment (trace, quotient, FRI folding, final poly) and the
public values are absorbed before the challenge that depends on them**, the AIR shape is bound, and grinding
augments the query soundness. The Frozen-Heart / weak-Fiat-Shamir class — the source of the real historical
breaks — is **closed at the implementation level.** **No finding.** **The honest boundary:** a source read
confirms *the transcript absorbs everything before it samples* and *the proof is bound to the public values +
AIR shape*; it does **not** re-derive the FRI/STARK *soundness bound* itself (the query count + blowup +
grinding giving the target bits), which is a security-proof + parameter-choice question. What's checkable is
checked and correct; what isn't is named.

---

## Z2. Halo2 + Groth16 (arkworks) — textbook Fiat-Shamir, and the one named residual: who checks the public-input count
**Target:** `zcash/halo2` (`halo2_proofs/src/plonk/verifier.rs`), `arkworks-rs/groth16` (`src/verifier.rs`).
The two most widely-deployed SNARK verifier families. **Result: Halo2's transcript is textbook-correct (the
exact spot the Frozen-Heart class lived, and it's right); arkworks-groth16's native verifier delegates the
public-input *count* check to the caller — a documented contract and a known integration footgun, not a novel
forge. No finding; one residual named.**

- **Halo2 — absorb-before-squeeze, instance double-bound (verified myself).** `vk.hash_into(transcript)`
  (`:109`) and the instance commitments `common_point(...)` (`:114`) are absorbed **before any challenge**;
  then advice commitments → **`theta` squeezed** (`:126`); lookup commitments → **`beta`,`gamma`** (`:140-143`);
  permutation/product/vanishing-before-y → **`y`** (`:166`); vanishing-after-y → **`x`** (`:172`). **Every
  commitment class is absorbed before the dependent challenge — Frozen-Heart not present.** The public instance
  is bound *two* ways: absorbed into the transcript *and* folded into the gate/quotient evaluation via
  `instance_evals` gated by `l_0`. **Input-binding: sound.**
- **Groth16 (arkworks) — pairing correct, but no public-input length check (verified myself).** The pairing
  `multi_miller_loop([A, L_pub, C], [B, -γ, -δ]) → final_exp == e(α,β)` is the correct Groth16 equation, and
  `prepare_inputs` folds `L_pub = IC[0] + Σ pub_i · IC[i+1]`. **But the fold is
  `public_inputs.iter().zip(gamma_abc_g1.iter().skip(1))` (`verifier.rs:30`) with *no*
  `len(public_inputs) == len(gamma_abc_g1) - 1` assertion** — `zip` silently truncates to the shorter. Passing
  *fewer* public inputs than the vk expects drops the omitted `IC` terms from `L_pub`, weakening the
  input-binding for those wires. **This is the documented arkworks contract** (the caller must supply exactly
  the circuit's public inputs; the *in-circuit* gadget `constraints.rs:269` does check the length, the native
  verifier doesn't) and a long-known footgun — *not a demonstrated live forge, and not a novel finding*. The
  **named residual** (the constructive mirror): **an integrator using arkworks-groth16 natively must enforce
  `public_inputs.len()` against the vk themselves** — a verifier that accepts an attacker-influenced *number*
  of public inputs is the real hazard, and it lives at the integration boundary, not in arkworks.

## Z3. SP1 (Hypercube) — observe-before-sample at every layer, native *and* in-circuit, bound to vk + public values
**Target:** `succinctlabs/sp1`, `crates/hypercube/src/verifier/` + the vendored `slop/` (Basefold/jagged) +
`crates/recursion/circuit/`. Current SP1 is the **Hypercube** architecture (multilinear sumcheck + LogUp-GKR +
Jagged-PCS over Basefold/FRI). **Result: the Fiat-Shamir transcript is honest at every layer — including the
in-circuit recursive verifier — and the proof is bound to the vk and public values. No finding.**

- **Observe-before-sample, end to end (per the sweep, structurally confirmed):** `vk.observe_into(challenger)`
  before any shard (`machine.rs:163`); per-shard **public_values + main_commitment + chip-count/heights
  observed (`shard.rs:468-488`) before GKR/zerocheck sample any challenge**; LogUp-GKR observes output claims
  before sampling the eval point and observes each round's prover message before its challenge; Basefold
  observes the univariate message + commitment before `beta`, and observes the final poly (+ PoW) before
  sampling query indices. **The recursion in-circuit verifier mirrors the native order exactly**
  (`recursion/circuit/src/shard.rs:145-164,491`) — the recursive proof re-checks the inner transcript with the
  same discipline.
- **Input binding:** `MachineVerifyingKey::observe_into` absorbs the **preprocessed (program/AIR) commitment,
  `pc_start`, the initial cumulative sum**; public values are observed per-shard with length + zero-padding
  enforced (`PROOF_MAX_NUM_PVS=187`); the PCS opening is checked against `[vk.preprocessed_commit,
  main_commitment]`, and the jagged shape is hashed into the commitment. **The proof is bound to the program
  and its I/O.**
- **FRI params:** 100-bit target, 16 PoW bits (22 for wrap), query count for the unique-decoding regime
  (~124 queries at log_blowup=2), GKR grinding 12 bits; **degree-0 final poly enforced** (every folded query
  eval must equal the constant). (Minor non-soundness nit observed: stray `println!` debug lines in
  `basefold/verifier.rs` — cosmetic.)

## Z4. RISC Zero — observe-before-sample, bound to imageID + journal digest + control-root
**Target:** `risc0/risc0`, `risc0/zkp/src/verify/` + `risc0/zkvm/src/receipt.rs`. DEEP-ALI + FRI STARK with a
recursion/succinct wrapper. **Result: Fiat-Shamir ordering correct, proof bound to the program image and the
public journal. No finding.**

- **Observe-before-sample (per the sweep, structurally confirmed):** the `ReadIOP` (Poseidon2/SHA `Rng`)
  `commit()=rng.mix(digest)` mixes every commitment before its challenge — `commit_circuit_info` seeds the
  transcript with proof-system + circuit info; globals/outputs committed before any draw; **each Merkle group's
  root is mixed at construction before `poly_mix`/`z` are sampled** (`mod.rs:312/333`); FRI mixes each round's
  Merkle root before that round's folding challenge and commits the final coeffs before sampling query
  positions (`fri.rs`). No Frozen-Heart gap.
- **Receipt binding (the strong part):** `Receipt::verify_with_context` reconstructs
  `expected_claim = ReceiptClaim::ok(image_id, Pruned(journal.digest()))` and requires
  **`expected_claim.digest() == inner.claim().digest()`** — binding **both the imageID (the guest program) and
  the journal digest (the public output)** through the claim digest. The succinct layer binds the control via
  `check_code` (`control_id == self.control_id` + Merkle inclusion in `control_root`). **The proof is bound to
  the exact program and its exact output.**
- **Params:** `QUERIES=50, INV_RATE=4, FRI_FOLD=16`; ~100-bit conjectured soundness from 50 queries at rate
  1/4; **no grinding/PoW step — a deliberate parameter choice**, not a defect.

---

## Synthesis — the two checkable soundness properties hold everywhere; the math-soundness delegates to proofs
Across **five proving systems** — Plonky3/FRI, SP1/Hypercube, RISC Zero/DEEP-ALI, Halo2, Groth16 — the two
*implementation-level* soundness-critical properties, which are where the **real historical breaks lived**, are
correct in every system read:

1. **Fiat-Shamir is honest — observe-before-sample, everywhere.** Every commitment (trace, quotient, lookup,
   permutation, FRI/Basefold folding, final poly) **and every public input** is absorbed into the transcript
   **before** the challenge that depends on it is squeezed — in the STARK verifiers (Plonky3, SP1, RISC Zero),
   the SNARK verifier (Halo2), *and* SP1's in-circuit recursive verifier. **The Frozen-Heart / weak-Fiat-Shamir
   class — the source of the 2022-era forgeries — is closed in every implementation audited.**
2. **The proof is bound to the statement.** vk/program-commitment + public values (Plonky3, SP1), imageID +
   journal digest + control-root (RISC Zero), the absorbed-and-folded instance (Halo2). The one residual is
   **arkworks-groth16's caller-enforces-the-public-input-count contract** — a documented footgun pushed to the
   integration boundary, named for downstream review, not a defect in the library.

**The honest boundary, stated plainly (this is the whole point of the layer):** a source read **can** confirm
*the transcript absorbs everything before it samples* and *the proof is bound to its statement* — and those are
exactly the two things the real-world breaks got wrong. A source read **cannot** re-derive the *soundness
bound* itself: whether 50 (RISC Zero) or ~124 (SP1) FRI queries at the given blowup + grinding actually deliver
the target bits, whether the FRI list-decoding radius is the conjectured or the proven one, whether the
GKR/sumcheck soundness error composes correctly. **Those are security-proof and parameter-choice questions** —
and the way the ecosystem answers them is the corpus's discipline one final time: **independent re-derivation
by decorrelated observers** — the academic security proofs, the formal-verification efforts (Lean/Coq
formalizations of FRI/PlonK/sumcheck), and independent audits of the same code. **Five proving systems, the two
checkable soundness properties correct in all, one integration residual named; the deep soundness rests, as it
must, on proofs that a code read defers to and the corpus's own rule endorses** — *the only defense against a
blind spot is an observer who does not share it.* At the very bottom of the stack, the verifier checks the
prover, the security proof checks the verifier, and the formal verification checks the proof — snakes all the
way down, each eating the tail of the one below.

---

## Sweep status
| # | Target | System | Fiat-Shamir honest + input bound? | Dominant failure mode |
|---|---|---|---|---|
| Z1 | Plonky3 (uni-stark + FRI) | STARK/FRI (SP1's base) | **yes** — every commitment + public values observed before its challenge; grinding both phases | FROZEN-HEART **closed**; soundness-bound is a security-proof question |
| Z2 | Halo2 + Groth16 (arkworks) | SNARK verifiers | Halo2 **yes** (textbook); Groth16 pairing correct | Groth16 native verifier has **no public-input length check** (documented caller-contract footgun) |
| Z3 | SP1 (Hypercube) | sumcheck + GKR + Basefold | **yes** — native *and* in-circuit recursion; bound to vk + public values | clean; param adequacy = security-proof question |
| Z4 | RISC Zero | DEEP-ALI + FRI | **yes** — bound to **imageID + journal digest + control-root** | clean; 50 queries @ 1/4, no PoW by design |

**Result:** 5 proving systems — **the two checkable soundness properties (Fiat-Shamir observe-before-sample +
proof-bound-to-statement) are correct in all of them; Frozen-Heart closed everywhere.** One integration
residual named (arkworks-groth16 public-input count is the caller's job). The deep soundness bound is, by
construction, a security-proof question a code read defers to.
