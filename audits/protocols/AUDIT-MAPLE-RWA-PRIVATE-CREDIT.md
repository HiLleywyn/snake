# Maple Finance — undercollateralized private credit (the off-chain borrower & the delegate underwriter)

**Scope.** Maple Finance v2 — on-chain pooled lending where a **Pool Delegate underwrites off-chain
(KYC'd institutional) borrowers** with little or no collateral (`maple-labs/*` v2 component repos:
pool-v2, fixed-term-loan(+manager), open-term-loan(+manager), globals-v2, liquidations). This adds a
**new trust model** to the corpus: *real-world credit risk* — a loan whose repayment depends on an
off-chain borrower's solvency the contract cannot verify, extending the off-chain-backing theme
(USDC/Ethena) from *reserves* to *uncollateralized credit*. Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**; the
off-chain-default residual, the par-NAV marking, and the delegate's discretion are characterized
factually.

**Sources (verbatim, line refs):** pool-v2 `MaplePool.sol`, `MaplePoolManager.sol`,
`MaplePoolDelegateCover.sol`; open-term `MapleLoan.sol`, `LoanManager.sol`; fixed-term `MapleLoan.sol`,
`LoanManager.sol`; `MapleGlobals.sol`.

---

## 0. The one-paragraph result

Every lending audit so far had an on-chain collateral floor — overcollateralized vaults (Maker, Morpho,
BendDAO), reserve-locked pools (GMX), or at least a liquidatable position. Maple is the first
**undercollateralized** one, and that single fact relocates the entire trust model off-chain. Lenders
deposit a pool asset (e.g. USDC) into a standard ERC4626 `MaplePool` and receive shares priced by
`totalAssets/totalSupply` — but `totalAssets` **books outstanding loan principal at par**
(`assetsUnderManagement = principalOut + interest`), so the share price reflects loans-not-yet-defaulted
*as if fully recoverable*. A **Pool Delegate** then deploys that capital: for **open-term loans (the
private-credit workhorse) the *entire principal is wired directly to the borrower with zero collateral*
— the storage has no collateral fields at all**; for fixed-term loans collateral is an optional ratio the
delegate picks, typically far below principal. **Repayment is purely borrower-driven** (`makePayment` is
a `transferFrom` from the borrower) — the contract can neither enforce nor verify it. So the dominant
residual is *not* a contract property at all: it is **(a) the off-chain borrower's solvency and
willingness to pay, and (b) the Pool Delegate's underwriting** — the delegate alone sets every loan term,
chooses which allowlisted borrowers to fund, and decides *when* (and reversibly *whether*) to mark a loan
impaired or defaulted, which directly moves the published lender share price. On default, `repossess`
recovers only the ~zero funds sitting in the loan contract, the first-loss `PoolDelegateCover` (a
governance-capped vault) is hit, and **everything beyond it is socialized to lenders**. So the Maple law:
*this is real-world credit on-chain — the floor conserves the ledger but guarantees nothing about
recovery, because the loan is a claim on an off-chain institution the contract can't see; the residual is
borrower default + delegate underwriting discretion, exactly the seam where Maple's real 2022 losses
occurred, and no on-chain conservation guarantee touches it.*

---

## 1. The pool — ERC4626 lender capital, NAV booked at par. **The floor that conserves the ledger, not recovery.**

`MaplePool` is a standard ERC4626 (`deposit → _mint(previewDeposit)`, `convertToShares/Assets` off
`totalAssets`). `totalAssets() → IPoolManagerLike(manager).totalAssets()`. The NAV definition is the key
(`MaplePoolManager.totalAssets :445-454`): `pool asset balance + Σ strategy.assetsUnderManagement()`,
where **`assetsUnderManagement = principalOut + accountedInterest + accruedInterest`** (OT LoanManager
`:539-541`, FT `:939-941`). **So the NAV counts outstanding loan principal at *face value*** — until a
delegate chooses to impair a loan, a deteriorating off-chain borrower is *invisible* in the lender share
price.

**Characterization:** the on-chain accounting conserves perfectly (shares ↔ assets ↔ booked principal),
but "booked principal" is a *par mark on an unsecured claim*, not recoverable value. This is the same
shape as the Ethena/USDC finding (§5i/§5j) — the floor is honest about the *ledger* and silent about the
*backing* — here applied to credit instead of reserves.

---

## 2. The loan — principal to an off-chain borrower, little or no collateral. **The residual's root.**

**Open-term (the private-credit instrument):** `fund() :276-290` transfers the **entire principal
directly to the borrower** (`transferFrom(fundsAsset, msg.sender, borrower, fundsLent)`), **no
drawable-funds escrow, no collateral** — `MapleLoanStorage.sol` has *zero* collateral fields (confirmed).
`makePayment :180-239` is purely a borrower-driven `transferFrom`.

**Fixed-term:** `collateralRequired() :587-589` returns a free parameter set at origination — **can be
zero or far below principal**; `_getCollateralRequiredFor :730-743` is a *proportional ratio the delegate
chose*, not a market LTV.

