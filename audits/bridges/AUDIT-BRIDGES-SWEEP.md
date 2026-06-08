# Bridge sweep — the weak link, audited

Bridges are the corpus's **highest-risk category** (§4f settlement seam): every nine-figure hack lives
here — Ronin $625M, Poly $611M, Wormhole $325M, Nomad $190M, Harmony $100M. The MemeCore work and the
Meson note made the lens sharp, so this is a dedicated sweep. **The two questions that decide every
bridge's safety:**

> **(1) Who authorizes the mint/release?** (the trust model) · **(2) What does the mint check — a real
> proof, or a signed message?** (the verification). Plus: **mint == lock 1:1 + replay guard**, and **who
> can upgrade / pause / change the authorizer** (the governance ceiling).

**Posture:** defensive; no exploit; clone public source where available, characterize + name the trust
where not. Findings (if exploitable + live) → stopped-and-notified privately. The trust-model taxonomy
extends the §4f spectrum (`../methodology/AUDIT-CAPSTONE.md`).

### Bridge trust-model taxonomy (ranked by who you must trust, best → worst)
| Model | Trust | Examples (in this sweep) |
|---|---|---|
| **Light client / native proof** | cryptographic (verify the source chain's consensus/proof) | IBC, zkBridge, native rollup bridges |
| **HTLC atomic swap** | hash-lock + timelock (no free-mint authority) | Meson core / Express |
| **PoS validator set / separate chain** | >2/3 stake of a staked set | Axelar |
| **Oracle + relayer (separated)** | 2 independent parties must both be honest | LayerZero |
| **Optimistic / intent** | 1-of-N honest watcher + a fronting relayer's capital | Across, Hop |
| **External appointed committee (multisig)** | >threshold of an appointed signer set | **Wormhole (13/19)**, Hyperliquid Bridge2, Ronin |

The multisig committee is the most-hacked model (Ronin, Harmony, Hyperliquid-class). Light-client and
HTLC are the most trust-minimized. Most "bridges" are message-passing layers that *a token bridge sits
on top of* — the token bridge's mint trusts the messaging layer's authorizer.

---

## B1. Wormhole — Guardian multisig (13/19); robust, post-hack-hardened (clean contract; trust = the Guardians)
**Target:** `wormhole-foundation/wormhole`, `ethereum/contracts/{Messages,bridge/Bridge}.sol`. The
canonical **external-committee** bridge, and the one whose **$325M Feb-2022 hack was exactly a
signature-verification bypass** — so the guardian check is *the* thing to read. **Result: the on-chain
verification is robust and post-hack-hardened; the trust is cleanly the 19 Guardians.**

**Trust model:** a **VAA** (Verified Action Approval) signed by **≥13 of 19 Guardians** authorizes every
mint/release. The contract verifies the multisig; the irreducible trust is the Guardian set.

**Guardian signature verification (`Messages.sol verifyVMInternal`/`verifySignatures`) — every guard the
hack taught is present (with WARNING comments documenting why):**
1. **Hash binds body** (`:50-65`): `keccak(keccak(body)) == vm.hash` — a valid signed hash can't be
   paired with a different body (the body-swap class).
2. **Empty guardian-set rejected** (`:75-77`): `guardianSet.keys.length == 0 → "invalid guardian set"` —
   the exact "set falls to zero → quorum compromised" trap, explicitly guarded.
3. **>2/3 quorum** (`:90`, `quorum = (n*2/3)+1` `:216` → **13/19**): `signatures.length >= quorum`.
4. **ecrecover ≠ 0** (`:119`): `require(signatory != address(0))` — rejects the invalid-signature-returns-0
   trap (the heart of the original bypass class).
5. **Ascending guardian indices** (`:122`): `sig.guardianIndex > lastIndex` — no guardian double-counted.
6. **Bounds + per-guardian key match** (`:131,135`): `guardianIndex < guardianCount` and
   **`signatory == guardianSet.keys[sig.guardianIndex]`** — each signature must match the *specific real
   Guardian* at its index. So 13 distinct, real Guardians must have signed.

**Token bridge `_completeTransfer` (`Bridge.sol:588`) — mint/release is gated + replay-guarded:**
- **Replay guard:** `if (isTransferCompleted(vm.hash)) revert TransferAlreadyCompleted();
  setTransferCompleted(vm.hash)` (`:602-603`) — a VAA is redeemable **exactly once**.
- Mints the wrapped token (or releases the locked native) against the **guardian-verified VAA**, gated by
  the source **emitter registration** (`bridgeContracts[emitterChainId]` must equal the VAA emitter — so
  only the real source token-bridge can authorize a mint), and `notPaused`.

**Verdict: the contract is clean and well-hardened** — the verification has every guard, the post-hack
WARNING comments show the lessons were internalized, mint==release with a one-time replay guard and
emitter registration. **Residual (the irreducible trust): the 19 Guardians.** A **≥7-of-19 (>1/3)
Guardian compromise forges any VAA → mints anything → drains everything** — the canonical multisig-bridge
risk, identical class to Ronin/Hyperliquid, mitigated only by *who the Guardians are* (reputable
entities, distributed keys) and the guardian-set governance (itself guardian-signed). The code can't fix
that; it's the model. **No finding** in the contract; the trust is named and it's the Guardians.

---

## B2. LayerZero v2 — configurable DVN set (oracle+relayer, generalized); clean lib, trust = the app's DVN choice
**Target:** `LayerZero-Labs/LayerZero-v2`, `messagelib/contracts/uln/{UlnBase,ReceiveUlnBase}.sol` +
`uln302/ReceiveUln302.sol`. LayerZero is the **oracle+relayer** archetype, generalized in v2 into a set
of **DVNs** (Decentralized Verifier Networks). **Result: the verification library is clean and well-
constructed; the irreducible trust is per-application — *whichever DVN set the OApp configures.***

**Trust model (the key structural fact):** LayerZero v2 has **no single protocol-wide trust root.** Each
application (OApp) picks a `UlnConfig` (`UlnBase.sol:8`): a set of **required DVNs** (all must attest) +
**optional DVNs** with a **threshold** (M-of-N must attest), plus block `confirmations`. A message is
authorized only when **every required DVN AND the optional threshold** have independently signed the
exact payload hash. This is the v1 "oracle + relayer must both be honest" principle, made into an
M-of-N+required policy the app chooses.

**Verification path (read end-to-end, sound):**
1. **Per-DVN attestation** (`ReceiveUlnBase.sol:43` `_verify`): each DVN writes
   `hashLookup[headerHash][payloadHash][msg.sender] = (submitted, confirmations)` — keyed by the DVN's
   own address, so a DVN can only vouch *as itself*.
2. **`_verified`** (`:48-57`): a DVN counts only if `submitted && confirmations >= required` — a DVN
   can't attest with fewer confirmations than the config demands.
3. **`_checkVerifiable`** (`:90-124`): iterates **all** required DVNs (any missing → `false`, `:99`),
   then counts optional DVNs until `optionalDVNThreshold` is hit. Catch-all `return false`. The predicate
   is exactly "all required + threshold optional, each at sufficient confirmations."
4. **`commitVerification`** (`ReceiveUln302.sol:48`): asserts header (right size/version/**dstEid==localEid**,
   `:79-86`), then `_verifyAndReclaimStorage` — **reverts if not verifiable** (`:60`) and **deletes the
   per-DVN entries** (`:64-76`) so the same attestation set can't be re-committed. Then calls
   `endpoint.verify(origin, receiver, payloadHash)`; **the endpoint reverts if `nonce <= lazyInboundNonce`**
   (`:59` comment) — monotonic-nonce replay protection at the protocol layer.

**Config integrity (`UlnBase`):** DVN lists must be **sorted ascending with no duplicates**
(`_assertNoDuplicates :187-194` — `dvn <= lastDVN → revert`, so the same DVN can't be double-counted
toward a threshold), `requiredDVNs.length == requiredDVNCount`, `0 < optionalThreshold <= optionalDVNCount`,
and **at least one DVN** always (`_assertAtLeastOneDVN :146`). The "NIL vs DEFAULT vs literal-0" sentinel
design lets an OApp inherit the owner's default or override — cleanly separated.

**Verdict: the messaging library is clean** — no duplicate-counting, no zero-DVN config, attestation
bound to DVN identity + payload + confirmations, reverts-if-not-verifiable, storage reclaimed,
protocol-level monotonic-nonce replay guard. **Conservation note:** this layer only authenticates
*messages*; the no-free-mint property lives one layer up in the **OFT** (debit-on-source ==
credit-on-dest). **Residual (the irreducible trust): the OApp's DVN choice + the messagelib owner.** The
well-known weakness is *social, not code*: an OApp that configures **a single DVN** (e.g. only the
LayerZero Labs DVN) collapses the whole "2 independent parties" guarantee to one party — the library
faithfully enforces whatever (possibly weak) policy the app picks. Plus the **messagelib `onlyOwner`**
sets the *default* config (governance ceiling). **No finding** in the lib; the trust is named and it's
*per-app DVN configuration* (use ≥2 independent DVNs) + the lib owner.

---

## B3. Across v3 — optimistic root-bundle + intent-fill; clean, well-bonded; trust = 1 honest disputer + UMA
**Target:** `across-protocol/contracts`, `hub-pool/HubPool.sol` + `spoke-pools/SpokePool.sol`. The
**optimistic / intent** archetype: relayers **front their own capital** to fill user intents on the
destination, then are **repaid from a pre-funded LP pool** against a root bundle validated optimistically.
**Result: a sound optimistic design; no free-mint anywhere (refunds draw a pre-funded pool, not a mint);
the trust is the optimistic challenge + UMA's oracle.**

**The conservation loop (closed at both ends — this is the elegant part):**
- **Fill side** (`SpokePool.fillRelay`/`fillV3Relay`): a relayer pays the user out of *its own* tokens on
  the destination chain. Replay-guarded: `if (fillStatuses[relayHash] == Filled) revert RelayFilled()`
  then set `Filled` (`:1598-1599`), where `relayHash` binds all relay data — **each intent is filled
  exactly once.** No mint: the relayer is out-of-pocket until repaid.
- **Refund side** (`SpokePool.executeRelayerRefundLeaf :1197`): repays the relayer from the pool, gated by
  `MerkleLib.verifyRelayerRefund(rootBundle.relayerRefundRoot, leaf, proof)` (`:1210`) + a **claimed
  bitmap** (`_setClaimedLeaf :1471`, `isClaimed → revert ClaimedMerkleLeaf`) — **each refund leaf claimed
  exactly once.** So fill-once + refund-once: a relayer can't be paid twice, and the pool only pays for
  real fills.

**Who authorizes the refund root (the trust seam):** the SpokePool's `relayRootBundle` is **`onlyAdmin`**
(`:347`) — admin is the **HubPool** via cross-chain messaging. On the HubPool the root is **optimistically
verified**:
1. **`proposeRootBundle`** (`:560`): a proposer posts the roots + a **bond** (`bondToken`, `bondAmount`),
   starting a **`liveness`** window (`:571`, default **7200s = 2h**).
2. **`disputeRootBundle`** (`:715`): **anyone**, within liveness (`require currentTime <=
   challengePeriodEndTimestamp`, `:717`), can stake an equal bond to dispute → escalates to **UMA's
   SkinnyOptimisticOracle** (`:742-758`) for token-vote adjudication; loser's bond is slashed.
3. **`executeRootBundle`** (`:612`): **only after** `getCurrentTime() > challengePeriodEndTimestamp`
   (`:622`) and a `MerkleLib.verifyPoolRebalance` proof (`:629`) + per-leaf claimed bitmap (`:625,650`),
   sends pool tokens to the spoke and relays the refund/slow roots down.

**Verdict: a sound, well-bonded optimistic bridge** — fill-once and refund-once are both enforced, refunds
are draws on a pre-funded LP pool (no mint authority exists to abuse), and the authorizing root must
survive a 2h public challenge backed by an economic bond and UMA's DVM. **Residual (the irreducible
trust):** (1) the **1-of-N-honest-watcher** assumption — a fraudulent root that *no one disputes within
2h* executes and can drain the pool; safety rests on a watcher being online and the **`bondAmount` being
large enough** to make fraud unprofitable / disputes rational; (2) **UMA's DVM** (token-weighted vote) as
the final arbiter — the ultimate oracle; (3) the **owner** sets `liveness`, `bondAmount`, pause, and the
cross-chain admin adapters (governance ceiling). **No finding;** the trust is named — an honest disputer
within liveness + correctly-sized bond + UMA.

---

## B4. Axelar — weighted PoS validator set (separate chain); clean, well-hardened multisig; trust = the set's stake
**Target:** `axelarnetwork/axelar-gmp-sdk-solidity`, `governance/BaseWeightedMultisig.sol`. The **PoS
validator set / separate chain** archetype: a message is authorized by **>threshold weight of Axelar's
staked verifier set**, which signs every cross-chain message and **rotates by epoch**. **Result: the
weighted-multisig verification is clean and notably well-hardened; the trust is Axelar's validator set.**

**Trust model:** Axelar is its own Cosmos-SDK PoS chain; its validators form a **weighted signer set**.
Each message's proof must carry signatures whose **summed weight ≥ threshold** from a *known* signer-set
epoch. The set rotates (`_rotateSigners`), so trust is the **current (or recently-retired) staked set**.

**Verification (`_validateProof` + `_validateSignatures` — read carefully, it's a tidy design):**
1. **Known signer set, within retention** (`:116-122`): `signersHash = keccak(signers)`; its epoch must be
   nonzero and `currentEpoch - signerEpoch <= previousSignersRetention` — an unknown or too-old set is
   rejected (`InvalidSigners`).
2. **Domain + set binding** (`messageHashToSign :244-247`): the signed hash binds `domainSeparator`
   (chain/protocol) **and `signersHash`** — a signature is bound to *this* signer set on *this* domain, so
   it can't be replayed across chains or across rotations.
3. **Sorted single-pass weight accumulation** (`_validateSignatures :189-229`): both `signers` and
   `signatures` must be **ascending by address**; one pass recovers each signature (`ECDSA.recover`) and
   advances `signerIndex` to find its match — out-of-set signer → `MalformedSignatures`. Accumulates
   `weight`; on reaching `threshold` it returns **only if that was the last signature**, else
   `RedundantSignaturesProvided` (no padding the proof with extra sigs). Falls through to
   `LowSignaturesWeight` if the sum never reaches threshold.
4. **Rotation integrity** (`_validateSigners :254-284`): new set must be **strictly increasing** (dedupe +
   bars `address(0)`), every `weight > 0`, `0 < threshold <= totalWeight`. `_rotateSigners` bumps epoch
   and **rejects a repeat set** (`DuplicateSigners`) and enforces `minimumRotationDelay`.

**Verdict: a clean, well-hardened weighted multisig** — set-bound and domain-bound hashes, no duplicate or
zero-address or zero-weight signers, no redundant-signature padding, sound rotation with delay + dedupe.
The sorted single-pass merge is a gas optimization that *preserves* correctness (the ascending invariant +
the redundancy check). **Conservation note:** no-free-mint lives above, in the ITS (Interchain Token
Service). **Residual (the irreducible trust): Axelar's validator set.** A set controlling **≥threshold
weight** can sign any message → authorize any mint → drain. It's **better than a fixed appointed multisig**
(it's stake-weighted, permissionless-to-join-by-stake, and rotates) but **weaker than a light client** (you
trust the set's *honesty*, not a proof of the source chain's consensus). **No finding;** the trust is named
and it's the staked validator set (+ the rotation/governance keys).

---

## B5. SP1 Helios — zk light client (native proof); the trust-minimized end; trust = source consensus + the vkey guardian
**Target:** `succinctlabs/sp1-helios`, `contracts/src/SP1Helios.sol`. The **light-client / native-proof**
archetype, and the **most trust-minimized model in the taxonomy**: instead of trusting any committee, the
contract **verifies Ethereum's own consensus** (the sync committee) via a **succinct SP1 zk proof** of the
light-client state transition. **Result: the model is the strong end — trust collapses to the source
chain's consensus + the proof system; the one residual is the upgradeable verification key (guardian).**

**Trust model:** a `head`, `headers`, `executionStateRoots`, and `syncCommittees` live on-chain. Each
`update` advances the head **only if a SNARK proves the Ethereum light-client transition** — i.e. that
**>2/3 of the current sync committee signed** the new header. That's the *same* trust as running an
Ethereum light client yourself; no extra party is introduced.

**Verification (`update :149-203` — the elegant part is what the contract refuses to take from the caller):**
1. **Proof bound to the contract's *own* state** (`:167-178`): `ProofOutputs.prevHeader / prevHead /
   prevSyncCommitteeHash` are filled **from storage** (`headers[head]`, `head`,
   `syncCommittees[period(head)]`), **not** from calldata. So the proof can only be a transition *from the
   contract's current head* — it can't be replayed against a forged starting point. (Comment `:165-166`:
   "the proof will not verify if they aren't correct.")
2. **The SNARK is the verifier** (`:181`): `ISP1Verifier(verifier).verifyProof(lightClientVkey,
   abi.encode(po), proof)` — reverts unless the proof attests the committed public values under the
   light-client program's verification key. This is the whole authorization: a valid proof == the sync
   committee really signed this transition.
3. **Monotonic, checkpoint-aligned** (`:184-195`): `newHead > head` (no reorg backwards / replay) and
   `newHead % 32 == 0` (checkpoint slot).
4. **Sync-committee handoff** (`:206-227`): stores the new period's committee only if unset; a provided
   `nextSyncCommitteeHash` must match any already-stored one (`NextSyncCommitteeMismatch`) — no silent
   committee swap.

**Verdict: the trust-minimized end of the taxonomy, cleanly built** — authorization is a *cryptographic
proof of the source chain's own consensus*, bound to the contract's committed state, monotonic, with a
guarded committee handoff. No committee, no optimistic window, no extra honest-party assumption. **Residual
(the irreducible trust):** (1) **Ethereum's sync committee** — but that *is* the source chain; trusting it
is unavoidable and minimal. (2) **SP1 soundness + the program's correctness** — the zkVM and the
light-client program (the vkey) must be sound. (3) **the guardian** — `updateLightClientVkey` /
`updateStorageSlotVkey` / `changeGuardian` are **`onlyGuardian`** (`:315-339`); a malicious or compromised
guardian could swap the vkey for one that accepts forged proofs. **This is the punchline of the whole
sweep:** even the most trust-minimized bridge keeps a **governance residual** — the upgradeable
verification key. The cryptography removes the committee; it can't remove the key that can change the
cryptography. **No finding;** the trust is named — source consensus + proof soundness + the vkey guardian.

---

## B6. OptimismPortal2 — native rollup bridge (fault-proof-gated); the canonical L1↔L2 seam; trust = the proof system + Security Council
**Target:** `ethereum-optimism/optimism`, `packages/contracts-bedrock/src/L1/OptimismPortal2.sol`. The
**native rollup bridge** — the canonical L1↔L2 withdrawal path every OP-stack chain actually uses, and the
real-world shape of the trust-minimized end (cf. the existing `../chains/AUDIT-OPTIMISM-FRAUD-PROOF.md`).
**Result: the withdrawal is gated by the chain's own fault-proof system + a maturity delay + a Security
Council backstop; the contract is clean; the trust is the dispute-game system and the Guardian.**

**Trust model:** a withdrawal is authorized only against an **L2 output root that a dispute game (fault
proof) has resolved as valid**, after a **7-day proof-maturity delay**, with a **Security Council Guardian**
able to pause and to blacklist bad games. Conservation is **lock-release** (ETH locked in the `ETHLockbox`
on deposit, released on withdrawal — no mint).

**Two-phase verification (prove, then finalize — both gated):**
- **`proveWithdrawalTransaction` (`:368`):** not paused (`:377`); safe target (`:380`); the dispute game is
  **Proper** (factory-registered, not blacklisted — `isGameProper :393`), was the **respected game type when
  created** (`:398`), and **has not resolved `CHALLENGER_WINS`** (`:403`); the game's `rootClaim` must equal
  `Hashing.hashOutputRootProof(_outputRootProof)` (`:426` — binds the L2 state root); then a **Merkle-Patricia
  proof** that the withdrawal hash lives in the `L2ToL1MessagePasser` storage at that proven root (`:436+`).
- **`checkWithdrawal` (`:620`, gate before finalize):** **not already finalized** (replay guard, `:626`);
  **proven** (`timestamp != 0`, `:633`); proven *after* game creation (`:641`); **`PROOF_MATURITY_DELAY_SECONDS`
  elapsed** (`:646` — the 7-day challenge window); and **`anchorStateRegistry.isGameClaimValid(game)`** (`:651`)
  — the game must be respected, past the finality delay, and not blacklisted. `finalizedWithdrawals[hash] = true`
  on completion (one-time).

**Verdict: a clean, defense-in-depth native bridge** — the authorizing root must survive the fault-proof
game *and* a 7-day window, the output-root proof binds the L2 state, the withdrawal is MPT-proven into L2
storage, replay is guarded at both prove and finalize, and a compromised/buggy proof can be paused and the
game blacklisted. **Residual (the irreducible trust):** (1) the **fault-proof / dispute-game system** —
the same **1-of-N honest challenger within the 7-day window** assumption as the optimistic model (B3), but
over the rollup's *own* state; (2) the **Security Council Guardian** — pause + blacklist + the backstop if
the proof system itself fails (the governance ceiling, identical in spirit to B5's vkey guardian). **No
finding;** the trust is named — the dispute-game system + the Security Council. This is B5's lesson in its
production form: the proof minimizes the *committee*, and a governance key (here a Council, there a vkey
owner) remains as the backstop that can change or halt the proof machinery.

---

## Sweep status (running)
| # | Bridge | Model | Result |
|---|---|---|---|
| B1 | Wormhole | external committee (13/19 Guardian multisig) | clean contract; trust = the 19 Guardians (>1/3 = drain) |
| B2 | LayerZero v2 | oracle+relayer → configurable DVN set | clean lib; trust = app's DVN choice (use ≥2 independent) + lib owner |
| B3 | Across v3 | optimistic root-bundle + intent-fill | clean, well-bonded; trust = 1 honest disputer in 2h + bond size + UMA |
| B4 | Axelar | weighted PoS validator set (separate chain) | clean, hardened multisig; trust = the staked set (≥threshold weight) |
| B5 | SP1 Helios | zk light client (native proof) | trust-minimized; trust = source consensus + proof soundness + vkey guardian |
| B6 | OptimismPortal2 | native rollup bridge (fault-proof-gated) | clean, defense-in-depth; trust = the dispute-game system + Security Council |

**The pattern across the whole taxonomy (best → worst), and it's the corpus's §5b boundary again:** in
**all five**, the on-chain *code* is clean — the verification predicate is sound, replay is guarded,
mint==lock / refund-once / proof-bound-to-state. **The risk is never the contract; it's the named trust
root the contract faithfully serves**, and the *only* thing that changes down the taxonomy is **how human
that root is:**
- **B5 light-client/zk (best):** trust = the source chain's *own consensus*, checked by a proof. The only
  human residual is the **vkey-upgrade guardian** — cryptography removes the committee but not the key that
  can change the cryptography.
- **B4 PoS set:** trust = a *staked, rotating* validator set (≥threshold weight) — economic + permissionless-ish.
- **B3 optimistic:** trust = *1 honest watcher within a window* + a correctly-sized bond + a backstop oracle.
- **B2 configurable DVNs:** trust = *whatever verifier set the app picks* (strong if ≥2 independent, weak if 1).
- **B1 / appointed committee (worst, most-hacked):** trust = *a fixed appointed multisig* — Ronin, Harmony.

**So "audit the bridge" almost always means "name the trust root and size the residual," not "find the
contract bug."** Every nine-figure bridge hack was either a *contract* bug in the verification (Wormhole
2022 signature bypass, Nomad 2022 zero-root) — the class these five have each explicitly guarded — **or** a
*trust-root* compromise (Ronin 5/9 keys, Harmony 2/5) — the residual that no amount of clean code removes.
The lens earns its keep by putting **"who authorizes the mint"** first: the contract read tells you the
code is clean; the *answer to that question* tells you what you're actually trusting. **Six bridges, six
clean contracts, six named-and-sized residuals; no finding.**

**The single sentence the whole sweep proves:** *across all six models, the contract is never the weak
link — the trust root is,* and going down the taxonomy you don't remove the trust, you only make it **less
human** (committee → staked set → optimistic watcher → proof) until, at the trust-minimized end (B5/B6),
the *only* residual left is a **governance key** — a vkey owner or a Security Council — that can change or
halt the very proof machinery the security rests on. **Cryptography moves the trust; it never deletes it.**
That is the §4f settlement-seam spectrum and the governance-ceiling coordinate, measured on six live
bridges. The remaining open candidate (the conserve-by-construction end) is an **HTLC** path with readable
source — the one model with *no* mint authority at all (cf. the Meson note); worth a contract-level read if
a public HTLC implementation surfaces.
