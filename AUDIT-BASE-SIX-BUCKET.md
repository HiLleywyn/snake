# Base — Six-Bucket Trust Audit (OP Stack optimistic rollup, L1 settlement contracts)

**Target:** Base (Coinbase L2). Base ships no standalone consensus code — it runs
`op-node` + `op-geth` and inherits its trust-critical surface from the **OP Stack**.
Reviewed: `ethereum-optimism/optimism`, cloned `/tmp/optimism`, HEAD `dfea9e0`,
`packages/contracts-bedrock/src/{L1,dispute}`.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. Verdicts say "enforced by
constraint X" / "deterministically derived at Y" / "not enforced in reviewed path" /
"unclear, needs human review" — never bare "safe."

Base is the first **optimistic rollup** in the series, and it is the cleanest possible
test of the methodology's §9 generalization (*name the equivalence and who discharges
it*). An optimistic rollup discharges its core equivalence — "the L2 output root equals
the true result of executing L2" — by a mechanism distinct from every prior target:
**a fault proof inside a challenge window, backstopped by a governance Guardian.** Not a
validity proof (zk), not consensus re-execution (Aleo/Sui), not a commitment sum (MWEB) —
an *interactive dispute* whose silence-implies-truth default is the whole design.

---

## The centerpiece: the L2→L1 withdrawal settlement seam (Bucket 6)

This is where value leaves L2 and where the entire optimistic trust model is concentrated.
A withdrawal is **prove → wait → finalize**, and finalize is gated by `checkWithdrawal`
(`OptimismPortal2.sol:620`), which is the 6b discharge in five conditions:

```solidity
checkWithdrawal:
  finalizedWithdrawals[h] == false                       // :626 replay protection
  provenWithdrawal.timestamp != 0                         // :633 must be proven
  provenWithdrawal.timestamp > disputeGame.createdAt()    // :641 anti-same-block sanity
  block.timestamp - provenWithdrawal.timestamp > PROOF_MATURITY_DELAY_SECONDS  // :646 air-gap #1
  anchorStateRegistry.isGameClaimValid(disputeGameProxy)  // :651 the real gate
```

And `isGameClaimValid` (`AnchorStateRegistry.sol:320`) is itself a four-part conjunction:

```solidity
isGameProper(game)      // registered in factory + not blacklisted + not retired + not paused (:275)
&& isGameRespected(game)   // correct (respected) game type (:327)
&& isGameFinalized(game)   // resolved AND past DISPUTE_GAME_FINALITY_DELAY_SECONDS air-gap #2 (:302)
&& game.status() == DEFENDER_WINS   // the proposer's output root was not disproven (:337)
```

**The single most important line in the whole audit is a comment, not code**
(`AnchorStateRegistry.sol:262`):

> **"DO NOT USE THIS FUNCTION ALONE TO DETERMINE IF A ROOT CLAIM IS VALID. The root
> claim of a proper game CAN BE incorrect and still be a proper game."**

The OP Stack team itself names the exact 6b residue this methodology is built around:
**"not disproven" is not "true."** `isGameClaimValid` is the careful composition that
layers *respected + finalized + defender-wins* on top of *proper* to climb from
"not-invalidated" toward "valid" — and even then validity rests on an assumption outside
the contract (an honest challenger existed and the window was long enough). **enforced
gate; the residual equivalence is named and irreducible.**

---

## How `DEFENDER_WINS` is produced: the fault proof (Bucket 2 — witnessed computation)

`DEFENDER_WINS` is the output of `FaultDisputeGame`, a bisection game. Challenger and
defender `attack`/`defend` (`:564`/`:573`) down a binary tree (`move`, `:447`), each move
on a chess clock (`MAX_CLOCK_DURATION`, `:497` — a party that runs out of time loses,
guaranteeing liveness). Bisection narrows a multi-million-step L2 state transition to a
**single instruction**, then `step` settles it on-chain (`:362`):

