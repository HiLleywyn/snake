# zkSync Era (ZK) — validity-proof conservation audit (clean gating; circuit soundness stated as irreducible)

**Target:** `matter-labs/era-contracts`, cloned `/tmp/zke`. The L1 contracts of a **ZK validity
rollup** — `Executor.sol` (commit/prove/execute) and `Mailbox.sol` (L2→L1 message / withdrawal
inclusion), plus the `IVerifier` seam. **Posture:** defensive; no exploit, no PoC. **Result: the
on-chain validity-proof gate is correctly wired (clean); the conservation guarantee rests on circuit
soundness + verifier correctness + governance, which are stated as the irreducible trusts — nothing
to disclose.**

Chosen as a standout because it is the **ZK chain the methodology branch is named for**
(`zk-chain-audit-methodology`), and because it introduces a conservation-enforcement mechanism
**distinct from every other one in the corpus**. The four I'd catalogued enforce conservation *inside
the executing chain*: UTXO equation (Cardano/Avalanche), Move/Substrate type-system floors
(Sui/Aptos/Polkadot), recomputed/asserted invariants (Algorand/XRPL/Stellar), and multisig+dispute
bridges (Hyperliquid). zkSync's L1 **does not re-execute and does not check balances** — it **verifies
a SNARK proof** that the (L1-opaque) L2 execution was correct. The L1 conservation floor *is the
verifier*. This is a Bucket-2 (witnessed crypto object — the proof is the witness) floor.

## The validity-proof gate — commit → prove → execute, in order, no skipping (enforced)
1. **Commit** (`Executor.sol:_commitOneBatch`, `:60`): the operator posts each batch's claimed
   `newStateRoot`, `priorityOperationsHash`, and system logs, chained to the prior batch
   (`previousBatchHash` must match `:82-83`, batch number sequential `:67`). The commitment records
   the *claimed* transition; **it is not yet trusted.**
2. **Prove** (`proveBatchesSharedBridge`, `:641-692`): the load-bearing step.
   - The `prevBatch` must hash to the stored hash at `totalBatchesVerified` — you can only prove the
     *first unverified* batch, no skipping (`:661-667`).
   - For each committed batch, its stored hash must match (`:672-677`), and the public input is built
     as `proofPublicInput[i] = keccak256(prevCommitment, currentCommitment) >> shift` (`:680`,
     `_getBatchProofPublicInput :707-713`) — **the proof is cryptographically bound to the exact
     committed `(prev → current)` state-transition commitments.** A proof for a different transition
     won't satisfy this public input.
   - `_verifyProof` → `s.verifier.verify(proofPublicInput, _proof)`; **`revert InvalidProof()` if it
     returns false** (`:700-703`). No valid SNARK → the batch never becomes "verified."
   - Only then `s.totalBatchesVerified` advances (`:691`), bounded by committed (`:684-685`).
3. **Execute** (`executeBatchesSharedBridge`, `:606-636`): finalizes the L2 root on L1, but
   **`revert CantExecuteUnprovenBatches()` if `totalBatchesExecuted > totalBatchesVerified`**
   (`:629-630`). So **nothing executes that wasn't validity-proven.**

