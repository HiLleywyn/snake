# NFT-finance lending — three liquidation philosophies for illiquid collateral (BendDAO · NFTfi · Blend)

**Scope.** Three NFT-lending designs chosen to disagree on the hardest question in the domain —
**how do you liquidate collateral that has no reliable price?** BendDAO (`/tmp/bend` @ `81c90c0`,
pool, oracle-priced, English auction), NFTfi (`/tmp/nftfi` V2-3 @ `d7cc689`, peer-to-peer fixed-term,
no oracle), and Blur **Blend** (`/tmp/blend` @ `d112a70`, code-423n4 2023-04 drop; peer-to-peer
perpetual, **oracle-free**, Dutch interest-rate auction). Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**;
factual concerns flagged for context.

**Sources read (verbatim, line refs against those checkouts):** BendDAO `LendPoolLoan.sol`,
`LiquidateLogic.sol`, `GenericLogic.sol`, `ReserveLogic.sol`, `NFTOracle.sol`, `DataTypes.sol`;
NFTfi `DirectLoanBaseMinimal.sol`, `DirectLoanFixedOffer.sol`, `LoanData.sol`, `BaseLoan.sol`;
Blend `Blend.sol`, `CalculationHelpers.sol`, `Signatures.sol`, `Structs.sol`.

---

## 0. The one-paragraph result

NFT lending is the domain where the **price oracle is hardest** — the collateral is illiquid, the
"floor price" is a thin and manipulable signal — so the three protocols are best understood as three
*answers to the oracle problem*, and the answer determines everything else about the design. BendDAO
**leans into** the oracle: a pool prices every loan against a single admin-pushed collection floor and
liquidates underwater positions via an English auction with a borrower-redeem grace window — maximal
capital efficiency, but the **oracle is the single largest trust point** and thin-market liquidation
liveness is a real concern. NFTfi **refuses** the oracle: bilateral, fixed-term, EIP-712-signed loans
with no LTV and no valuation; "liquidation" is just the lender seizing the NFT at maturity, with all
value risk on the lender and **zero protocol bad debt**. Blend **replaces** the oracle with a market:
a perpetual loan whose lender exits by auctioning the *interest rate* upward until someone refinances —
the NFT is "underwater" precisely when no one will lend against it even at ~1000% APR, at which point
the lender seizes. So the NFT-lending law is: *price-oracle risk and liquidation design are the same
decision; you can pay for the oracle (BendDAO), avoid it bilaterally (NFTfi), or let an auction
discover it (Blend) — and each choice relocates the residual to a different place (admin feed vs lender
diligence vs upgrade key).*

---

## 1. The three floors — all bilateral-solvent, none socialize except BendDAO's pool

| | BendDAO | NFTfi | Blend |
|---|---|---|---|
| **Structure** | Pool (Aave-fork), bNFT escrow | P2P bilateral escrow, fixed term | P2P perpetual, hash-committed lien |
| **Debt accounting** | scaled amount ÷ borrowIndex (RAY) | fixed `maximumRepaymentAmount` | continuous `amount·e^(rate·t)` |
| **Loss-bearer on default** | pool/LPs absorb shortfall if bid < debt | the two counterparties only | the lender only |

- **BendDAO floor** is Aave-style scaled-share/index accounting: debt stored as `amountScaled =
  amount.rayDiv(borrowIndex) (LendPoolLoan.sol:97)`, real NFT escrowed + bNFT receipt minted
  (`:105-107`), liquidity/utilization re-derived on every state change
  (`ReserveLogic.updateInterestRates :177-214`, debt = `scaledTotalSupply.rayMul(index) :189-191`).
  This is the only one of the three with a *pool* that can take **socialized bad debt**.
- **NFTfi floor** is pure bilateral escrow: loan terms fixed at origination (`LoanData.sol:42-54`),
  lender→borrower principal at start (`DirectLoanBaseMinimal.sol:902`), escrow counters isolate
  collateral from admin reach (`drainERC20Airdrop` guard `:394`). Conserve-by-isolation: no pool, no
  socialization.