```solidity
// prestate must be the preimage of the disputed prestate claim hash:
if (keccak256(_stateData) << 8 != preStateClaim.raw() << 8) revert InvalidPrestate();  // :413
// execute ONE MIPS instruction on-chain and compare to the claimed poststate:
bool validStep = vm().step(_stateData, _proof, uuid.raw()) == postState.claim.raw();    // :430
if (parentPostAgree == validStep) revert ValidStep();                                  // :432
```

This is the ground truth: a single deterministic MIPS instruction (the Cannon FPVM) is
re-executed on L1 over a **preimage-checked** prestate, and the result either matches or
contradicts the disputed claim. The entire bisection exists to make the L2 STF cheap
enough to settle one instruction on L1. **enforced — the witnessed computation is a
preimage-bound, deterministic on-chain VM step.** The equivalence "output root ≡ honest L2
execution" is discharged by: *if anyone disagrees, they can force L1 to re-execute the
disputed instruction* — under the standing assumption that at least one honest party
challenges within the window.

---

## Bucket 1 — Conservation (the ETHLockbox anchor)

The conservation root is `ETHLockbox`. ETH is **locked on deposit** and **unlocked on
finalized withdrawal**, both gated to authorized portals:

```solidity
function lockETH()   { ... if (!authorizedPortals[sender]) revert ETHLockbox_Unauthorized(); }  // :143-146
function unlockETH() { ... if (!authorizedPortals[sender]) revert ETHLockbox_Unauthorized(); }  // :156-162
```

`unlockETH` is reachable only from `finalizeWithdrawalTransactionExternalProof`
(`OptimismPortal2.sol:579`), which is downstream of `checkWithdrawal`. So ETH leaves the
lockbox **only for a withdrawal whose dispute game resolved valid** — invariant: locked
balance = Σ deposits − Σ finalized withdrawals, with unlock gated by the fault proof.
The deposit side burns L1 ETH into the lockbox and mints on L2 via the derived deposit
transaction (`depositTransaction`, `:667`); the withdrawal side is the inverse. **enforced
by constraint** (authorized-portal gate + game-validity gate).

*Cross-chain conservation seam (interop):* the lockbox is **shared** —
`authorizedPortals` is a mapping, so multiple chains' portals can draw on one ETH pool.
This makes ETH fungible across a Superchain interop set: one chain's invalid withdrawal
would drain shared liquidity. It is bounded by (a) the same per-withdrawal game-validity
gate and (b) the `ProxyAdmin owner` controlling which portals are authorized and lockbox
migration (`migrateLiquidity`/`migrateToSharedDisputeGame`, `:479`/`:503`). **trust-boundary
debt** — cross-chain ETH conservation rests on every sharing chain's fault proof being
sound, not just one's.

---

## Bucket 3 — Dual representations

- **L2 output root / Super Root ↔ L2 state.** The output root is the compressed L1-visible
  commitment to L2 state; its equivalence to actual L2 state is exactly the fault-proof
  subject above. The contract supports two encodings (Output Roots and Super Roots) and
  can migrate between them (`migrateToSharedDisputeGame`, `:503`) — a representation switch
  that requires a new `AnchorStateRegistry` (`:523`).
- **L1 address ↔ aliased L2 address.** A contract depositor's address is aliased via
  `AddressAliasHelper.applyL1ToL2Alias` (`:710`) so L1 and L2 senders can't collide — the
  classic dual-representation guard. **enforced.**
- **Withdrawal/deposit hashing.** `Hashing.hashWithdrawal(_tx)` (`:569`) is the canonical
  identity bridging the L2-emitted withdrawal and the L1 finalization; replay protection
  keys off it (`finalizedWithdrawals[withdrawalHash]`, `:575`). **enforced.**

---

## Bucket 4 — Dependency / fork & version lineage

This is where the "rollup as an evolving, governed system" shows up:

