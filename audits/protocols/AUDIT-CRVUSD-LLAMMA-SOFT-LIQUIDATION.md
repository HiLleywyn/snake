# crvUSD LLAMMA — continuous soft-liquidation, a new liquidation-mechanism class

**Scope.** Curve's crvUSD / LlamaLend LLAMMA — the banded AMM that performs **continuous,
liquidator-optional, oracle-driven soft-liquidation** (`curvefi/curve-stablecoin` @ `61f1a61`, Vyper
0.4.3; contracts under `curve_stablecoin/`). This adds a genuinely **new liquidation mechanism** to the
corpus taxonomy: *continuous deleveraging across price bands* rather than a *discrete threshold-triggered
auction/seizure*. Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found**; the oracle-dependency, the soft-liq bleed,
and the bypassable oracle-swap deviation guard are characterized factually.

**Sources read (verbatim, line refs):** `AMM.vy` (the band model, `exchange`/`calc_swap_out`,
`limit_p_o`, `get_x_down`/`get_xy_up`), `controller.vy` (`create_loan`, `_calculate_debt_n1`,
`_health`, `liquidate`), `Configurator.vy` (`set_price_oracle`, discounts), `ControllerFactory.vy`,
`price_oracles/{EmaPriceOracle, CryptoFromPool}.vy`.

---

## 0. The one-paragraph result

Every prior lending/perp/CDP audit in this corpus had a liquidation that was **discrete**: a health
factor crosses a threshold, and *something happens at that instant* — an auction opens (Maker/BendDAO), a
keeper seizes (GMX/Aave), the pool deleverages a winner (GMX v2 ADL). LLAMMA is the first **continuous**
one, and it is genuinely different in kind. A borrower's collateral isn't a single position valued at
the oracle price — it is **spread across a grid of narrow price "bands,"** and the LLAMMA AMM is wired so
that *only the active band holds both assets; every band above is 100% collateral, every band below is
100% crvUSD.* As the oracle price **falls** through the borrower's bands, each band becomes
arbitrage-profitable, and **any external party calls `exchange()`** — the AMM automatically converts that
band's collateral to crvUSD at the band price, band by band. There is **no `liquidate()` call, no
discrete trigger, no auction, and no designated liquidator** — deleveraging is continuous and
band-granular, and it **reverses** (the AMM buys the collateral back) when price recovers. The genius is
that this makes liquidation *soft and recoverable*: a borrower whose collateral dips and rebounds keeps
their position, having paid only the AMM spread on each crossing. The cost — and the residual — is that
**the borrower bleeds that spread to arbitrageurs on every oscillation** (worst under whipsaw), and the
*entire* mechanism (which bands activate, and the health floor itself, via `get_x_down`) is **driven by
one price oracle**. A discrete **hard `liquidate()`** exists only as a *fallback* when the oracle drops
too fast/far for soft-liquidation plus the `liquidation_discount` buffer to keep up (`health < 0`). So
the LLAMMA law: *it trades the discrete-liquidation cliff for a continuous, reversible, self-executing
slide — moving the residual from "was the keeper fast enough" to "is the oracle honest and how much does
the borrower bleed to arbitrageurs," and making the AMM itself the liquidation engine.*

---

## 1. The banded AMM — the novel floor. **Collateral as a price-grid.**

`AMM.vy` spreads a borrower's collateral across `bands`, each a price range of relative width `1/A`, with
edges scaling geometrically: `p_oracle_up(n) = base_price · ((A-1)/A)^n` (`_p_oracle_up:345-363`). The
load-bearing structural fact (docstring `:10-37`): **only `active_band` holds both x (crvUSD) and y
(collateral); all bands above the active band are 100% collateral, all below are 100% crvUSD.** Per-band
balances live in `bands_x`/`bands_y`; per-user ownership via `total_shares`/`_user_shares`. The bonding
curve per band is `(f + x)·(g + y) = p_oracle · A² · y0²` — a Curve-style invariant where `f`/`g` are
derived from the oracle price, so **the band's exchange rate tracks the oracle.**

