# Liquid staking — the base of the staking stack (Lido stETH vs Rocket Pool rETH)

**Scope.** The two dominant liquid-staking tokens: Lido `stETH` (rebasing shares) and Rocket Pool
`rETH` (non-rebasing exchange-rate). This completes the staking stack the corpus already touched from
the top — **validator → LST (here) → restaking/LRT (the EigenLayer/ether.fi audit)** — and isolates the
LST-specific residual. Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found**; the cross-protocol residuals are
characterized factually.

**Sources read (verbatim, line refs):** Lido `StETH.sol`, `Lido.sol`, `Accounting.sol`,
`AccountingOracle.sol`, `HashConsensus.sol`, `OracleReportSanityChecker.sol`, `StakingRouter.sol`,
`WithdrawalQueue*.sol`, `NodeOperatorsRegistry.sol` (`lidofinance/core` @ `eb4ff80`, post-Accounting
refactor); Rocket Pool `RocketTokenRETH.sol`, `RocketNetworkBalances.sol`,
`RocketDAOProtocolSettingsNetwork.sol`, `RocketMinipoolManager.sol`, `RocketNodeDeposit/Staking.sol`,
`RocketStorage.sol` (`rocket-pool/rocketpool` @ `fef41a4`, Saturn/megapool branch).

---

## 0. The one-paragraph result

An LST is a **share/exchange-rate claim on ETH that is mostly staked off-chain on the beacon chain** —
so its entire peg rests on a number the contract *cannot see*: the validators' consensus-layer
balance. Both protocols conserve cleanly *given* that number (Lido: `balanceOf = shares ·
totalPooledEther / totalShares`; Rocket Pool: `ethValue = rethAmount · totalETH / totalRETHSupply`), and
both bound how fast it can move per report. The dominant residual is therefore identical in *kind* and
is the **same shape as the EigenLayer-LRT layer above it and the Chainlink/Pyth oracles beside it**: a
**permissioned committee attests an off-chain validator balance**, and that attested number sets every
holder's value. The two differ on three axes that together define the LST design space: **(1) floor
shape** — Lido *rebases* (balances move, slashing is **socialized** across all holders via a downward
rebase) vs Rocket Pool's *fixed-balance exchange rate* (rETH holders are insulated by node-operator
**ETH bond + RPL** first-loss collateral); **(2) withdrawal-credential trust** — Lido points *all*
validators at *one protocol-controlled* credential (operators can't abscond, but a credential-role
compromise is systemic) vs Rocket Pool's *per-minipool* operator-controlled credential (recovered via
bond/minipool logic); and **(3) the same beacon-oracle residual**, bounded by per-report sanity limits
(Lido annual-increase + negative-rebase second-opinion; RP 2% max-delta + frequency gate). And — the
point every LST audit must make loudest — **the thing users actually fear, the secondary-market
depeg, lives *outside* these contracts entirely**: both define only the *primary* mint/redeem rate; the
traded stETH/rETH price on AMMs is a market phenomenon, not a contract invariant. So the LST law: *the
floor conserves against an oracle-reported beacon balance; the residual is that committee plus the
node operators plus the governance that can swap them; and the headline risk (depeg) is a market fact
the contracts neither cause nor prevent.*

---

## 1. The conservation floor — rebasing shares (Lido) vs exchange rate (Rocket Pool). **Sound in both.**

**Lido (`StETH.sol`) — rebasing shares.** `balanceOf(a) = getPooledEthByShares(sharesOf(a))` and
`totalSupply() = _getTotalPooledEther() (:158)`. The redeemable rate is `totalPooledEther/totalShares`
(`:317-334,410-421`). Crucially `_getTotalPooledEther` *includes the off-chain CL balance*
(`Lido.sol:1043-1053`: `bufferedEther + clBalance + transientEther`), and **`clBalance` is
oracle-supplied** — that is the residual, baked directly into every balance.

**Rocket Pool (`RocketTokenRETH.sol`) — non-rebasing exchange rate.** Balances are fixed; value accrues
via `getExchangeRate = getEthValue(1 ether)` where `ethValue = rethAmount · totalETHBalance /
rethSupply (:39-47)`, with `totalETHBalance` from `RocketNetworkBalances`. On-demand `burn` only
succeeds against *liquid* collateral (`require(getTotalCollateral() >= ethAmount) :113-114`, =
deposit-pool excess + the rETH contract's ETH) — **larger redemptions wait for collateral; instant
1:1 exit is not contract-guaranteed.**

**Verdict:** both conserve by construction *relative to the reported beacon balance*. The floor is not
where the risk is — the reported number is.

---

## 2. The dominant residual — a beacon-balance oracle committee. **Same shape, top to bottom of the stack.**

**Lido:** the CL balance is written only through the oracle path. `Lido.processClStateUpdate
(:803-818)` is gated to the Accounting contract; `Accounting.handleOracleReport (:127-134)` is gated to
`accountingOracle`; `AccountingOracle.submitReportData (:335)` is fed by a **HashConsensus quorum**
(`HashConsensus.sol:945` — `support >= _quorum` → consensus). **Sanity bounds**
(`OracleReportSanityChecker.sol`): an **annual CL-balance-increase limit**
(`:755-762 annualBalanceIncrease > annualBalanceIncreaseBPLimit → revert`) and a **negative-rebase
limit with second-opinion-oracle escalation** (`:702-735`). A permissioned committee's number,
bounded per report.

**Rocket Pool:** `RocketNetworkBalances.submitBalances (:81-112)` is `onlyTrustedNode` (oDAO members);
once `submissionCount/memberCount >= getNodeConsensusThreshold()` (`:109`, **51%** floor-enforced) the
rate updates, bounded by a **per-update max-delta** (`_updateBalances:148-158`, `max.reth.balance.delta`
default **2%**, RPIP-61) and a min-time gate. A permissioned **oDAO** quorum's number, bounded per
report.

**Characterization (the stack-spanning observation):** this is *mechanically the same residual* as
(a) the ether.fi LRT rate above it (committee + APR band), and (b) the Chainlink/Pyth oracles beside
it (signer quorum + sanity bound). **The off-chain-balance-attestation residual recurs at every layer
of the staking stack and is the universal DeFi residual in another costume.** Sanity bounds cap
per-report manipulation; they do not remove the trust.

---

## 3. The two design-axis splits — slashing socialization & withdrawal credentials

**Slashing / loss handling (the floor-shape consequence):**
- **Lido socializes.** A validator penalty/slash arrives as a *lower reported `clBalance`* → a
  **downward rebase** → every stETH holder's `balanceOf` drops pro-rata (the negative-CL-rebase sanity
  path gates how much per report). Holders are the uninsured loss-bearer of record.
