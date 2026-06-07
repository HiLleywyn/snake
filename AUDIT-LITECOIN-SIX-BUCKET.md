# Litecoin — Six-Bucket Trust Audit (UTXO base layer + MWEB extension)

**Target:** litecoin-project/litecoin, cloned `/tmp/litecoin`, HEAD `d8c8adc` (tag
`v0.21.5.5`).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. A verdict says "enforced
by constraint X" / "deterministically derived at Y" / "not enforced in reviewed path" /
"unclear, needs human review" — never bare "safe."

Litecoin is a UTXO chain (C++ Bitcoin fork), so the trust model is the opposite of the
Move/Rust L1s audited earlier: conservation is **transparent arithmetic on plaintext
amounts** on the base layer, and **homomorphic commitment algebra** on the MWEB extension.
The base layer is mostly inherited-and-unchanged from Bitcoin (high evidence depth, low
novelty); the audit weight is on **MWEB (MimbleWimble Extension Blocks)** — Litecoin's
confidential-transaction layer and its single richest trust surface, where Buckets 1, 3,
and 6 intersect.

---

## The centerpiece: MWEB's tri-layer conservation (Bucket 1 ∩ 3 ∩ 6)

The same LTC value held inside MWEB is pinned from **three independent representations**
that must *all* reconcile on *every* block. This is the strongest cross-representation
conservation structure in the entire audit series, because the three views are computed by
different subsystems in different number systems and cross-checked against each other.

### Representation 1 — canonical plaintext scalar (`mweb/mweb_node.cpp::ConnectBlock`)

A single `CAmount mweb_amount` is carried on each block index = total LTC inside MWEB. It
is reconciled per block:

```cpp
CAmount hogex_input_amount = pindexPrev->mweb_amount;              // :195 running total
... for each pegin output: hogex_input_amount += output.nValue;    // :200
    if (!MoneyRange(hogex_input_amount)) ... "accumulated-pegin-outofrange";  // :201
CAmount hogex_fee = hogex_input_amount - pHogEx->GetValueOut();    // :215
if (hogex_fee != *mweb_fee) ... "bad-txns-mweb-fee-mismatch";      // :216
const auto mweb_amount = AmountUtil::TrySafeAdd(pindexPrev->mweb_amount, *supply_change);  // :223
if (!MoneyRange(*mweb_amount) || *mweb_amount != pHogEx->vout.front().nValue)  // :228
    ... "mweb-amount-mismatch";
```

`supply_change = (pegins − pegouts) − fees`. The new running total must **exactly equal
the first output of the HogEx transaction** (`:228`) — i.e. the canonical chain carries a
real UTXO whose value *is* the MWEB total supply. And each HogEx's first input must spend
the previous HogEx's first output (`:181`–`:186`), forming an unbroken supply-carrying
chain (with a special case for the very first HogEx, `:180`). **enforced; overflow-safe**
(`MoneyRange` + `TrySafeAdd`).

### Representation 2 — cross-layer peg lists (`libmw/.../node/BlockValidator.cpp`)

The pegins/pegouts *declared inside* the MWEB block must match the pegins/pegouts *visible
on the canonical chain*:

- **Pegins:** every canonical pegin output (`scriptPubKey.IsMWEBPegin`, collected in
  `mweb_node.cpp:147`–`:154`) must match an MWEB-internal pegin by **kernel id and amount**,
  with equal counts and no duplicates (`BlockValidator.cpp:38`–`:50`). **enforced.**
- **Pegouts:** the MWEB block's pegouts must match the HogEx's pegout outputs as a
  **multiset** of (amount, scriptPubKey) — duplicates allowed, counts equal
  (`:57`–`:71`). **enforced.**

So value cannot enter or leave MWEB without an exactly-matching transparent counterpart on
the canonical chain. This is the dual-representation reconciliation that ties the hidden
layer to the visible one.

### Representation 3 — homomorphic commitments (`libmw/.../consensus/KernelSumValidator.h`)

