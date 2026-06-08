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

## Sweep status (running)
| # | Bridge | Model | Result |
|---|---|---|---|
| B1 | Wormhole | external committee (13/19 Guardian multisig) | clean contract; trust = the 19 Guardians (>1/3 = drain) |
| B2 | LayerZero v2 | oracle+relayer → configurable DVN set | clean lib; trust = app's DVN choice (use ≥2 independent) + lib owner |
| B3 | Across v3 | optimistic root-bundle + intent-fill | clean, well-bonded; trust = 1 honest disputer in 2h + bond size + UMA |

**Pattern so far (consistent with the §5b fail-safe-substrate boundary):** in all three, the on-chain
*code* is clean — the verification predicate is sound, replay is guarded, mint==lock/refund-once. **The
risk is never the code; it's the named trust root** the code faithfully serves: a committee (Wormhole),
an app-chosen verifier set (LayerZero), or an optimistic-watcher+oracle (Across). Bridges are the weak
link not because their contracts are buggy but because **their trust roots are external and human** —
exactly why the two-question lens puts "who authorizes the mint" first. Next candidates (distinct models):
**Axelar** (PoS validator set / separate chain) and a **native light-client** bridge (the most trust-
minimized end of the taxonomy).
