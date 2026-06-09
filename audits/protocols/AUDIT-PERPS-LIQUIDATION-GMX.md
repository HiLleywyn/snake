# On-chain perps — the liquidation engine as the load-bearing seam (GMX v1 & v2)

**Scope.** GMX v1 monolithic vault (`gmx-io/gmx-contracts` @ `fe55c4b`) and GMX v2 synthetics
(`gmx-io/gmx-synthetics` @ `919da19`). Focus: the **liquidation engine** and the pool-counterparty
solvency floor that backs it. Read as the perps companion to the prediction-market and lending
verticals. Public source, read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit.
No exploitable defect found**; one structural concern (v1 has no insurance fund) is flagged
factually for context.

**Sources read (verbatim, line refs against those checkouts):** v1 `Vault.sol`, `VaultUtils.sol`,
`VaultPriceFeed.sol`, `FastPriceFeed.sol`, `Timelock.sol`; v2 `PositionUtils.sol`,
`LiquidationHandler.sol`, `AdlUtils.sol`, `Oracle.sol`.

---

## 0. The one-paragraph result

A perp DEX is the **house-counterparty** floor family (like Azuro), but with a twist the
prediction markets never had: the position stays open and the mark price moves *continuously*, so
solvency depends not on a one-time reserve lock but on a **liquidation engine firing in time**.
GMX v1's floor is a hard on-chain invariant — `reserved ≤ pool ≤ token balance` — so the protocol
can *never promise more trader profit than tokens it holds*; but that invariant does **not**
guarantee a *losing* trader's collateral covers their loss. That gap is the dominant residual, and
it has two halves: **(1)** the liquidation must trigger before collateral is exhausted
(`validateLiquidation`), and **(2)** the trigger reads a **keeper-pushed price**, bounded relative
to Chainlink. When liquidation is late, v1 **socializes the shortfall to GLP LPs with no insurance
fund and no ADL**; v2 closes exactly that hole by adding **ADL** (force-deleverage winners once
trader PnL relative to the pool exceeds a cap) and a **multi-provider oracle with a Chainlink
deviation guard**. So the perps law is: *the floor is a continuously-moving solvency invariant whose
enforcement IS the liquidation engine, and whose correctness rests on the keeper oracle + the
bad-debt backstop (LP socialization in v1, ADL in v2).*

---

## 1. The conservation floor — pool-counterparty solvency by hard invariant. **Sound.**

GMX v1 (`Vault.sol`) enforces three coupled invariants on **every** mutation of pool/reserve state:
```solidity
// reserve can never exceed pool — can't promise more profit-backing than the pool holds
_increaseReservedAmount: require(reservedAmounts[token] <= poolAmounts[token])   // :1178 (err 52)
// pool is always backed by real tokens
_increasePoolAmount:     require(poolAmounts[token] <= balanceOf(this))          // :1136 (err 49)
// re-checked on every outflow
_decreasePoolAmount:     require(reservedAmounts[token] <= poolAmounts[token])   // :1143 (err 50)
```
On `increasePosition (:601-616)` the size delta is reserved, long collateral folds into the pool,
and `guaranteedUsd` tracks `Σ(size − collateral)` so longs' redeemable collateral is exactly
accounted; short OI is capped by `maxGlobalShortSizes (_increaseGlobalShortSize :1197-1204)`.