This is the cryptographic conservation, run during state application
(`CoinsViewCache.cpp:56`, inside the `ApplyBlock` called from `mweb_node.cpp:237`):

```cpp
// ValidateSums: Σoutputs − Σinputs − (coins_added · H)  ==  Σkernel_excess + offset · G
Commitment sum_utxo  = Pedersen::AddCommitments(output_commits, input_commits);
... ± Commitment::Transparent(coins_added) ...                 // :102–:110
Commitment sum_excess = Pedersen::AddCommitments(kernel_commits) (+ offset·G);  // :113–:118
if (sum_utxo_commitment != sum_excess_commitment) ThrowValidation(BLOCK_SUMS);  // :120
```

Pedersen commitments are `C = r·G + v·H`. The balance holds iff the value components
satisfy `Σout_v − Σin_v = coins_added` (kernels/offset carry blinding only, no value).
**This proves no net value is created inside MWEB** — and `coins_added` is the *same*
`supply_change` that Representation 1 added to the scalar. The three representations are
welded at `coins_added ≡ supply_change ≡ (HogEx_out − prev_amount)`.

**Critical companion — range proofs.** Commitment-sum conservation is necessary but *not
sufficient*: without bounding each value, a negative `v` (via curve-order wraparound) could
forge supply while keeping the sum balanced. `TxBody::Validate` (`tx/TxBody.cpp`) runs
`Bulletproofs::BatchVerify` on **every** output's range proof, proving each `v ∈ [0, 2⁶⁴)`.
Both halves are present: **commitment balance (no net creation) + range proofs (no
negative/overflow forgery).** `ValidateState` additionally enforces total MWEB supply
`≥ 0` (`KernelSumValidator.h:37`). **enforced invariant (cryptographic).**

**Verdict (MWEB conservation): enforced invariant**, reconciled per-block across three
representations. The scalar, the peg lists, and the commitments must agree or the block is
`BLOCK_CONSENSUS`-invalid.

---

## Bucket 1 — Conservation (base layer, inherited from Bitcoin)

- **Coinbase bound:** `block.vtx[0]->GetValueOut() <= nFees + GetBlockSubsidy(height)`
  (`validation.cpp:2267`). A coinbase paying more is `bad-cb-amount`. **enforced.**
- **Per-tx value conservation:** `CheckTxInputs` (`consensus/tx_verify.cpp`) requires
  `Σinputs ≥ Σoutputs`, accumulating the difference into `nFees` with `MoneyRange` guards.
  **enforced** (inherited, high evidence depth).
- **Subsidy schedule:** `GetBlockSubsidy` (`validation.cpp:1266`) = `50 * COIN >> halvings`,
  `halvings = height / nSubsidyHalvingInterval`, zero after 64 halvings. **enforced.**

---

## Bucket 2 — Witnessed cryptographic objects

- **Base PoW:** scrypt (Litecoin's headline divergence from Bitcoin's SHA-256d) — witnessed
  by the block header meeting the target. (Algorithm divergence; not re-derived here.)
- **Base tx sigs:** ECDSA script verification (inherited, `control.Wait()` batch at
  `validation.cpp:2272`).
- **MWEB signatures:** `Schnorr::BatchVerify` over **all** kernels, inputs, *and* outputs
  (`TxBody::Validate`) — ownership/authorization witnesses for every MWEB component.
  **enforced.**
- **MWEB accumulators (the binding witnesses):** the MWEB header commits to state via three
  roots that must equal the recomputed structures:
  - **kernel MMR root** == recomputed `kernel_mmr.Root()` (`Block.cpp:26`),
  - **output PMMR root**, **NumTXOs**, **leafset root** == recomputed
    (`CoinsViewCache.cpp:90`–`:95`),
  and the canonical block's HogEx commits the MWEB header hash
  (`mweb_node.cpp:89`, `mweb-hash-mismatch`). These tie the cheap header commitment to the
  full hidden state. **enforced.**

