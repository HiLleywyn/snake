# Blue-chip deep hunts — the infrastructure tier: the singleton AMM, the lending market, the LST, the CDP dollar

**Why this hunt exists.** A continuation of the depth-not-breadth mode, aimed at the **highest-TVL,
infrastructure-grade** protocols — the ones other protocols build on: **Uniswap v4** (the singleton AMM, up to
$15.5M bounty — the largest in crypto), **Aave v3** (the reference lending market), **Lido** (the largest LST), and
**Sky/Maker** (the USDS/sUSDS CDP dollar, historically a $10M bounty). Each is a full-lifecycle read of the state
machine + the end-to-end conservation invariant.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute every rounding
direction and conservation invariant from source, and pin deployed-vs-HEAD honestly. Anything real and live would be
stopped and routed for private disclosure (redacted here). **All four came back clean — no live finding.**

| Target | Tier | The conservation invariant | Version pinned | Verdict |
|---|---|---|---|---|
| **Uniswap v4** (`v4-core`) | singleton AMM | `NonzeroDeltaCount == 0` before every lock close | deployed (`0x0000…8A90`) | **clean** |
| **Aave v3** (`aave-v3-origin`) | lending | scaled mint-down/burn-up (collateral), mint-up/burn-down (debt) | **v3.7 dev** (ahead of deployed v3.6) | **clean** |
| **Lido** (`lidofinance/core`) | LST | shares↔ETH floor both ways; withdrawal `min(rate@req, rate@final)` | **v3 dev** (ahead of deployed v2) | **clean** |
| **Sky/Maker** (USDS/sUSDS/litePSM) | CDP dollar | `chi` accrual exact; USDS minted ⟺ DAI locked; PSM buffer = backing + fees | deployed (audit-report-pinned) | **clean** |

---

## 1. Uniswap v4 — the flash-accounting conservation (the highest-value invariant in DeFi)

**Repo:** `Uniswap/v4-core` (`46c6834`), the audited source for the singleton at `0x000000000004444c…`. Two
load-bearing invariants, both holding at the line level:

- **Conservation — safe.** `unlock` runs the caller's callback then enforces `NonzeroDeltaCount.read() != 0 → revert`
  **before** `Lock.lock()` — one chokepoint. The count is maintained *only* by `_accountDelta` (increment on
  `0→nonzero`, decrement on `nonzero→0`), and every value-moving op (swap/modifyLiquidity/donate/take/settle/mint/
  burn/clear) routes through it. **No path can close the lock with an outstanding debt** ⟹ no unsettled value leaves
  the singleton. The native-ETH `settle` uses `msg.value`; ERC20 uses the synced reserve delta then resets the slot
  (no double-settle, no wrong-currency credit).
- **Per-pool hook trust — safe (by design).** Hook-returned deltas are attributed to the **hook's own account**
  (`_accountPoolBalanceDelta(key, hookDelta, address(key.hooks))`), so any value a hook "takes" is *its own* debt
  under the count==0 close; permission bits (low 14 of the hook address) reject a RETURNS_DELTA flag without the
  action flag. A malicious hook can only harm users who opted into *its* pool — **it cannot touch other pools or the
  singleton's reserves**.
- **Math / fees / 6909 — safe.** Swap rounds amountIn up / amountOut down / fee up; protocol fee rounds down (favors
  LPs) and is capped at 0.1%/direction; ERC6909 supply per currency is exactly the net settled deposit. The
  alarming-looking items (single-position fee-growth inflation, fee-growth underflow subtraction) are documented
  by-design properties, not defects.

**No live finding.**

---

## 2. Aave v3 — the scaled-balance lattice + the v3.7 liquidation-rounding fix

**Repo:** `aave-dao/aave-v3-origin` (`d7919c0`), the **v3.7 dev branch** (past the deployed `v3.6.0` tag; five fresh
March-2026 audits in-repo). Honestly pinned: v3.6 is deployed, v3.7 this HEAD is audited-but-pre-release.

- **Scaled-balance accounting — clean.** All directional rounding is centralized in `TokenMath`: aToken mints floor /
  burns ceil, vToken (debt) mints ceil / burns floor, collateral balance floors / debt balance ceils. The
  explicit-amount withdraw burns `ceil(amount/index)` so `floor(scaledBurned·index) ≥ amount` (solvency preserved);
  the treasury accrual *under*mints. No same-block deposit/withdraw inflation (floor-mint then ceil-burn nets ≤ 0 for
  the user).
- **Liquidation — clean.** The v3.7 `liquidation-rounding.md` change makes every site deterministic and against the
  liquidator (`percentMulFloor` seized, `percentDivCeil` debt-needed, floor/ceil split on the protocol fee) — closing
  a half-up non-determinism a liquidator could previously game. The new `hasNoCollateralLeft` uses scaled-balance
  consumption capped at the borrower's scaled balance, with the fee re-capped against the post-burn balance — the
  ordering that prevents a double-ceil over-seize/DoS; bad debt books to `reserve.deficit` and is cleared by
  `_burnBadDebt`.
- **Structural find:** classic **isolation mode (debt ceiling) and siloed borrowing are entirely removed in v3.7**
  (replaced by the `isolated` eMode flag), so those bypass classes don't apply to this tree. HF counts collateral via
  floored balances + floored base conversion, debt via ceiled balances + `mulDivCeil` — conservatively protocol-favorable.

