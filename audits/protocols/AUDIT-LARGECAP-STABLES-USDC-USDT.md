# Large-cap stablecoins — a deep comparative audit of USDC vs USDT (the settlement layer of crypto)

**Scope.** The two dominant fiat-backed stablecoins, side by side, at depth: Circle **USDC** FiatToken
(`circlefin/stablecoin-evm`, `FiatTokenV2_2`, Solidity 0.6.12, behind `FiatTokenProxy`) and Tether
**USDT** `TetherToken` (the Etherscan-verified `0xdAC17F958D2ee523a2206206994597C13D831ec7`, Solidity
`^0.4.17`, sourced verbatim from `tethercoin/USDT`). These two tokens are the collateral floor under most
of the rest of this corpus, so their trust model is *inherited* by nearly every protocol audited
elsewhere. This deepens the earlier permissioned-tokens note (which only skimmed USDC's blacklist/pause)
into a full comparative of the control surface, the integration surface, the upgrade model, the role
topology, and the off-chain backing residual. Public source, read-only, recompute-don't-trust.
**Defensive, characterize-don't-exploit. No exploitable defect found**; the divergent issuer powers and
integration footguns are characterized factually.

**Sources (verbatim, line refs):** USDC `v2/{EIP3009,EIP2612,FiatTokenV2,FiatTokenV2_2,EIP712Domain}.sol`,
`util/{SignatureChecker,ECRecover,EIP712}.sol`, `v1/{FiatTokenV1,Ownable,Pausable,Blacklistable,
FiatTokenProxy}.sol`, `v1.1/Rescuable.sol`, `upgradeability/AdminUpgradeabilityProxy.sol`; USDT
`TetherToken.sol` (451 lines, `Pausable, StandardToken, BlackList`).

---

## 0. The one-paragraph result

USDC and USDT are **both** issuer-is-god designs — each can freeze, pause, mint, and replace its own logic
— but they are *architecturally and philosophically different gods*, and the differences are exactly the
ones an integrator and a regulator care about. The decisive divergence is **seizure**: USDT's owner can
call `destroyBlackFunds` to **zero a blacklisted address's entire balance and burn it from supply**
(irreversible confiscation), whereas USDC's blacklister can only **freeze** — immobilize, not destroy
(historical seizures required a proxy *upgrade*). USDT also carries a **live owner-settable transfer tax**
(`setParams`, currently 0, capped <0.2%) that USDC has no equivalent of, and an **upgrade-by-forwarding**
model (`deprecate` points every call at an arbitrary new contract) versus USDC's **transparent storage
proxy**. Their *trust topology* differs too: USDC splits power across **five logic roles + a separate
proxy admin** (two independent Circle multisigs — policy vs code), while **every** USDT power collapses
onto a **single owner** on a `^0.4.17` contract with single-step ownership transfer. Their *integration*
surface inverts: USDT is **non-ERC20-compliant** (its `transfer`/`transferFrom` return no `bool`, and it
has a fee-on-transfer lever) — the canonical footgun that forced DeFi onto `SafeERC20` — while USDC is
**hyper-modern** (EIP-2612 permit, EIP-3009 gasless authorizations, EIP-1271 smart-wallet sigs) with its
own subtler surface (a `transferWithAuthorization` front-running/nonce-griefing nuance that
`receiveWithAuthorization`'s `to == msg.sender` gate exists to close). And both share the residual that
dwarfs all of this: **the 1:1 backing is entirely off-chain**, with redemption gated to whitelisted
partners and a real depeg history (USDC→\$0.87 during SVB, March 2023; USDT wobbles repeatedly). So the
large-cap-stable law: *these are not trustless tokens — they are centrally-administered claims on
off-chain reserves, USDT with maximal unilateral owner power (including outright seizure and a fee lever)
on legacy code, USDC with split, modern, more-constrained controls — and every "sound conservation floor"
in this corpus that holds one of them inherits that issuer's freeze/seize/mint/upgrade keys and that
off-chain backing as a residual it cannot see or constrain.*

---

## 1. The control surface — freeze vs freeze-AND-destroy, and the fee lever

| Power | USDC | USDT |
|---|---|---|
| **Freeze a holder** | `blacklist` — `notBlacklisted` checked on **sender AND receiver** (can't send or receive); V2.2 stores the flag in the balance slot's high bit, and `_setBalance` reverts if blacklisted | `addBlackList` — checked on `msg.sender`/`_from` only (a blacklisted address can still *receive*) |
| **Seize / destroy** | **No** — freeze only; destruction historically needs a proxy upgrade | **Yes** — `destroyBlackFunds` zeroes the balance and **decrements `_totalSupply`** (irreversible burn) |
| **Transfer fee** | **None** | `setParams(basisPointsRate, maximumFee)` — owner-settable tax to the owner's balance, currently 0, **capped <20bps / <50 tokens** |
| **Pause** | `pause` (pauser role) halts transfer/mint/burn/approve | `pause` (owner) halts transfer/transferFrom |

**USDT's seizure (the decisive difference), verbatim:**
```solidity
function destroyBlackFunds (address _blackListedUser) public onlyOwner {   // TetherToken.sol:291
    require(isBlackListed[_blackListedUser]);
    uint dirtyFunds = balanceOf(_blackListedUser);
    balances[_blackListedUser] = 0;
    _totalSupply -= dirtyFunds;          // :295  burns the seized funds from supply
}
```
USDC has *no such function* — `_setBlacklistState` (FiatTokenV2_2 `:196-204`) sets a high bit and freezes;
`_setBalance` reverts on a blacklisted account, so the balance is immobilized but **not destroyed**.

**USDT's fee lever, verbatim:**
```solidity
function setParams(uint newBasisPoints, uint newMaxFee) public onlyOwner {  // :429
    require(newBasisPoints < 20);   // hardcoded cap — the only protection
    require(newMaxFee < 50);
    basisPointsRate = newBasisPoints; maximumFee = newMaxFee.mul(10**decimals);
}
```
`transfer` deducts `fee = min(value·bps/10000, maximumFee)` to `balances[owner]` (`:127-136`). **A single
owner call taxes every transfer.** This is also a *fee-on-transfer* footgun: any DeFi contract that
assumes `amountReceived == amountSent` would mis-account if the fee were ever turned on.

---

## 2. The mint model — decrementing per-minter allowance (USDC) vs owner issue/redeem (USDT)

**USDC — two-tier, capped, decrementing.** `masterMinter` whitelists minters and assigns each a
`minterAllowed[minter]` cap; each `mint` consumes from it (FiatTokenV1 `:133-141`):
```solidity
require(_amount <= minterAllowed[msg.sender], "mint amount exceeds minterAllowance");  // :135
totalSupply_ = totalSupply_.add(_amount);
minterAllowed[msg.sender] = mintingAllowedAmount.sub(_amount);   // :141  decrement
```
`configureMinter` *overwrites* the allowance (top-up or throttle). No global supply cap; the ceiling is the
sum of granted allowances. A compromised `masterMinter` can self-configure a large allowance and mint —
but mint is `whenNotPaused` and the structure at least *separates* the policy key (masterMinter) from the
mint act.

**USDT — owner mints/burns to its own balance, no allowance, no SafeMath on the path** (`:406-426`):
```solidity
function issue(uint amount) public onlyOwner { require(_totalSupply + amount > _totalSupply); balances[owner] += amount; _totalSupply += amount; }
function redeem(uint amount) public onlyOwner { require(_totalSupply >= amount); balances[owner] -= amount; _totalSupply -= amount; }
```
Raw arithmetic guarded by hand-rolled `a+b>a` overflow checks; **no per-minter structure, no cap** — supply
is whatever the single owner decides. **Neither token has any on-chain reserve/collateral check** — minting
is pure issuer discretion in both; USDC merely partitions the discretion across roles.

---

## 3. The upgrade model — transparent proxy (USDC) vs deprecate-and-forward (USDT)

**USDC — EIP-1967-style transparent proxy.** The `FiatTokenProxy` admin (a *separate* storage slot,
`keccak256("org.zeppelinos.proxy.admin")`) can `upgradeTo`/`upgradeToAndCall` to arbitrary new logic over
live storage (`AdminUpgradeabilityProxy:107-132`), and `_willFallback (:160-166)` **forbids the admin from
calling implementation functions through the proxy** (admin/user separation). So code-governance is a
distinct super-role from token-policy.

**USDT — forward-by-call.** A single `deprecate(addr)` flips `deprecated = true` and points *every* ERC20
entrypoint at an arbitrary `upgradedAddress` (`:387-391`); thereafter `transfer`/`balanceOf`/etc. delegate
to `UpgradedStandardToken(upgradedAddress).transferByLegacy(...)` (`:342-396`). **No timelock, no validation
that the target is even a contract, no admin/user separation** — the same owner that runs policy also flips
the entire token's logic. Both models can replace semantics under live balances; USDC's is at least
*structurally separated* and standardized.

---

## 4. The role topology — split (USDC) vs single owner (USDT)

**USDC — 5 logic roles + a separate proxy admin, all `update*` setters `onlyOwner`:**

| Role | Power | Set by |
|---|---|---|
| `owner` | apex of policy graph; rotates the four roles below | self (`transferOwnership`) |
| `masterMinter` | whitelist minters + set caps | owner |
| `pauser` | global pause | owner |
| `blacklister` | freeze any holder | owner |
| `rescuer` | sweep *other* ERC20s sent to the contract (`rescueERC20`, not user USDC) | owner |
| proxy `admin` | **`upgradeToAndCall` — arbitrary new logic, overrides everything** | proxy admin (separate) |

Two independent trust roots **by design**: `owner` (token policy) and proxy `admin` (code) — held by
different Circle multisigs.

**USDT — one owner for everything.** `Ownable` single `owner` (`:45-74`), single-step `transferOwnership`
(no two-step accept, silently no-ops on zero address), gating pause, blacklist, **destroy**, issue/redeem,
fee-setting, and deprecate/forward. No contract-level timelock or multisig; `^0.4.17` predates the
`constructor` keyword and built-in overflow checks. **All emergency and economic powers collapse onto a
single key** at the contract layer (any multisig is external/operational).

---

## 5. The integration surface — USDT's non-compliance vs USDC's gasless modernity

**USDT breaks the ERC20 ABI.** `transfer`/`transferFrom`/`approve` return **no `bool`** (`:85,95,...`), so
`require(token.transfer(...))` reverts or misbehaves — the canonical "USDT integration bug" that forced the
ecosystem onto `SafeERC20`. Plus the fee-on-transfer lever (§1) and the obsolete `onlyPayloadSize`
short-address guard, which can break some batch/meta-call wrappers. **An auditor reviewing any protocol's
"conservation floor" that holds USDT must check it uses safe-transfer wrappers and tolerates fee-on-transfer
— two assumptions most DeFi floors silently make and USDT silently violates.**

**USDC is hyper-modern, with a subtler surface.** It adds:
- **EIP-2612 `permit`** (sequential per-owner nonce, EIP2612 `:35,97`; a `deadline == type(uint256).max`
  "no expiry" sentinel `:85`).
- **EIP-3009 gasless authorizations** — `transferWithAuthorization`/`receiveWithAuthorization`/
  `cancelAuthorization` with **random `bytes32` nonces** in a boolean replay map (`EIP3009:48`), a
  `validAfter`/`validBefore` window, and EIP-712 sig check.
- **The front-running nuance (the key integration footgun):** `transferWithAuthorization (:117-145)` puts
  **no constraint on `msg.sender`** — anyone with the signed blob can submit it. `receiveWithAuthorization`
  is byte-identical *except* `require(to == msg.sender) (:205)`. So a relayer/mempool observer can copy a
  broadcast `transferWithAuthorization` and **front-run the intended submitter, burning the nonce** and
  breaking a contract flow that expected to call it and react in the same tx. **`receiveWithAuthorization`'s
  payee-must-be-caller gate is what makes atomic pull-deposits safe** — integrators that use
  `transferWithAuthorization` for deposits are exposed. `cancelAuthorization` is the only pre-emptive
  defense and is itself a signed, front-runnable op.
- **EIP-1271 smart-wallet sigs** (V2.2, via `SignatureChecker.isValidSignatureNow`, `extcodesize`-dispatch)
  — note contract-wallet signatures are **revocable and time-varying** (a once-valid permit can become
  invalid across blocks), and an EOA that later deploys code (EIP-7702-style) switches verification paths.
- **V2.2 domain-separator fix:** earlier versions **cached** the EIP-712 domain separator at `initializeV2`,
  freezing the chainid — a hard-fork producing a new chainid would have enabled cross-chain signature
  replay. V2.2 **recomputes it live every call** (`FiatTokenV2_2:82-84` via `chainid()`), closing that
  fork-replay window at a small gas cost.

ECRecover has explicit malleability protection (rejects upper-half `s`, enforces `v ∈ {27,28}`).

---

## 6. The residual that dwarfs the code — off-chain backing & redemption. **Both.**

Neither contract enforces the peg. USDC's FiatToken tracks only `totalSupply_`; USDT's only `_totalSupply`.
The **1:1 USD backing is entirely off-chain** — bank deposits + short-dated T-bills (USDC, with monthly
attestations and, post-SVB, more transparency) and a historically more opaque reserve (USDT: commercial
paper → T-bills, with attestations rather than full audits). Critical facts an on-chain audit cannot verify:
- **Redemption is gated.** Only whitelisted institutional partners can redeem 1:1 directly with the issuer;
  retail exits via the secondary market, so the on-chain token has **no contractual redeemability** for
  most holders.
- **Depeg history is real.** USDC traded to **~\$0.87** in March 2023 when ~\$3.3B of reserves were briefly
  stranded at the failed Silicon Valley Bank — a *banking-counterparty* risk entirely outside the contract.
  USDT has wobbled to ~\$0.95 in multiple stress events. Both recovered, but the events prove the residual:
  **the peg is a claim on off-chain reserves at off-chain banks, not an on-chain invariant.**
- **The backing is the dominant residual**, exactly as with Ethena USDe (§5i) but with regulated banks
  instead of CeFi perp custody — different counterparty, same structural fact: *the floor is only as real as
  the off-chain reserve behind it, and nothing on-chain attests it.*

---

## 7. The systemic meta-point — these two tokens are the floor under the corpus

USDC and USDT are the collateral leg, settlement asset, or quote token in a large fraction of every protocol
this corpus audited — Polymarket's CTF, the perps vaults, the lending markets, the CDP secondary pegs, the
intent settlements. Each such protocol's "sound, conserve-by-construction floor" verdict therefore **inherits
two residuals it cannot see**:
1. **The issuer's keys.** A blacklist of a pool/router address **bricks that contract's stablecoin leg**
   (USDC checks the receiver; USDT can *destroy* a frozen balance); a `deprecate`/`upgrade` can re-author the
   token's meaning underneath all integrators. The protocol's conservation guarantee holds *only while the
   issuer doesn't act.*
2. **The off-chain backing.** A "fully USDC-backed" position has imported an unauditable banking-reserve
   residual on top of its own.

**The honest restatement:** every DeFi "floor conserves" verdict that involves USDC/USDT is *conditional on
the issuer's forbearance and the reserve's solvency* — neither visible on-chain. USDT concentrates this risk
maximally (single owner, seizure, fee lever, forward-upgrade, legacy code) and USDC distributes and
modernizes it (split roles, freeze-not-destroy, transparent proxy, gasless standards) — but **both** are
centrally-administered off-chain-backed claims, and that is the residual beneath crypto's settlement layer.

---

## 8. Comparison at a glance

| Axis | USDC | USDT |
|---|---|---|
| Compiler / pattern | 0.6.12, transparent proxy | `^0.4.17`, deprecate-and-forward |
| Freeze | yes (sender+receiver) | yes (sender/from only) |
| **Seize/destroy** | **no** (freeze only) | **yes (`destroyBlackFunds`)** |
| Transfer fee | none | **owner-settable, capped <0.2%** |
| Mint | per-minter decrementing allowance (masterMinter) | owner `issue`/`redeem`, no cap |
| Upgrade | proxy admin (separate key), admin/user split | owner `deprecate` → arbitrary forward |
| Roles | 5 logic roles + separate proxy admin | **single owner** |
| ERC20 ABI | compliant + permit/3009/1271 | **non-compliant (no bool return)** |
| Integration footgun | `transferWithAuthorization` front-run/nonce-grief | no-return + fee-on-transfer (SafeERC20 required) |
| Backing | off-chain (banks/T-bills, attested) | off-chain (reserves, attested) |
| Redemption | gated to partners | gated to partners |
| Depeg precedent | ~\$0.87 (SVB, Mar 2023) | ~\$0.95 (multiple) |

---

## 9. Posture & conclusion

- **No exploitable contract defect found** in either token — both are doing exactly what they are designed to
  do. The findings are *trust-model* facts, not bugs: USDT grants its single owner maximal unilateral power
  (seizure, fee, forward-upgrade) on legacy code; USDC splits and modernizes the same authority, trading
  outright destruction for freeze and adding a gasless surface with its own front-running nuance.
- **The dominant residual in both is off-chain** (reserve solvency + gated redemption), proven live by the
  SVB depeg — unauditable from the contracts.
- **Method note:** this is "recompute, don't trust the summary" applied to the *most-trusted asset in
  crypto*. The summary — "USDC and USDT are dollars" — hides that they are *centrally-administered claims*
  whose issuers can freeze, (for USDT) destroy, mint, and re-author them, and whose dollar value is an
  off-chain banking fact. The two are not interchangeable: an integrator must handle USDT's non-compliant
  transfer and fee lever, must not assume redeemability for either, and must treat the issuer's freeze/seize
  power as a live dependency under any "trustless" floor that holds them.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