## The withdrawal seam — funds released only against a proven+executed root (Bucket 1 via Bucket 2)
L1 fund release (and any L2→L1 message) is finalized through `_proveL2LeafInclusion`
(`Mailbox.sol:220-248`): it Merkle-checks the withdrawal leaf against
`s.l2LogsRootHashes[_batchNumber]` (the batch's L2→L1 logs root) and reverts `BatchNotExecuted` if
`_batchNumber > s.totalBatchesExecuted` (`:239-240`), with `LocalRootIsZero` if the root is unset
(`:244-245`). So the full chain is:
> **L1 funds released ⟸ withdrawal leaf Merkle-proven in batch B ⟸ B executed ⟸ B validity-proven
> (SNARK verified) ⟸ proof bound to B's committed state transition.**
The SNARK attests that the *entire* L2 execution — including that each L2→L1 withdrawal message was
backed by a real L2-side burn — was correct. That is the conservation floor: **you cannot fabricate a
withdrawal without producing a valid proof of a real L2 burn.** **enforced (the gating is correctly
wired).**

## The irreducible trusts (stated plainly — what the Solidity does NOT prove)
The contracts I read prove the *gating* is sound (no execute-without-proof, no withdrawal-without-
inclusion-in-an-executed-batch). They do **not** establish, and cannot:
1. **Circuit soundness.** The ZK circuit must actually enforce L2 conservation; a bug that lets an
   invalid state transition produce a valid proof would forge funds *with* a passing on-chain check.
   The circuit is **not in these contracts** — it is the deep irreducible trust of any ZK rollup.
   (Cryptographic, not social — but unaudited here.)
2. **Verifier contract correctness.** `Verifier.sol` (Plonk/FFLONK pairing/precompile math) must
   correctly implement proof verification. It is auditable Solidity, but I read it only at the
   `s.verifier.verify(...)` interface — a stated residual.
3. **Trusted setup** (KZG/Plonk) — toxic-waste assumption, off-chain.
4. **Governance ceiling.** The diamond-proxy can upgrade facets and **swap the verifier**; an
   `onlyValidator`/`onlySettlementLayer` gate guards prove/execute. So the real-world escape hatch is
   governance (matches `AUDIT-GOVERNANCE-CEILING.md`): the math is trustless, but *who can replace the
   math* is the ceiling. Not opened here beyond noting the modifiers.

## Connections to the corpus
| Mechanism | Conservation enforced by | Safety assumption |
|---|---|---|
| **zkSync (ZK rollup)** | **SNARK verifier** gates execute+withdraw | circuit+verifier soundness (cryptographic) |
| Hyperliquid bridge | >2/3 validator multisig + dispute window | honest-majority + dispute liveness |
| Cardano/Avalanche | UTXO `consumed ==/≥ produced` | in-protocol re-execution |
| Sui/Aptos/Polkadot | type-system floor (linear / Imbalance) | verifier/compiler + in-protocol |
| Algorand/XRPL/Stellar | recomputed/asserted invariant | in-protocol re-execution |
The distinctive property: zkSync's withdrawal safety needs **no honest-majority assumption** — a valid
proof can't be forged without breaking the cryptographic assumption, so even a fully malicious
operator cannot withdraw funds it isn't owed (it can censor/halt — a *liveness* problem — but not
*steal*). Compare Hyperliquid, where withdrawal safety *does* rest on 2/3 honest validators + a
dispute window. This is the sharpest contrast in the corpus between **cryptographic** and **social**
settlement-seam trust, and it is exactly the §9 equivalence / Bucket-2 "witnessed crypto object"
distinction the methodology was built to locate.

## What this audit did NOT cover (coverage honesty)
- **`Verifier.sol` internals** (the pairing math) — interface only.
- **The ZK circuit / prover** — not in this repo; the deepest irreducible trust.
- **The DA (data-availability) path** and system-log validation in `_commitBatch` (`:211-302`) —
  read structurally (the log-key/sender checks), not exhaustively; DA is the other classic rollup
  residual (validity ≠ availability).
- **Priority-tree / L1→L2 forced inclusion** and the Bridgehub multi-chain message-root aggregation
  (`_proveL2LeafInclusion`'s settlement-layer recursion, `:250-268`) — the interop seam, noted not
  opened.
- **Governance/upgrade authority** (diamond cut, who controls verifier swaps) — modifiers noted only.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I traced the actual ordering dependency: `totalBatchesExecuted ≤
  totalBatchesVerified` (execute gate) and `totalBatchesVerified` only advances after
  `verifier.verify` returns true (revert `InvalidProof` otherwise), and the withdrawal path reverts
  `BatchNotExecuted` — so the dependency chain proof→execute→withdraw is real, not assumed.
- **Exposure to reversal.** I am explicitly **not** clearing circuit/verifier soundness — those are
  marked irreducible/residual, not "safe." The on-chain-gating verdict would itself flip if the public
  input failed to bind the proof to the committed transition (I confirmed it does, via
  `_getBatchProofPublicInput`) or if an execute path existed that bypassed the
  `CantExecuteUnprovenBatches` check (I read the single `executeBatchesSharedBridge` entry; I did not
  enumerate every diamond facet for an alternate executor).

## Verdict
**The on-chain validity-proof gate is clean and correctly wired:** zkSync releases L1 funds only for
withdrawals Merkle-proven inside a batch that was *executed*, which requires the batch to have been
*validity-proven* by `verifier.verify` (revert-on-false), with the proof's public input bound to the
exact committed state transition. This is the corpus's first **cryptographic** (rather than social or
in-protocol-re-execution) conservation floor — withdrawal safety needs no honest-majority. **The
conservation guarantee bottoms out on circuit soundness + verifier correctness + the governance
ceiling, which I record as irreducible/residual trusts, not as cleared.** Nothing exploitable found in
what is auditable here; nothing to disclose. Honest bottom line: zkSync's L1 contracts correctly
*check the receipt*; whether the *receipt-printing machine* (the circuit) is itself sound is the
trust you cannot read from Solidity.
