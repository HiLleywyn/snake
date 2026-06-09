# Ethena USDe — a synthetic dollar whose backing lives off-chain (delta-neutral + CeFi custody)

**Scope.** Ethena's USDe synthetic dollar (`code-423n4/2023-10-ethena` @ `9fd8e26`, the canonical audited
source; Solidity 0.8.19). USDe is a **new peg model** for the corpus: a dollar token backed by a
delta-neutral position whose collateral is **routed off-chain to CeFi custodians** and hedged on CeFi
perp exchanges — so the backing is *not on-chain auditable*. Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**; the
off-chain-custody residual and the trusted-order pricing are characterized factually.

**Sources read (verbatim, line refs):** `USDe.sol`, `EthenaMinting.sol`, `interfaces/IEthenaMinting.sol`,
`SingleAdminAccessControl.sol`, `StakedUSDe.sol`, `StakedUSDeV2.sol`, `USDeSilo.sol`.

---

## 0. The one-paragraph result

Every stablecoin the corpus saw kept its backing *on-chain and verifiable*: Maker's `vat` ledger, Liquity's
ETH troves, even USDC's "off-chain reserve" at least holds nothing on-chain to *misreport*. USDe is the
first whose **economic floor is deliberately off-chain**, and the contracts are honest about it: there is
**no oracle, no collateralization check, no liquidation, no peg-enforcement code anywhere**. The on-chain
`EthenaMinting` is a *routed swap+mint*: a user (benefactor) EIP-712-signs an `Order` whose
`collateral_amount ↔ usde_amount` ratio is set **by Ethena's off-chain server**, a `MINTER_ROLE` operator
submits it, and the contract **immediately `safeTransferFrom`s the collateral straight to allowlisted
custodian wallets** — *the contract never custodies mint collateral.* USDe is then minted to the
beneficiary. The actual dollar peg is maintained **entirely off-chain**: the spot collateral sits in CeFi
custody, and a short-perp hedge on CeFi exchanges makes the position delta-neutral. So the peg residual
decomposes into three things, **none of which any on-chain audit can see**: (a) custodian solvency holding
the routed spot, (b) CeFi perp-exchange counterparty risk for the hedge, and (c) funding-rate risk — if
perpetual funding goes persistently negative, the hedge bleeds and erodes backing. The on-chain code is a
well-built *operator interface* around this — per-block mint/redeem rate limits bound a compromised
minter's blast radius, a low-trust `GATEKEEPER_ROLE` can only halt/de-authorize (never mint or steal), and
the EIP-712 + nonce + custodian-allowlist machinery is sound — but it is *interface, not backing*. So the
USDe law: *the floor's conservation is trivially on-chain (mint exactly against a signed order) and
economically off-chain (is that order fairly priced, and is the delta-neutral position actually solvent at
its custodians and exchanges) — the dominant residual is, by design, a CeFi trust the contracts route to
and cannot verify.*

---

## 1. The token — a deliberately minimal mintable ERC20. **All logic is elsewhere.**

`USDe.sol` (37 lines) is plain OZ `ERC20Burnable + ERC20Permit` with **one mint authority**:
```solidity
function mint(address to, uint256 amount) external {
  if (msg.sender != minter) revert OnlyMinter();   // :28-31  single externally-set minter
  _mint(to, amount);
}
```
`setMinter (:23-26, onlyOwner)` names the one minter (in production, `EthenaMinting`); `renounceOwnership`
is overridden to **revert** (`:33-35`) — ownership is permanent. The token carries **no collateral, no peg,
no oracle** — total mint-supply control is concentrated in one externally-set address. *All economic logic
lives in the minter contract.*

---

## 2. The minting engine — a routed swap to off-chain custody. **The load-bearing design.**

`EthenaMinting.mint (:162-187, onlyRole(MINTER_ROLE), belowMaxMintPerBlock)`:
1. `verifyOrder (:339-348)` — the benefactor (or its `delegatedSigner`) must EIP-712-sign the `Order`
   (`order_type, expiry, nonce, benefactor, beneficiary, collateral_asset, collateral_amount,
   usde_amount`); `ECDSA.recover` must match, and `block.timestamp ≤ expiry`. **There is no on-chain price
   oracle — the `collateral_amount ↔ usde_amount` ratio is whatever the off-chain server signed, trusted
   verbatim.**
2. `verifyRoute (:351-374)` — every route address must be in the **custodian allowlist** and the ratios
   must sum to exactly `10_000` bps.
3. `_transferCollateral (:413-433)` — **pulls collateral directly from the benefactor to the custodian
   addresses** (`token.safeTransferFrom(benefactor, addresses[i], amountToTransfer)`): *the contract never
   holds mint collateral.*
4. `usde.mint(beneficiary, usde_amount)`.

`redeem (:194-216, onlyRole(REDEEMER_ROLE))` burns the benefactor's USDe and pays collateral **from the
contract's own balance** (`_transferToBeneficiary`) — so redemption liquidity must be *pre-funded* into the
contract by custodians sending collateral back; there is **no on-chain pull from custodians.** Replay is
guarded by a per-benefactor nonce bitmap + expiry.

