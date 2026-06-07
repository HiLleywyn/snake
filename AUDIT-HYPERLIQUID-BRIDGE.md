# Hyperliquid (HYPE) — auditability floor + Bridge2 settlement-seam audit (clean, with stated irreducible trust)

**Targets:** `hyperliquid-dex/node` (cloned `/tmp/hl` — operational tooling, **no core source**) and
`hyperliquid-dex/contracts` (cloned `/tmp/hlc` — `Bridge2.sol`, the **open-source** Arbitrum
settlement contract, 842 LoC). On-chain: Bridge2 at `0x2df1c51e09aecf9cacb7bc98cb1742757f163df7`
(Arbitrum One). Top-perps L1. **Posture:** defensive; no exploit, no PoC. **Result: the open
settlement seam is clean; the conservation *core* is closed-source and therefore an explicitly
stated irreducible trust — nothing to disclose.**

Chosen as a standout because Hyperliquid is the corpus's clearest **split-auditability** case: the
*enforcing* core (HyperCore matching engine + HyperBFT consensus) ships only as **signed binaries**
(closed), while the *custody/settlement* seam — where the actual USDC lives — is **open Solidity**.
This is the inverse of the usual "open client, closed enforcing program" auditability-floor pattern
(`AUDIT-GOVERNANCE-CEILING.md`, the TradePort/DefiApp closed-source notes): here the **money custody
is open even though the matching/consensus is closed.** Worth mapping precisely.

## The auditability floor (Bucket 4 / governance) — what is and isn't verifiable
| Component | Source | Auditable? |
|---|---|---|
| HyperCore (matching/clearing engine, USD balances) | signed binary only (`hl-node`, GPG-verified `pub_key.asc`) | **No** — closed |
| HyperBFT (consensus) | signed binary only | **No** — closed |
| HyperEVM (general EVM) | on-chain bytecode | Partially (bytecode, not source) |
| **Bridge2** (USDC custody + withdrawals, Arbitrum) | **open Solidity** (`Bridge2.sol`) | **Yes** |
| ABCI state snapshots / info API | published format (`translate-abci-state`, `clearinghouseState`) | observable, not enforcing |
The node repo (`/tmp/hl`) is Dockerfile + pruner + GPG key — confirmed **no core logic**. So the
deepest conservation question ("does HyperCore conserve USD across trades, funding, liquidations?")
**cannot be audited from source** — it is the irreducible trust (Bucket 6b). What *can* be audited is
the seam where value crosses between Arbitrum and HyperCore: Bridge2.

## Bridge2 — the settlement seam (open, and sound) — Bucket 6 (irreducible-ish), enforced
The bridge custodies USDC on Arbitrum; HyperCore credits/debits off-chain; the contract releases
USDC only on **>2/3 stake-weighted validator signatures** plus a **dispute window**.

### The conservation gate — `checkValidatorSignatures` (`Bridge2.sol:419-457`)
- **Checkpoint pinning:** `makeValidatorSetHash(activeValidatorSet) == validatorSetHash` (`:425-428`)
  — the supplied validators+powers must hash to the on-chain checkpoint; you can't substitute a fake
  set.
- **>2/3 stake quorum:** walks validators in order, recovers each signer, accumulates `power`, and
  requires `3 * cumulativePower > 2 * totalValidatorPower` (`:442`, re-asserted `:453-456`). **Same
  BFT bound as MonadBFT** (`AUDIT-MONADBFT-CONSENSUS.md`: `total_stake*2/3+1`) — a cross-chain
  re-derivation of the supermajority quorum, here as the bridge-release condition.
- **No double-count:** the ordered merge advances `signatureIdx` *only* on a match (`:446`), and each
  validator index is visited once (`:436`), so a signature is consumed once and a validator's power
  added once — the same anti-double-count property I verified in MonadBFT's `DuplicateValidator`
  guard and Avalanche's sorted-unique inputs. (Requires signatures supplied in validator-set order;
  that's the implicit precondition, satisfied by the honest signer.)

### Replay & lifecycle guards
- **Domain-separated messages:** `makeMessage` binds `domainSeparator` (chain-id) (`:590`) → no
  cross-chain replay; `checkMessageNotUsed` marks `usedMessages[message]` (`:459-462`) for
  config/invalidate ops; withdrawals dedup via `requestedWithdrawals[message]` + per-withdrawal
  `nonce` (`:302-305`).
- **Dispute window before release:** `finalizeWithdrawal` (`:338-374`) releases USDC
  (`usdcToken.safeTransfer`, `:366`) **only after** `getDisputePeriodErrorCode(...) == 0` (`:355-363`)
  — both wall-clock (`block.timestamp > time + disputePeriodSeconds`) *and* L1-block-count elapsed.
- **Double-finalize guard:** `finalizedWithdrawals[message]` set before transfer (`:344-347`, `:365`)
  — checks-effects-then-interaction, plus `nonReentrant whenNotPaused` on every external entry.