---

## Bucket 3 — Dual / multiple representations

- **The tri-layer value representation** (scalar ⇄ peg lists ⇄ commitments) above — the
  primary Bucket-3 surface, and it is *reconciled*, not merely co-existing.
- **Input metadata rebinding:** an MWEB input carries serialized metadata that must be
  rebound to the *real* spent UTXO — `pUTXO->GetCommitment() == input.GetCommitment()` and
  `pUTXO->GetReceiverPubKey() == input.GetOutputPubKey()` (`CoinsViewCache.cpp:77`–`:82`),
  else `UTXO_MISMATCH`. Prevents substituting a different output's metadata. (The
  `allow_historical_metadata_mismatch` grandfather is a lineage carve-out, Bucket 4.)
  **enforced** (modulo the grandfather block).

---

## Bucket 4 — Dependency / fork lineage

This is where Litecoin's "fork of Bitcoin, plus a soft-forked-in MimbleWimble" history
shows up as concrete seams:

- **Subsidy parameterization vs. a stale inherited comment.** The *algorithm* in
  `GetBlockSubsidy` is byte-for-byte Bitcoin; Litecoin diverges only by parameter
  (`nSubsidyHalvingInterval = 840000`, `chainparams.cpp:76`/`:198`, vs Bitcoin's 210000).
  But the inline comment at `validation.cpp:1274` still reads *"every 210,000 blocks ...
  approximately every 4 years."* The **840000** figure is correct in code (it reads the
  param); the "210,000 blocks" in the comment is the ancestor's value left un-updated.
  (The "~4 years" remains accurate, since Litecoin's 2.5-min blocks × 840000 ≈ Bitcoin's
  10-min × 210000.) **documentation debt** — a fork-lineage artifact, not a code defect.
- **MWEB activation gating.** `IsMWEBEnabled` gates all MWEB validation; pre-activation
  blocks carrying MWEB data are rejected (`mweb_node.cpp:31`–`:49`), and the *first* HogEx
  is special-cased (`:180`) since it has no predecessor to chain to. **enforced.**
- **Grandfather carve-outs (consensus-critical magic values).** Three lineage anchors let
  current code accept historical chain data that predates a rule tightening:
  `mweb_input_metadata_grandfather_blockhash` (`mweb_node.cpp:232`), the
  `frozen_mweb_output_ids` consensus blocklist (`:247`, incident-response output freeze),
  and `KERNEL_LOCK_HEIGHT_GRANDFATHER_HEIGHT` (`Block.cpp:15`). Each is correct *as*
  history-compatibility handling, but each is a hardcoded trust anchor that must match the
  real historical chain exactly. **constraint debt** (intentional, lineage-bound).

---

## Bucket 5 — Arithmetic / bounds

- `MoneyRange` on every accumulation and final amount (`mweb_node.cpp:201`, `:216`, `:228`).
- Overflow-safe addition: `AmountUtil::TrySafeAdd` (`:223`), `AmountUtil::SafeAdd` +
  `ValidateAmountRange` in the supply loop (`KernelSumValidator.h:33`–`:34`).
- Total MWEB supply forced `≥ 0` (`KernelSumValidator.h:37`).
- `coins_added` range-validated before use in the commitment math (`:98`).
**enforced** throughout; the MWEB accounting is consistently defensive about overflow and
range, matching the base-layer `MoneyRange` discipline.

---

## Bucket 6 — Cross-layer settlement seams

- **6a (reducible, discharged per-block): the HogEx bridge.** The HogEx transaction is the
  settlement instrument between the canonical UTXO set and MWEB. Unlike a deferred rollup
  proof, the conservation across this seam is **reconciled in full at every block**
  (`ConnectBlock` + `ValidateMWEBBlock` + `ApplyBlock`), inside the same atomic
  `CChainState::ConnectBlock` (`validation.cpp:2280`). Nothing is deferred to a later
  challenge window. **reduced to per-block reconciliation.**
