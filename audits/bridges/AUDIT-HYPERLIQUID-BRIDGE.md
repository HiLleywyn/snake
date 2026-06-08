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
- **No *signature* double-count — but uniqueness of the *set* is delegated off-chain (CORRECTED, see note):**
  the ordered merge advances `signatureIdx` *only* on a match (`:446`) and visits each validator **index** once
  (`:436`), so a single **signature blob** is consumed once and a single **index** is counted once. **However —
  and this is a correction to this entry's first version — that is *not* the same as "each key's power is added
  once."** If the active validator *set* contains a **duplicate address** (`[A, A, B]`), key A can produce **two
  distinct valid ECDSA signatures** (different nonces) and have its power counted at **both** positions 0 and 1,
  inflating quorum from one physical key. The contract does **not** enforce set-uniqueness on-chain — it is
  **explicitly delegated to the L1 side** (`Bridge2.sol:147`: *"The uniqueness of the validators is enforced on
  the L1 side"*). So the anti-double-count property holds **only under the unique-set precondition**, which the
  contract assumes but does not check. *(See the correction note below — an external report correctly flagged
  this; my original "a validator's power added once" over-claimed by omitting the unique-set qualifier.)*

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
>2/3 stake-weighted, checkpoint-pinned, replay-protected, *signature*-double-count-safe (but set-uniqueness-
delegated-off-chain — see correction) validator quorum plus an
optimistic dispute window with cold-wallet invalidation and locker-pause fraud response — a sound
optimistic-bridge, and a cross-chain re-derivation of the MonadBFT supermajority bound. **The
conservation core (HyperCore/HyperBFT) is closed-source and is recorded as an irreducible Bucket-6b
trust, not as "safe."** Nothing exploitable found in what is auditable; nothing to disclose. The
honest bottom line: on Hyperliquid you can verify *the lock on the vault door*, but not *the
ledger inside the vault*. Next pulls (if source ever opens): HyperCore clearinghouse conservation and
the HyperEVM CoreWriter precompile seam.

---

## Correction & severity calibration — the duplicate-validator-set / quorum-inflation finding (external report, re-verified)

An external audit report flagged a **quorum-inflation** path I had under-specified: because `checkValidatorSignatures`
accumulates power **per validator-array position** and consumes signatures positionally (no signer-uniqueness or
strictly-increasing-*signer* check), a checkpointed validator set with a **duplicate address** lets a single physical
key reach quorum by signing multiple times. I re-read the actual source (`Bridge2.sol:419-457, 490-521, 147`) on the
explicit premise that **I might be wrong**, and the report's mechanism is **correct** — and it corrects my original
"a validator's power added once" claim (accurate only for a *unique* set). Credit to the report; the discipline it
applied to my work is the discipline this corpus is built on (`../methodology/AUDIT-REASONER-EPISTEMOLOGY.md`).

**What is confirmed (read from source):**
- `checkValidatorSignatures` (`:436-450`): positional two-pointer merge. `signatureIdx` advances **only on a match**,
  so a single **signature blob** can't be replayed within one call, and each **index** is counted once — *but* a
  **duplicate address across two indices** + two **distinct** valid signatures from that key counts its power twice.
  For `[A,A,B]` powers `[40,40,20]`, key A alone reaches `cumulativePower = 80 → 3·80 > 2·100`. **Mechanism: real.**
- Uniqueness is **not enforced on-chain** — explicitly delegated: `:147` *"The uniqueness of the validators is enforced
  on the L1 side."* This is a *conscious* trust-boundary decision, not an unknown bug.

**Severity calibration (where I differ from the report's High→Critical framing, and where I agree):**
- The malicious/duplicate set can only be **checkpointed** via `updateValidatorSetInner`, which is **itself
  >2/3-quorum-gated** (`:521` calls `checkValidatorSignatures` against the *current* set). So a duplicate set requires
  **either** (a) the current **honest** validators to sign it — i.e. an **off-chain generator bug** emitting a duplicate
  set with **>2/3 of power concentrated on one bridge key** (a specific bug), **or** (b) a **>2/3 validator compromise**
  — in which case the bridge is already fully drainable and the duplicate trick is moot.
- Therefore the standalone-contract severity is **latent / defense-in-depth (Medium)**, *escalating to Critical only if*
  a duplicate set was ever actually checkpointed on-chain, or the upstream L1→bridge-signer mapping is shown able to
  emit a concentrated-power duplicate. The report's own severity hedge says exactly this — that part is well-calibrated;
  the headline "High" slightly over-weights a path gated by the honest quorum + a documented off-chain invariant.
- **The principle the report gets exactly right (and `../../DESIGN-PRINCIPLES.md` preaches):** *a security-critical
  invariant must be enforced at the contract boundary, never delegated to an upstream pipeline.* The on-chain check
  should reject duplicates (and `address(0)`) **regardless** of off-chain promises — cheap (`O(n²)` over a small set),
  and it removes the entire class. **Recommended remediation stands: enforce hot/cold address uniqueness + non-zero in
  `updateValidatorSetInner` before hashing/committing.**

**Verification that would settle latent-vs-live (passive, defensive):** decode the `address[]` hot/cold arrays from every
historical `updateValidatorSet` / `emergencyUnlock` calldata to `0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7` and check
`len(arr) != len(set(arr))`. If a duplicate was **ever** checkpointed, this is a **live Critical** → per posture, that
finding is **stopped-and-notified privately to Hyperliquid**, not published. I could not run that on-chain query here
(no confirmed Arbiscan API access in this environment); it is the correct and only step that distinguishes the two.

**Net:** a genuine defense-in-depth weakness, correctly identified, that **also caught a real over-claim in my prior
audit** — logged here transparently. Standalone severity *Medium* (latent), *Critical-iff* a duplicate set is found in
history. The single bridge finding-class of the corpus (off-chain-trusted validator generation) now has a concrete,
named mechanism on Hyperliquid.

### VERIFIED on-chain (full history, public Arbitrum RPC) — the finding is LATENT, not live

The settling step was **run** against the live chain (`arb1.arbitrum.io/rpc`, read-only, no API key — discovered
the update txs via `RequestedValidatorSetUpdate` + `FinalizedValidatorSetUpdate` logs, then decoded each
`updateValidatorSet`/`emergencyUnlock` calldata and the **genesis constructor** args):

- **11 distinct validator-set transactions = the bridge's entire history.** Genesis set: **1 validator** (launch),
  unique. Every subsequent set (5 `update` requests, 4 `emergencyUnlock`, 2 finalized-via-their-request): **4 hot /
  4 cold, all unique** — **zero duplicate addresses, zero `address(0)`, across the whole history.**
- **Result: no duplicate set was *ever* checkpointed.** The duplicate-validator quorum-inflation path was **never
  realized on-chain** — Hyperliquid's off-chain generation has always produced unique sets, exactly as
  `Bridge2.sol:147` ("enforced on the L1 side") promises.

**Final disposition:** the finding is a genuine **defense-in-depth weakness** (the on-chain check *should* enforce
uniqueness regardless of off-chain promises — `../../DESIGN-PRINCIPLES.md`), confirmed **LATENT** — it did *not*
escalate to live Critical, so nothing required private disclosure of a live exploit; the recommended hardening
(`requireUniqueAddresses` + non-zero) stands as public defense-in-depth. Verified read-only; no exploit, no tx sent.