- **Fraud response (the optimistic-bridge safety net):** during the dispute window, cold-wallet 2/3
  validators can `invalidateWithdrawals` (`:676-693`, marks `withdrawalsInvalidated`), and **lockers**
  can emergency-`_pause()` the bridge once `lockersVotingLock.length >= lockerThreshold`
  (`:726-728`, `:750-751`). So a withdrawal that doesn't match real L1 state can be frozen and voided
  before any USDC moves.
- **Privileged config** (dispute period, block duration, locker threshold, validator-set update) all
  require **cold-validator 2/3 signatures + replay-guarded messages** (`:659-730`, `:466-521`) — no
  unilateral admin key on these.

## The irreducible trust (stated plainly — "no cap")
Bridge2 verifies that **2/3 of validators signed a withdrawal**, and gives a window to challenge it.
It does **not** — and structurally **cannot** — verify that the signed withdrawal corresponds to a
real debit inside HyperCore, because HyperCore's balance state lives off the Arbitrum chain in the
closed L1. The on-chain invariant `bridge USDC reserve ≥ Σ legitimate HyperCore USD` is **not
independently checkable from any open source.** The mitigations are real but social/optimistic:
(a) >2/3 of stake must be honest (the BFT assumption), and (b) the dispute window + locker pause give
honest validators time to void a fraudulent withdrawal. **This is a Bucket-6b irreducible seam** — the
same class as Avalanche's atomic shared-memory (`AUDIT-AVALANCHE-AVM.md`) and the Canton/Splice
settlement seam (`AUDIT-CANTON-SPLICE.md`), but sharper here because the *core conservation engine
itself is closed.* I am not claiming HyperCore conserves value; I am claiming the **bridge that
guards the only USDC exit is correctly gated** by a supermajority + dispute mechanism.

## Connections to the corpus
- **Quorum = MonadBFT.** `3*cumulativePower > 2*totalValidatorPower` is the same >2/3 stake bound,
  re-derived as a Solidity bridge gate rather than a consensus vote rule.
- **Anti-double-count = MonadBFT/Avalanche.** Ordered single-pass over a checkpointed set.
- **Optimistic dispute window = settlement-seam family.** Request → window → finalize, with
  invalidate/pause as the fraud path — the canonical optimistic-bridge shape.
- **Auditability floor, inverted.** Prior closed-source notes (TradePort, DefiApp) had open
  client/closed program; Hyperliquid has **closed core / open custody** — I could read the exact code
  holding the money, but not the code deciding who's owed it.

## What this audit did NOT / could NOT cover (coverage honesty)
- **HyperCore conservation** (trades, funding, liquidations, the perps clearinghouse math) — closed
  source; the central question, unauditable from source. **Stated as irreducible trust, not cleared.**
- **HyperBFT consensus safety/liveness** — closed; cf. the open MonadBFT analysis as the nearest
  legible analog, but Hyperliquid's is not verifiable.
- **HyperEVM precompiles / CoreWriter** (the HyperEVM↔HyperCore action bridge) — on-chain bytecode,
  not read here; a real residual surface (read-precompiles into closed core state).
- **`recoverSigner`/`Signature.sol` ecrecover details** and the validator-set update transition —
  read at interface; the ecrecover malleability/zero-address guard is the deepest residual in the
  open contract.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I confirmed the quorum arithmetic is strictly `>2/3`
  (`3*cum > 2*total`, not `≥`), that USDC transfer is gated behind *both* the dispute-period check and
  the `finalizedWithdrawals` flag, and that the validator set is checkpoint-pinned by hash before any
  signature is trusted. I verified the node repo contains no core source rather than assuming "closed."
- **Exposure to reversal.** The *open-contract* verdict flips if: ecrecover can be coerced to return a
  validator address from a crafted signature (malleability / `s`-value / zero-address — not opened
  here), or if the ordered-merge loop can be made to count one signature for two validators (I argued
  it can't, given distinct validators and single-advance). The *core* verdict is not a verdict — it's
  an explicit "unauditable, trusted" marking, which is itself the honest finding.

## Verdict
**The open settlement seam is clean and well-constructed:** Bridge2 gates every USDC exit behind a
>2/3 stake-weighted, checkpoint-pinned, replay-protected, double-count-safe validator quorum plus an
optimistic dispute window with cold-wallet invalidation and locker-pause fraud response — a sound
optimistic-bridge, and a cross-chain re-derivation of the MonadBFT supermajority bound. **The
conservation core (HyperCore/HyperBFT) is closed-source and is recorded as an irreducible Bucket-6b
trust, not as "safe."** Nothing exploitable found in what is auditable; nothing to disclose. The
honest bottom line: on Hyperliquid you can verify *the lock on the vault door*, but not *the
ledger inside the vault*. Next pulls (if source ever opens): HyperCore clearinghouse conservation and
the HyperEVM CoreWriter precompile seam.