- **Game-type lineage.** `respectedGameType` (`AnchorStateRegistry.sol:49`) selects which
  dispute-game *implementation* is authoritative. `isGameRetired` invalidates every game
  created at/before `retirementTimestamp` (`:248`) — the mechanism to discard all games
  built on a buggy game implementation in one stroke. `isGameProper` deliberately *stopped*
  checking game type (documented at `:267`) and moved that check into `isGameClaimValid`,
  so a non-respected game can still be "proper" (not-invalidated) without being claim-valid.
  This is careful lineage hygiene. **enforced.**
- **Blacklist.** `blacklistDisputeGame` (`:174`) lets the Guardian invalidate one specific
  game (e.g. one that resolved on a bad root). **enforced (Guardian-gated).**
- **Lockbox / interop migration.** `migrateToSharedDisputeGame` and `migrateLiquidity`
  (`:503`/`:479`) are `ProxyAdmin owner`-gated lineage transitions joining a chain to the
  interop set or swapping proof methods — with an explicit warning (`:495`) that
  non-atomic migration can strand ETH. **constraint debt** (operationally fragile, admin-gated).

---

## Bucket 5 — Arithmetic / bounds & call safety

- **Gas air-gaps as bounds.** Two independent time windows must elapse:
  `PROOF_MATURITY_DELAY_SECONDS` after proving (`:646`) and
  `DISPUTE_GAME_FINALITY_DELAY_SECONDS` after game resolution (`AnchorStateRegistry.sol:310`).
  Two separate clocks defend against proving-step bugs and resolution-edge bugs respectively.
- **`callWithMinGas`** (`OptimismPortal2.sol:592`) guarantees the target gets at least the
  user-specified gas and can't grief via large returndata — bounds on the cross-domain call.
- **Deposit bounds:** `minimumGasLimit` floor (`:695`) and 120 kB calldata cap (`:703`,
  to fit p2p block policy). **enforced.**
- **Reentrancy:** `l2Sender != DEFAULT_L2_SENDER` is a defacto reentrancy guard on finalize
  (`:559`), reset after the call (`:595`). **enforced.**

---

## Bucket 6 — Cross-layer settlement seams (the whole point)

- **6a (reducible): the L2-STF claim → on-chain instruction.** The bisection game *reduces*
  an unprovable-on-L1 claim (correct execution of millions of L2 steps) to a single
  on-chain VM step (`step`/`vm().step`, `:430`). This is the reducible part — and the OP
  Stack reduces it all the way to L1 re-execution, not a deferral to a later window. Within
  a started game, the equivalence is *discharged by execution*.
- **6b (irreducible): `DEFENDER_WINS` ⇒ root claim valid.** The inference from "the game
  resolved for the defender" to "the output root is the true L2 state" is **not closeable
  inside the contract** — the contract documents this itself (`:262`). It rests on three
  out-of-band assumptions:
  1. **Honest-challenger liveness** — at least one honest party watches and challenges a
     bad root within `MAX_CLOCK_DURATION`.
  2. **Adequate windows** — `PROOF_MATURITY_DELAY` + `DISPUTE_GAME_FINALITY_DELAY` are long
     enough for L1 censorship-resistance to guarantee a challenge lands.
  3. **VM/spec equivalence** — the Cannon MIPS FPVM faithfully implements the L2 STF
     (native execution ≡ on-chain VM), the same native↔circuit-style 6b seen in Mina/Aztec.
- **The governance backstop (the actual trust root).** Because 6b cannot be closed
  cryptographically, the OP Stack adds a permissioned backstop: the **Guardian**
  (`systemConfig.guardian()`) can `setRespectedGameType` (`:153`), `updateRetirementTimestamp`
  (`:163`), `blacklistDisputeGame` (`:174`), and (via `SuperchainConfig`) `pause` withdrawals
  (`:81`). The `ProxyAdmin owner` can upgrade implementations and migrate the lockbox. This
  is the "stage 1" rollup trust model: **Base's withdrawal safety is the fault proof's
  soundness OR the Guardian's honesty, whichever holds** — a deliberate, disclosed
  centralization anchor, not a defect. **trust-boundary debt (by design).**