- **6b (irreducible, interpretation): plaintext scalar ⇄ hidden commitment sum.** The
  canonical `mweb_amount` is the *only plaintext view* of MWEB's total supply; the
  commitment side is value-hidden by construction. The claim "the scalar faithfully tracks
  the true hidden total" holds **inductively from genesis**: it is true at block N+1 iff it
  was true at N *and* the per-block commitment balance + range proofs held. The irreducible
  trust is therefore in **range-proof (Bulletproofs) soundness** — a soundness break there
  would let hidden value diverge from the scalar *undetectably*, surfacing only when an
  over-large peg-out is attempted. This is the deepest MWEB trust assumption and it cannot
  be discharged by any single-block check; it rests on the cryptographic primitive. **named,
  irreducible** (the correct place for the residual to live — in the proof system, not the
  bookkeeping).
- **Atomicity.** `ApplyBlock` validates into a temporary `validation_cache` and only
  `Flush()`es after full validation (`CoinsViewCache.cpp:42`–`:46`) — the MWEB state
  transition is all-or-nothing. **enforced.**

---

## Summary table

| Bucket | Subject | Verdict |
|---|---|---|
| 1 (MWEB) | Tri-layer conservation (scalar ⇄ pegs ⇄ commitments) | **enforced invariant** — reconciled per-block; commitment balance + range proofs |
| 1 (base) | Coinbase ≤ fees+subsidy; per-tx value-in ≥ value-out | **enforced** (inherited Bitcoin) |
| 2 | Schnorr batch sigs; Bulletproofs; MMR/PMMR/leafset roots; scrypt PoW | **enforced** (MWEB witnesses bind header to hidden state) |
| 3 | Tri-layer value representation; input-metadata rebinding | **enforced** — reconciled, not merely coexisting |
| 4 | Subsidy param vs. stale "210,000" comment | **documentation debt** — code correct (840000), comment is ancestor's value |
| 4 | MWEB activation + grandfather/frozen-output anchors | **enforced / constraint debt** — lineage-bound magic values |
| 5 | MoneyRange, SafeAdd/TrySafeAdd, supply ≥ 0 | **enforced** |
| 6a | HogEx canonical⇄MWEB bridge | **reduced** — per-block reconciliation, not deferred |
| 6b | Plaintext scalar ⇄ hidden commitment sum | **irreducible** — rests inductively on Bulletproofs soundness |

## What this audit did NOT cover (coverage honesty)

- The base-layer Bitcoin-inherited machinery (script interpreter, ECDSA, mempool policy,
  scrypt PoW correctness) — treated as high-evidence-depth inherited code, read only at the
  conservation interface.
- The libmw crypto primitives' internals (`Pedersen`, `Schnorr::BatchVerify`,
  `Bulletproofs::BatchVerify`, MMR) — read at their call sites and contracts, not their
  field arithmetic.
- The wallet/mining MWEB paths (`mweb_wallet.cpp`, `mweb_miner.cpp`, `TxBuilder.cpp`) —
  out of consensus scope for a conservation audit.
- Reorg/undo correctness beyond confirming `UndoBlock` rewinds the PMMR/leafset to the
  prior header roots (`CoinsViewCache.cpp:141`–`:148`).

## Nothing routed privately

No untrusted-input → unvalidated → value-moving path was found. MWEB value conservation is
reconciled per-block across three independent representations with explicit
`BLOCK_CONSENSUS` rejections, overflow-safe arithmetic, and an atomic apply. The one
irreducible residual (6b) is a *by-design* reliance on range-proof soundness, not a defect
in the bookkeeping — it is the correct place for the trust to sit, and it is shared by
every MimbleWimble system. There is nothing here to disclose to a security channel — only
the architectural fact worth recording: **Litecoin conserves the visible supply by
transparent arithmetic and the hidden supply by commitment algebra, and the two are welded
together every block by a single plaintext scalar carried in the HogEx output.**