**Characterization:** on-chain this is an atomic, conserving mint-against-a-signed-order, but the collateral
is *immediately routed out* to CeFi custodian wallets and never retained. The contract is a **permissioned
operator interface**; the backing it implies lives elsewhere.

---

## 3. The controls — well-scoped, but the admin holds the keys that matter

- **Per-block rate limits** (`belowMaxMintPerBlock`/`belowMaxRedeemPerBlock :97-107`) bound a compromised
  minter's or rogue order's blast radius; setters are `DEFAULT_ADMIN_ROLE`.
- **`GATEKEEPER_ROLE` break-glass** (`:229-285`): `disableMintRedeem` (zeroes both limits), `removeMinter
  Role`/`removeRedeemerRole`. The gatekeeper can **only subtract** power — it cannot mint or grant roles. A
  correctly minimal-trust circuit breaker.
- **Allowlists** (`addCustodianAddress`/`addSupportedAsset`, `DEFAULT_ADMIN_ROLE`).

**The residual in the controls:** `DEFAULT_ADMIN_ROLE` sets the rate limits, names the minter, and **can
add any address as a custodian** — i.e. it can re-point collateral routing to an address it controls. Rate
limits + gatekeeper *bound* but do not *eliminate* this. The admin key is the central on-chain trust.

---

## 4. The peg/backing residual — off-chain, not on-chain auditable. **The dominant trust.**

There is **no on-chain peg-enforcement code** — confirmed: no oracle, no collateralization ratio, no
liquidation, no price feed in either contract. USDe's $1 backing is asserted entirely off-chain:
- **Spot collateral** is `safeTransferFrom`'d straight to custodian wallets at mint (`:426`) — it lives in
  **CeFi custody, invisible to these contracts** (no proof-of-reserves).
- **The short-perp hedge** (the delta-neutral leg) is **entirely off-chain** on CeFi exchanges; nothing in
  the repo references it.
- **The 1:1 ratio** is whatever the off-chain server signs.

So the peg trust decomposes — *all off-chain, none auditable here* — into **(a) custodian solvency**,
**(b) CeFi perp-exchange counterparty risk**, and **(c) funding-rate risk** (persistently negative funding
bleeds the hedge and erodes backing). **This is the dominant residual, and it is structurally invisible to
on-chain analysis** — the cleanest case in the corpus of a floor whose *conservation* is trivially on-chain
but whose *solvency* is entirely off-chain.

**The staking wrapper (`StakedUSDe`/sUSDe, ERC4626):** yield streams in over an 8h `VESTING_PERIOD`
(`transferInRewards`, `REWARDER_ROLE`; `totalAssets = balanceOf(this) − unvested`), guarded by `MIN_SHARES
= 1 ether` against the ERC4626 donation attack; V2 adds a 90-day `cooldownDuration` (withdraw disabled when
cooldown > 0; USDe parks in a `USDeSilo` until `cooldownEnd`). The yield source is the **off-chain protocol
earnings** (LST staking + perp funding), delivered by a privileged rewarder — so even the *yield* is an
off-chain-attested number, like an LST rebase. The staking side also carries strong centralization:
`redistributeLockedAmount` lets admin **burn a FULL-restricted staker's balance and re-mint it elsewhere**
(a seizure power, scoped to restricted accounts).

---

## 5. Governance — single two-step admin + scoped gatekeeper, no proxy

`SingleAdminAccessControl`: a single, **two-step-transferable** admin (`transferAdmin` + `acceptAdmin`;
granting `DEFAULT_ADMIN_ROLE` auto-revokes the prior admin). Contracts are **non-upgradeable** (no proxy);
"upgrade" = deploy new + `USDe.setMinter` to re-point (controlled by the separate USDe `Ownable2Step`
owner). No in-contract timelock/multisig (those are operational). **Characterization:** powerful admin
levers (set/zero rate limits, manage minter/custodian/asset allowlists, set cooldown, staker
blacklist/redistribute), bounded by the gatekeeper's halt-only power and the per-block caps.

---

## 6. Where this sits in the corpus

USDe is the corpus's first **off-chain-backed floor** — the peg residual is not a worse on-chain oracle but
*no on-chain backing at all*, by design. It sharpens the LST/RWA finding (§5g, §5i): the
committee-attests-an-off-chain-number residual is here taken to its limit — *the entire backing is an
off-chain CeFi position, and the contracts are an honest interface to it that makes no solvency claim.* It
is the dual of the permissioned-token finding: USDC's *issuer* can freeze an on-chain balance; USDe's
*backing* is off-chain and unverifiable — both are reminders that **the on-chain conservation floor is only
as real as the off-chain facts it imports** (a reserve, a custodian, a hedge, a funding rate). It also
confirms the §5h off-chain-actor sub-type: the Ethena off-chain server (pricing the orders) and custodians
(holding the collateral) are actors whose *behavior* the contract cannot bound — it bounds only the
*payment path* (signed order, rate limit, allowlist) and routes trust to them. The honest user statement:
*USDe mints exactly against a signed order and the on-chain controls are sound, but your dollar is backed
by a delta-neutral position held at CeFi custodians and exchanges that no on-chain audit can verify — your
peg is a bet on custodian solvency, exchange counterparty risk, and funding staying non-negative, none of
it visible in the contracts.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
