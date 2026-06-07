# Recent-commits hunt — the freshest, least-reviewed code

The other high-EV vein: code that *postdates the last audit*. New EIPs, new precompiles, new
consensus features — least battle-tested, where un-found bugs live. Method: clone a major repo *with
history*, `git log` recent security-relevant commits, and read the **changed** code (biased to new
*features*, not bug-fixes — fixed bugs are already fixed). Same failure classes (determinism, swallowed
errors, conservation, missing checks). **Live+exploitable → stopped-and-notified privately; redacted
placeholder only.** Defensive, no PoC.

---

## R1. go-ethereum — EIP-7928 Block Access List (BAL) construction/encoding (clean)
**Target:** `ethereum/go-ethereum` (history clone), `core/types/bal/{bal,bal_encoding}.go` +
`core/state/reader_eip_7928.go`. Picked because recent commits (`#34803` "track the block-level
accessList", `#34957` "construct block accessList") add a **brand-new consensus-relevant feature**: the
block access list (a canonical, hashable summary of all addresses/slots/balance/nonce/code touched in a
block). It's the *freshest* consensus-surface code, and the precise MemeCore-class risk applies: the BAL
is **built from Go maps** (`ConstructionBlockAccessList.Accounts map[common.Address]*...`, storage/
balance/nonce/code all maps, `bal.go:30-76`) and then must produce a **canonical** encoding — if it
encoded in map-iteration order, different nodes would compute different BALs → different block hash →
consensus split.
- **It canonicalizes correctly before encoding — clean.** `EncodeRLP` sorts *everything*:
  addresses by `common.Address.Cmp` (`bal_encoding.go:465`), storage write/read slots by
  `common.Hash.Cmp` (`:394,416`), and every per-tx index list by `cmp.Compare`
  (`:403,423,433,443` — write/balance/nonce/code indices); the canonical `BlockAccessList.EncodeRLP`
  form sorts accounts by `bytes.Compare(a.Address[:], b.Address[:])` (`:84`) and entries by
  `BlockAccessIndex` (`:187,290,301,313`). So the encoded/hashed BAL is **canonical regardless of map
  iteration order** — the build-from-map-then-sort-before-consensus pattern, done right (same as Sonic
  L3 / BSC L1).
**Result: clean.** The newest consensus-relevant feature in geth handles the exact MemeCore-class
determinism concern correctly (comprehensive canonical sort at encode time). **Residual:** BAL
*validation/enforcement* (matching the constructed BAL to actual execution, once the fork activates) and
the per-field completeness (every touched slot recorded) are the surfaces to re-check when the fork
goes live — currently construction is canonical. **No finding.** *(Also noted: recent blob-hash fixes
`#35065`/`#35109` are already-merged fixes — the area is active but the bugs are patched.)*

---

## R2. reth — EIP-7928 BAL *validation* (the geth-BAL counterpart, in a newer client) (clean structure; pre-fork)
**Target:** `paradigmxyz/reth` (history clone), `crates/ethereum/consensus/src/validation.rs` +
`crates/engine/tree/src/tree/payload_processor/bal/execute.rs`. The deliberate complement to R1: reth is
a *newer* client, and the recent commit `03d9691 feat(consensus): add experimental BAL validation`
implements the **validation** side of the same EIP-7928 BAL whose *construction* I checked in geth. The
high-EV risk is **client-diversity consensus divergence**: if reth's canonical BAL encoding differs from
geth's by even one byte, a geth-produced block's BAL hash would be recomputed differently by reth →
reth rejects a valid block → chain split.
- **Validation is recompute-and-hash-compare — structurally sound.** reth re-executes, builds the BAL,
  and `if block_access_list_hash != block_bal_hash { return Err(BlockAccessListHashMismatch) }`
  (`validation.rs:118`). Correct shape (recompute, don't trust the header's claim).
- **Encoding is delegated to a *shared canonical crate*, not reimplemented.** reth uses
  `alloy_eip7928::{Bal, BlockAccessList}` and `compute_block_access_list_hash` (`bal/execute.rs:20,303`)
  — so the sort/RLP canonicalization lives in the shared `alloy-eip7928` library, the Rust-ecosystem
  counterpart to geth's `core/types/bal`. The divergence risk therefore reduces to **"alloy-eip7928's
  canonical encoding == geth's `bal` encoding == the EIP-7928 spec,"** which is exactly what the
  EIP-7928 **cross-client execution-spec test vectors** exist to enforce — centralized agreement, not
  N independent encoders.
- **Pre-fork / experimental.** It's an *experimental toggle* for the future Amsterdam/Glamsterdam fork
  (`6a5f371 validate Amsterdam header fields`), **not yet mainnet-consensus-enforced** — so even a
  latent encoding discrepancy could not currently split mainnet.
**Result: clean structure.** reth validates correctly (recompute + hash-compare) and delegates encoding
to the shared canonical crate, so it can't trivially diverge from geth by a private sort choice.
**Residual (named, not closed):** the byte-for-byte agreement of `alloy-eip7928` ↔ geth's `bal` encoder
— I did not read alloy's source here (separate crate), so the cross-client canonical-encoding match is
asserted to be covered by EIP-7928 test vectors, not verified by me. Re-check at fork activation. **No
finding.**

### Recent-commits hunt status
Two complementary fresh-feature reads on the *same* newest consensus feature (EIP-7928 BAL): geth's
**construction** (R1) canonically sorts before encoding; reth's **validation** (R2) recompute-and-hash-
compares with encoding delegated to the shared `alloy-eip7928` crate. Both clean; both pre-fork. The
freshest consensus code in the two major EL clients handles the MemeCore-class determinism concern
correctly, and the cross-client divergence risk is centralized into a shared canonical encoder + spec
test vectors. The honest residual is the shared-encoder byte-agreement (test-vector territory) — to
re-verify when the fork activates. **No finding.**

---

## R3. Optimism Superchain interop — `CrossL2Inbox` cross-chain message validation (clean by design; security is off-chain)
**Target:** `ethereum-optimism/optimism` (history clone), `packages/contracts-bedrock/src/L2/CrossL2Inbox.sol`.
The freshest *value-critical cross-chain* feature (Superchain interop — execute a message on chain B
that was emitted on chain A). The classic cross-chain bug class is **value-from-a-fake-message**: can an
executing message be validated without a real source? Recent history is dominated by interop "failsafe"
work (`#21205` dedicated failsafe RPC error, `#21151`/`#21115` failsafe metrics) — a kill-switch design.
- **The on-chain check is intentionally minimal — and alone is NOT the security boundary.**
  `validateMessage` (`:76-82`) computes a `checksum` of the message `Identifier`+`msgHash` and only does
  `(bool isWarm,) = _isWarm(checksum); if (!isWarm) revert NotInAccessList();` then emits
  `ExecutingMessage`. `_isWarm` literally measures the **EIP-2930 access-list warmth** of the checksum
  slot. **The access list is sender-controlled** — so the *contract by itself* would let a tx self-warm
  the checksum of a fabricated message and pass. This is **by design**, not a bug: the checksum is a
  **type-3 access-list entry** (`_TYPE_3_MASK`, `:111`).
- **The real validation is the off-chain derivation rule.** Safety comes from the protocol layer: the
  **op-supervisor + the block-derivation rule reject any block whose type-3 interop access-list entries
  don't correspond to a valid, existing, in-dependency-set, non-reorged source message.** So warmth
  (necessary, on-chain) ∧ "every interop access-list entry maps to a real message" (sufficient,
  off-chain derivation) = the full check. The contract is a gas-cheap hook; the **derivation/supervisor
  is the security boundary** (and the `failsafe` is the anomaly kill-switch over it).
**Result: clean by design** — the minimal on-chain `validateMessage` is *not* exploitable in context
because the derivation layer rejects blocks with unbacked interop access-list entries. **Residual (large,
and precisely located):** the **op-supervisor / op-node derivation** that enforces "interop access-list
entry ⟺ valid source message" — that off-chain Go is the actual cross-chain safety boundary and the
real audit target (not opened here; it's the irreducible interop trust, same shape as §4f settlement
seams). **No finding** — but the honest note: reading *only* the contract would look broken; safety lives
in the derivation rule, which I did not open.

### Recent-commits hunt status (3 entries)
R1 geth BAL construction (canonical sort — clean), R2 reth BAL validation (recompute+hash, shared
encoder — clean, pre-fork), R3 op-stack interop `CrossL2Inbox` (minimal on-chain gate; security
relocated to off-chain derivation — clean by design). Pattern across the freshest code in the major
EL/L2 stacks: the on-chain/consensus components handle determinism correctly **and** increasingly
*relocate* the heavy validation to shared canonical encoders (alloy) and off-chain
supervisors/derivation — so the residual is consistently a **cross-client encoder agreement** or an
**off-chain validator**, exactly the "name the oracle" shape (§4h). No findings.

---

## R4. Optimism op-supervisor — interop cross-safety validation (the R3 security boundary, opened — clean)
**Target:** `ethereum-optimism/optimism`, `op-supervisor/supervisor/backend/cross/hazard_set.go`. This is
the **off-chain security boundary R3 pointed at** — the supervisor logic that enforces "interop
executing-message ⟺ valid source message," which the minimal on-chain `CrossL2Inbox` delegates to.
Opened it, and the core cross-chain safety is **correctly enforced**:
- **No value from a fake message (existence + checksum).** For every executing message, `build`
  (`:124-135`) runs `deps.Contains(msg.ChainID, {Timestamp, BlockNum, LogIdx, Checksum})` — the source
  log **must actually exist** at that exact coordinate **with a matching checksum**, or "failed inclusion
  check." A fabricated/self-warmed message (the R3 self-warm concern) **fails here** — this is the check
  that makes the minimal on-chain contract safe.
- **Timestamp / causality invariant.** A source message in the **future**
  (`msg.Timestamp > candidate.Timestamp`) → **`breaks timestamp invariant: ErrConflict`** (`:155-156`):
  you cannot execute a message initiated after you. Older source → `checkMessageWithOlderTimestamp`
  (must be in a cross-valid block); same-timestamp → `checkMessageWithCurrentTimestamp` with cycle-aware
  hazard recursion (`:137-154`, handles back-and-forth same-ts messaging without inconsistent cycles).
- **Dependency-set linking.** `checkChainCanExecute` → `linker.CanExecute(destChain, ts, srcChain, ts)`
  (`:59-62`) gates chain-pair execution + the chain-level timestamp link before any message is linked.
- **Expiry** is checked upstream (noted `:74`), and the hazard set feeds the cross-safe/unsafe update so
  an executing block is only as safe as its source messages.
**Result: clean** — the supervisor enforces existence (checksum-matched inclusion), the
no-future-execution timestamp invariant, dependency-set linking, and cycle-safe same-timestamp handling.
This **closes most of the R3 residual**: the off-chain validator the on-chain `CrossL2Inbox` relies on
genuinely rejects fake/future/unlinked messages. **Remaining residual:** the **log-DB correctness**
(`deps.Contains` faithfully mirroring source-chain logs) and the **reorg/invalidation + finalization
progression** (`safe_update`/`unsafe_update` — what happens if a source message is reorged out after
execution) — deeper surfaces, not opened. **No finding.**

### Recent-commits hunt — convergence
R3 (on-chain `CrossL2Inbox`: minimal warmth gate) + R4 (off-chain supervisor: the real existence +
timestamp-invariant + dependency checks) together show the interop design is sound *as a system*: the
contract is a cheap hook, the supervisor is the enforcer, and the enforcer does its job. This is the
"name the oracle, then open it" follow-through (§4h) applied to a live, recently-shipped cross-chain
feature — the oracle (op-supervisor) checks out on its core message-validation. Net across R1–R4: the
freshest EL/L2 code is clean on determinism and cross-chain existence/causality; residuals are the
shared encoder byte-agreement (R2), the log-DB + reorg/finalization progression (R4) — both
named, neither a finding.

---

## R5. Optimism op-supervisor — cross-safe progression & reorg invalidation (the R4 remainder, opened — clean)
**Target:** `op-supervisor/supervisor/backend/cross/{safe_update,safe_frontier}.go`. The deepest interop
residual: can an executing block reach a safety level (cross-safe / finalized) while its **source
message gets reorged out**? Opened the progression logic, and it's **soundly gated**:
- **Cross-safe promotion requires all dependencies cross-safe.** `scopedCrossSafeUpdate` builds the
  candidate's hazard set, then runs **`HazardSafeFrontierChecks`** (`safe_update.go:14`) + `HazardCycleChecks`
  + a read-consistency abort **before** `UpdateCrossSafe` (`:26`). The frontier check
  (`safe_frontier.go`) iterates every hazard dependency and requires it to be **cross-derived (cross-safe)
  within the current L1 scope** — out-of-scope → `ErrOutOfScope` (bump scope, *don't* promote).
- **Reorg detection = `ErrConflict`.** If a dependency block at a given number has a **different ID than
  expected** (i.e. the source was reorged), `HazardSafeFrontierChecks` returns **`ErrConflict`**
  (`safe_frontier.go:14-16`) — so a block depending on a reorged-out source **cannot be promoted**.
- **Invalidation cascade.** On any such failure, `CrossSafeUpdate` calls **`InvalidateLocalSafe`**
  (`safe_update.go:61`) — the candidate (and its replacement chain) is invalidated and re-derived. So a
  reorged source cascades to invalidate the dependent executing block; it cannot remain cross-safe.
**Result: clean** — the cross-safe frontier advances *only* when every source-message dependency is
itself cross-safe and same-ID (non-reorged); a reorged dependency yields `ErrConflict` → invalidation
cascade. The interop safety progression correctly prevents "executed a message whose source later
vanished." **Remaining residual (deepest):** the **log-DB reorg detection** itself (how the supervisor
marks a source block invalid / the `reads.Handle` consistency + DB rewind) and the cross-**unsafe**
analog (`unsafe_update.go`) — the substrate beneath the progression, not opened. **No finding.**

### Interop deep-dive — full chain traced (R3→R4→R5), all clean
The freshest, most-complex, most-value-critical cross-chain feature in the entire corpus, traced
end-to-end across three layers: **R3** on-chain `CrossL2Inbox` (minimal warmth hook, delegates) → **R4**
supervisor message validation (checksum-matched existence + no-future-execution timestamp invariant +
cycle handling) → **R5** cross-safe progression (dependencies must be cross-safe + non-reorged;
`ErrConflict` + invalidation cascade on reorg). All clean. The system is soundly designed: the on-chain
gate is cheap, the off-chain enforcer checks existence/causality, and the safety progression refuses to
advance (and cascades invalidation) when a dependency is non-cross-safe or reorged. Residuals are the
substrate: shared-encoder byte-agreement (R2), log-DB reorg detection + cross-unsafe analog (R5) — all
named, none a finding. This is "name the oracle, then open it, then open *its* substrate" — three levels
deep on a live feature, and it holds.

---

## R6. Solana / Agave (SOL) — capitalization (total-supply) accounting + recent cached-account fix (clean) [non-EVM]
**Target:** `anza-xyz/agave` HEAD `fed083b`, `runtime/src/bank.rs` + `accounts-db/src/accounts_db.rs`.
First **non-EVM** recent-commits target — genuinely different ground (account model, Rust runtime, not
type-enforced conservation). Picked the conservation-critical surface flagged by the recent commit
`205b6e2 / #12909 "Add Cached Account updates to capitalization"`. **Capitalization = Solana's total
supply** (Σ all account lamports); the invariant is `capitalization == Σ lamports`.
- **Incremental delta-tracking is correct + checked.** `store_account_and_update_capitalization`
  (`bank.rs:4685+`) computes the lamport **diff** (new vs old) and `fetch_add`/`fetch_sub`s exactly that,
  handling the created-account case; the create/destroy/rent points (`:3118,3183,4416`) likewise add/sub
  the precise lamports. Comment is appropriately cautious ("Technically this issues (or even burns!) new
  lamports").
- **Recompute-and-verify gate (the conservation check) — and the recent fix.**
  `calculate_capitalization_at_startup_from_index` (`accounts_db.rs:5010`) recomputes capitalization by
  summing non-zero stored lamports over the whole account index with **`checked_add`** ("capitalization
  cannot overflow", `:5035-5038`) **plus** the **cached (un-flushed) account updates**
  (`accounts_cache.cached_pubkeys()`, `:5045+`) — summed as **i128** with explicit overflow reasoning.
  The recent commit's content *is* this cached-update inclusion: before it, the recompute could miss
  accounts still in the write cache, causing a spurious mismatch; the fix makes the recompute =
  storage-index Σ + cache-delta. Correct hardening.
**Result: clean** — capitalization is delta-tracked with checked arithmetic and verified by a full
recompute (index Σ + cache delta, overflow-guarded), the recompute-don't-trust conservation gate (the
Solana analog of Algorand's `totals.All()`), and the recent change correctly closes a cache-omission gap
in that recompute. **Residual:** the exact compare-site (recomputed vs tracked capitalization at
snapshot verification) + the accounts-hash verification — confirmed the recompute, not every compare
call. **No finding.**

### Non-EVM note
The recent-commits lens transfers cleanly to a non-EVM chain: same discipline (conservation as a
recomputed invariant, checked arithmetic, recompute-don't-trust), different substrate (account-lamports
capitalization vs EVM balances). Solana verifies total supply by full recompute — the same
"strongest-floor" family as Algorand/ICP/Tezos — and the freshest change *hardens* that recompute. The
non-EVM frontier looks the same as the EVM one: clean conservation core, residual at the verification
substrate.

---

## R7. Solana / Agave — Alpenglow / votor consensus (the freshest consensus code in the repo) (clean) [non-EVM]
**Target:** `anza-xyz/agave`, `votor/src/consensus_pool/{vote_pool,slot_stake_counters,certificate_builder}.rs`.
The **newest consensus code in the corpus** — Solana's Alpenglow (votor) replacing TowerBFT, brand-new
and consensus-safety-critical. The conservation analog is *safety*: no two conflicting blocks both
notarized/finalized. Hunted the MemeCore classes + the BFT-safety primitives (vote double-count,
threshold correctness, determinism).
- **Vote dedup — each validator counted once (no equivocation/double-count inflation).** `vote_pool.rs`
  keeps `prev_voted_validators: BTreeSet<Pubkey>`; `add_vote` does `if
  !self.prev_voted_validators.insert(key) { return }` (`:30-36`) — a re-vote is rejected, so a validator
  cannot inflate a certificate's stake by voting twice. The notarize pool (`prev_voted_block_ids:
  BTreeMap<Pubkey, BTreeSet<Hash>>`) additionally rejects a repeated block_id per validator and caps
  `max_entries_per_pubkey` (`:78-96`). This is the anti-equivocation / quorum-honesty primitive (the
  Solana analog of MonadBFT's `DuplicateValidator` guard).
- **Thresholds are exact rationals — no float determinism hazard.** Stake fractions compared as
  `Fraction::new(num_stake, self.total_stake) >= THRESHOLD` (`slot_stake_counters.rs:158`); the
  Alpenglow safe-to-notar conditions (`:117,134-137`): `notar ≥ 40%` OR (`notar ≥ 20%` AND
  `notar+skip ≥ 60%`), and a skip threshold — all exact-rational comparisons (no `f64`, so no
  cross-node float divergence; contrast EOS's softfloat-contained float, L-sweep). Deterministic.
- **Deterministic containers.** `BTreeSet`/`BTreeMap` (ordered) throughout — no Go-map-style
  nondeterministic iteration into a consensus decision (the MemeCore class is structurally absent).
**Result: clean** — the freshest consensus code handles vote dedup (no double-count), exact-rational
stake thresholds (no float), and deterministic ordered containers correctly. Same BFT-safety shape as
MonadBFT (vote-once + stake-supermajority quorum), in brand-new non-EVM Rust. **Residual:** the **BLS
signature aggregation** (does an aggregate certificate genuinely prove the counted validators signed —
the crypto under the stake count) and the **Alpenglow quorum-intersection safety proof** (that the
40/20/60 thresholds actually guarantee no two conflicting certs — the protocol proof, per the paper) —
the deeper trusts, same residual shape as MonadBFT. **No finding.**

### Non-EVM recent-commits status (R6–R7)
Two non-EVM Solana reads on the freshest, most-critical surfaces: **R6** capitalization (total-supply
conservation, recompute-verified, recent cached-account fix correct) and **R7** Alpenglow/votor (newest
consensus — vote-dedup + exact-rational thresholds + deterministic containers, all sound). The
recent-commits lens transfers fully to non-EVM: same failure classes checked, same clean result, same
residual shape (crypto soundness + protocol safety proof). Across R1–R7 (geth, reth, op-stack ×3,
Solana ×2) the freshest code in the major EVM and non-EVM stacks is clean on determinism, conservation,
and consensus-safety primitives; residuals are uniformly crypto/encoder/off-chain-validator substrate.
**MemeCore remains the sole code-level finding.**
