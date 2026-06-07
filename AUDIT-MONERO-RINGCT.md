# Monero (XMR) — RingCT commitment-conservation audit (clean)

**Target:** `monero-project/monero`, sparse clone `/tmp/xmr` (`src/ringct`). Audited the **RingCT
value-conservation core** — `verRctSemanticsSimple` (`src/ringct/rctSigs.cpp:1344`), the
commitment-sum balance + range-proof gate that enforces "no value created" while amounts stay hidden.
**Posture:** defensive; no exploit, no PoC. **Result: clean — no finding, nothing to disclose.**

Chosen to **complete the privacy-conservation triad** alongside the two privacy models already in the
corpus: ZK-shielded (Namada/Penumbra circuits) and MimbleWimble (Litecoin MWEB,
`AUDIT-LITECOIN-SIX-BUCKET.md`). Monero is the third — **Pedersen commitments + range proofs + ring
signatures** — a distinct way to make conservation hold over *hidden* amounts. Connection-driven: MWEB
and RingCT share the same commitment-and-range floor family, so MWEB was the explicit reference.

## Conservation floor — homomorphic commitment-sum balance (Bucket 2 + Bucket 5)
Each amount is a **Pedersen commitment** `C = x·G + a·H` (blinding mask `x`, amount `a`; `G`,`H`
independent generators). The verifier sees only the points, never `a`. `verRctSemanticsSimple`
enforces conservation in EC-point space (`rctSigs.cpp:1403-1419`):
```
sumOutpks   = Σ outPk[i].mask          // Σ output commitments
sumOutpks  += scalarmultH(txnFee)       // + fee·H  (fee is public, zero blinding)
sumPseudoOuts = Σ pseudoOuts            // Σ input (pseudo-output) commitments
if (!equalKeys(sumPseudoOuts, sumOutpks)) { "Sum check failed"; return false; }
```
i.e. **Σ inputs == Σ outputs + fee·H.** Because the prover builds the input *pseudo-output* masks to
sum to the output masks (and the fee carries zero blinding), the blinding factors cancel and the
equality holds **iff the hidden amounts balance** — input value = output value + fee, with no amount
ever revealed. **enforced.**

## Why the floor is sound — range proofs (the load-bearing companion)
A commitment-sum check **alone is forgeable**: amounts live mod the curve order, so a malicious
"output" committing to a near-order (effectively negative) value could make the sum balance while
minting value. RingCT closes this by requiring a **range proof on every output commitment**
(`:1421-1460`): Bulletproofs+ (`verBulletproofPlus`), Bulletproofs (`verBulletproof`), or legacy
Borromean (`verRange`), each proving the committed amount lies in `[0, 2^64)`. **The range proof is
what makes the hidden-amount sum check sound** — exactly the role I identified for Bulletproofs in the
Litecoin MWEB audit (the "inductive residual"). Any failure → `return false` (tx rejected). This is
the same `commitment-sum + range-proof` two-part floor as MWEB, in a different codebase. **enforced.**

## Division of labor (coverage honesty — what `verRctSemanticsSimple` does *not* do)
RingCT splits its guarantees, and I audited the **conservation** half:
- **Semantics (this audit):** "no value created" — commitment balance + range proofs.
- **Non-semantics (separate, `verRctNonSemanticsSimple` / CLSAG/MLSAG, key images):** *ownership*
  ("the spender controls a real ring member") and *no double-spend* (the **key image** uniqueness,
  checked at the blockchain layer). These are the Bucket-2 "witnessed crypto object" companions —
  the ring signature hides *which* input is spent; the key image prevents spending it twice. I did
  **not** open the CLSAG verification or the key-image database here.
So: this audit clears *inflation resistance*; double-spend/ownership rests on the ring-signature +
key-image machinery (named, not opened).

## Failure philosophy (correct)
The whole verifier is wrapped in `try/catch` (`:1345`,`:1464-1473`): a malformed point (e.g. a throw
from `ge_frombytes_vartime` on an invalid curve element) is caught and turns into `return false` —
**reject the transaction**, never accept-on-error. This is the halt/reject-over-divergence discipline
verified positively in Sui/MonadBFT and whose *absence* is the MemeCore finding
(`AUDIT-MEMECORE-POSA.md`'s swallowed-error class). Here an exception can't smuggle a tx through.

## Connections to the corpus — the privacy-conservation triad
| Model | Conservation mechanism | Amount hiding | Sender hiding | Setup |
|---|---|---|---|---|
| **Monero RingCT** | Pedersen sum `Σin = Σout + fee·H` + range proofs | commitments | ring sig + key image | **transparent** (Bulletproofs+) |
| **MWEB (Litecoin)** | Pedersen sum-to-zero (kernel excess) + range proofs | commitments | cut-through / no address | transparent |
| **ZK-shielded (Namada/Penumbra/zkSync)** | circuit value-balance constraint | in-circuit | in-circuit | often trusted (KZG) |
RingCT and MWEB are the **same homomorphic-commitment floor** (Pedersen + Bulletproofs); they differ
only in how they hide the *sender* (Monero's ring/key-image vs MWEB's cut-through). The ZK family
proves balance *inside a circuit* instead of via a homomorphic sum. All three reduce conservation to a
**cryptographic** floor — the strongest rung of the §11 ladder (algebra, not a runtime check) — and
all three carry the same shape of irreducible residual: **the soundness of the underlying proof
system.** Monero's advantage over KZG-based ZK: Bulletproofs+ are **transparent** (no trusted setup,
no toxic waste).

