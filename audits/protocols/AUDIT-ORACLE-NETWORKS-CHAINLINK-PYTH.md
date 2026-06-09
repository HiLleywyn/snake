# Price oracles — opening the box every DeFi vertical trusts (Chainlink OCR vs Pyth/Wormhole)

**Scope.** The two dominant price-oracle networks — Chainlink (push/OCR median aggregator) and Pyth
(pull oracle over Wormhole). This is the deliberate companion to the governance dissection: every
prior audit in this corpus telescoped its dominant residual onto "the oracle," then deferred. **This
report opens that box.** Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found**; the two canonical *consumer-side* footguns
and the depeg-clamp behavior are characterized factually.

**Sources read (verbatim, line refs):** Chainlink — `OffchainAggregator.sol` +
`AccessControlledOffchainAggregator.sol` (OCR1, the live data-feed contract, sourced canonically from
`smartcontractkit/libocr` @ `c101335` after confirming the current `chainlink` monorepo **no longer
ships them**), `OCR2Base.sol` (`chainlink-evm` @ `b78bae5`). Pyth — `Pyth.sol`, `PythAccumulator.sol`,
`PythGovernance.sol`, `PythUpgradable.sol`, `wormhole-receiver/ReceiverMessages.sol`,
`ReceiverGovernance.sol`, `PythStructs.sol`/`AbstractPyth.sol` (`pyth-crosschain` @ `29239b2`).

*(Method note: the recon itself re-enacted the corpus's first law. The Chainlink aggregators are not
in the repo the docs point you at; trusting the monorepo's table of contents would have produced a
"can't find it" non-answer. Recomputing — going to libocr for the byte-source that actually ships —
is what made this audit possible. "Recompute, don't trust the summary" applied to a repo layout.)*

---

## 0. The one-paragraph result

Across ~50 audits the dominant residual was, again and again, "an oracle attests an off-chain number."
This report shows that **both** dominant oracle networks reduce to *exactly that* — a permissioned
quorum signs a number off-chain, and the on-chain contract only verifies signatures; **no price
discovery happens on-chain in either.** The two differ on *whose* quorum and *what shape* of number.
Chainlink: a **per-feed, owner-appointed set of `N` signer oracles** (`f+1` quorum) attests a **median**
computed off-chain; the contract verifies ECDSA sigs, checks the observations are sorted, takes the
middle, and **clamps it to an immutable `[minAnswer, maxAnswer]`**. Pyth: a **single global Wormhole
guardian set** (~13/19, 2/3+1) signs a Merkle root of Pythnet state; *any* user pulls a signed VAA
on-chain, pays a fee, and the contract verifies guardian sigs + a Merkle proof + the Pythnet emitter,
then exposes `price ± conf` (a **confidence interval**, not a median). The corpus-wide consequence is
twofold and sobering: **(1) the residual the whole corpus telescoped onto is itself a multisig** — for
Pyth, *one* ~13-key quorum sits under thousands of integrations on every EVM chain; for Chainlink, an
`onlyOwner` key rotates each feed's signer set. And **(2) both networks push the freshness/sanity
decision onto the *consumer*** — each ships an "unsafe / no-staleness" getter that is trivial to
misuse, and Chainlink's immutable depeg-clamp will *freeze a feed at the boundary* during a real
crash (the LUNA class). So the oracle law: *the universal residual bottoms out not in a proof but in a
signer quorum + a consumer who must check staleness, bounds, and confidence themselves — the oracle
is the most-trusted and most-deferred-to component in DeFi, and it is, mechanically, a multisig with a
footgun-shaped read API.*

---

## 1. Chainlink — a per-feed signer quorum attesting an off-chain median. **The trust root, dissected.**