- **Blend floor** is a hash-committed lien — state is just `liens[id] = keccak256(abi.encode(lien))
  (Blend.sol:119)`, preimage re-validated on every call (`_validateLien :981-983`); debt compounds
  continuously with a 2-hour minimum-interest floor (`CalculationHelpers.sol:19-34`). Again no pool,
  no socialization.

---

## 2. The three liquidation engines — the heart of the contrast

**BendDAO — oracle-triggered English auction (3 phases).** Health-factor `< 1` against the floor
oracle opens it. `executeAuction (LiquidateLogic.sol:123-221)`: first bid requires
`borrowAmount > thresholdPrice (:166)` (HF below 1) and must cover debt + liquidatePrice; later bids
beat prior by ≥1% (`:187`). `executeRedeem (:248-361)`: borrower buys back during a grace window,
repaying ≥`redeemThreshold`% (`:311`) plus a bid fine to the first bidder (`:342`). `executeLiquidate
(:384-486)`: only after the window (`:415`); **surplus `bidPrice − borrowAmount` returns to the
borrower (:438,467)**, NFT to the winning bidder (`:472`); if the bid can't cover debt the liquidator
tops up `extraDebtAmount (:432)`. Liquidate-price math: `thresholdPrice = nftPrice·liquidationThreshold`,
`liquidatePrice = nftPrice·(1−bonus)` floored to ≥ debt (`GenericLogic.sol:215-267`).

**NFTfi — lender-only seizure, no auction, no price.** `liquidateOverdueLoan
(DirectLoanBaseMinimal.sol:617-656)`: after `loanStartTime + loanDuration`, **only the lender** (`:637`)
takes the whole NFT and forfeits the principal claim. Repay (`payBackLoan :546`, `_payBackLoanSafe
:1016-1089`) is a fixed `maximumRepaymentAmount` with a USDC-blacklist fallback to escrow so the
borrower always recovers the NFT (`:1030`). CEI flag `loanRepaidOrLiquidated = true (:1129)` guards
double-resolve. **No auction, no surplus, loss isolated to the two parties.**

**Blend — rising-rate Dutch *refinance* auction → seize.** A lender exits by auctioning the **interest
rate**, never the price. `startAuction (Blend.sol:214-245, lender-only)` records `auctionStartBlock`.
`refinanceAuction (:328-374)`: **anyone** takes over the loan at any `rate ≤ rateLimit`, where
`rateLimit` **rises over time** via `calcRefinancingAuctionRate (CalculationHelpers.sol:43-94)` up to
`_LIQUIDATION_THRESHOLD = 100000` bps; the new lender pays off the old at current debt and the
borrower's position continues seamlessly. `seize (:251-283)` only if `_lienIsDefaulted` — auction
started AND `auctionStartBlock + auctionDuration < block.number (:986-990)`, i.e. **no refinancer
accepted even at the max rate**. The lender then takes the NFT; loss is solely theirs. **The auction
*is* the price-discovery; no feed exists.**

---

## 3. The oracle seam — lean in / refuse / replace

- **BendDAO — `NFTOracle` push oracle (the single largest trust point).** `getAssetPrice` returns a
  TWAP or last pushed price (`:245-255`); prices are pushed by **one `priceFeedAdmin`** via
  `setAssetData`/`setMultipleAssetsData` (`onlyAdmin :186-204`). Guards (`checkValidityOfPrice
  :355-384`) reject per-update deviation `> maxPriceDeviation`, too-frequent updates, and time-windowed
  deviation — these blunt single-tx spoofing but **do not defend a compromised/incorrect admin feed or
  sustained floor mispricing**, and collection floor price is itself a thin, manipulable signal for
  illiquid NFTs. This is the classic NFT-lending residual (cf. BendDAO's historically observed
  near-bad-debt episode when floor crashes outran liquidations). Auditor focus: **oracle key custody +
  deviation-parameter governance.**
- **NFTfi — no oracle at all.** No LTV, no on-chain valuation; terms are bilaterally agreed off-chain
  and EIP-712 signed. Value risk is **entirely the lender's** underwriting.
