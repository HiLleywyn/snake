# Mid-cap sweep (≈ranks 100-200) — running log

Moving down-market from the majors: smaller caps are where real findings are likelier (less audited,
more forked/copy-paste code, more governance centralization, more closed mirrors). Same discipline as
the rest of the corpus — recompute, name the trust, no bare "safe." **If a genuinely exploitable
finding turns up it is NOT written here** — it gets stopped-and-notified privately (per the standing
rule), and only a redacted placeholder appears in this log. Entries below are clean / characterized.

---

## 1. Synthetix V3 (SNX) — distribution-based shared credit; mint double-gated (clean)
**Target:** `Synthetixio/synthetix-v3` (the legacy V1 `Synthetixio/synthetix` repo is gone/private;
V3 is the live architecture). Audited the core issuance path
(`protocol/synthetix/contracts/modules/core/IssueUSDModule.sol` + `storage/{Pool,Vault,Distribution}.sol`).
**Result: clean — well-structured, heavily audited; recorded for the model, not for signal.**

V3 replaces V1's literal "shared debt pool" with a **distribution-based shared-credit** system: pools
provide credit to markets, debt is apportioned to accounts as **scaled shares** (`Distribution` /
`ScalableMapping`), and snxUSD is minted against a position only when collateralization holds.
`mintUsd` (`:60-118`) is **double-gated**:
- per-account **`verifyIssuanceRatio(newDebt, collateralValue, issuanceRatioD18)`** (`:93`) — the
  position's new debt must clear the issuance c-ratio;
- vault-level **`verifyLiquidationRatio(rawVaultDebt, vaultCollateralValue)`** (`:108`) — the mint must
  not push the *whole vault* into liquidation territory;
- plus a monotonicity guard (`newDebt > debt`, `:82`), and only *then* `usdToken.mint(core, amount)` +
  credit to the account.
So issuance is bounded by both the individual and the aggregate collateral position before any snxUSD
exists. **Conservation floor: sound** — debt assigned == snxUSD minted, gated by c-ratio at two scopes.
**Residual:** the deepest surface is the **`Distribution`/`ScalableMapping` precision math** (the
scaled-shares accounting that spreads market debt across pools/accounts — where rounding/precision drift
would live) and the **cross-market credit-capacity** accounting (`MarketManager`); not opened here.
The oracle (collateral valuation) is the usual external 6b (cf. Drift/marginfi). A well-audited target;
**no finding.**

---

## 2. Pendle (PENDLE) — yield tokenization (SY→PT+YT); monotonic index + against-user rounding (clean)
**Target:** `pendle-finance/pendle-core-v2-public`, `contracts/core/YieldContracts/PendleYieldToken.sol`
+ `SYUtils.sol`. Distinct mechanism: a Standardized-Yield wrapper (SY) is split into a Principal Token
(PT, redeems to principal at expiry) and a Yield Token (YT, accrues the yield). Conservation = PT+YT
redeem back to the SY deposit; yield is metered by a `pyIndex`.
- **Mint** (`_mintPY → _calcPYToMint`, `:301-351`): `amountPY = SYUtils.syToAsset(index, amountSy) =
  (amountSy·index)/1e18` — **rounds down**, so PT+YT minted never exceed the SY warrants (protocol-
  favorable).
- **Redeem** (`_redeemPY → _calcSyRedeemableFromPY`, `:323-363`): `syOut = assetToSy(index, amountPY) =
  (amountPY·1e18)/index` — **rounds down**, so SY paid out never exceeds the PY warrants (protocol-
  favorable). Both legs round against the user → **no rounding leak**; dust accrues to reserves. `Up`
  variants exist for the directions where the protocol must over-charge.
- **`pyIndex` is monotonic non-decreasing** (`_pyIndexCurrent`, `:243-`): `index = max(SY.exchangeRate(),
  _pyIndexStored)`. Even if the underlying SY rate *drops* (negative yield / depeg), the index never
  decreases — the known Pendle guard against down-manipulating the conversion / draining PT value.