## The irreducible trusts (named, not cleared)
1. **Range-proof (Bulletproofs+) soundness** — if unsound, a negative/wraparound amount could forge
   value past the sum check. The deep cryptographic residual (analog of zkSync's circuit / Optimism's
   FPVM / MWEB's Bulletproofs). Well-studied, transparent setup, but not re-derived here.
2. **Discrete-log hardness / generator independence** (`G`,`H` with unknown relative dlog) — Pedersen
   *binding* rests on it; if broken, a commitment could be opened to a different amount. Standard
   assumption, stated.
3. **Curve-point validity** — handled defensively (invalid points throw → reject), confirmed.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read the actual sum: output commitments + `fee·H` on one side,
  pseudo-input commitments on the other, with `equalKeys` as the gate — and confirmed the range-proof
  loop rejects if *any* output proof fails, not just on aggregate. I did not take "RingCT conserves"
  on faith; I located the exact `equalKeys(sumPseudoOuts, sumOutpks)` line.
- **Exposure to reversal.** This clears *inflation* only. It would not catch a double-spend (that's
  the key-image layer I did not open) and rests entirely on range-proof + DL soundness (named
  residuals). If a tx path existed that committed outputs without a range proof, the floor would break
  — I confirmed `verRctSemanticsSimple` requires `outPk.size() == n_bulletproof(_plus)_amounts`
  (`:1367-1369`), so every output is range-covered; I did not audit the mempool/consensus glue that
  *calls* this verifier on every tx (assumed, per Monero's design).

## Verdict
**Clean.** Monero's RingCT enforces value conservation cryptographically: `Σ input commitments ==
Σ output commitments + fee·H` over hidden Pedersen-committed amounts, made sound by a mandatory
range proof on every output (Bulletproofs+/Bulletproofs/Borromean), with malformed inputs rejected via
catch-and-return-false. It completes the corpus's privacy-conservation triad — same homomorphic floor
as MimbleWimble, a transparent-setup alternative to ZK circuits. No inflation path found; nothing to
disclose. Named irreducible trusts: range-proof and discrete-log soundness. Next pulls (separate
surfaces): CLSAG ring-signature verification and the key-image double-spend layer.

---

# Addendum — Pass 2: ownership + double-spend (CLSAG + key images) — opened, clean

Closing the deferred "non-semantics" half of Pass 1: RingCT splits *no-inflation* (Pass 1, the
commitment sum) from *ownership + no-double-spend* (this pass). Both are needed for a complete value
guarantee, and both are now traced.

## Ownership without revealing which — CLSAG ring signature
`verRctCLSAGSimple` (`src/ringct/rctSigs.cpp:875`) verifies a CLSAG ring signature over the input's
ring (`pubs`). The hardening checks I confirmed up front:
- **Canonical scalars:** every `sig.s[i]` and `sig.c1` must pass `sc_check` (`:884-886`) — rejects
  non-reduced scalars, closing signature-malleability.
- **Non-degenerate key images:** `sig.I != identity()` (`:887`) and the auxiliary `D_8 != identity()`
  (`:898`) — a degenerate (identity) key image is rejected.
- The verifier then rebuilds the **aggregation hashes** (`mu_P`, `mu_C` over domain-separated
  `I, D, P, C, C_offset`, `:904-914`) and walks the ring recomputing the challenge chain, accepting
  iff the chain closes back to `c1`. That is the standard CLSAG soundness: the signature verifies **iff
  the signer knew the private key `x` of exactly one ring member and the key image `I = x·Hp(P)` is
  correctly formed** — proving ownership of *a* ring member while hiding *which* one (sender ambiguity).
Wrapped in `try/catch → false` (`:876`,`:...`), so a malformed point rejects rather than throws. **enforced.**

## No double-spend — deterministic key image + a spent-set registry
Because the key image `I = x·Hp(P)` is a deterministic function of the spent output's key, **spending
the same output twice yields the same `I`**. The chain enforces uniqueness:
`have_tx_keyimges_as_spent(tx)` (`src/cryptonote_core/blockchain.cpp:3214-3224`) iterates the tx's
inputs and **rejects if any `in_to_key.k_image` is already recorded as spent** (`have_tx_keyimg_as_spent`,
`:123`); the same check guards input validation (`:3220`,`:3488`), and within-block key-image
uniqueness is enforced too. So the key image is the privacy-preserving analog of the UTXO
"mark-spent"/nonce: it reveals nothing about *which* output was spent, yet a re-spend collides on `I`
and is rejected. **enforced.**

## The complete Monero value guarantee (both halves)
| Property | Mechanism | Pass |
|---|---|---|
| No inflation | Pedersen `Σin = Σout + fee·H` + range proofs | 1 |
| Ownership (spender controls an input) | CLSAG ring signature (knows `x` for one ring member) | 2 |
| No double-spend | deterministic key image `I = x·Hp(P)` + spent-set registry | 2 |
| Amount hiding | Pedersen commitments | 1 |
| Sender hiding | ring signature + key image | 2 |
*(Receiver hiding via one-time stealth addresses is a further surface, not opened.)* With Pass 2, the
audit covers both the inflation-resistance and the double-spend-resistance of Monero — the full
"value can't be forged or double-spent" guarantee. **No finding.** The deepest residual is unchanged:
the soundness of the underlying crypto (range proofs, and now the CLSAG/Schnorr ring-signature
soundness + the `Hp` hash-to-point being a genuine random oracle so `I` can't be forged for a key you
don't control) — named, not cleared.