- **Blend — no *price* oracle by design.** The `oracle` field in offers is only an off-chain
  **order-authorization co-signer** (anti-fraud / blocklist), verified in
  `Signatures._verifyOfferAuthorization (:232-268)` and expiring after `blockRange` blocks. Price
  discovery is the rising-rate auction itself. **The oracle attack surface is removed; the residual
  moves to lender vigilance** (an inattentive lender simply accrues a perpetual loan and must actively
  `startAuction` to exit).

---

## 4. Governance ceiling — inversely proportional to how much the design trusts the market

- **BendDAO — high.** `LendPoolConfigurator (onlyPoolAdmin)` sets per-collection LTV / liquidation
  threshold / bonus (`:239-263`), reserve factor, IRM, redeem threshold, bid fine, and can **upgrade
  BToken/DebtToken implementations (:79-90)**; `onlyEmergencyAdmin` can pause (`:370`); oracle owner +
  `priceFeedAdmin` solely control prices. Whole protocol behind `BendUpgradeableProxy`. The ceiling is
  pool admin (all risk params + token-impl upgrades) **and** the oracle key.
- **NFTfi — modest.** `Ownable, Pausable`; owner sets fees/permits/max-duration and can `drainERC20
  Airdrop` (guarded against escrowed collateral `:384`), but **cannot pause repay/liquidate** (deliberate
  — prevents holding collateral hostage) and cannot alter live loan terms. Not upgradeable.
- **Blend — narrow operationally, absolute via upgrade.** UUPS proxy; `_authorizeUpgrade` is
  `onlyOwner (:26)` — **owner can replace the entire settlement implementation.** Otherwise owner only
  approves order co-signers (`setOracle :102`) and `setBlockRange`. No pause, no per-loan control, no
  ability to touch live liens. **The chief residual is the upgrade key.**

---

## 5. Where this sits in the corpus — and the sharpened law

NFT lending is the cleanest demonstration yet of a corpus-wide pattern: **the oracle choice and the
liquidation design are one decision, and the residual is conserved — it only moves.**

| Design | Oracle stance | Liquidation | Where the residual lands | Bad debt |
|---|---|---|---|---|
| **BendDAO** | lean in (admin floor feed) | oracle-triggered English auction + redeem grace | **oracle key + thin-floor manipulation + auction liveness** | pool/LPs socialize |
| **NFTfi** | refuse (bilateral, no LTV) | lender seizes at maturity | **lender underwriting** (no protocol risk) | none (bilateral) |
| **Blend** | replace (auction discovers price) | rising-rate Dutch refinance → seize | **lender vigilance + UUPS upgrade key** | none (lender's loss) |

This both specializes the prediction-market floor taxonomy (BendDAO is a *reserve/index pool* that
*can* socialize loss; NFTfi/Blend are *bilateral* — a floor family with **no house and no pool risk at
all**) and adds a distinct lesson the fungible-collateral verticals couldn't show: **when the
collateral itself is unpriceable, the protocol must either import a fragile price (and own that
fragility), or engineer the price away** — and Blend's rising-rate refinance auction is the elegant
"engineer it away" answer, paid for with a less-bounded upgrade key. The universal law holds: trust
telescopes onto valuation/resolution; here the novelty is that one design **deletes** that seam by
turning liquidation itself into the price-discovery mechanism.

**Factual concerns flagged (defensive, no exploit):** (1) BendDAO — oracle key custody and the
deviation-param governance are the dominant risk; thin-market auction liveness + the redeem/bid-fine
mechanics (`:295-347`) deserve grief-scenario scrutiny. (2) NFTfi — verify the
`loanRepaidOrLiquidated` CEI flag (`:1129`) fully closes any double-resolve/reentrancy path (the
non-pausable repay/liquidate design is a deliberate, good property). (3) Blend — the 2-hour
minimum-interest floor and the `salt`/`amountTaken` offer-fill accounting (`Blend.sol:179-188`) are the
spots to verify for offer-reuse/partial-fill consistency; the UUPS owner key is unconditioned beyond
`onlyOwner`.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