- Post-expiry index growth is routed to the treasury (`totalSyInterestForTreasury`), not to redeemers.
**Conservation floor: sound** — SY held by the YT contract backs PT+YT, rounding favors the protocol,
the index can't be gamed downward. **Residual:** the SY's own `exchangeRate()` is the trusted input
(the monotonic-max blocks *downward* games; an *upward* exchange-rate spike would let YT claim more
yield, but it's bounded by actual SY reserves and the SY wrapper is user-chosen), and the
`InterestManagerYT` yield-distribution accounting is the deeper surface, not opened. Well-audited;
**no finding.**

---

## 3. THORChain (RUNE) — cross-chain CLP with solvency-as-checked-invariant + auto-halt (clean; strong positive)
**Target:** `gitlab.com/thorchain/thornode`, `x/thorchain/` (Cosmos-SDK app). Picked for high signal:
complex, cross-chain (external-chain TSS vaults), and a real 2021 exploit history. Audited the swap CLP
math + the post-hack solvency defenses. **Result: clean — and notably well-hardened.**
- **In-pool conservation (CLP).** `GetSwapCalc` (`swap_current.go:548-553`): slip-based output
  `emit = x·X·Y/(x+X)²`; the swap **reverts/zeroes if `emitAssets.GTE(Y)`** (`:360`) so a swap can never
  drain more than the pool's output depth, and pool balances update via underflow-safe `SafeSub`
  (`:408,412`). Sound constant-product-family floor; RUNE is the settlement asset (asset↔asset = double
  swap).
- **The cross-chain seam (the irreducible 6b).** The asset side of every pool lives in **external-chain
  vaults** (Asgard TSS), observed by the Bifrost. This is the settlement seam where THORChain was
  actually exploited (the observation/router layer), and it's the irreducible trust: *do validators
  correctly observe external-chain vault balances?*
- **Solvency as a continuously-checked invariant + auto-halt (the standout, post-hack hardening).**
  Two layers: (a) **per-tx vault-underflow clamp** — `detectVaultSubFundsClamp`
  (`handler_observed_tx_helpers.go:917-946`): if an observed outbound would subtract more of an asset
  than the vault holds, it emits a security event and **halts both signing and trading on that chain**
  (`MimirTemplateHaltSigning` + `HaltTrading`); it **aggregates coins by asset first** to catch a
  duplicate-asset sum that no single entry would trip (a real, considered edge-case guard). (b)
  **validator-attested solvency voter** — `handler_solvency.go` aggregates a supermajority of active
  validators' observed vault balances (`processSolvencyAttestation`) and halts on insolvency. So the
  network **verifies vault solvency every block and halts on divergence rather than letting an
  insolvent vault be drained** — the explicit "halt over loss" discipline, the exact inverse of the
  MemeCore swallowed-error class, applied to the cross-chain seam.
**Conservation floor: sound + defended.** The CLP conserves in-pool; the cross-chain seam is the
irreducible trust, but it is wrapped in a per-tx clamp + supermajority-attested solvency check with
auto-halt — a strong member of the checked-invariant family (XRPL/Stellar/Algorand/Berachain) extended
to cross-chain settlement. **Residual:** the Bifrost **observation layer** (correctness of external-
chain balance observation under TSS; the solvency checks are only as good as the attestations feeding
them — mitigated by supermajority, not eliminated) — the deepest surface, not opened. **No finding.**

---

## 4. Liquity V2 (BOLD) — CDP with stability-pool offset; the fork-parent reference (clean, formally verified)
**Target:** `liquity/bold`, `contracts/src/{StabilityPool,ActivePool,TroveManager,BorrowerOperations}.sol`.
Distinct conservation model not yet in the corpus, and the **parent of a large fork ecosystem**
(Gravita, Prisma, Ethos, Felix, …) — auditing the reference pins down exactly what forks must preserve.
**Result: clean — and `certora/harnesses/` shows it's formally verified (Certora specs).**

**Conservation model.** A CDP stablecoin: debt (BOLD) is minted against collateral troves; liquidations
are absorbed by the **Stability Pool** (SP BOLD is burned to cancel the liquidated debt, and the
liquidated collateral is distributed to SP depositors); BOLD is redeemable for collateral at **$1 face
value**. V2 adds user-set interest rates, tracked in aggregate (`ActivePool.aggRecordedDebt +
calcPendingAggInterest() + batch fees`, `:157`) and per-trove — the sum must reconcile.

**The error-prone heart forks break — and the reference's guards.** The SP uses a scaled-deposit
accounting (`P` product, `S`/`B` sums per scale) so one offset updates all depositors O(1):
- `offset` (`StabilityPool.sol:383-406`): `scaleToS[scale] += P·_collToAdd/totalBoldDeposits` (coll
  gain per unit, rounds down); `newP = numerator/totalBoldDeposits` (P scaled down by the surviving
  deposit fraction).
- **`require(newP > 0, "P must never decrease to 0")`** (`:399`) — the classic Liquity invariant; if `P`
  hit 0 all deposits' value would be wiped. Forks have gotten this wrong.
- **Multi-exponent scale handling** (`SCALE_FACTOR=1e9`, `MAX_SCALE_FACTOR_EXPONENT=8`, the
  `while (newP < P_PRECISION/SCALE_FACTOR)` re-scale loop, `:404-406`) — keeps `P` from underflowing
  across many liquidations. This is the single most fork-misimplemented piece (the original V1
  "scale factor" subtlety; V2 hardened it to multi-step).
**The fork-divergence surface (what to diff any fork against):** (1) this `P`/`S`/`B` scale-factor math;
(2) **recovery mode** (TCR < CCR changes liquidation rules — routinely mis-ported); (3) **redemption
ordering** (V2 routes redemptions by interest rate; V1 by collateral ratio — forks mixing the two break
redemption fairness/solvency); (4) the aggregate-interest accounting (`aggRecordedDebt` vs per-trove).
**Conservation floor: sound and formally verified** in the reference. **No finding in the reference;**
the actionable fork-hunt is a line-diff of a *specific* fork's StabilityPool/recovery-mode against this
(named, ready to run on a target). Residual: the collateral **oracle** (the usual external 6b).

---

### Sweep status
Four mid-caps, all clean: Synthetix V3, Pendle, THORChain, Liquity V2 — established protocols are mostly
well-audited (often formally), so the lens reads *proportional*: clean floor + named residual, no
manufactured findings. The genuine fork-bug hunt needs a **named specific fork** to diff against these
references (Liquity-fork P/S math; lending-fork first-depositor/share-inflation; Solidly-fork gauge
rewards; Uniswap-fork fee-on-transfer assumptions). **Any real finding → stopped-and-notified privately,
not logged here.**

---

## 5. Alchemix V2 (ALCX) — self-repaying loans (a conservation model new to the corpus) (clean)
**Target:** `alchemix-finance/v2-foundry`, `src/{AlchemistV2,TransmuterV2}.sol`. Genuinely distinct: you
deposit yield-bearing collateral, mint alAsset debt up to an LTV, and **the collateral's yield
automatically repays the debt** — no liquidation under normal operation. Nothing else in the corpus
works this way.
- **Mint is LTV-gated *after* harvesting yield** (`_mint`, `:1209-1234`): it first
  `_preemptivelyHarvestDeposited` + `_distributeUnlockedCreditDeposited` (apply accrued yield as
  debt-reducing credit so debt is current), then `_updateDebt(+amount)`, then **`_validate`**
  (`:1459`): `collateralization = totalValue·SCALAR/debt; revert Undercollateralized if <
  minimumCollateralization`. So debt is always ≥-collateralized at mint, measured post-yield. A global
  `_mintingLimiter` rate-caps total alAsset issuance.
- **Self-repayment = credit distribution:** harvested yield is distributed as "credit" that reduces
  account debt (`_distributeCredit`, `:1277`) — the debt decays as yield accrues, the defining feature.
- **The transmuter keeps alAsset backed at par (1:1):** `TransmuterV2` tracks per-account
  `unexchangedBalance` (alAsset awaiting conversion) → `exchangedBalance` (underlying), distributing
  repaid underlying to alAsset depositors **1:1**. So every alAsset minted corresponds to debt, and as
  debt is repaid in underlying that underlying flows to the transmuter, making alAsset redeemable at par.
**Conservation floor: sound** — alAsset issuance is LTV-gated + globally rate-limited; the
self-repayment is a credit distribution against real harvested yield; the transmuter conserves alAsset↔
underlying at 1:1 funded by repayments. **Residual:** the **yield-token value reporting**
(`convertYieldTokensToUnderlying`) is the trusted input — if a yield strategy loses value or is
manipulated, positions can become genuinely undercollateralized (the alAsset-depeg / external-strategy
6b), and the transmuter relies on repayment inflow timing. **No finding.**

---

## 6. Reserve Protocol (RSR / RToken) — basket-backed stablecoin + staked backstop + auction recollateralization (clean)
**Target:** `reserve-protocol/protocol`, `contracts/p1/{RToken,BasketHandler,BackingManager,StRSR}.sol`.
Distinct: an RToken is backed by a **basket** of collateral (overcollateralized), with **StRSR** (staked
RSR) as an insurance backstop and **Dutch-auction recollateralization** when a collateral defaults.
- **The backing-ratio invariant.** `basketsNeeded` (D18 basket units the BackingManager must hold);
  issue/redeem exchange at `totalSupply()/basketsNeeded`. Issuance updates `basketsNeeded` with **CEIL
  rounding** (`basketsNeeded.muluDivu(amount, supply, CEIL)`, `:137`) — conservative (the system needs
  *at least* that many baskets). Redemption preserves the documented invariant **`basketsNeeded' /
  totalSupply' >= basketsNeeded / totalSupply`** (`:174`) — a redemption can never lower the backing
  ratio for remaining holders.
- **No preferential drain.** Standard `redeem` requires **`basketHandler.fullyCollateralized()`**
  (`:197`); if the basket is impaired, holders must use **pro-rata `redeemCustom`**, so a fast redeemer
  can't drain the sound collateral and leave others holding the bad — the run-resistance design.
- **Issuance gated on basket soundness.** `issue` requires `basketHandler.isReady()` (`:120`) — can't
  mint against a basket in default/warmup.
- **Recollateralization + backstop.** On a collateral default the BackingManager runs auctions to
  restore the basket and, if collateral is insufficient, **seizes StRSR (RSR stakers' capital)** — the
  staked backstop absorbs the loss before RToken holders. Overcollateralization + insurance, in code.
**Conservation floor: sound** — the backing ratio is non-decreasing across issue/redeem (CEIL on issue,
ratio-preserving redeem), standard redemption is gated on full collateralization with pro-rata fallback,
and losses hit the RSR backstop first. **Residual:** the **collateral plugins** report price /
`refPerTok` / default status — a mis-reporting or slow-to-default plugin is the trusted input (the
oracle/peg 6b), and the Dutch-auction price bounds are the recollateralization-efficiency surface. **No
finding.**

---

### Distinct-mechanism tally (corpus value of the sweep)
Six mid-caps, six conservation models, all clean: **Synthetix V3** (distribution-based shared credit),
**Pendle** (yield-token split with monotonic index), **THORChain** (cross-chain CLP + solvency-halt),
**Liquity V2** (CDP stability-pool offset, formally verified), **Alchemix** (self-repaying loans +
1:1 transmuter), **Reserve** (basket + RSR backstop + auction recollateralization). Each adds a *new*
conservation shape to the corpus, and each bottoms out on the same family of residuals — an external
**oracle / price / value-reporting** input (Synthetix collateral, Pendle SY rate, THORChain Bifrost
observation, Liquity oracle, Alchemix yield-token value, Reserve collateral plugins). The down-market
lesson holds: established mid-caps are well-defended; the trust keeps relocating to the value-reporting
boundary, never disappearing.
