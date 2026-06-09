# FRAX — fractional-algorithmic backing + the AMO residual (reflexive collateral & protocol-owned strategies)

**Scope.** Frax Finance's FRAX stablecoin: the fractional-algorithmic collateral-ratio (CR) model, the
mint/redeem split, and the **AMO (Algorithmic Market Operations) minter** that mints unbacked FRAX into yield
strategies (`FraxFinance/frax-solidity` @ `30532c8`, contracts under `src/hardhat/contracts/`). This is the
companion to the decentralized-dollars audit (DAI/CCTP) and adds **two stablecoin mechanisms the corpus
hadn't isolated**: *algorithmic/reflexive backing* (part of the dollar is backed by the protocol's own
governance token) and the *AMO* (protocol mints its own stablecoin into external strategies, solvency tracked
by self-reported valuations). Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found**; the reflexive-backing, AMO-solvency, oracle, and
governance residuals are characterized factually.

**Sources (verbatim, line refs):** `Frax/Frax.sol`, `Frax/Pools/{FraxPool, FraxPoolLibrary, FraxPoolV3}.sol`,
`Frax/FraxAMOMinter.sol`, `Misc_AMOs/Convex_AMO_V2.sol`, `Oracle/{UniswapPairOracle,
ChainlinkETHUSDPriceConsumer}.sol`.

---

## 0. The one-paragraph result

FRAX is the corpus's first **algorithmic** dollar — a stablecoin where, by construction, *only a fraction is
backed by real collateral and the rest is backed by the protocol's own governance token (FXS)*. The
`global_collateral_ratio` (CR, 6-decimal) is that fraction; it moves *algorithmically* — when FRAX trades
above \$1.005 the CR drops 0.25% (more algorithmic), below \$0.995 it rises (more collateral) — and mint/redeem
enforce the split: **to mint \$1 FRAX you deposit \$CR of collateral and burn \$(1−CR) of FXS; to redeem you
get \$CR collateral and \$(1−CR) in *newly minted* FXS.** That last clause is the reflexive core and the
canonical algorithmic-stablecoin risk: a depeg triggers redemptions that mint-and-sell FXS, depressing the
very asset that backs the algorithmic slice — the UST-style death-spiral vector, mitigated here only by the CR
floor not reaching 0 in practice and (in V3) by mint/redeem price thresholds. On top of this sits the **AMO**,
the genuinely novel residual: a governance-allowlisted `FraxAMOMinter` that can `pool_mint` FRAX **out of thin
air** and borrow real collateral from the pool to deploy into external yield (Curve/Convex/Aave), bounded
on-chain only by static caps and a single `new_cr ≥ min_cr` (81%) check — while **the system's accounting of
whether those strategies are still solvent depends on each AMO's *self-reported* `dollarBalances()`, which
governance can even hand-adjust via `correction_offsets_amos`.** So the FRAX law: *its dollar rests on three
residuals stacked — a reflexive governance-token backing (endogenous, death-spiral-prone), a manipulable
price oracle that drives the CR, and governance-controlled AMOs that mint unbacked FRAX into off-chain
strategy/counterparty risk tracked by self-reported numbers — a fundamentally different and more reflexive
trust model than the overcollateralized (Maker), redemption-pegged (Liquity), or off-chain-custody (Ethena,
USDC) dollars.*

---

## 1. The fractional-algorithmic model (`Frax.sol`). **Part collateral, part FXS-seigniorage.**

The CR is the fraction backed by real collateral; the rest is "backed" by burning FXS. State + the
permissionless, rate-limited adjustment (`Frax.sol:67-127,197-221`):
```solidity
uint256 public global_collateral_ratio;   // 1e6 precision; starts at 1000000 (100%)
frax_step = 2500;        // 0.25% CR step
refresh_cooldown = 3600; // 1h between adjustments
price_band = 5000;       // +/- $0.005 dead-band around $1
// refreshCollateralRatio():
if (frax_price_cur > price_target + price_band)      global_collateral_ratio -= frax_step;  // >$1.005 -> more algorithmic
else if (frax_price_cur < price_target - price_band) global_collateral_ratio += frax_step;  // <$0.995 -> more collateral (cap 100%)
```
**Characterization:** mint/redeem are hardcoded at \$1 (`price_target`); only the CR *responds* to the market
price, slowly (0.25%/hour, dead-banded). The dollar's backing composition is itself a *control loop* tuned by
governance params — a mechanism distinct from every prior stablecoin, where backing was static.