`deposit_range (:639-716)` (Controller-only) spreads `amount` of collateral evenly across the chosen band
range (`y_per_band`), minting proportional shares — and **requires the bands to be empty and strictly
below the active band**, i.e. *you cannot open a loan already in soft-liquidation.*

---

## 2. Soft-liquidation — the AMM *is* the liquidation engine. **The new mechanism.**

`exchange (:1276-1288)` is **callable by anyone**. As `p_oracle` falls, `calc_swap_out (:804-948)` walks
bands from `active_band`; the **dump path** (`pump=False`, collateral in / crvUSD out, `:904-938`)
**sells the borrower's collateral for crvUSD band-by-band**, `_exchange (:1012-1095)` rewrites `bands_x`/
`bands_y` and advances `active_band`. *That* is soft-liquidation: no `liquidate()`, no trigger, no
auction — external arbitrageurs, chasing the band-vs-market spread, do the conversion for free, and the
borrower's position smoothly transitions from collateral to crvUSD as price drops. On recovery the
**pump path** (`:867-902`) buys the collateral back. **Soft-liquidation is continuous and reversible.**

**Where the borrower's loss comes from (the residual, by design):** the AMM's spread — a static `fee`
*plus* the `limit_p_o` dynamic fee `(1 − ratio³)` (`:251-257`) *plus* `get_dynamic_fee` (`:262-275`),
applied as `antifee` in every swap (`:852-855`). Arbitrageurs capture this on each crossing, so **the
borrower "bleeds" the spread every time price oscillates across their bands** — cumulatively material
under sustained whipsaw. This is the economic price of *not* being discretely liquidated, and it is the
mechanism's defining trade-off.

---

## 3. The health floor — soft-liq losses are baked in. **Why devaluation alone doesn't liquidate.**

`_health (:1158-1197)` computes `health = (1 − liquidation_discount)·AMM.get_x_down(user)/debt − 1`, where
`get_x_down (→ get_xy_up :1306-1462)` is the **crvUSD value of the position *after a full
soft-liquidation*** — i.e. the floor value once all the user's collateral has been adiabatically
converted down. Because health uses `get_x_down`, **soft-liquidation losses are already priced into
health**, and the docstring's key claim holds: *"Liquidation starts when < 0, however devaluation of
collateral doesn't cause liquidation"* (`:1164-1165`) — once a position is fully soft-liquidated to
crvUSD, `get_x_down` is roughly price-independent, so further price drops don't keep pushing health down.
`_calculate_debt_n1 (:483-536)` back-solves the band range from collateral discounted by `loan_discount +
extra_health`, and **reverts "Debt too high" if the loan would open already in soft-liquidation**.

---

## 4. Hard liquidation — the discrete fallback only. **Health < 0.**

