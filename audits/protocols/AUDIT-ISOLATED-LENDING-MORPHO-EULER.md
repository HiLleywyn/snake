# Isolated lending — the oracle as a per-market choice (Morpho Blue vs Euler v2)

**Scope.** The two modern *isolated*-lending primitives: Morpho Blue (`morpho-org/morpho-blue`, a
single immutable 555-line contract) and Euler v2 (`euler-xyz/euler-vault-kit` + `ethereum-vault-
connector`, the modular EVK/EVC). This extends the lending vertical from NFT collateral (BendDAO/
NFTfi/Blend) to **fungible isolated markets**, and surfaces a design move the corpus hadn't seen: the
oracle as a *per-market caller choice* rather than a protocol-wide trusted feed. Public source,
read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect
found**; the caller-chosen-oracle and bad-debt-socialization surfaces are characterized factually.

**Sources read (verbatim, line refs):** Morpho `Morpho.sol`, `SharesMathLib.sol`, `MarketParamsLib.sol`,
`ConstantsLib.sol`, `IOracle.sol`; Euler `EthereumVaultConnector.sol`, EVK `modules/{Vault, Borrowing,
Liquidation, RiskManager, Governance}.sol`, `shared/{Base, EVCClient, LiquidityUtils, lib/ProxyUtils}.sol`.

---

## 0. The one-paragraph result