**Verdict:** the floor is a *reserve-locking solvency* invariant (Azuro's family), here expressed as
`reserved ≤ pool ≤ balance`. It guarantees **winners can always be paid**. It explicitly does **not**
guarantee a loser's collateral covers their loss — that is the liquidation engine's job, and the
residual lives there. GLP holders are the counterparty / loss-bearer of record.

---

## 2. The liquidation engine — the dominant residual. **Correct math; the residual is timeliness + oracle.**

**v1 trigger** (`VaultUtils.validateLiquidation :61-105`) — three independent conditions, returning
`1` (liquidate) or `2` (max-leverage → forced partial decrease):
```solidity
if (!hasProfit && position.collateral < delta) return (1, marginFees);                       // :70 losses > collateral
if (remainingCollateral < marginFees + liquidationFeeUsd) return (1, marginFees);            // :94 fees eat collateral
if (remainingCollateral * maxLeverage < position.size * BASIS_POINTS_DIVISOR) return (2,..); // :99 leverage breached
```
**v1 entry** (`Vault.liquidatePosition :701-754`): permissioned when `inPrivateLiquidationMode`
(`isLiquidator[msg.sender]`, `:703`), and it **disables the AMM price leg** (`includeAmmPrice=false`,
`:705`) "to prevent manipulated liquidations." The mark price uses the *adverse* side — long →
`getMinPrice`, short → `getMaxPrice` (`:734`). Settlement releases the reserve, writes the loss down
against `guaranteedUsd`/`poolAmount` for longs, returns `remainingCollateral` to the pool for shorts,
and pays `liquidationFeeUsd` **from the pool** to the keeper (`:748-751`) — the code comment *assumes*
the liquidated collateral covers that fee.

**v2 trigger** (`PositionUtils.isPositionLiquidatable :316-450`):
`remainingCollateralUsd = collateralUsd + pnlUsd + priceImpactUsd − costUsd (:417-421)`, with positive
impact capped to 0 for the check (`:374`) and negative impact **floored** by
`getMaxPositionImpactFactorForLiquidations (:386-389)` to prevent liquidation cascades; triggers at
`< minCollateralUsd (:436)`, `≤ 0 (:441)`, or `< sizeInUsd·minCollateralFactor (:445)`. **v2 entry**
(`LiquidationHandler.executeLiquidation :47-84`) is `onlyLiquidationKeeper`, `withOraclePrices`, calls
`oracle.validateSequencerUp() (:60)`, and routes liquidation through the **normal decrease-order
executor** rather than bespoke pool math — a cleaner, single-settlement-path design.

**Verdict:** the underwater math is correct and conservative (adverse-side pricing, AMM-leg disabled,
v2 cascade-floor). The residual is **timeliness** — a position underwater between blocks/oracle
updates can cross into negative equity before a keeper fires.

---

## 3. The price-oracle seam — keeper-pushed, Chainlink-bounded. **Disclosed trust.**

v1 `VaultPriceFeed`: `getPrimaryPrice (:287-337)` is Chainlink with an **Arbitrum-sequencer-down
guard (:291-297)** and multi-round min/max sampling; `getSecondaryPrice (:339-342)` is the **keeper**
(`FastPriceFeed`). The keeper price is **bounded relative to Chainlink** (`FastPriceFeed.getPrice
:272-330`): if stale → Chainlink fallback; if `diffBasisPoints > maxDeviationBasisPoints`, or watchers
force-disable (`disableFastPriceVoteCount ≥ minAuthorizations :317`), or cumulative delta exceeds
`maxCumulativeDeltaDiff`, it returns the **more conservative** of {fast, Chainlink}. Pushes are
`onlyUpdater`; signer votes `onlySigner`.

v2 `Oracle._validatePrices (:232-328)`: per-action prices, each token's provider must be enabled and
equal the configured `oracleProviderForToken (:280-283)`, age-bounded by `MAX_ORACLE_PRICE_AGE`, and
**every non-Chainlink provider's min/max is validated against the Chainlink ref price**
(`_validateRefPrice → MaxRefPriceDeviationExceeded :330-345`).

**Characterization:** the oracle is a **keeper/data-stream price bounded by Chainlink deviation** — a
*fifth* oracle type for the corpus (low-latency push + on-chain reference clamp). The historically
discussed GMX manipulation class (e.g. AVAX/GLP) targeted the *zero-price-impact fill model* + oracle
latency, **not** a missing bound here; the residual trust is that the keeper set keeps prices honest
within `maxDeviationBasisPoints` of Chainlink, and that Chainlink itself is sound.

---

## 4. Bad-debt backstop — the v1→v2 evolution. **The real difference.**

- **v1: no ADL, no insurance fund.** Late liquidation → the shortfall is **socialized to GLP**
  (`_decreasePoolAmount`/`_decreaseGuaranteedUsd :729-732` write the pool down by the loss). The only
  structural limits are `maxGlobalShortSizes (:1200)` and `bufferAmounts (_validateBufferAmount
  :1147)`. **LPs are the uninsured loss-bearer**, and `liquidationFeeUsd` is paid from the pool
  regardless of whether the dead position covered it (`:748-751`). This is the one item genuinely
  worth flagging factually: a sufficiently late or oracle-gapped v1 liquidation produces **pool-borne
  bad debt with no insurance fund**.
- **v2: ADL caps it.** `AdlUtils.updateAdlState (:86-125)` enables ADL per market/side once
  `isPnlFactorExceeded(MAX_PNL_FACTOR_FOR_ADL) (:105-113)` — i.e. trader profit relative to the pool
  exceeds a cap — and `createAdlOrder (:133)` force-closes winning positions. The loss-bearer shifts
  from **LPs (v1)** to the **profitable traders being ADL'd (v2)**, bounded by `MAX_PNL_FACTOR`. ADL
  adds a *new* residual: ADL-keeper liveness.

This is the perps analog of the prediction-market floor-mechanism distinction: same goal (the pool
stays solvent), evolved mechanism (unbounded LP socialization → bounded winner-deleveraging).

---

## 5. Governance ceiling

- **v1:** every Vault param is behind `_onlyGov (:1217)` — `setPriceFeed (:299, swap the entire
  oracle)`, `setMaxLeverage (:304)`, `setFees`/`setLiquidationFeeUsd (:320-348)`,
  `setInPrivateLiquidationMode`+`setLiquidator (:269-278, who may liquidate)`, token whitelist. Vault
  is **non-upgradeable** (no proxy) but `gov` can repoint `priceFeed`/`vaultUtils` to arbitrary
  contracts. `gov` is normally a `Timelock (MAX_BUFFER = 5 days)` with signal/execute for sensitive
  actions — **but `setIsLeverageEnabled (onlyHandlerAndAbove :293)` disables trading immediately,
  bypassing the buffer.** So the *pause* lever is fast; the *oracle/gov-swap* levers are timelocked.
- **v2:** all params are `DataStore` keys behind keeper/controller roles, with per-function kill
  switches (`FeatureUtils.validateFeature`). Trust anchors = `onlyLiquidationKeeper`/`onlyAdlKeeper`/
  `onlyController` roles.

**Characterization:** high ceiling — gov can repoint the oracle (the position-valuation source) under
a 5-day timelock, and can pause trading instantly. The keeper/role set is the operational trust.

---

## 6. Where this sits in the corpus

Perps are the **house-counterparty floor under continuous price motion**, which forces a property the
static markets didn't need: the floor invariant (`reserved ≤ pool ≤ balance`) only guarantees
*winners are paid* — keeping the *pool* whole additionally requires a **liquidation engine that fires
in time** plus a **bad-debt backstop**. That backstop is the perps-specific residual, and the v1→v2
evolution (LP socialization → ADL) is the same "who bears the shortfall" question the Azuro/Thales
study raised, now answered under time pressure. The oracle is a **fifth type**: a low-latency keeper
push **clamped to a Chainlink reference** — distinct from optimistic (Polymarket), self-token
(Augur), trusted-provider (Azuro), and pure-feed (Thales). Net: perps confirm the universal law
(trust telescopes onto the price oracle + the solvency-enforcement mechanism) and add the
**timeliness** dimension — a solvency invariant that must be *continuously* re-enforced, not locked
once.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
