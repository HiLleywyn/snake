# Restaking & LRTs — EigenLayer core + ether.fi liquid-restaking trust map

**Scope.** EigenLayer restaking core (`Layr-Labs/eigenlayer-contracts` @ `f84a515`,
Solidity ^0.8.27, BUSL-1.1) and a liquid-restaking token built on it (`etherfi-protocol/
smart-contracts` @ `a816695`). Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found** — two factual concerns are flagged
for the teams' own attention, defensively, with no exploit developed.

**Sources read (verbatim, line refs against those checkouts):** `StrategyBase.sol`,
`StrategyManager.sol`, `DelegationManager.sol` (+ `DelegationManagerStorage.sol`),
`AllocationManager.sol`, `EigenPod.sol`, `Pausable.sol`; ether.fi `LiquidityPool.sol`,
`EETH.sol`, `EtherFiAdmin.sol`, `EtherFiOracle.sol`, `EtherFiRestaker.sol`.

---

## 0. The one-paragraph result

Restaking adds a genuinely **new residual** that none of the prior verticals had: **slashing**
— stake that can be *destroyed* by a third party (an AVS's slasher) as the price of the yield.
The conservation floor underneath is a clean, well-mitigated ERC4626-style share vault
(`(balance+1e3)/(shares+1e3)` price with the virtual-shares inflation guard); it conserves. But
above it sit three residuals stacked in series: **(1)** the AVS-designated **slasher** can burn
up to 100% of an operator's *allocated magnitude* per strategy/operator-set, propagated
pro-rata to every delegated staker; **(2)** the **withdrawal queue** keeps exiting funds
slashable for a fixed immutable delay (~14 days), so you bear slashing that lands after you
queue; and **(3)** the **beacon-chain proof** anchors the whole thing to Ethereum's EIP-4788
block-root predeploy. An LRT (ether.fi) then wraps all of that in a *second* trust layer: its
eETH exchange rate is **not derived on-chain** — it is pushed by a permissioned oracle
committee, guarded only by a single APR-band sanity check the code itself documents as
temporary. So restaking's trust map is: *sound conservation floor → slashing ceiling (new) →
withdrawal-delay liquidity seam → beacon-proof oracle → (for LRTs) an off-chain rate oracle on
top.*

---

## 1. The conservation floor — ERC4626 share vault, inflation-mitigated. **Sound.**

`StrategyBase.sol` is a non-tokenized ERC4626-style vault, one per strategy. Share price is
bounded by virtual offsets (`StrategyBase.sol:38,42`):
```solidity
uint256 internal constant SHARES_OFFSET = 1e3;
uint256 internal constant BALANCE_OFFSET = 1e3;
```
Deposit (`:110-122`) computes `newShares = amount · (priorTotalShares+1e3) / (priorTokenBalance+1e3)`
and **reverts `NewSharesZero()` (`:118`)** — the explicit neutralization of the first-depositor
donation/inflation attack (cost: small acknowledged rounding losses, header `:22-28`). The view
functions (`sharesToUnderlyingView :218-226`, `underlyingToSharesView :236-244`) use the same
`(balance+1e3)/(shares+1e3)` ratio, and withdraw mirrors it. `StrategyManager` holds only the
**share ledger** (`_addShares :261-286`, `_removeDepositShares :328-357`); the underlying lives
in the strategy. **Verdict: conserves; the canonical inflation vector is closed by construction.**
This is the strongest member of the conservation-ladder family — a share-price identity with a
zero-share revert guard.

---

## 2. The slashing ceiling — the restaking-specific residual. **Disclosed, bounded, new.**

This is the thing restaking introduces that lending/perps/prediction-markets do not have:
**a third party can destroy your principal.** `AllocationManager.slashOperator` (`:61-75`) is
callable **only by `getSlasher(operatorSet)` (`:72`)** — the AVS-designated slasher. The bound
is `0 < wadsToSlash[i] ≤ WAD` (`:428`), i.e. up to 100%. The math (`_slashOperator :410-499`):
```solidity
slashedMagnitude = currentMagnitude.mulWadRoundUp(wadsToSlash[i]);   // :449
allocation.currentMagnitude   -= slashedMagnitude;                    // :453
info.maxMagnitude             -= slashedMagnitude;                    // :454
shares[i] = delegation.slashOperatorShares({... prevMaxMagnitude, newMaxMagnitude});  // :488
```
The staker consequence is in `DelegationManager.slashOperatorShares (:279-319)`: operator (and
all delegated stakers') shares are scaled by `newMaxMagnitude/prevMaxMagnitude`, and the cut
**reaches into the withdrawal queue** (`_getSlashableSharesInQueue :293-298`), then is
burned/redistributed (`:315-316`).

**Characterization:** slashing is *bounded* (≤100% of the operator's **allocated magnitude** for
that specific strategy/operator-set — not the whole stake unless fully allocated), *attributable*
(per operator-set), and *trust-anchored on the AVS slasher address*. The honest user statement is
not "your stake is safe" but **"your stake is safe up to the slashing conditions of every AVS your
operator has opted into, each of which holds a key that can burn your allocated magnitude."** That
is the deliberate price of shared security — a real ceiling, correctly bounded in code, not a bug.

---

## 3. The withdrawal-delay seam — security-vs-liquidity. **Fixed immutable.**

`DelegationManager.queueWithdrawals (:176-201)` decrements shares **immediately** but marks the
entry still-slashable (`_addQueuedSlashableShares :484`, records `startBlock :513`).
`_completeQueuedWithdrawal (:535-617)` gates on the delay:
```solidity
uint32 slashableUntil = withdrawal.startBlock + MIN_WITHDRAWAL_DELAY_BLOCKS;   // :549
require(uint32(block.number) > slashableUntil, WithdrawalDelayNotElapsed());   // :550
```
and re-multiplies the exiting shares by the **slashing factor captured at `slashableUntil`**
(`:554-581`) — so any slashing during the window hits the leaver. `MIN_WITHDRAWAL_DELAY_BLOCKS`
is an **immutable set at construction** (`DelegationManagerStorage.sol:51`, assigned `:129`,
mainnet ≈ 100800 blocks ≈ 14 days), changeable only by upgrade. **Characterization:** the dominant
*liquidity* residual — funds are illiquid and slashable for the full delay; not governance-tunable.

---

## 4. The beacon-chain proof — cryptographic, not a price oracle. **Anchored on EIP-4788.**

`EigenPod.verifyWithdrawalCredentials (:189-236, onlyOwnerOrProofSubmitter)` Merkle-verifies
validator fields against the beacon state root obtained from the **EIP-4788 predeploy**
(`BEACON_ROOTS_ADDRESS = 0x000F3df6…Beac02`, `:36`, read in `getParentBlockRoot :736-745` with an
8192-slot history bound). Checkpoints (`verifyCheckpointProofs`) and `verifyStaleBalance (:239)`
are **permissionless** (intended liveness). **Characterization:** unlike every prior vertical,
the "oracle" here is **cryptographic proof against Ethereum consensus state**, not an attested
price — trust = correctness of EIP-4788 + the `BeaconChainProofs` Merkle library, not a quorum or
a feed. The least-discretion oracle of the whole corpus.

---

## 5. The LRT layer (ether.fi) — a *second*, weaker oracle on top. **The added residual.**

eETH is a rebasing share token (`EETH.sol:21-22`). The exchange rate (`LiquidityPool.sol`):
```solidity
getTotalPooledEther() = totalValueOutOfLp + totalValueInLp;   // :569-570
sharesForAmount  = amount · totalShares / totalPooledEther;    // :573
amountForShare   = share · totalPooledEther / totalShares;     // :593
```
Withdraw uses **ceiling division** (rounding favors protocol, `:582-591`) and is liquidity-gated
(`require(totalValueInLp ≥ amount) :222`). The rate moves **only** via `totalValueOutOfLp`, set by
`rebase` (`:440-442`, `onlyMembershipManager`), fed from an **oracle committee quorum**
(`EtherFiOracle.submitReport :72-107`, consensus at `support ≥ quorumSize :99`). The **only**
on-chain guard against a bad report is an APR band (`EtherFiAdmin._handleAccruedRewards :237-260`):
```solidity
apr = 10000 * (accruedRewards * 365 days) / (currentTVL * elapsedTime);   // :254
require(absApr <= acceptableRebaseAprInBps, "TVL changed too much");      // :257
```

**Characterization:** the LRT replaces EigenLayer's *cryptographic* balance proof with an
**off-chain attested rate**. Crucially, ether.fi's own share price has **no virtual-shares
inflation offset** (unlike `StrategyBase`); its correctness rests entirely on the committee +
the single APR band — which the code itself documents as temporary (`EtherFiAdmin.sol:246`). This
is the dominant LRT residual: *you trust the rate oracle, bounded only by a sanity band slated for
removal.* Governance is role-gated (`RoleRegistry`), committee/quorum owner-controlled
(`EtherFiOracle.sol:232-272`), all UUPS proxies behind an `EtherFiTimelock`.

**Two factual concerns flagged for the team (defensive, no exploit):**
1. **No self-contained inflation/price guard on eETH** — rate integrity is fully oracle-dependent,
   and the one on-chain check (`acceptableRebaseAprInBps`) is documented as temporary
   (`EtherFiAdmin.sol:246-257`). Worth a permanent invariant.
2. **APR guard divides by `elapsedTime`** (`:254`) — if a report path ever reaches it with
   `elapsedSlots == 0`, that's a divide-by-zero; worth confirming the report-cadence invariant
   structurally prevents it rather than relying on operator discipline.

---

## 6. Governance ceiling

- **EigenLayer:** asymmetric pause (`Pausable.sol` — 256-bit bitmap; `pause :93-100` `onlyPauser`
  can only *set* bits, `unpause :108-116` `onlyUnpauser`), strategy whitelister
  (`StrategyManager :225-250`), and **upgrade keys** behind transparent/UUPS proxies (`__gap` at
  `StrategyBase.sol:293`) — the practical ceiling is the ProxyAdmin owner (Eigen multisig +
  timelock).
- **ether.fi:** role-gated admin/restaking ops, owner-set committee + quorum, UUPS upgradeable
  behind a timelock. The restaking position itself (`EtherFiRestaker` delegate/queue/complete,
  all `onlyAdmin`) inherits EigenLayer's ~14-day slashable delay, so eETH redemption liveness =
  EigenLayer delay + LP liquidity gate.

---

## 7. Where this sits in the corpus

Restaking extends the methodology's residual taxonomy with a **fourth residual class** the L1/
rollup/prediction-market/lending work never exercised: **destructible principal (slashing)**.
Conservation floors (CTF, share vaults) answer "can the system always pay what it owes"; slashing
answers a different question — "can a third party deliberately reduce what you are owed" — and the
answer is *yes, by design, bounded and attributable*. The trust gradient also inverts the prior
oracle finding: EigenLayer's base "oracle" is the **most** trustless of the entire corpus (a
cryptographic beacon-state proof), yet the LRT built on top reintroduces a **committee-attested
rate** as the weakest link — a clean demonstration that *the residual migrates to whatever layer
re-tokenizes the position*, and that wrapping a trustless primitive in a liquid token can lower,
not raise, the trust floor.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
