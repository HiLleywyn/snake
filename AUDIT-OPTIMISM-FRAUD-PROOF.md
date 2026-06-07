# Optimism (OP) — optimistic-rollup fraud-proof withdrawal audit (clean gating; FPVM stated as irreducible)

**Target:** `ethereum-optimism/optimism`, cloned `/tmp/op` (sparse: `contracts-bedrock/src/L1` +
`/dispute`). The L1 withdrawal seam of an **optimistic (fraud-proof) rollup** —
`OptimismPortal2.sol` + `AnchorStateRegistry.sol` + the `FaultDisputeGame`. **Posture:** defensive;
no exploit, no PoC. **Result: the on-chain fraud-proof withdrawal gate is correctly wired (clean);
the conservation guarantee rests on the fault-proof VM (Cannon) + a live honest challenger + the
governance ceiling, which are stated as the irreducible trusts — nothing to disclose.**

Chosen deliberately as the **complement to the zkSync audit** (`AUDIT-ZKSYNC-VALIDITY-PROOF.md`): same
withdrawal-seam problem (release L1 funds for an L2 burn), **opposite trust model**. zkSync proves the
output *valid* (a SNARK); Optimism assumes it valid *unless someone proves it fraudulent* within a
challenge window. Auditing both completes the rollup-trust taxonomy and lets me place the third model
(Hyperliquid's multisig+dispute, `AUDIT-HYPERLIQUID-BRIDGE.md`) precisely.

## The withdrawal gate — prove, wait, and the dispute game must have resolved DEFENDER_WINS
Two-step withdrawal, both in `OptimismPortal2.sol`:
1. **Prove** (`proveWithdrawalTransaction`, `:368-462`): the user supplies a withdrawal that is
   Merkle-proven (`OptimismPortal_InvalidMerkleProof :455`) against an **output root** committed by a
   specific `disputeGameProxy`, with the game registered/respected (`ImproperDisputeGame :394`,
   `InvalidDisputeGame :399/404`) and an output-root proof check (`InvalidOutputRootProof :427`).
   Records `provenWithdrawals[hash][msg.sender] = {timestamp, disputeGameProxy}`.
2. **Finalize** gate — `checkWithdrawal` (`:620-654`), the load-bearing check:
   - not already finalized (`AlreadyFinalized :626`, replay protection);
   - proven (`Unproven :633`);
   - proof timestamp strictly after the game's `createdAt` (`InvalidProofTimestamp :641` — sanity);
   - **challenge window elapsed:** `block.timestamp - provenWithdrawal.timestamp >
     PROOF_MATURITY_DELAY_SECONDS` (`ProofNotOldEnough :646`);
   - **`anchorStateRegistry.isGameClaimValid(disputeGameProxy)`** or `InvalidRootClaim :651`.

`isGameClaimValid` (`AnchorStateRegistry.sol:320-342`) is the heart of the optimistic floor:
```
isGameProper(_game)      // registered by factory, NOT blacklisted (:282), NOT retired (:287)
&& isGameRespected(_game) // the currently-recognized game type
&& isGameFinalized(_game) // resolvedAt != 0 AND block.timestamp - resolvedAt > DISPUTE_GAME_FINALITY_DELAY (:310)
&& _game.status() == GameStatus.DEFENDER_WINS  // (:337) — the proposed output root survived the game
```
So: **L1 funds are released only for a withdrawal Merkle-proven against an output root whose
FaultDisputeGame resolved `DEFENDER_WINS`** — i.e. nobody successfully proved the root fraudulent in
the bisection game — **and** the game is the respected, non-blacklisted, non-retired type, **and**
both the proof-maturity delay and the post-resolution finality air-gap have passed. **enforced (the
gating is correctly wired).**

## The three settlement-seam trust models — the taxonomy this completes
| Model | Output trusted because… | Honesty assumption for *safety* | Irreducible oracle |
|---|---|---|---|
| **zkSync** (validity proof) | a SNARK proves it valid | **0-of-N** — cryptographic | the ZK circuit |
| **Optimism** (fraud proof) | nobody disproved it in the window | **1-of-N honest watcher** + L1 liveness | the FPVM (Cannon) single-step proof |
| **Hyperliquid** (multisig + dispute) | ≥2/3 validators signed it | **>2/3 honest stake** + watchers | the closed L1 + validators |
This is the cleanest spectrum in the corpus, and exactly the §9-equivalence / Bucket-2-vs-Bucket-6
distinction the methodology was built to surface. Optimism sits in the middle: stronger than a
multisig (any *single* honest party can stop a theft, vs needing 1/3 of stake to be honest), weaker
than a validity proof (it needs that honest party to actually *be watching and able to transact* on L1
during the window — a liveness/censorship assumption a SNARK doesn't need).

## The irreducible trusts (stated plainly — what the Solidity does NOT prove)
The contracts prove the *gating* is sound (no finalize without a `DEFENDER_WINS`, finalized, respected
game + elapsed delays). They do **not** establish, and cannot:
1. **FPVM (Cannon) soundness.** The fault dispute game bisects a disputed output down to a single
   MIPS instruction, then `step()` adjudicates it on-chain by re-executing that one instruction in the
   on-chain FPVM. If the FPVM mis-models the off-chain client even once, the *wrong* side can win the
   game with a passing on-chain check. This is the deep irreducible trust — the **exact analog of
   zkSync's circuit**: both rollups bottom out on an on-chain oracle of off-chain-execution-
   correctness (a STARK/SNARK circuit there, a single-step MIPS proof here). Not audited here.
2. **Live honest challenger + L1 liveness.** Fraud-proof safety is vacuous if no honest party
   challenges a bad root within the window, or if the challenger is censored on L1 during it. A
   *social/liveness* assumption, unlike zkSync's purely cryptographic one.
3. **Governance ceiling.** The Guardian can **blacklist games**, **retire** game types, and the
   **respected game type** can be changed; the system is upgradeable. So — like every seam in the
   corpus — *who controls the dispute machinery* is the ceiling (cf. `AUDIT-GOVERNANCE-CEILING.md`).
   The blacklist/retire hooks are a deliberate safety valve **and** a trust surface.

## Connections to the corpus
- **Completes the rollup pair** with zkSync: validity vs fraud proof, the cryptographic-vs-liveness
  contrast made concrete in two real codebases.
- **Dispute-window shape = Hyperliquid.** Prove → window → finalize, with a fraud/invalidation path
  during the window. Optimism's "fraud proof game" is a richer (interactive bisection) version of
  Hyperliquid's "validators invalidate / lockers pause."
- **Air-gap + blacklist = defense-in-depth.** The post-resolution `DISPUTE_GAME_FINALITY_DELAY` plus
  the Guardian blacklist are belt-and-suspenders over the game result — the same "halt rather than
  let a bad state settle" philosophy verified in MonadBFT/Sui (`AUDIT-MEMECORE-POSA.md`'s positive
  inverse).
- **Replay/maturity guards** mirror every settlement contract audited (Avalanche, Hyperliquid,
  zkSync): per-hash finalized flag + a strict time delay.

## What this audit did NOT cover (coverage honesty)
- **`FaultDisputeGame.sol` internals** — the bisection clock, bond mechanics, and `resolve()` logic
  that *set* `DEFENDER_WINS`/`CHALLENGER_WINS`; I verified the Portal *consumes* the result
  correctly, not that the game *computes* it correctly. The game's resolution correctness is a major
  residual.
- **Cannon / the FPVM `step()`** — the MIPS single-step proof; the deepest irreducible trust, not
  opened.
- **Output-root proof internals** (`Hashing.hashOutputRootProof`, the `_outputRootProof` check at
  `:427`) — read at the revert level.
- **Interop / Super games** (`SuperFaultDisputeGame`, the `_isUsingInterop` finalize path `:474-509`)
  and the ETHLockbox value-source — noted not opened.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I traced the real dependency: finalize → `checkWithdrawal` →
  (proof maturity delay) AND `isGameClaimValid` → (`isGameProper` ∧ `isGameRespected` ∧
  `isGameFinalized` ∧ `status == DEFENDER_WINS`), and confirmed `isGameFinalized` enforces the
  post-resolution air-gap (`> DISPUTE_GAME_FINALITY_DELAY_SECONDS`, `:310`), not just `resolvedAt != 0`.
  So a withdrawal genuinely cannot finalize on a game that lost or is still contestable.
- **Exposure to reversal.** I am explicitly **not** clearing FPVM/game-resolution soundness — marked
  irreducible/residual. The gating verdict would flip if a finalize path existed that bypassed
  `checkWithdrawal` (I read the `finalizeWithdrawalTransactionExternalProof` path at `:542-575` which
  sets `finalizedWithdrawals` *after* the checks; I did not exhaustively prove no other ETH-releasing
  entry exists) or if `isGameClaimValid` could return true for a `CHALLENGER_WINS` game (the explicit
  `== DEFENDER_WINS` makes that false). Stated as bounded reads.

## Verdict
**The on-chain fraud-proof withdrawal gate is clean and correctly wired:** Optimism releases L1 funds
only for withdrawals Merkle-proven against an output root whose FaultDisputeGame resolved
`DEFENDER_WINS`, is the respected/non-blacklisted/non-retired type, and cleared both the proof-maturity
delay and the post-resolution finality air-gap. Together with zkSync and Hyperliquid this fixes the
corpus's **settlement-seam trust spectrum: validity proof (0-of-N, cryptographic) → fraud proof
(1-of-N honest watcher + L1 liveness) → multisig+dispute (>2/3 honest stake).** **The conservation
guarantee bottoms out on the FPVM (Cannon) soundness + a live honest challenger + the Guardian
governance ceiling, which I record as irreducible/residual trusts, not as cleared.** Nothing
exploitable found in what is auditable here; nothing to disclose. Honest bottom line: Optimism's
Portal correctly *honors the verdict of the dispute game*; whether the *court* (the FPVM) judges
correctly, and whether *someone shows up to prosecute* (the honest challenger), are the trusts you
can't read from the Portal.