- **Rocket Pool insulates rETH with operator collateral.** Node operators post an **ETH bond**
  (`RocketNodeDeposit:141-145`) + stake **RPL** as junior collateral (`RocketNodeStaking.stakeRPL
  :168-198`); a misbehaving/slashed operator's bond+RPL is hit **before** rETH value. This is the key
  trust difference: Lido holders take slashing directly; rETH holders sit behind first-loss capital.

**Withdrawal-credential trust (inverts between the two):**
- **Lido:** one **protocol-controlled** credential for *all* validators (`StakingRouter:1193-1194`,
  role-changeable at `:1230`). Operators **cannot abscond** with exited ETH (it returns to the protocol
  vault) — but a `MANAGE_WITHDRAWAL_CREDENTIALS_ROLE` compromise is **systemic across every validator**.
- **Rocket Pool:** **per-minipool** credentials pointing at the operator's own contract
  (`RocketMinipoolManager:253-254`, `0x01..minipoolAddress`). The protocol recovers its share via
  minipool/bond logic, not by owning the credential — distributing the trust but relying on the bond
  economics and minipool contract correctness.

---

## 4. Governance ceiling — upgradeable root admin in both

- **Lido:** Aragon ACL — every privileged action is `_auth(role) → canPerform` (`Lido.sol:1157-1166`);
  roles include `PAUSE_ROLE`, `STAKING_CONTROL_ROLE`, `MANAGE_WITHDRAWAL_CREDENTIALS_ROLE`. Contracts
  are upgradeable Aragon-app proxies. **The DAO/Agent can change the oracle set, sanity limits, the node
  -operator registry, fees, and the withdrawal credentials** — a high ceiling.
- **Rocket Pool:** eternal-storage proxy — all state in `RocketStorage`, writable only by registered
  network contracts (`onlyLatestRocketNetworkContract:41-53`); upgrades = re-pointing `contract.address`
  keys (the **pDAO** holds upgrade power, the **oDAO** holds the rate-oracle + penalty power, a deploy
  -time **guardian** is a residual bootstrap admin).

Per the §5f governance dissection, both ceilings are "a DAO vote + (Aragon/RocketStorage) upgrade
key" — the LST's safety is ultimately bounded by that governance, sitting *above* the oracle residual.

---

## 5. Where this sits in the corpus — and the depeg point every LST audit must lead with

The LST completes the staking stack and confirms the residual is *layered and correlated*: **validator
honesty → (beacon-balance oracle) → LST rate → (LST oracle again, for an LRT) → restaked position.**
The same committee-attests-an-off-chain-number residual appears at *every* rung, and an integrator
stacking LRT-on-LST-on-validator inherits *all* of them.

**The factual point that dominates LST risk, stated plainly:** the secondary-market **depeg** — the
thing users actually experience (stETH trading at 0.94 ETH in June 2022) — is **outside these
contracts**. Both define only the *primary* mint/redeem rate against the oracle-reported balance;
neither enforces the AMM price, and neither *can*. A depeg is a liquidity/market event (redemption
queues, withdrawal delays, leverage unwinds), **not** a violation of any on-chain invariant audited
here. This is the cleanest example in the corpus of a risk that is *real, severe, and entirely
non-contractual* — and an audit that only verified the share math while implying "therefore safe"
would be technically correct and practically misleading. The honest statement: *the floor conserves
against an oracle-reported beacon balance; redemption is queue/collateral-gated, not instant; slashing
is socialized (Lido) or bonded (RP); and the depeg you fear is a market fact the contracts neither
cause nor prevent.*

**Factual concerns flagged (defensive, no exploit):** (1) both — the beacon-balance oracle committee is
the dominant residual; sanity bounds (Lido annual-increase/negative-rebase + second-opinion; RP 2%
max-delta) cap but do not remove it. (2) Lido — a `MANAGE_WITHDRAWAL_CREDENTIALS_ROLE` compromise is
systemic; slashing socializes into holder balances. (3) Rocket Pool — `burn` is collateral-gated, so
on-chain instant redemption is not guaranteed under low collateral. (4) both — upgradeable root admin
(Aragon ACL / RocketStorage) can swap the oracle set and sanity bounds; that governance is the trust
anchor above the oracle.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