Isolated lending makes explicit a choice every prior lending audit treated as ambient: **who picks the
oracle.** In pooled designs (Aave/BendDAO) the protocol governance picks one trusted feed per asset;
the risk is the governance ceiling. In *isolated* designs the seam moves — and the two leading
primitives move it in opposite directions, which is the whole story. **Morpho Blue** makes the oracle a
**per-market, caller-chosen, never-validated** input: anyone can `createMarket` with *any* `oracle`
address (the only owner-curated gates are the IRM and LLTV allowlists), and `IOracle.price()` is a bare
`uint256` with no staleness, decimals, or bounds enforced by Morpho at all. The entire price-trust
decision is *delegated to whoever creates the market and whoever chooses to supply into it* — a
malicious oracle fully compromises one market but is **contained to that `Id`**. **Euler v2** freezes
the oracle **per-vault and immutable** (baked into the metaproxy trailing data, unchangeable even by the
governor), conventionally pointing it at a *governed* `EulerRouter` — so the vault address is fixed but
the price *sources behind it* remain governable, shifting (not removing) the trust to the router's
governor. Both conserve cleanly underneath (ERC4626 shares with conservative rounding and virtual
offsets), both **socialize bad debt to suppliers automatically and permissionlessly** when a position's
collateral hits zero, and both sit on the same isolated-floor idea. The novelty Euler adds is the
**EVC's deferred-check model** — solvency is *not* enforced inline but accumulated and validated *once*
at the end of a batch (the same "let it be imbalanced mid-flight, force it to balance at the boundary"
shape as Uniswap v4's flash accounting). So the isolated-lending law: *the conservation floor is the
same conservative-rounding share ledger; the residual is, as always, the oracle — and isolation turns
the oracle from a governance ceiling into a per-market (Morpho) or per-vault (Euler) *configuration
choice*, which means the critical audit object is no longer "the admin" but "who chose this market's
oracle, and is it sound."*

---

## 1. The conservation floor — isolated ERC4626 share ledgers. **Sound in both.**

**Morpho Blue.** A market is `MarketParams{loanToken, collateralToken, oracle, irm, lltv}`, its `Id` the
keccak of those five fields (`MarketParamsLib:16-20`). The four primitives (supply/withdraw/borrow/repay,
`Morpho.sol:169-298`) round **always in the protocol's favor** — supply `toSharesDown`/`toAssetsUp`,
withdraw the opposite (`:216-217`) — with the liquidity guard `totalBorrowAssets ≤ totalSupplyAssets`
(`:223`) on every outflow. Shares use a **virtual offset** (`SharesMathLib:20-44`,
`VIRTUAL_SHARES = 1e6`, `VIRTUAL_ASSETS = 1`) — the OZ inflation-attack mitigation, with the explicit
note that virtual borrow shares "behave like unrealizable bad debt." `_accrueInterest (:482-508)` adds
*identical* `interest` to both `totalBorrowAssets` and `totalSupplyAssets` (`:489-490`) — **that
lockstep is the conservation link** — then mints fee shares; `irm == address(0)` legally means zero
interest.

**Euler EVK.** ERC4626 e-tokens with the same against-the-user rounding (`Vault.sol:124-179`); debt is
d-tokens; `flashLoan` is balance-checked, no fee (`Borrowing.sol:145-158`). The difference is *when*
solvency is checked — see §3.

**Verdict:** both floors conserve by construction. As everywhere in the corpus, the floor is not where
the risk lives.

---

## 2. The residual — the oracle, now a configuration choice. **The contrast.**

**Morpho — caller-chosen, never-validated, contained per-market.** `liquidate` and `_isHealthy` fetch
the price per-call, per-market:
```solidity
uint256 collateralPrice = IOracle(marketParams.oracle).price();   // :361
require(!_isHealthy(marketParams, id, borrower, collateralPrice), HEALTHY_POSITION);  // :363
// health: maxBorrow = collateral · price / 1e36 · lltv ; healthy iff maxBorrow >= borrowed (:514-537)
```
`IOracle` is a **bare `price()` returning `uint256` — no staleness, no decimals, no bounds enforced by
Morpho.** `createMarket (:150-164)` validates *neither* the oracle nor the tokens; only `isIrmEnabled`
and `isLltvEnabled` (owner allowlists) gate creation. **The entire price-trust decision is delegated to
the market creator and the suppliers who opt in.** A malicious or manipulable oracle *fully* compromises
that market — but the isolation is the mitigation: the damage is **contained to the `Id`**, and passive
capital only enters via a curator/depositor's explicit choice. This is the §5f "delete the governance,
push the choice to the user" dial applied to the oracle itself.

**Euler — per-vault, immutable, but pointing at a governed router.** The oracle and `unitOfAccount` are
**not in vault storage and cannot be changed even by the governor** — they are baked into the EIP-3448
metaproxy trailing data (`ProxyUtils.metadata():15-21`, surfaced read-only by `Governance.oracle()`),
with `validateOracle` rejecting `address(0)` (`LiquidityUtils:122-124`). The recommended pattern points
that immutable address at a **governed `EulerRouter`**, so **the vault is fixed but the price *sources*
behind it remain governable** — the trust moves to the router's governor rather than disappearing.
Liquidation uses **mid-point** prices for the health/discount and **bid/ask** for the post-op status
check (`LiquidityUtils:36-55`) — a deliberate conservatism the single-price Morpho design doesn't have.

**Characterization:** isolation relocates the oracle residual from a *protocol governance ceiling* to a
*per-market (Morpho) or per-vault (Euler) configuration object*. The critical audit question is no
longer "what can the admin do" but **"who chose this market's oracle, and is it sound for this
collateral."**

---

## 3. Euler's EVC — deferred solvency checks. **The v4-shaped mechanism, in lending.**

The EVC's defining move: solvency is **not enforced inline**. `call`/`batch`/`controlCollateral` cache
context and `setChecksDeferred()` (`EthereumVaultConnector.sol:553-614`); `requireAccountStatusCheck`/
`requireVaultStatusCheck` (`:696-729`) merely *insert the account/vault into a set* when checks are
deferred; only the **outermost frame** (`restoreExecutionContext:916-925`) runs `checkStatusAll` for
accounts then vaults, draining the sets. **This lets a batch transiently violate solvency mid-execution
and be validated once at the end** — structurally the *same* idea as Uniswap v4's net-zero-delta flash
accounting (§ AMM audit): let the books be imbalanced mid-flight, force them to balance at the boundary.
The checks enforce the **single-controller rule** (`numOfControllers > 1 → EVC_ControllerViolation
:941`) and `staticcall` the controller's `checkAccountStatus`. The reentrancy guards
(`nonReentrantChecks*` `:151-192`) and the in-progress lock are the load-bearing protections of this
deferred model.

**Liquidation's `forgive` (the soundness-critical detail):** Euler liquidation deliberately calls
`forgiveAccountStatusCheck(violator)` (`Liquidation.sol:217`) — because the violator is *expected* to be
left unhealthy post-seizure. Its safety rests on three *stated* assumptions (comment `:200-211`): the
violator wasn't pre-deferred (`isAccountStatusCheckDeferred(violator)` guard `:95`), a
`liquidationCoolOffTime` has elapsed (`:98`, anti-self-liquidation), and **collateral transfer
functions make no external calls**. **Factual flag:** any LTV-configured collateral whose `transfer` has
side effects would break the forgiveness assumption — a per-listed-collateral audit item.

---

## 4. Bad-debt socialization — automatic and permissionless in both

- **Morpho (`:389-402`):** when a liquidated position's `collateral == 0`, all remaining `borrowShares`
  become bad debt and **both** `totalBorrowAssets` and `totalSupplyAssets` are decremented by
  `badDebtAssets` — i.e. the loss is written off **pro-rata against all suppliers' share value**, with no
  governance gate. Always socializes on collateral-zero.
- **Euler (`Liquidation.sol:220-234`):** same write-off, but **gated** behind
  `MIN_SOCIALIZATION_LIABILITY_VALUE`, a `CFG_DONT_SOCIALIZE_DEBT` flag, and `checkNoCollateral`.

**Characterization:** in both, a bad oracle or thin-liquidity collateral **directly dilutes passive
suppliers** with no admin in the loop — which is precisely why the *oracle choice at market/vault
creation* is the dominant decision. Socialization is the mechanism that turns an oracle failure into a
supplier loss.

---

## 5. Governance — Morpho minimal-immutable vs Euler dual-mode

- **Morpho:** owner powers are *exhaustively* `setOwner`, `enableIrm`/`enableLltv` (**one-way** — cannot
  disable), `setFee` (capped `MAX_FEE = 0.25e18`), `setFeeRecipient`. **There is no function by which the
  owner can pause a market, move funds, change a market's oracle/IRM/LLTV after creation, or seize
  collateral.** Non-upgradeable. *Factual flag:* the one-way allowlists mean a later-discovered-flawed
  IRM/LLTV can never be revoked for *new* market creation.
- **Euler:** `governorOnly` gates `setLTV`/`setIRM`/`setHookConfig`/fees/discount/cool-off; a vault is
  explicitly **governed** (mutable config, for passive deposits) or **finalized** (`governorAdmin ==
  address(0)`, frozen forever), orthogonal to upgradeable/immutable (factory beacon vs metaproxy). LTV
  *increases* apply immediately, *decreases* can be ramped to avoid hard liquidations (`Governance:268-
  315`).

Both sit firmly on the "minimal governance" side — Morpho by hard immutability, Euler by an *opt-in*
finalize switch. Per §5f, each ceiling reduces to "an allowlist + a capped fee" (Morpho) or "a per-vault
governor that can self-abolish" (Euler).

---

## 6. Where this sits in the corpus

Isolated lending extends the lending vertical and sharpens the oracle finding from the
Chainlink/Pyth audit: **isolation turns the oracle from a shared governance ceiling into a per-market
configuration choice**, which is the "delete the trust, push the choice to the user" dial applied to the
*price source*. Morpho is the extreme — a caller-chosen, unvalidated oracle, contained per-`Id`,
where *the market-creation choice is the entire risk*; Euler is the middle — an immutable per-vault
oracle that conventionally re-introduces governance one level down (the router). It also shows the
v4-shaped **deferred-settlement** mechanism recurring in a *second* domain (EVC checks-at-batch-end ≈
v4 net-zero-delta-at-unlock), suggesting "let it be imbalanced mid-flight, validate once at the
boundary" is a general primitive, not an AMM quirk. And it confirms the §5e *destructible-principal*/
socialization motif: bad debt is written off against suppliers automatically and permissionlessly, so
the oracle residual and the supplier-loss bucket are the *same* risk viewed from two ends. The honest
user statement: *your supplied capital is as safe as the specific oracle whoever created this market/
vault chose — the protocol conserves perfectly and will never let an admin touch your funds, and will
just as surely socialize a bad-oracle loss onto you with no one to appeal to.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
