# Permissioned tokens — the issuer-is-god model, and the freeze key under all of DeFi (USDC + ERC-3643)

**Scope.** Two centrally-controlled token designs that **invert** the corpus's defaults: Circle's USDC
FiatToken (`circlefin/stablecoin-evm`, freeze/pause/upgrade) and ERC-3643 / T-REX
(`TokenySolutions/T-REX`, identity-gated transfers + agent clawback). Where ~17 prior verticals chased
"delete the trust," these are *maximal* trust by design — and the finding that matters is a **meta-residual
sitting under the entire corpus**. Public source, read-only, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No exploitable defect found**; the issuer-control surface and the
integrator-inherited freeze risk are characterized factually.

**Sources read (verbatim, line refs):** USDC `FiatTokenV1.sol`, `Pausable.sol`, `Blacklistable.sol`,
`FiatTokenV2_2.sol`, `FiatTokenV2_1.sol`, `FiatTokenProxy.sol`, `AdminUpgradeabilityProxy.sol`; T-REX
`token/Token.sol`, `registry/implementation/IdentityRegistry.sol`, `roles/AgentRoleUpgradeable.sol`.

---

## 0. The one-paragraph result

Every conservation-floor audit in this corpus quietly assumed the collateral token is a **neutral
ERC20** — value moves 1:1, balances are sacrosanct, no one can reach into a holder's wallet. Permissioned
tokens violate that assumption *by design*, and USDC is the one that matters because it sits *under* most
of DeFi. The USDC issuer holds a complete control surface: a single **`pauser`** can halt **all**
transfers globally; a single **`blacklister`** can freeze **any** holder bidirectionally (the
`notBlacklisted` check is on *both* sender and receiver, so a frozen address can neither send *nor
receive* — its balance is immobilized in place); the **`masterMinter`** controls supply; and the
**`FiatTokenProxy` admin** can **replace the entire implementation wholesale** — i.e. introduce arbitrary
new logic, including direct balance seizure, over live balances. The 1:1 backing is **off-chain with
off-chain attestation** — the contract guarantees no redeemability, only `totalSupply` bookkeeping.
ERC-3643/T-REX goes further into the same philosophy: you **cannot even hold or receive** without an
on-chain KYC identity, every transfer is double-gated by an identity registry + a mutable compliance
module, and a designated **agent** can freeze wallets, force-transfer (seize), burn, and "recover" any
holder's entire position into a new wallet — **clawback as a first-class, always-available base-layer
capability** (no upgrade needed, unlike USDC). The corpus-shaking consequence is the **meta-residual**:
*every* DeFi protocol, vault, or LP pool that custodies USDC inherits Circle's freeze power as a **hidden
dependency** — a blacklist of a pool/router address bricks that contract's USDC leg, and a proxy upgrade
could re-author balance semantics underneath all integrators. So the permissioned-token law: *the
trustless floors audited everywhere else in this corpus rest on a token layer that, for the most-used
collateral in DeFi, is the opposite of trustless — an issuer-is-god design whose freeze/seize/upgrade
keys are a residual under every protocol that touches it, and which no amount of on-chain conservation
review can see or constrain.*

---

## 1. USDC — the issuer control surface. **Freeze, pause, mint, upgrade.**

**Pause — global halt by one address.** `Pausable.pause() (:70-73)` is `onlyPauser` and sets `paused =
true`; the `whenNotPaused` modifier (`:54-57`) gates `transfer`, `transferFrom`, `mint`, `burn`, and
`approve`. **One key freezes the entire token's movement.**

**Blacklist — per-holder bidirectional freeze.** `Blacklistable.blacklist(account) (:71-74)` is
`onlyBlacklister`; the `notBlacklisted` modifier (`:50-56`) is applied to `transfer` for **both**
`msg.sender` *and* `to` (`FiatTokenV1.sol:292-293`), and likewise on transferFrom/mint/burn/approve.
**Net effect: a blacklisted address can neither send nor receive — its balance is frozen in place.** In
V2.2 the freeze and balance share one slot: `_setBlacklistState (:196-204)` sets the high bit, and
`_setBalance` **reverts if the account is blacklisted** (`:215-226`) — a frozen balance literally cannot
be mutated until unblacklisted.

**Mint — masterMinter-controlled.** `configureMinter`/`removeMinter` (`:329-355`, `onlyMasterMinter`);
`mint` (`:121-145`, `onlyMinters`, gated by pause + blacklist). Burn is minter-self-only (`:363-378`) —
Circle can't burn a victim's tokens via this path; the freeze *immobilizes*, and historical seizure
required an upgrade.

**Upgrade — the proxy admin owns everything.** `AdminUpgradeabilityProxy.upgradeTo(newImpl) (:107-109,
ifAdmin)` and `upgradeToAndCall (:121-132)` let the admin **replace the implementation wholesale** over
live balances — arbitrary new logic, including direct balance seizure. The admin lives in an
unstructured slot (`:44-45`). **This is the ultimate control: the token's *meaning* is mutable by the
proxy admin.**

