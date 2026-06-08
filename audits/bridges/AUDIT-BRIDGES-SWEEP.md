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
| **First-party issuer burn-and-mint** (trust-minimal *relative to the asset*) | the asset's own issuer (whom you already trust by holding it) — **zero marginal trust** | **Circle CCTP (USDC)** |
| **Light client / native proof** | cryptographic (verify the source chain's consensus/proof) | IBC, zkBridge, native rollup bridges |
| **HTLC atomic swap** (no authorizer at all) | hash-lock + timelock; conservation by construction, **nothing to compromise** | **HTLC ref (B12)**, Meson core / Express, Lightning |
| **PoS validator set / separate chain** | >2/3 stake of a staked set | Axelar |
| **Oracle + relayer (separated)** | 2 independent parties must both be honest | LayerZero |
| **Optimistic / intent** | 1-of-N honest watcher + a fronting relayer's capital | Across, Hop |
| **External appointed committee (multisig)** | >threshold of an appointed signer set | **Wormhole (13/19)**, Hyperliquid Bridge2, Ronin |
| **Off-chain signer + on-chain bare role-check** (worst) | a single role-holding address (backed by an off-chain MPC/threshold group the contract never verifies) | **Synapse (NODEGROUP_ROLE)**, Multichain-class |

The multisig committee is the most-hacked model (Ronin, Harmony, Hyperliquid-class), and the **off-chain
signer + bare role-check** below it is weaker still — the contract verifies *nothing* cryptographic, it
just checks `msg.sender` has a role, so security is entirely off-chain key management + the proxy admin
(this is the Multichain failure class). Light-client and HTLC are the most trust-minimized. Most "bridges"
are message-passing layers that *a token bridge sits on top of* — the token bridge's mint trusts the
messaging layer's authorizer.

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

## B7. Synapse — off-chain MPC "node group" + on-chain **bare role-check**; the weakest taxonomy row (no on-chain verification at all)
**Target:** `synapsecns/synapse-contracts`, `contracts/bridge/SynapseBridge.sol` + `ECDSANodeManagement.sol`.
Surfaced as **interesting** by the rapid sweep, and on a deeper read it earns a **new worst-case row** in
the taxonomy: a bridge whose mint path performs **zero cryptographic verification on-chain** — it trusts a
single address holding a role. **Result: not an exploitable contract bug (the role-check works as designed),
but the starkest trust-concentration in the sweep — security collapses entirely to off-chain key management
+ the upgradeable-proxy admin. Characterized and named; no finding (the trust is the whole story).**

**Trust model:** an off-chain **MPC / threshold-ECDSA "node group"** (a tBTC-style *keep* —
`ECDSANodeManagement.sol` tracks `members`, `honestThreshold`, and a single aggregated `publicKey`,
`:29-36`) reaches consensus off-chain and produces **one** signature from **one** aggregate-key address.
That address is granted `NODEGROUP_ROLE`. **The bridge never sees or verifies that signature.**

**The mint/withdraw authorization — the entire on-chain check (read it; this is the whole gate):**
- `mint` (`SynapseBridge.sol:232`): `require(hasRole(NODEGROUP_ROLE, msg.sender), "Caller is not a node
  group")` (`:239`) → `token.mint(address(this), amount); safeTransfer(to, amount - fee)` (`:245-246`).
- `withdraw` (`:200`), `mintAndSwap` (`:351`), `withdrawAndRemove` (`:459`): **identical bare role-check.**
- There is **no `ecrecover`, no signature, no source-chain proof, no Merkle inclusion** anywhere in the
  release path. Whoever holds `NODEGROUP_ROLE` can mint **arbitrary** `synERC20` to **any** address. This
  is *weaker than every other bridge in the sweep* — Wormhole/Axelar/LayerZero at least **verify a multisig
  on-chain**; Synapse verifies a **role**.
- **Conservation:** mint-on-dest (`:245`); **nothing on-chain ties the minted amount to a verified
  source-chain lock/burn** — the off-chain node group is trusted to have seen the deposit. Replay guard *is*
  present and correct: `require(!kappaMap[kappa], "Kappa is already present"); kappaMap[kappa] = true`
  (`:241-242`, on every path) — so a given authorization (`kappa`) mints exactly once.

**Governance ceiling (where the rest of the trust sits):** `Initializable` **upgradeable proxy**
(`:21`); `initialize` does `_setupRole(DEFAULT_ADMIN_ROLE, msg.sender)` (`:42`). `DEFAULT_ADMIN_ROLE`
**grants/rotates `NODEGROUP_ROLE`** and pauses; `GOVERNANCE_ROLE` sets fees/gas and adds kappas
(`:139-154`). So two keys fully control the bridge: the **admin** (can hand `NODEGROUP_ROLE` to any address,
or upgrade the logic entirely) and the **node-group key** (can mint at will). Either compromise = unlimited
mint = total drain. **This is exactly the Multichain failure class** (the 2023 ~$130M loss was off-chain
MPC-key control, not a contract bug).

**Verdict: the contract is *correct* for what it is** (role-check + `kappa` replay guard both sound), **but
the trust model is the thinnest in the sweep** — no on-chain verification of anything, security == off-chain
threshold-keep key hygiene + the proxy admin + the role-admin key. **No finding** (nothing is exploitable
*in the contract*; the role-check does precisely what it says), and this is a **publicly-documented
architecture**, so naming it here is characterization, not disclosure. The lesson it adds to the taxonomy:
**"audit the bridge" can mean reading the contract and finding it sound, yet the bridge is still the weak
link — because the contract delegates the entire trust off-chain to a key the chain can't see.** The
defensive recommendation (the constructive mirror) is the standing one: **verify the attestation on-chain**
(as Wormhole/Axelar do) so a single off-chain key compromise can't mint, and **timelock the role-admin +
proxy upgrade** so a grant of `NODEGROUP_ROLE` is observable before it's live.

---

## B8. Socket DL (Bungee) — "FastSwitchboard": the headline is n-of-n, the **floor is optimistic+veto**; sound, but the name oversells
**Target:** `SocketDotTech/socket-DL`, `switchboard/default-switchboards/FastSwitchboard.sol` +
`SwitchboardBase.sol` + `socket/SocketDst.sol`. Surfaced as **interesting** by the rapid sweep (the agent
flagged `allowPacket` returning `true` on timeout with zero attestations). On a careful read it is **not a
bug — it's a deliberate optimistic-with-watcher-veto model — but it's a genuinely instructive one**: the
switchboard's *advertised* security (all watchers must attest) is only its **fast path**; its actual
security **floor** is a 1-of-N honest-watcher veto within a timeout. Worth a full write-up because the gap
between the two is exactly the kind of thing the "name your oracle" discipline exists to surface.

**The two-tier security (read `allowPacket`, `:187-213`):**
```
if (trips...) return false;                                  // global/path/proposal trip, or stale packet
if (isRootValid[root_]) return true;                         // FAST PATH: all watchers attested
if (block.timestamp - proposeTime_ > timeoutInSeconds) return true;   // FLOOR: optimistic timeout
return false;
```
1. **Fast path** — `isRootValid[root]` is set **only when `attestations[root] >= totalWatchers[srcChainSlug]`**
   (`attest :128` — i.e. **n-of-n**, *every* registered watcher signed). This is the strong, advertised case.
2. **The floor** — if not all watchers attest, then after `timeoutInSeconds` the root becomes valid **with
   zero attestations** (`:209`, commented "used to make the system work when watchers are inactive due to
   infra etc problems"). So the *effective* security is **not** n-of-n — it's "a transmitter-proposed root
   executes after the timeout **unless a watcher vetoes it.**"

**Why it's sound, not a hole — the veto (this is the part that matters, and I verified it):** a **single**
honest watcher can stop a fraudulent root within the window. `tripProposal` (`SwitchboardBase.sol:232-260`)
is gated by **`WATCHER_ROLE` per source chain** (`:254`) and sets `isProposalTripped[packetId][proposalCount]`,
which makes `allowPacket` return `false` (`:200`) — **permanently blocking that proposal**, even past the
timeout. `tripPath` (`:194`, also WATCHER_ROLE) halts an entire source lane; `tripGlobal` (`:164`, TRIP_ROLE)
halts everything. All are nonce-protected signed messages. So the model is precisely the **optimistic family**
(cf. Across B3, OptimismPortal B6): **1-of-N honest, online watcher within a timeout**, not n-of-N.

**The execution gate is otherwise tight** (`SocketDst.execute`): `PacketNotProposed` if the root is zero,
executor-signature check, `switchboard.allowPacket(...)` else `VerificationFailed`, **a real Merkle
inclusion proof** `decapacitor.verifyMessageInclusion(...)` else `InvalidProof`, and a replay guard
`if (messageExecuted[msgId]) revert MessageAlreadyExecuted()` set before external calls. So a forged root
still needs valid Merkle inclusion of the message — the timeout path doesn't skip the inclusion proof, only
the *attestation*.

**Verdict: a correctly-built optimistic switchboard whose marketing ("Fast", n-of-n attestation) describes
its best case, while its security floor is the weaker, accurate one: 1 honest watcher must be live and must
veto within `timeoutInSeconds`.** No finding. **Residual (the irreducible trust):** (1) **watcher liveness**
— if *no* watcher is online/honest for `timeoutInSeconds`, a fraudulent (but Merkle-valid-for-a-fake-root)
packet finalizes; safety rests on at least one watcher watching; (2) the **`timeoutInSeconds` parameter** —
too short and watchers can't react, too long and the bridge stalls when watchers are genuinely down (the
liveness/safety knob, GOVERNANCE_ROLE-set); (3) the **watcher set + trip roles** governance. The lesson it
adds: **read the *floor*, not the headline** — a switchboard that looks like n-of-n attestation can have a
1-of-N-veto security floor, and the floor is what an attacker targets. (This is publicly-documented Socket
DL behavior; characterization, not disclosure.)

---

## B9. Circle CCTP — first-party issuer burn-and-mint; the model that adds **zero marginal trust** (a new axis for the lens)
**Target:** `circlefin/evm-cctp-contracts`, `MessageTransmitter.sol` + `roles/Attestable.sol` +
`TokenMessenger.sol`/`TokenMinter.sol`. CCTP is how USDC moves natively across chains, and it forces a
**refinement of the whole lens**: the question isn't only *who authorizes the mint* — it's **does the bridge
add a trust root beyond the one you already hold?** For CCTP the answer is **no**, and that makes it a
distinct (and, for its asset, near-optimal) model despite being fully centralized.

**Trust model:** **Circle — the issuer of USDC itself — is the attester.** USDC is `burn`ed on the source
(`TokenMessenger.depositForBurn`) and `mint`ed on the destination (`TokenMinter.mint`) when a message
signed by Circle's off-chain **Attestation Service** arrives. The attestation is an **m-of-n multisig** of
Circle-operated attester keys (`signatureThreshold` of `enabledAttesters`, **initialized to 1**,
`Attestable.sol:89-90`).

**Verification (`receiveMessage :250` → `_verifyAttestationSignatures`):** exactly `signatureThreshold`
signatures, each over `keccak256(message)`, each from a **distinct enabled attester in strictly increasing
address order** (`_recoveredAttester > _latestAttesterAddress` → dedupe + bars `address(0)`;
`isEnabledAttester` membership). Then: **destination domain == localDomain** (`:263`), optional
**destinationCaller binding** (`:269` — a message can be locked to a specific redeemer), version, and a
**nonce replay guard** `require(usedNonces[sourceAndNonce] == 0)` then set to 1 (`:284-286`). Then dispatches
to the recipient's `handleReceiveMessage` (→ `TokenMinter.mint`).

**Conservation — the strong part:** burn-on-source **== mint-on-dest, 1:1, by the issuer's own authority.**
There is **no wrapped/canonical divergence** at all: it's the *same* canonical USDC on both sides, destroyed
on one chain and recreated on another by the entity that issues it. Most bridges have to *prove* mint==lock;
CCTP doesn't need to, because the minter and the issuer are the same party — conservation is true by issuer
fiat, and Circle can't "over-mint" relative to itself without simply… issuing USDC, which it can already do
anywhere.

**The refinement to the lens — "marginal trust":** every *wrapped-asset* bridge (lock USDC in a vault, mint
a bridge-issued wrapped-USDC on the far side) adds a **new trust root** — the bridge operator — *on top of*
Circle. If that operator is compromised, the wrapped token de-pegs even though Circle did nothing wrong.
CCTP adds **none**: if you already hold USDC, you already trust Circle to honor it (freeze, blacklist, mint,
redeem — Circle can already do all of it on the base asset). So bridging USDC via CCTP is **strictly less
trust** than bridging it through any third-party bridge. **This is why "who authorizes the mint" needs the
follow-up "…and is that anyone you weren't already trusting?"** For a first-party issuer bridge the marginal
trust is zero; for a wrapped bridge it's the whole operator.

**Verdict: clean verification, sound replay, and — uniquely — zero marginal trust for its asset.** **No
finding.** **Residual (the irreducible trust):** (1) **Circle, completely** — `attesterManager` sets the
attesters and `signatureThreshold` (default **1-of-n**, so a *single* attester-key compromise could mint
USDC on a destination chain until Circle rotates/blacklists), `owner` pauses, `tokenController` sets mint
caps and which tokens are mintable. It is total centralization — **but it is the *same* centralization you
accept the moment you hold USDC**, which is the entire point. The defensive note (constructive mirror):
**prefer first-party issuer bridges (CCTP) over wrapped bridges for the issuer's own asset** — they collapse
two trust roots into the one you can't avoid anyway — and **raise the attester `signatureThreshold` above 1**
so no single key mints. The taxonomy gains a top-tier row that is *centralized yet trust-minimal*, because
trust-minimality is **relative to what you already hold**, not absolute.

---

## B10. Chainflip — TSS vault: off-chain threshold-Schnorr, **one** on-chain aggregate signature, native assets (no mint)
**Target:** `chainflip-io/chainflip-eth-contracts`, `KeyManager.sol` + `Vault.sol` + `abstract/SchnorrSECP256K1.sol`.
The **TSS-vault** archetype (the THORChain/Multichain-MPC family): a rotating validator committee runs
**threshold-Schnorr (FROST) off-chain** to produce a **single aggregate signature**, and native assets sit
in a **vault** that pays out against that one signature — **no minting anywhere.** **Result: a clean,
carefully-built contract; the threshold check is off-chain by design, so on-chain the trust is the one
aggregate key, backstopped by a governance key.**

**Trust model:** the chain holds **one `_aggKey`** (a secp256k1 Schnorr pubkey) representing the whole
validator set's combined threshold key. Every vault outflow is authorized by **one Schnorr signature** from
that key — the >2/3 threshold is enforced *off-chain* in the FROST signing ceremony, so the on-chain
footprint is a single verification, not an m-of-n loop (contrast Axelar B4, which does the weighted multisig
*on-chain*).

**Authorization (`Vault.transfer :155` → `consumesKeyNonce` → `KeyManager._consumeKeyNonce :54`):**
- Every outflow (`transfer`, `allBatch`, `transferBatch`, `fetchBatch`) carries
  `consumesKeyNonce(sigData, keccak256(this.transfer.selector, transferParams))` (`:165`) — the signature
  must cover the **exact call selector + params.**
- `_consumeKeyNonce`: `verifySignature(msgHash, sig, aggKey.pubKeyX, parity, kTimesGAddress)` (`:58`) +
  **nonce replay** `require(!_isNonceUsedByAggKey[nonce])` then set (`:61-64`).
- **Replay binding is strong** (`consumeKeyNonce :80-84`): the signed `msgHash` =
  `keccak(contractMsgHash, nonce, msg.sender, block.chainid, address(this))` — bound to the **caller, chain,
  and contract**, so a signature can't be replayed across chains, contracts, or callers.
- **Schnorr core** (`SchnorrSECP256K1.verifySignature`): guarded against the `ecrecover`-abuse edge cases —
  `signingPubKeyX < HALF_Q` (`:109`), `signature < Q` (`:111`), and **forbids trivial inputs that would make
  `ecrecover` return `0x0`** (`:113-119`). This is the well-known "ecrecover-as-Schnorr-verifier" trick,
  implemented with its standard hardening.

**Conservation:** **native assets in a vault — no mint, no wrapped token.** Outflow ≤ what the vault holds;
the conservation floor is vault solvency (like THORChain's Asgard vaults), and the cross-chain accounting is
the State Chain's job, not an on-chain mint==lock check.

**Key rotation / governance ceiling (the backstop, cleanly separated):**
- **`setAggKeyWithAggKey` (`:94`):** the *current* agg key signs to rotate to the next epoch's agg key — the
  normal validator-set rotation, self-authorized.
- **`setAggKeyWithGovKey` (`:113`):** the **governance key** can rotate the agg key, **but only after
  `timeoutEmergency`** — an emergency recovery path for when the validator set goes dark (liveness backstop),
  time-gated so it can't front-run a live committee.
- Plus a community/suspend key (`onlyNotSuspended` guards every outflow).

**Verdict: a clean, well-hardened TSS-vault bridge** — single aggregate-Schnorr authorization with strong
caller/chain/contract/nonce replay binding, the Schnorr verifier hardened against the `ecrecover→0` trap,
native-asset vault (nothing to over-mint), and an emergency gov backstop that's *timeout-gated* rather than
unilateral. **No finding.** **Residual (the irreducible trust):** (1) the **aggregate key** — i.e. >2/3 of
the validator set; if enough validators collude or the threshold key is reconstructed, the vault drains
(the TSS-compromise class — this is the *same* trust shape as a PoS set, just with the threshold enforced
off-chain and the funds native-in-vault). (2) the **govKey** emergency backstop (time-gated, but it *can*
rotate the agg key — the governance ceiling, congruent with B5's vkey-owner and B6's Security Council).
The lesson it adds: **a single on-chain signature can still be a >2/3 threshold** — the absence of an m-of-n
loop on-chain doesn't mean centralization; the multisig moved *into the cryptography* (FROST). To audit it
you must look *past the contract* (which only sees one key) to the **off-chain signing protocol**, which is
exactly where the "name your oracle" discipline points.

---

## B11. Native canonical L1↔L2 bridges (6 rollups/sidechains) — the proof-gated end, with one instructive outlier
**Targets:** zkSync Era (`matter-labs/era-contracts`), Starknet StarkGate (`starknet-io/starkgate-contracts`),
Scroll (`scroll-tech/scroll-contracts`), Arbitrum Nitro (`OffchainLabs/nitro-contracts`), Polygon
zkEVM/Agglayer (`0xPolygonHermez/zkevm-contracts`), Polygon PoS (`0xPolygon/pos-contracts`). The **native
proof** family — the canonical bridge of each chain, where the L1 withdrawal should gate on the L2's *own*
proof system. **Result: five of six gate withdrawals on a verified proof with no bypass — including the
permissionless escape hatches; the sixth (Polygon PoS) is a checkpoint *sidechain* whose withdrawals rest on
a validator-quorum signature, not a proof — the one genuinely weaker trust root, and it's by design.**

**The five proof-gated bridges (each traced from `finalizeWithdrawal`/`claim` back to a proof):**
- **zkSync Era** — `L1Nullifier._finalizeDeposit` (replay-guarded `isWithdrawalFinalized`) → `_verifyWithdrawal`
  → `proveL2MessageInclusion` → `Mailbox._proveL2LeafInclusion`: **`if (batchNumber > totalBatchesExecuted)
  revert`** and root match; `l2LogsRootHashes` is written only in `Executor._executeOneBatch`, which reverts
  `CantExecuteUnprovenBatches` unless `totalBatchesVerified` was advanced by `verifier.verify(...)`. Chain:
  **verify → execute → withdraw**, tight.
- **Scroll** — `relayMessageWithProof`: replay guard + `require(isBatchFinalized(batchIndex))` +
  `WithdrawTrieVerifier.verifyMerkleProof(withdrawRoots(batchIndex), …)`; `withdrawRoots` is written only
  after `verifyBundleProof(...)` and **`withdrawRoot` is a public input to the proof** — root⇄proof
  cryptographically bound. Even the **permissionless enforced-mode escape hatch** (`commitAndFinalizeBatch`,
  callable by anyone when the sequencer stalls) **still calls `verifyBundleProof`** — there is *no* no-proof
  finalize path.
- **Polygon zkEVM/Agglayer** — `claimAsset` → `_verifyLeaf` (SMT proof vs `mainnet/rollupExitRoot`,
  `claimedBitMap` replay guard); `rollupExitRoot` enters the global exit root only via RollupManager **after
  `verifyProof(...)`**; even `verifyBatchesTrustedAggregator` (role-gated) **still runs the proof** — the
  role gates *who posts*, never *whether the proof runs*.
- **Arbitrum Nitro** — `Outbox.recordOutputAsSpent` recomputes the Merkle root and `revert UnknownRoot` if
  unknown (`spent` bitmap replay guard); `roots` is written only by `confirmAssertionInternal`, reached only
  after the **BoLD fraud-proof window** (`block.number >= createdAtBlock + confirmPeriodBlocks`) and, if
  contested, `winningEdge.status == Confirmed`. Nothing executes against an unconfirmed assertion. (The
  `anyTrustFastConfirmer` is a documented **AnyTrust-only** governance path, not full-rollup.)
- **StarkGate** — `withdraw` → `consumeMessageFromL2` on the StarknetCore registry, which only holds a
  message after a **STARK-proof-gated `updateState`**. (Caveat: the verifier lives in the *external*
  StarknetCore repo not vendored here, so the proof gate itself is one repo away — named, not read.)

**The outlier — Polygon PoS (`pos-contracts`):** withdrawals are authorized by a **Heimdall validator
checkpoint signature, explicitly not a fraud/validity proof.** `WithdrawManager.checkBlockMembershipInCheckpoint`
proves Merkle membership against a checkpoint header that `StakeManager.checkSignatures` accepts only at
**`signedStakePower >= totalStake*2/3 + 1`**. So a **≥2/3 stake-weighted validator collusion can sign an
arbitrary checkpoint root** → forge exits; plus `RootChain.setNextHeaderBlock` is **`onlyOwner`** (a header-
pointer admin lever). This is the documented PoS-sidechain trust model (the same family as Axelar B4 /
Chainflip B10 — a >2/3 set — but here it gates the *canonical* bridge of a major chain). Replay-guarded
(`EXIT_ALREADY_EXISTS` + exitNFT burn + challenge period). **No code defect; the weaker trust root is the
architecture** (a checkpoint sidechain is not a rollup, and its bridge inherits that).

**Verdict: the native-proof end of the taxonomy holds up** — five of six canonical bridges make withdrawal
*impossible* without a verified proof, escape hatches included, and the residual is uniformly the **standard
governance ceiling: a multisig+timelock that can swap the verifier or upgrade the proxy** (the same key-at-
the-top pattern as B5/B6). Polygon PoS is the instructive contrast: it *looks* like "a native bridge" but is
a **validator-signature checkpoint bridge**, so it belongs with the >2/3-set models, not the proof-gated
ones — exactly the distinction the taxonomy exists to draw. **No finding** in any of the six.

---

## B12. HTLC atomic swap — the conserve-by-construction floor; the **only** model with *no authorizer at all*
**Target:** a canonical `HashedTimelockERC20.sol` reference (the model Meson/Lightning/Connext-vector use;
read at the contract level to finally close the taxonomy's trust-minimized end). **Result: the one bridge
model in the entire sweep with zero authorizer, zero governance, zero upgrade, and conservation enforced
purely by a binary state machine over self-custodied funds — the theoretical floor, paid for in convenience.**

**Trust model: there isn't one.** No committee, no validator set, no oracle, no relayer, no proof system, no
admin key, no proxy. The "release" is just a counterparty claiming **pre-locked** funds by revealing a hash
preimage. There is literally nothing external to compromise.

**The whole state machine (three functions, all the safety is structural):**
- **`newContract` (`:112`):** sender locks `_amount` into the contract under `hashlock = sha256(preimage)`
  and `timelock`; `contractId = sha256(sender, receiver, token, amount, hashlock, timelock)` and a duplicate
  id is rejected (`:138` — replay/dup guard). Funds move in via `transferFrom` — **the contract only ever
  holds what was deposited.**
- **`withdraw(id, preimage)` (`:176`):** gated by `hashlockMatches` (**`sha256(preimage) == hashlock`**,
  `:71-74`) + `withdrawable` (`msg.sender == receiver`, not already withdrawn/refunded). Sets
  `withdrawn = true` (one-shot) then transfers to receiver.
- **`refund(id)` (`:198`):** after `timelock` passes and if not withdrawn, `msg.sender == sender` reclaims;
  sets `refunded = true`.

**Conservation — by construction, not by check:** every locked contract resolves to **exactly one of
{withdrawn → receiver, refunded → sender}**, both flags one-shot and mutually exclusive (`withdrawable`/
`refundable` each require the other false). The contract can never pay out more than was locked, never to
anyone but the two named parties, never twice. `Σ in == Σ out` is a *property of the state machine*, not an
invariant the code recomputes — the strongest possible conservation floor.

**How it bridges without a bridge (atomic swap):** Alice locks on chain A under `H = sha256(s)`; Bob locks
on chain B under the *same* `H`. Alice reveals `s` to withdraw on B — which exposes `s` on-chain — and Bob
uses `s` to withdraw on A. **Either both legs complete or both refund.** Cross-chain atomicity comes entirely
from the shared hashlock + the two chains' own liveness; **no messenger, no mint, no trusted party crosses
the gap.**

**Verdict: the trust-minimized floor of the taxonomy — and the reason the rest of the taxonomy exists.**
**No finding.** **Residual (and it's purely liveness/economic, never safety):** (1) **timelock ordering** —
A's timeout must exceed B's, or a party can be griefed; funds always eventually return to their owner, so
it's a liveness not a custody risk; (2) the **free-option problem** — whoever reveals second can walk away
(economic, mitigated by timelock design); (3) a reference subtlety worth flagging — this impl **comments out
the post-timeout withdraw block** (`:80-84`), so at the expiry boundary both `withdraw` and `refund` are live
until one executes; correct atomic-swap practice relies on timelock *ordering* to avoid that race, not on
the contract. **Why everything else in the taxonomy is weaker-but-used:** HTLC requires a **counterparty with
matching liquidity on the far side** and an **interactive, per-swap** protocol — it can't pass arbitrary
messages or tap pooled liquidity. **The entire taxonomy is the price of giving up HTLC's zero-trust for
convenience and capital efficiency:** the moment you want a pool, a wrapped asset, or one-way messaging, you
must reintroduce an authorizer — and from there it's only a question of *how human* that authorizer is.

---

## B13. Non-EVM bridges (Solana · Cosmos · Move) — same trust pattern, but the **substrate makes conservation structural**
**Targets:** Solana (Wormhole core+token bridge, Circle CCTP, Across SVM-spoke), Cosmos (IBC 07-tendermint
light client, ICS-20, Gravity Bridge), Move (Sui native bridge, Wormhole Sui, Wormhole Aptos) — **20 programs/
modules across 3 ecosystems, three parallel sweeps, each spot-verified.** The point of going non-EVM is the
**different bug surface** (Solana account/signer/owner confusion; Move linear types; Cosmos light-client Go),
and the result sharpens the corpus's central thesis: **every contract's verification is clean, the trust is
the same named root as on EVM — but the non-EVM substrates each add a conservation guarantee the EVM bridges
have to enforce by hand.** No findings.

### 13a. Cosmos — IBC is the gold-standard light client; Gravity is the cautionary contrast
- **IBC `07-tendermint`** is the non-EVM realization of the **native-proof / light-client** top tier, and the
  cleanest in the whole sweep. `verifyHeader` calls cometbft `light.Verify(signedHeader, trustedVals,
  signedHeader, valSet, TrustingPeriod, now, MaxClockDrift, TrustLevel)` (`update.go:112` — **verified
  myself**) — a *real Tendermint consensus proof*, **1/3 default trust level** (`fraction.go:9`,
  skipping-verification standard), `checkTrustedHeader` binds `TrustedValidators.Hash() ==
  NextValidatorsHash` (no forged trusted set), and **misbehaviour freezes the client**
  (`UpdateStateOnMisbehaviour` → `FrozenHeight`). Recovery/upgrade are gov-gated. Trust = *the source chain's
  own validators*, proven — no extra party.
- **ICS-20 conservation is structural via x/bank:** escrow-on-source (`EscrowCoin`) == mint-on-dest
  (`MintCoins`), sink-side burns/unescrows mirror it, total-escrow tracked per denom, and — the key point —
  **the bank module is the backstop**: a malicious counterparty trying to over-unescrow simply fails at
  `SendCoins` (insufficient balance). Conservation is enforced by the *module beneath the bridge*, not by the
  bridge's own arithmetic.
- **Gravity Bridge is the contrast that proves the point:** it is **not** a light client — the Cosmos side
  **mints on a >66% validator *attestation*** (validators vote that they "saw" an Ethereum deposit; **no
  on-chain proof of Ethereum consensus**): `AttestationVotesPowerThreshold = 66` (`genesis.go:25` — **verified
  myself**), `requiredPower = 66 * totalPower / 100` and `attestationPower.GT(requiredPower)`
  (`attestation.go:105,120` — **verified**). The Ethereum side releases on a stored-valset signature checkpoint
  with `constant_powerThreshold = 2863311530` (`Gravity.sol:71` — **verified**, = ⅔ of 2³² normalized power).
  Solid nonce-replay guards and post-mint supply asserts, no code defect — but its Q2 answer is *"a validator
  signature,"* where IBC's is *"a consensus proof."* Same chain ecosystem, two tiers of the taxonomy apart.
  (Gravity is the documented federated-attestation model; characterized, not a finding.)

### 13b. Move (Sui / Aptos) — conservation is **type-enforced**; mint is unreachable without a verified threshold
- **Sui native bridge** (Sui↔Eth) is a **stake-weighted validator committee** that auto-rotates each epoch
  from `SuiSystemState` (no admin key rotates it). Mint is gated by a real threshold signature:
  `committee.verify_signatures` ecrecovers each sig, rejects duplicates/non-members, skips blocklisted
  weight, and **`assert!(threshold >= required_voting_power, ESignatureBelowThreshold)`** (`committee.move:119`
  — **verified myself**), where `required_voting_power` is **3334/10000 (~⅓) for a token transfer, 5001 for
  governance** (`message.move:622-643` — **verified**). The decisive structural fact: **`treasury::mint` is
  `public(package)` and only reachable via `claim_token_internal`, which first asserts the message's
  `verified_signatures.is_some()`** — so the **linear-type `TreasuryCap` conservation guarantee can never be
  reached without the signature check.** Plus an on-chain per-route hourly USD-notional **rate limiter** and a
  claimed-flag replay guard.
- **Wormhole Sui & Aptos** are the **13/19 guardian quorum** (`quorum = (n*2)/3+1`), with the mint capability
  (`TreasuryCap`/`MintCapability`) again `public(friend)` and reachable only after `vaa::verify_only_once`
  consumes the VAA — and the **consumed-VAA digest set** is the replay guard. The Move invariant *"only
  `parse_and_verify` can produce a verified-message object"* is explicitly preserved, so the type system
  carries the security, not convention.
- **The Move lesson:** linear types mean conservation isn't an invariant you *check* — it's one the compiler
  *won't let you violate*; the only thing the bridge code adds is the **authorization** gate in front of the
  mint capability. That is the cleanest possible separation of "conservation floor" (substrate) from "trust
  root" (the committee/guardians).

### 13c. Solana — the account model **forces** explicit ownership; every mint is PDA-gated + one-shot
- **Wormhole** (core + token bridge): core verifies the **2/3 guardian quorum** by binding each guardian key
  to the native `secp256k1_program` instruction and **re-deriving the VAA body keccak hash**
  (`post_vaa.rs check_integrity`) — defeating VAA/signature confusion; the `PostedVAA`/`SignatureSet` are
  **PDAs owned by the bridge program**, so a forged "posted VAA" can't be injected. Token-bridge mint is
  gated by a typed `PayloadMessage<PayloadTransfer>` (only constructible from a bridge-owned PostedVAA) and a
  **one-shot `Claim` PDA** seeded by `(emitter, chain, sequence)` with an `Uninitialized` constraint — the
  replay guard *is* the account model.
- **Circle CCTP**: m-of-n attester `secp256k1_recover` with **strictly-increasing signers (dedup), enabled-
  attester membership, and low-s malleability rejection**; `UsedNonces` PDA replay guard; and the downstream
  mint is gated by the message-transmitter's **`authority_pda` being a `Signer` with `seeds::program` pinned
  to the transmitter** — cross-program authority forgery is blocked by seed derivation, not a checked flag.
- **Across SVM**: keccak merkle proof against a HubPool-relayed root (itself delivered via **CCTP
  attestation**), claimed-bitmap replay guard, and a neat **EVM/SVM domain separation** (leaf encoding
  prepends 64 zero bytes so an EVM leaf can never collide with an SVM leaf). Fills are self-funded
  (`fill_status` PDA, double-fill → `RelayFilled`).
- **The Solana lesson:** the account model has no implicit `msg.sender`/owner — **every** security-critical
  account's owner, mint, and PDA seeds must be *explicitly* asserted, and all six programs do it
  consistently; the one-shot init-constrained PDAs (`Claim`, `UsedNonces`) make replay protection a property
  of account existence rather than a mutable bool.

**Verdict across all three ecosystems: clean verification everywhere; the trust roots are the same named ones
as on EVM (guardians, a stake-weighted committee, Circle's attesters, a >2/3 validator set), and not one
exploitable finding.** What the non-EVM substrates add is exactly the corpus's **fail-safe-substrate** thesis,
now seen from the bridge angle: **Move makes conservation a compiler guarantee, Solana makes replay an
account-existence guarantee, Cosmos makes conservation a bank-module guarantee** — so even a buggy bridge
*can't* over-mint or double-claim, because the layer beneath it forbids it. The bridge still chooses a trust
root, and that root is still the residual — but the floor under it is structural, not hand-rolled. **IBC is
the standout** (a real light client, the top tier), **Gravity the standout caution** (a validator attestation
masquerading in the same ecosystem), and **everything else lands exactly where its EVM cousin did** — which
is itself the finding: *the trust-model taxonomy is substrate-independent; only the conservation floor gets
stronger off-EVM.*

---

## Rapid sweep — the surface layer (12 bridges, 4 parallel passes)
Beyond the deep reads above, a batch of **rapid surface sweeps** (the two-question lens, ~10 lines each) over
12 bridges. The point of the batch is the **distribution**, and it's the same one the whole corpus keeps
finding: **the contracts are clean; the trust roots cluster into a few shapes, and the recurring weak shape
is "an owner key decides who attests."**

| Bridge | Authorizer | On-chain check | Clean? | Residual / why flagged |
|---|---|---|---|---|
| **Hop** | bonder + optimistic root | **Merkle inclusion proof** (trustless path) | ✅ | bond + challenge window; not flagged |
| **Celer cBridge** | SGN staked PoS set | signed msg, **2/3 power quorum** | ✅ | owner emergency `resetSigners` (notice period) |
| **Connext/Everclear** | AMB messaging + liquidity routers | signed router/sequencer + reconcile state machine | ✅ | routers risk own capital; not flagged |
| **Chainlink CCIP** | commit DON **+ independent RMN** | **Merkle proof vs RMN-blessed root** | ✅✅ | *best-in-class*: dual-quorum + curse; edge: owner can set RMN `minSigners=0` for unsupported lanes |
| **LayerZero OFT** | the LZ Endpoint (app's DVNs) | endpoint==caller + peer; proof is upstream | ✅ | 1:1 burn/mint **default**; fee-on-transfer subclasses can break 1:1 (integration footgun) |
| **Hyperlane** | **per-recipient configurable ISM** | signed checkpoint (+ optional Merkle) | ✅ | a recipient can point at `NoopIsm`/1-of-1 — strength is a *deployment choice*, not a guarantee |
| **deBridge v1** | admin-managed oracle set | signed `submissionId`, ≥N confirmations | ✅ | `DEFAULT_ADMIN_ROLE` can swap the whole `signatureVerifier` + oracle set; UUPS-upgradeable |
| **Allbridge Core** | **2-of-N** (1 primary + 1 secondary) validators | two `ecrecover` checks | ✅ | entire validator set **owner-rotatable**, single-owner, no in-contract timelock |
| **Wormhole NTT** | **M-of-N transceivers** (VAA-backed) | threshold + verified VAA + replay + **rate limiter** | ✅ | `setThreshold` floor is **1** (only 0 rejected) → owner can run 1-of-N; UUPS upgrade |
| **Synapse** | off-chain MPC + **bare role** | **none** (just `hasRole`) | ✅(code) | **B7** — no on-chain verification; Multichain class |
| **Socket DL** | transmitter + n-of-n watchers / optimistic floor | signed root + **Merkle inclusion** | ✅ | **B8** — security floor is 1-of-N veto + timeout, not n-of-n |
| **Across v3** | optimistic root + UMA | Merkle proof + 2h challenge | ✅ | **B3** — 1 honest disputer + bond |

**The one pattern, restated and now measured on ~12 more bridges:** every contract's *verification* is
sound (Merkle proofs, quorum checks, replay guards all present and correct) — **the variance is entirely in
the trust root**, and the modal weak point is **governance: an `onlyOwner`/`DEFAULT_ADMIN_ROLE` that can
rotate the signer set, swap the verifier, set the threshold to 1, or upgrade the logic.** CCIP is the
positive outlier (an *independent* RMN veto layered on the DON — two separate quorums must agree, the
defense-in-depth the others lack). Synapse is the negative outlier (no on-chain check at all). Everyone else
lives in between, and where they sit is decided by **one question: can a single key change who attests?**

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
| B7 | Synapse | off-chain MPC + on-chain **bare role-check** (weakest) | contract correct, but **no on-chain verification**; trust = off-chain key + proxy admin (Multichain class) |
| B8 | Socket DL (Bungee) | n-of-n attestation **or** optimistic timeout+veto | sound; floor = **1-of-N watcher veto + timeout**, not the headline n-of-n |
| B9 | Circle CCTP | first-party issuer burn-and-mint | clean; **zero marginal trust** for USDC (issuer == attester); residual = Circle, default 1-of-n |
| B10 | Chainflip | TSS vault (off-chain threshold-Schnorr) | clean, hardened; trust = the aggregate key (>2/3, FROST) + time-gated govKey backstop |
| B11 | 6 native canonical L1↔L2 | zkSync·StarkGate·Scroll·Arbitrum·zkEVM (proof) + Polygon PoS (sidechain) | 5/6 **gated on a verified proof**, no bypass; Polygon PoS outlier = 2/3+1 validator sig |
| B12 | HTLC atomic swap | conserve-by-construction (hashlock + timelock) | **no authorizer at all**; conservation by binary state machine; residual = liveness only |
| B13 | Non-EVM ×20 (Solana·Cosmos·Move) | guardians / stake-committee / attesters / light-client | all clean; **substrate makes conservation structural** (Move types, Solana PDAs, x/bank); IBC top-tier, Gravity the caution |
| — | +12 rapid sweeps | Hop·Celer·Connext·CCIP·OFT·Hyperlane·deBridge·Allbridge·NTT (table above) | all contracts clean; modal residual = an owner key that can change who attests |

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
2022 signature bypass, Nomad 2022 zero-root) — the class every clean contract here explicitly guards — **or**
a *trust-root* compromise (Ronin 5/9 keys, Harmony 2/5, Multichain MPC keys) — the residual that no amount of
clean code removes. The lens earns its keep by putting **"who authorizes the mint"** first: the contract read
tells you the code is clean; the *answer to that question* tells you what you're actually trusting.

**The tally after the full sweep:** **~43 bridge systems** — **13 deep reads (B1–B13; B11 = 6 canonical
L1↔L2 bridges, B13 = 20 non-EVM programs across Solana/Cosmos/Move) + 12 rapid EVM surface sweeps** —
spanning **every row of the taxonomy** from HTLC (no authorizer) and first-party issuer and native-proof down
to off-chain-bare-role, and now across **four substrates** (EVM, SVM, Cosmos-SDK, Move). **Every single
contract's verification is clean** (sound predicate, replay guard, conservation); **not one exploitable
finding.** The variance is *entirely* in the trust root, and the deep reads added three refinements the
original six-row table didn't have:
- **B9 marginal trust** — trust-minimality is *relative to what you already hold*. Circle CCTP is fully
  centralized yet adds **zero** trust for USDC (issuer == attester), beating every third-party wrapped bridge.
- **B10 the multisig can live in the cryptography** — Chainflip's *one* on-chain Schnorr signature is a >2/3
  FROST threshold; "no m-of-n loop on-chain" ≠ centralized. You must audit *past* the contract to the
  off-chain signing protocol — precisely where "name your oracle" points.
- **B13 the taxonomy is substrate-independent; only the floor changes** — the *same* trust roots recur on
  Solana, Cosmos, and Move, but the conservation floor gets **structurally stronger** off-EVM (Move linear
  types make it a compiler guarantee, Solana one-shot PDAs make replay an account-existence guarantee, Cosmos
  x/bank makes it a module guarantee). The trust model is portable; the fail-safe substrate is not — it
  *deepens*.

**The single sentence the whole sweep proves, now measured on ~23 bridges:** *the contract is never the weak
link — the trust root is,* and going down the taxonomy you don't remove the trust, you only make it **less
human** (off-chain key → committee → staked/FROST set → optimistic watcher → proof) until, at the
trust-minimized end (B5/B6/B11), the *only* residual left is a **governance key** — a vkey owner, a Security
Council, a verifier-upgrade multisig — that can change or halt the very proof machinery the security rests on.
**Cryptography moves the trust; it never deletes it.** That is the §4f settlement-seam spectrum and the
governance-ceiling coordinate, measured at scale. The one open candidate (the conserve-by-construction end)
remains an **HTLC** path with readable source — *no* mint authority at all (cf. the Meson note) — and the TSS
side was reached from the other direction by B10; a public HTLC implementation is the last contract-level read
to close the taxonomy end-to-end.
