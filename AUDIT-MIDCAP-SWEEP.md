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