`transmit()` (`OffchainAggregator.sol:576-712`) is the entire trust root, and it does four things:
```solidity
require(_rs.length > r.hotVars.threshold, "not enough signatures");                 // :625  f+1 quorum
require(r.observations.length > 2 * r.hotVars.threshold, "too few values...");      // :630
// ... each signature must ecrecover to a registered Signer, no duplicates:
address signer = ecrecover(h, uint8(r.vs[i])+27, _rs[i], _ss[i]);                   // :666
require(o.role == Role.Signer, "address not authorized to sign");                   // :668
require(!signed[o.index], "non-unique signature");                                  // :669
// ... observations must be sorted; the MEDIAN is the middle element:
int192 median = r.observations[r.observations.length/2];                            // :680
require(minAnswer <= median && median <= maxAnswer, "median is out of min-max range"); // :681
```
**That is all the chain does:** verify `f+1` distinct permissioned-signer ECDSA signatures over a
report, confirm the carried observations are sorted, take the middle, and clamp. The *price* — the
median of node observations — was computed **off-chain** by the OCR protocol; the contract never sees
the underlying data sources. OCR2 (`OCR2Base.sol:262-328`) is identical in spirit with quorum
`(n+f)/2+1` for unique reports, `MAX_NUM_ORACLES = 31`, and `n > 3f`. **The trust root is a quorum of
owner-appointed signers, full stop.**

---

## 2. Chainlink — the read path is a footgun, and the clamp is a depeg trap. **Consumer-side residuals.**

`latestRoundData()` (`:859-885`) returns the stored median with `startedAt == updatedAt ==
block.timestamp of the transmit tx` and `answeredInRound == roundId` always. **There is no on-chain
heartbeat or deviation enforcement in the read — nothing reverts on a stale feed.** The
heartbeat/deviation thresholds live entirely off-chain in node config; the nodes decide when to
`transmit`. The consumer-facing wrapper (`AccessControlledOffchainAggregator`) adds only read
*access control*, not freshness.

- **The canonical integration footgun (factual):** a consumer that calls `latestAnswer()`/
  `latestRoundData()` without itself asserting `updatedAt >= block.timestamp - maxAge` and `answer > 0`
  silently consumes an arbitrarily stale (or, on a fresh proxy, zero) price. This single mistake is
  behind a large fraction of real oracle-related incidents — and it is *by design*: the oracle exposes
  the data; **enforcing freshness is the integrator's job**, exactly the "residual telescopes onto the
  consumer" pattern.
- **The depeg clamp (factual, LUNA-class):** `minAnswer`/`maxAnswer` are **immutable** (`:57-59`). During
  a genuine depeg where the true price falls below `minAnswer`, `transmit()` **reverts at `:681`** —
  so the **last in-range price freezes** and every consumer keeps reading the clamp floor. This is the
  exact mechanism by which lending markets on BSC kept valuing LUNA near a floor while it traded far
  lower. The circuit-breaker that protects against a *spurious* zero becomes a *mispricing* during a
  *real* collapse. A protocol that trusts a Chainlink feed inherits this behavior whether it knows it
  or not.

---

## 3. Pyth — a single global guardian-set multisig + a Merkle root. **A broader trust root.**

Pyth is **pull-based**: prices are computed on Pythnet, the **Wormhole guardians** sign a Merkle root
of the price state into a VAA, and *any* user submits that VAA on-chain (`updatePriceFeeds():64-79`,
paying a fee `:77-78`). The contract verifies three things — the VAA's guardian signatures, the
Pythnet emitter, and a Merkle proof of the individual price:
```solidity
(vm, valid, ) = wormhole().parseAndVerifyVM(encodedVm);                         // PythAccumulator:38
if (!isValidDataSource(vm.emitterChainId, vm.emitterAddress)) revert ...;       // :43  must be Pythnet
(valid, endOffset) = MerkleTree.isProofValid(encoded, offset, digest, message); // :308 per-price proof
```
The actual trust root is `ReceiverMessages.parseAndVerifyVM` — guardian quorum `2/3+1`:
```solidity
function quorumThreshold(uint numGuardians) ... { return (((numGuardians*10)/3)*2)/10 + 1; } // :22-27
if (quorumThreshold(guardianSet.keys.length) > signersLen) return (vm, false, "no quorum");   // :148
// each sig ecrecovers to the guardian key at its index, indices strictly ascending (:252-271)
```
**Characterization:** with 19 guardians, quorum = 13. Compromise or collusion of 13 guardian keys
**forges any Pyth price on every EVM chain at once.** This is a *different and broader* assumption than
Chainlink's per-feed signer set: it is **one global multisig under all Pyth feeds and all integrating
protocols simultaneously.** The thing the entire corpus deferred to, for Pyth integrators, is a single
13-of-19.

---

## 4. Pyth — confidence interval + the same staleness footgun. **Consumer-side residuals.**