`liquidate (:1242-1366)` is the *fallback*: for third parties it **asserts `health < 0` ("Not enough
rekt", `:1267`)** — reachable only when the oracle dropped too fast/far for soft-liquidation + the
`liquidation_discount` buffer to keep up (or accrued interest outran it). It withdraws the user's AMM
position (a mix of crvUSD + leftover collateral), burns debt with the crvUSD, and the liquidator covers
any shortfall (optionally via callback). Self/approved users can liquidate **without** the health gate
(`:1266`) — intended, to let a borrower de-risk their own position. **Characterization:** the discrete
liquidation that *was the whole story* in every prior CDP/lending audit is here demoted to an exception
path; the *primary* deleveraging is continuous and keeper-optional.

---

## 5. The oracle — the single point of trust for both timing and floor. **The dominant residual.**

Everything rests on `price_oracle()`. The AMM reads it on every op (`_price_oracle_w :284-290`), and
**which bands soft-liquidate is entirely a function of where `p_oracle` sits relative to band edges**;
the health floor is `get_x_down`, also oracle-derived. The primary defense is **`limit_p_o (:212-259)`**:
it **caps the instantaneous oracle move** to `MAX_P_O_CHG (≈2^(1/3))` and imposes a **dynamic fee
`(1 − ratio³)`** that decays over a 2-minute delay — so an abrupt oracle jump is both *bounded* and *made
expensive to arbitrage* within a block. Production markets read a **Curve-pool internal
manipulation-resistant EMA** (`CryptoFromPool.vy:47-66`), not spot — though a thin underlying pool
weakens that EMA.

**Factual flags (defensive, no exploit):** (1) the oracle is the single point of trust for *both* band
activation and the health floor; `limit_p_o`'s per-block clamp + dynamic fee are the main mitigations and
deserve an auditor's focus, especially on thin underlying pools. (2) The soft-liq bleed to arbitrageurs
is by design but should be *quantified* per market (fee + volatility). (3) **`Configurator.set_price_
oracle (:195-236)` can swap the AMM's oracle live, and its ≤50% deviation guard is bypassable** by passing
`_max_deviation == max_value(uint256)` (`:209,217`) — the most consequential admin lever, since the new
oracle directly drives the band map and the floor; trust rests on the `default_admin` (the Curve DAO).

---

## 6. Governance — DAO via Configurator/Factory

The AMM's admin **is the Controller**; the Controller is configured only by the **`Configurator`**
(`controller.configure` asserts caller == CONFIGURATOR). Configurator powers (DAO-gated via
`default_admin`/per-controller `admins`): `set_borrowing_discounts` (loan/liquidation discounts, bounded
`loan>liq`, `loan<100%`), `set_monetary_policy`, `set_amm_fee`, **`set_view`** (redeploys a view impl
from a blueprint — code-changing), and **`set_price_oracle`** (the live oracle swap, §5). The
`ControllerFactory` deploys AMM+Controller pairs from blueprints and holds the **debt-ceiling kill lever**
(`rug_debt_ceiling` → 0 halts new loans). Existing AMM/Controller pairs are non-proxy immutables; the
system is upgradeable only for *new* markets and via the redeployable view. Interest flows from a
`monetary_policy.rate_write()` capped at `MAX_RATE` (300% APY), and the source itself flags that stateful
`rate_write` **must** be permissioned to preserve the reentrancy lock (`:310-313`).

**Characterization:** a DAO ceiling (Configurator `default_admin`) that can retune discounts, swap the
oracle (with a bypassable deviation guard), redeploy the view, and kill new borrows — but **cannot seize
a healthy position's collateral or alter live loans' terms.** Per §5f, the ceiling reduces to "the Curve
DAO + the oracle-swap lever."

---

## 7. Where this sits in the corpus

LLAMMA adds a **new member to the liquidation-mechanism taxonomy** (§5e, "liquidation/solvency-enforcement
timeliness"): joining *discrete auction* (Maker/BendDAO), *keeper seizure* (GMX/Aave), *Stability-Pool
offset* (Liquity), and *ADL* (GMX v2), it contributes **continuous, in-AMM, oracle-driven,
liquidator-optional deleveraging**. Conceptually it *dissolves* the timeliness residual that defined the
perps audit: there is no "was the keeper fast enough" cliff because deleveraging is continuous and
self-executing by arbitrage — instead the residual **migrates** to two new places: **(a) oracle honesty
and speed** (a fast enough oracle crash still outruns soft-liquidation into the hard-liquidation
fallback, so `limit_p_o` is doing the load-bearing work), and **(b) the borrower's spread-bleed to
arbitrageurs**, a *continuous* cost that replaces the *discrete* liquidation penalty. It is also the
clearest case in the corpus of **the AMM-as-mechanism**: where Uniswap v4 (§5g) showed an AMM as a pure
conservation floor, LLAMMA shows an AMM *repurposed as a liquidation engine*, the band structure encoding
a continuous collateral→debt conversion schedule. The honest borrower statement: *you are not liquidated
at a cliff; you are continuously and reversibly converted as price falls, paying a spread each crossing —
so your risk is oracle integrity and whipsaw bleed, not a keeper's reaction time.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