---

## 2. Mint/redeem — the CR sets the collateral-vs-FXS proportion. **The reflexive core.**

**Mint** (`FraxPool.sol:232-257`, math in `FraxPoolLibrary.sol:42-65`): deposit `$CR` collateral and **burn**
`$(1−CR)` of FXS to mint \$1 FRAX:
```solidity
calculated_fxs_dollar_value = (c_dollar_value · 1e6 / col_ratio) − c_dollar_value;  // the (1-CR) slice paid in FXS
FXS.pool_burn_from(msg.sender, fxs_needed); collateral in; FRAX.pool_mint(msg.sender, mint_amount);
```
**Redeem** (`FraxPool.sol:284-317`): burn FRAX, receive `$CR` collateral **plus** `$(1−CR)` in **newly minted
FXS**:
```solidity
FRAX.pool_burn_from(msg.sender, FRAX_amount);
FXS.pool_mint(address(this), fxs_amount);   // :316  the redeemer's algorithmic slice is paid in NEW FXS
```
V3 (`FraxPoolV3.sol:381-387`) makes the split explicit and adds `mint_price_threshold`/`redeem_price_threshold`
to throttle minting below / redeeming above peg.

**Characterization (the death-spiral vector, factual):** the `(1−CR)` slice is backed by an asset whose value
is **endogenous to FRAX confidence**. In a depeg, redemptions mint-and-sell FXS, depressing FXS, which weakens
the algorithmic backing, which can deepen the depeg — the UST mechanism. FRAX mitigates it structurally (the
CR never reached 0 in practice; later versions moved toward ~100% collateral + RWA) and via V3's price
thresholds, but the *mechanism* is reflexive by design, unlike overcollateralized or fully-reserved dollars.

---

## 3. The AMO minter — governance mints unbacked FRAX into strategies. **The novel residual.**

`FraxAMOMinter` is a governance-allowlisted "pool" that can mint FRAX with **no collateral** and borrow real
collateral from the pool to deploy externally. Mint, with its sole solvency guard (`FraxAMOMinter.sol:227-248`):
```solidity
function mintFraxForAMO(address destination_amo, uint256 frax_amount) external onlyByOwnGov validAMO(destination_amo) {
    require((frax_mint_sum + ...) <= frax_mint_cap, "Mint cap reached");        // static cap (100M)
    uint256 new_cr = (FRAX.globalCollateralValue() * 1e6) / (FRAX.totalSupply() + frax_amount);
    require(new_cr >= min_cr, "CR would be too low");                            // :241  the 81% floor — the only guard
    FRAX.pool_mint(destination_amo, frax_amount);                               // :244  UNBACKED mint
}
```
`giveCollatToAMO (:301-319)` similarly lends pool collateral into the AMO (bounded by `collat_borrow_cap`,
10M). Net exposure is tracked by `fraxTrackedGlobal() (:151)` and `syncDollarBalances() (:164-177)` — **but
the dollar values are *self-reported* by each AMO's `dollarBalances()` (`:171`), and governance can hand-adjust
them via `correction_offsets_amos (:409)`.** The strategy-side `fraxFloor() (Convex_AMO_V2.sol:255-261)` sizes
AMO deposits to the CR (or a governance override).