**No live finding.** (The GHO facilitator lives in a separate repo — out of this clone's scope, noted.)

---

## 3. Lido — shares↔ETH + the withdrawal share-rate cap

**Repo:** `lidofinance/core` (`eb4ff80`), the **v3 ("stVaults"/external-shares) dev line** — *not* deployed mainnet
v2 (sets contract version 3, has `finalizeUpgrade_v3`, extracts the rebase into a standalone `Accounting.sol`). The
carry-forward invariants were analyzed; a finding would need re-checking against deployed v2 bytecode.

- **Shares↔ETH — clean.** Both conversions floor (user gets ≤ fair shares); first-staker inflation is defused by the
  `0xdead` bootstrap holder (the "stone in the elevator" keeping `internalShares > 0` forever); the v3 split-rate uses
  internal-ether/internal-shares, with external ether derived floored — internal-holder conversions unperturbed.
- **Withdrawal queue — clean (the load-bearing invariant).** A claim pays `min(recorded request rate, finalization
  max rate)`, floored — **a post-request positive rebase can't increase a withdrawer's payout**; `_finalize` enforces
  `amountOfETH ≤ stETHToFinalize`; the double-claim guard sets `claimed` before `_sendValue` with `assert(remove())`;
  forged hints are bounded to the correct checkpoint range.
- **Oracle rebase — clean.** The positive-rebase limiter hard-caps `totalPooledEther` to the configured max (excess
  left in vaults for future reports); reported vault balances are floored against actual on-chain balances (reverts
  if over-reported); the fee-share mint uses the correct denominator. Trusting the oracle committee's CL-balance input
  is by-design, distinct from a sanity-bound code bug.

**No live finding.**

---

## 4. Sky/Maker — the `chi` accrual, the 1:1 converter, the litePSM buffer

**Repos:** `usds` (`d65551d`), `sdai`@`susds` branch (`SUsds.sol`, `dfc7f41`), `dss-lite-psm` (`dbf0022`),
`dss-allocator` (`6e99d87`); each carries matching in-repo audit reports (deployed==audited rests on those reports +
the mainnet impl address, not a byte-diff — Etherscan 403'd). The newer wrappers over the battle-tested pot core.

- **sUSDS savings accrual — clean.** `drip` updates `nChi = rpow(ssr, now−rho)·chi/RAY` and sucks **exactly**
  `floor(TS·nChi/RAY) − floor(TS·chi/RAY)` from the vow — conservation holds with no shortfall/over-mint. All four
  ERC4626 directions favor the vault (deposit shares down, mint assets up, withdraw shares up, redeem assets down).
  Every mutating path calls `drip()` first (sets `rho = block.timestamp`), so a same-block deposit→withdraw uses
  identical `chi` — **no free-yield capture**; `rpow` reverts on overflow; first-depositor inflation N/A (`chi`
  initialized to `RAY`, monotone, totalSupply tracked internally not via `balanceOf`).
- **USDS + converter — clean.** `DaiUsds.daiToUsds` pulls `wad` DAI → `daiJoin.join` → `usdsJoin.exit` mints exactly
  `wad` USDS, with the constructor enforcing a shared vat — **every USDS minted is backed by a locked DAI**, exact 1:1,
  no fee/rounding. `Usds.mint` is `auth` (the legitimate minter `UsdsJoin.exit` requires backing); permit recomputes
  the domain separator per call (chainId-bound, replay-safe).
- **litePSM — clean.** Principal strictly 1:1; `tin`/`tout` fee on top/off, bounded `≤ WAD`; the buffer invariant
  `gem.balanceOf(pocket)·conv + dai.balanceOf(this) == art + accumulatedFees` holds across fill/trim/chug (`chug`
  withdraws only fees, capped so backing is never removed; the under-collateralization underflow reverts in 0.8).
  The sub-wei fee-waiver on tiny swaps is documented, not a principal leak.

**No live finding.** Auth is the consistent `wards`/`rely`/`deny` pattern throughout; rate bounds enforced
(`ssr ≥ RAY`, no negative yield).

---

## Synthesis — the infrastructure tier

1. **One architecture, four times: round-against-the-actor + a conservation backstop.** Uniswap's count==0 before
   lock close; Aave's scaled mint-down/burn-up lattice; Lido's floor-both-ways + the withdrawal rate cap; Sky's exact
   `chi` suck + the PSM buffer identity. The deep read's job was confirming the *whole* lifecycle obeys it — and in
   each case the single backstop (the v4 delta count, the Aave solvency-preserving burn, the Lido min-rate, the Sky
   vat backing) is what converts per-step rounding choices into a hard invariant.
2. **Deployed ≠ HEAD is the rule at this tier, not the exception.** Three of the four ran *ahead* of deployed: Aave
   v3.7 (vs v3.6), Lido v3 (vs v2), and the broader batch's Morpho v1.0 / Ethena-correction. Each agent pinned the
   version and stated the carry-forward caveat — a confident "clean on HEAD" is worthless without saying *which*
   bytecode that is. Blue-chips run active dev branches; the discipline is naming it every time.
3. **The newest mechanism is where the attention goes — and where the design is tightest.** Aave's v3.7
   liquidation-rounding determinism fix, Lido v3's external-shares split-rate, Uniswap's hook-delta attribution, Sky's
   litePSM buffer — each is the freshest code, and each is *more* carefully constrained than the legacy core, not less
   (the v3.7 fix exists precisely to remove a roundable edge). The residual risk has migrated to integration and
   governance, not the primitive.
4. **"Looks alarming, is by-design" recognized four more times.** Uniswap's fee-growth inflation/underflow, Aave's
   LTV-0 collateral, Lido's oracle-trust, Sky's sub-wei fee waiver — each traced to *why it's safe* and not promoted
   to a finding. The method's value at this tier is overwhelmingly true-negative discrimination on code that is
   designed to look surprising.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