The `Price` struct is `{int64 price, uint64 conf, int32 expo, uint publishTime}` — Pyth returns a
**confidence interval** `price ± conf`, not a single point, because it is an aggregate signed once on
Pythnet rather than an on-chain median of `N` observations. `getPriceNoOlderThan(id, age)` checks
staleness (`AbstractPyth.sol:54-57`), **but `getPriceUnsafe()` does not** (`Pyth.sol:184-194`,
`publishTime == 0` only reverts as "not found"); updates are monotonic last-writer-by-publishTime
(`PythSetters.sol:19`).

- **Footgun (factual):** `getPriceUnsafe`/`getEmaPriceUnsafe` perform **no** staleness check — a
  consumer must use `getPriceNoOlderThan`. And because Pyth is pull-based, a price is only as fresh as
  the `updatePriceFeeds` in the *same transaction*; a consumer that reads without a fresh push, or that
  **ignores `conf`** (trusting `price` when the confidence band is huge during volatility), is trusting
  a stale or low-confidence value. The mitigation Pyth offers — *use `conf`* — is, again, the
  *consumer's* responsibility.

---

## 5. Governance — `onlyOwner` (Chainlink) vs guardian-VAA (Pyth)

- **Chainlink:** `setConfig` (`:161-224`) is a plain **`onlyOwner`** call that installs the entire
  signer set, transmitter set, and `f`. A single owner key rotates each feed's quorum. The depeg clamp
  is immutable (set in constructor) — to change it you redeploy.
- **Pyth:** governance is itself a **Wormhole governance VAA** (`PythGovernance.executeGovernanceInstruction
  :64-111`: `UpgradeContract`, `SetDataSources`, `SetFee`, `SetWormholeAddress`, …), with monotonic
  sequence anti-replay (`:56`); the Solidity `owner` is **`renounceOwnership()`'d** in
  `PythUpgradable.initialize:47`, so even **contract upgrades** run through the guardian-signed VAA, not
  a live admin key. Guardian-set rotation is also VAA-governed — the **current set authorizes its own
  successor** (`ReceiverGovernance.submitNewGuardianSet:48`). More decentralized *in form*, but rooted
  in the same quorum that signs prices: **for Pyth, the price signer, the upgrader, and the governor are
  the same guardian set.**

---

## 6. Where this sits in the corpus — the residual bottoms out in a multisig

This closes the **oracle** coordinate the way §5f closed the governance ceiling. The capstone's
"seven oracle types" (cryptographic-proof ↔ keeper-clamp ↔ optimistic ↔ token-vote ↔ trusted-feed ↔
self-token-fork ↔ committee-attested) all have, at the bottom, *this*: a **permissioned signer quorum
attesting an off-chain number**, plus a **consumer obligation** to check freshness/bounds/confidence.

| | Chainlink | Pyth |
|---|---|---|
| **Trust root** | per-feed `f+1` owner-appointed signer quorum, off-chain **median** | one global Wormhole guardian set (~13/19), off-chain Merkle root, `price ± conf` |
| **Push/pull** | nodes push (heartbeat off-chain, invisible) | consumer pulls + pays fee (freshness per-tx) |
| **Consumer must check** | `updatedAt` staleness + `answer>0` | `getPriceNoOlderThan` + respect `conf` |
| **Depeg behavior** | immutable `minAnswer/maxAnswer` **freezes at clamp** | no clamp; `conf` widens |
| **Governance** | `onlyOwner setConfig` per feed | guardian-VAA (owner renounced); same set signs price+upgrade+governance |

**The sharpened, corpus-closing law:** the universal residual every vertical telescoped onto does *not*
bottom out in a proof or an identity — it bottoms out in a **signer quorum and a footgun-shaped read
API**. Two practical consequences for every prior audit: *(a) "the oracle" is a multisig* — for Pyth, a
single ~13-key set sits beneath the conservation floors of lending, perps, stablecoins, and prediction
markets alike, so the "dominant residual" of dozens of protocols is *correlated* through one quorum;
and *(b) half the oracle's safety is not in the oracle* — it is in whether the integrating contract
checks staleness, bounds, and confidence. A complete protocol audit must therefore include the
consumer-side oracle read (the `updatedAt`/`conf`/min-max handling), because that is where the oracle's
deferred trust actually lands. This is why the corpus kept deferring to "the oracle" and was right to
name it the residual — *and* why naming it was never enough: the residual has an interface the
protocol itself must use correctly.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