**Characterization (the key residual):** the AMO is *protocol-owned strategy* — Frax governance mints its own
stablecoin into Curve/Convex/Aave to earn yield and defend the peg, with on-chain protection limited to static
caps + the `min_cr` floor. **The solvency of those strategies is not verified on-chain — it is whatever each
AMO reports**, with a governance override. This concentrates two risks the prior dollars didn't have in this
form: *unbacked issuance* (FRAX minted with no collateral, relying on the strategy to remain worth ≥ par) and
*self-reported / governance-adjustable accounting* of whether the system is still solvent. Strategy/counterparty
loss (a Curve pool depeg, an Aave shortfall) is off-core and unbounded on-chain beyond the static caps.

---

## 4. The oracle — the CR's input. **Manipulable, loosely guarded.**

V1 (`Frax.sol:133-148`): `oracle_price` = Chainlink ETH/USD × a **Uniswap V2 1-hour TWAP** (`UniswapPairOracle`,
`PERIOD = 3600`, with a governance-settable `ALLOW_STALE_CONSULTS` bypass). V3 (`FraxPoolV3.sol:235-247`):
direct Chainlink FRAX/USD and FXS/USD feeds. **Factual flags:** the V1 TWAP is manipulable with sustained
capital and the `ALLOW_STALE_CONSULTS` toggle is a governance footgun; the Chainlink staleness checks accept
`price >= 0` (allows 0) and verify only `updatedAt != 0`, **not freshness against `block.timestamp`** — the
canonical consumer-side oracle footgun the §5g oracle audit flagged, present here. Since the oracle drives the
CR (the backing composition), a mispriced feed mis-tunes the algorithmic/collateral split.

---

## 5. Governance — every load-bearing knob, owner-or-"timelock", no enforced delay in these sources

`Frax.sol` uses `onlyByOwnerGovernanceOrController` (owner | `timelock_address` | `controller_address`); the AMO
minter uses `onlyByOwnGov` (owner | timelock). Governance can: `addPool` (allowlist the AMO minter as a FRAX
minter), `addAMO` + raise `frax_mint_cap`/`collat_borrow_cap`, lower `min_cr`, apply `correction_offsets_amos`
(manually adjust reported AMO balances), change `frax_step`/`price_band`/`refresh_cooldown`, **swap the oracle**,
and `toggleCollateralRatio` (freeze the CR). **Crucially, `timelock_address` is merely an *authorized caller* in
these contracts — there is no per-action delay enforced here**, so the delay depends entirely on whatever
external contract holds that role; in these sources the **`owner` key alone can perform all of the above with no
timelock.** A high, largely-undelayed governance ceiling sitting directly over an unbacked-mint capability.

---

## 6. Where this sits in the corpus

FRAX extends the stablecoin taxonomy with the **reflexive/algorithmic** backing class — the dollar partly backs
itself with its own governance token — and the **AMO** residual — the protocol mints its own stablecoin into
external strategies, solvency tracked by self-reported numbers. Against the other dollars: Maker is
*overcollateralized* (with the §1 USDC-PSM caveat), Liquity is *redemption-pegged + immutable*, Ethena/USDC are
*off-chain-backed* (custody/reserve), and **FRAX is *reflexively-backed + protocol-owned-strategy*** — the most
*endogenous* trust model of the set, where a chunk of the backing (FXS) and the solvency accounting (AMO
self-reports) are internal to the system rather than an external asset or attestation. It re-confirms three
corpus laws at once: the **oracle residual** (the CR rides a manipulable TWAP / a staleness-unchecked feed), the
**governance ceiling** (here largely undelayed, over an unbacked mint), and the **off-chain/self-reported
residual** (AMO `dollarBalances()` is the same "trust a number you can't recompute" shape as an oracle attestation
or an LST beacon report). The honest user statement: *FRAX holds its peg by a control loop, not a reserve —
part of every FRAX is backed by FXS (which is backed by belief in FRAX) and part of the supply is minted
unbacked into yield strategies whose solvency the protocol reports to itself — so your dollar's safety rests on
the oracle, on FXS confidence, and on governance honestly accounting for strategies it controls, none of which
is the simple "is there a dollar in a vault" guarantee the name implies.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