This extends the §9 discharge table with a new, distinct row:

| System type | How the 6b equivalence is discharged |
|-------------|--------------------------------------|
| **Optimistic rollup (Base/OP Stack)** | output root assumed valid unless an **interactive fault proof disproves it within a challenge window**; backstopped by a **Guardian** who can blacklist/retire/pause |

Compared with the prior rows: zk bridges *prove* the equivalence (no window, no
honest-party assumption); committee bridges *sign* it; Aleo *re-executes* it. The
optimistic model is the only one whose default is **silence-implies-truth**, which is why
the entire design is windows + a kill switch.

---

## Summary table

| Bucket | Subject | Verdict |
|---|---|---|
| 1 | ETHLockbox conservation (lock on deposit / unlock on valid withdrawal) | **enforced** — authorized-portal gate + game-validity gate |
| 1 | Shared lockbox (interop) cross-chain ETH fungibility | **trust-boundary debt** — rests on every sharing chain's fault proof |
| 2 | Fault-proof VM `step` (preimage-bound, deterministic MIPS on L1) | **enforced** — witnessed on-chain re-execution; chess-clock liveness |
| 3 | Output/Super root ↔ L2 state; L1↔L2 address aliasing; withdrawal hashing | **enforced** (root↔state equivalence is the 6b subject) |
| 4 | Respected game type / retirement / blacklist / migration lineage | **enforced / constraint debt** — Guardian/admin-gated |
| 5 | Two air-gap windows, callWithMinGas, calldata/gas bounds, reentrancy guard | **enforced** |
| 6a | L2-STF claim → single on-chain instruction | **reduced** — discharged by L1 re-execution within a game |
| 6b | `DEFENDER_WINS` ⇒ valid root claim | **irreducible** — honest-challenger + windows + VM/spec equivalence; team-documented |
| 6b backstop | Guardian (blacklist/retire/pause/respected-type) + ProxyAdmin upgrades | **trust-boundary debt (by design)** — the actual trust root |

## What this audit did NOT cover (coverage honesty)

- The Cannon MIPS FPVM internals (`cannon/`) — read only at the `vm().step` contract; the
  native↔on-chain VM equivalence (6b assumption #3) was named, not verified.
- `op-node`/`op-geth` derivation pipeline (sequencer, batcher, output proposal) — Base's
  off-chain components; the audit is on the L1 settlement contracts only.
- The dispute game's full bisection-resolution accounting (`resolveClaim`, bond
  distribution via `DelayedWETH`) — read `step`/`move`/clock invariants, not the complete
  subgame resolution and bond math.
- L1CrossDomainMessenger / StandardBridge ERC-20 logic — read the ETH/portal core; the
  token-bridge layering on top was not traced.
- The actual Base mainnet parameter values and the identity/threshold of Base's specific
  Guardian and ProxyAdmin (Security Council multisig) — these are deployment config, not in
  this source tree.

## Nothing routed privately

No untrusted-input → unvalidated → value-moving path was found. Withdrawal value movement
is gated behind a proven withdrawal, two independent time air-gaps, a respected+finalized
dispute game resolved `DEFENDER_WINS`, and a not-blacklisted/not-retired/not-paused check;
ETH can only leave the lockbox through that gate. The irreducible residual (6b) — that
"defender wins" means "valid" only under honest-challenger liveness and VM/spec
equivalence, with a Guardian kill-switch as backstop — is the **disclosed, by-design**
trust model of a stage-1 optimistic rollup, and the OP Stack source documents the
"not-disproven ≠ true" gap in its own comments. There is nothing to disclose to a security
channel — only the architectural fact worth recording: **Base settles withdrawals on
silence-implies-truth, made safe by a challenge window and a governance kill-switch; its
trust root is "the fault proof is sound, or the Guardian is honest."**