**Characterization:** for open-term loans the full principal is wired to an off-chain KYC'd institution
with **no on-chain collateral**; repayment is entirely contingent on the borrower's solvency and
willingness to pay, which the contract **cannot enforce or verify**. This is the corpus's first floor
where the collateral *isn't undervalued or illiquid — it doesn't exist*, by design, because the security
is an off-chain credit relationship.

---

## 3. Default / impairment / loss socialization. **Delegate-driven, par-to-loss.**

`impairLoan` (OT `:210-222`, FT `:297-330`, `onlyPoolDelegateOrGovernor`) immediately adds `principal +
accrued interest` to `unrealizedLosses` — marking down the lender share price — but is **fully reversible**
(`removeLoanImpairment`, delegate discretion). `triggerDefault` (OT `:246-289`) calls `repossess`, which
**recovers only whatever `fundsAsset` happens to sit in the loan contract (≈0 for an off-chain borrower)**,
then realizes `remainingLosses = principal + netInterest − recovered` against the pool. Loss flows through
`MaplePoolManager._handleCover :520-539`: the **first-loss `PoolDelegateCover`** is hit first (capped by
`maxCoverLiquidationPercent`), **and any loss beyond available cover is borne by lenders** as a reduced
`totalAssets`, with no further backstop. `PoolDelegateCover` itself is a 34-line vault that only the
PoolManager can move funds from; its size is governed off-chain (`minCoverAmount`, checked only at funding).

**Characterization:** on default, recovery on an uncollateralized loan is ~nil on-chain; the delegate's
first-loss cover absorbs a bounded slice and **lenders socialize the rest.** The loss path is correct and
deterministic — what it *cannot* do is recover value that isn't on-chain.

---

## 4. The Pool Delegate trust — the dominant residual. **An underwriter the contract can't second-guess.**

The Pool Delegate is the load-bearing trusted party, concretely on-chain:
- **Only the delegate deploys lender capital** — `fund` is `onlyPoolDelegate` (OT `:93`, FT `:172`),
  funding any borrower that passes the `globals.isBorrower` allowlist (operator-controlled off-chain).
- **The delegate sets *all* loan terms** (principal, rate, collateralRequired, schedule) and proposes
  refinances.
- **The delegate alone decides impairment/default *timing and reversal*** (`impairLoan` /
  `removeLoanImpairment` / `triggerDefault`), which directly moves the *published* lender share price —
  and `convertToExitAssets` subtracts only *recognized* `unrealizedLosses`, so **a delegate who delays
  marking a known-bad loan affects the price at which lenders enter/exit.**

**The residual:** the borrower's repayment is an **off-chain credit decision**; the contract verifies
neither borrower solvency nor the existence/value of any off-chain backing. So Maple's dominant trust is
**undercollateralized real-world credit risk + delegate-underwriting discretion** — neither on-chain
auditable. (Factual historical context, off-chain: this is *exactly* the seam where Maple's real 2022
losses occurred — Orthogonal Trading / M11 Credit borrower defaults — the residual the contracts
structurally cannot mitigate.)

---

## 5. Governance — central admin over delegates, pause, and untimelocked upgrades

`MapleGlobals` is the central admin: a two-step `governor` (+ `operationalAdmin`/`securityAdmin` delegates)
controls the **pool-delegate allowlist** (`setValidPoolDelegate`) and **borrower allowlist**
(`setValidBorrower`), a global + per-contract + per-function **pause** (`isFunctionPaused` gates
`whenNotPaused` everywhere), and **beacon-proxy upgrades**. Two upgrade flags worth naming:
PoolManager `upgrade` requires a *timelocked* scheduled call for the delegate **but the `securityAdmin`
can upgrade with no timelock** (`:117`); and **loan `upgrade` is callable directly by `securityAdmin` with
no timelock** on any loan instance (FT Loan `:84-90`). **Characterization:** a single security-admin key
can swap pool/loan implementation logic *instantly* over live, capital-holding contracts — centralized
upgrade power, on top of the delegate trust.

---

## 6. Where this sits in the corpus

Maple is the corpus's **real-world-credit** floor and the cleanest extension of the off-chain-backing
theme. It sits one step further off-chain than every prior lender: Morpho/BendDAO have undervaluable but
*real* on-chain collateral; Maple's open-term loans have **none** — the security is an off-chain
institution's promise, underwritten by a delegate. It mirrors §5i/§5j exactly: the floor conserves the
*ledger* (ERC4626 shares, par NAV) and is silent on the *backing* (borrower solvency), so a "sound floor"
verdict is true of the accounting and uninformative about the risk — *recompute one layer down* lands on a
borrower and an underwriter the contract can't see. On the §5e taxonomy it is a **destructible-principal /
oracle-attestation hybrid with an off-chain-actor sub-type**: the "oracle" of loan value is the *delegate's
impairment decision* (a discretionary, reversible, par-defaulting human mark — the loosest "oracle" in the
corpus), and the principal is destructible by borrower default with only a bounded first-loss backstop. The
honest lender statement: *your Maple deposit is a share of unsecured loans to off-chain institutions, marked
at par until a delegate decides otherwise; your safety is the delegate's underwriting and the borrowers'
solvency — neither visible on-chain — plus a capped first-loss cover, beyond which the loss is yours. The
contract conserves the ledger flawlessly and guarantees nothing about getting your money back.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