**The backing floor is off-chain.** The contract enforces only `totalSupply_` bookkeeping
(`FiatTokenV1.sol:139,374`); the 1:1 USD reserve is **off-chain with off-chain attestation**, so on-chain
logic guarantees *no redeemability* — the peg trust is non-cryptographic, identical in shape to the LST
beacon-balance and Ethena custody residuals but with *no* on-chain sanity bound at all.

---

## 2. ERC-3643 / T-REX — identity-gated transfers + base-layer clawback. **The same philosophy, further.**

**You cannot hold or receive without on-chain KYC.** `transfer (Token.sol:417-426)` reverts unless
**both** `isVerified(_to)` *and* `compliance.canTransfer(from,to,amount)` pass, with frozen-wallet and
frozen-token checks:
```solidity
require(!_frozen[_to] && !_frozen[msg.sender], "wallet is frozen");
if (_tokenIdentityRegistry.isVerified(_to) && _tokenCompliance.canTransfer(msg.sender, _to, _amount)) { ... }
revert("Transfer not possible");
```
`IdentityRegistry.isVerified (:173-217)` returns false if the address has no registered ONCHAINID or
lacks valid KYC claims from trusted issuers. **No identity ⇒ cannot transact.** `mint (:454-459)` is
itself identity-gated and agent-only.

**The agent's seize/freeze powers (all base-layer, no upgrade):**
- `forcedTransfer (:431-449)` — move tokens from any holder, **auto-unfreezing** as needed, compliance
  bypassed. **The seize primitive.**
- `burn (:464-474)` — burn any holder's tokens. **Clawback.**
- `setAddressFrozen (:479-483)`, `freezePartialTokens (:488-493)` — full/partial freeze.
- `recoveryAddress (:297-322)` — reassign a holder's **entire** balance + frozen state + identity to a
  new wallet.
- `pause (:188-199)` — global halt.
Owner can swap the whole identity registry and compliance module (`setIdentityRegistry`/`setCompliance`,
`onlyOwner`) — **the rule set governing who may transact is fully mutable by the issuer.**

**Characterization:** maximal issuer control *by design*. Unlike USDC's freeze-only model (seizure needs
an upgrade), T-REX's `forcedTransfer`/`burn` are **first-class always-available clawback** — the token
is explicitly a permissioned, regulator-facing instrument where the issuer is omnipotent.

---

## 3. The meta-residual — Circle's freeze key sits under the whole corpus

This is the finding that reframes prior audits. Every protocol I characterized as having a sound,
conserve-by-construction floor — Polymarket's CTF, Azuro's pool, GMX's vault, Morpho's markets, every
stablecoin and LST — **holds USDC (or a USDC-like permissioned token) as collateral or a leg**, and
therefore **inherits Circle's control surface as a hidden dependency it cannot see or constrain:**
1. **Blacklist bricks the integrator.** Because `notBlacklisted` is checked on the *receiver*, blacklisting
   a pool/router/vault address immobilizes that contract's *entire* USDC balance — withdrawals, swaps, and
   redemptions in that leg simply revert. A protocol's "conservation floor cannot leak" is true *only as
   long as Circle doesn't freeze the contract.*
2. **Proxy upgrade re-authors balances.** The FiatTokenProxy admin can change what a USDC balance *means*
   underneath all integrators — a non-cryptographic, non-auditable dependency under thousands of contracts.
3. **The peg is off-chain.** USDC's 1:1 backing has no on-chain guarantee — so a stablecoin "fully backed
   by USDC" has *imported* an off-chain attestation residual it cannot verify, on top of its own.

**The honest restatement of dozens of prior "sound floor" verdicts:** *sound, conditional on the
collateral token being neutral — which, for USDC, it is not.* This does not invalidate the floor analyses;
it **names the token layer as a residual** those analyses implicitly trusted. It is the cleanest example
in the corpus of a risk that is invisible at the protocol level and only appears when you read one layer
down.

---

## 4. Where this sits in the corpus

Permissioned tokens are the **anti-pole of the own-vs-delete dial** — every other "delete the trust"
instance (Uniswap v2, Liquity, the ERC-4337 EntryPoint, Morpho) removed the admin; these *maximize* it,
deliberately, because the use case (regulated money, compliant securities) **requires** an omnipotent
issuer. They add a residual the §5e taxonomy implied but never isolated: the **token-layer control
residual** — freeze/pause/seize/upgrade authority over balances, which is *destructible principal* (§5e
class 5) and a *governance ceiling* (class 2) **fused and pushed beneath every protocol that holds the
token**. And they sharpen the corpus's central method: *recompute, don't trust the summary* — applied
here to the **token**: a protocol audit that stops at "the floor conserves" trusts the ERC20's summary of
itself; reading one layer down reveals that for the dominant collateral, the issuer can freeze the floor.
The honest user statement: *the trustless DeFi protocol you're using is trustless only above the token
layer — and the most common token under it (USDC) has an issuer who can freeze your funds, freeze the
protocol, and rewrite the token's logic, none of which the protocol's own conservation guarantees can
prevent.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
