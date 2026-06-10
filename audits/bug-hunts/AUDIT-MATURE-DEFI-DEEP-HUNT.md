# Mature-DeFi deep hunts — the second blue-chip wave, and the oracle-staleness class found again (known + de-risked)

**Why this hunt exists.** A third round of depth-not-breadth, on four more live large/mid-cap protocols across
lending, AMM, and restaking: **Compound v3 (Comet)**, **Balancer v3**, **Curve Stableswap-NG** (Vyper), and
**Kelp rsETH** (LRT). Full state-machine + conservation reads. The standout result is on Kelp: the deep read found
the **consumer-side oracle-staleness class** — the same class as the corpus's one live finding (the redacted Silo
disclosure) — here **known (C4-flagged), disputed, and materially de-risked** by the protocol's newer architecture.
That closes a loop: the class recurs, and the method recognizes it *and* calibrates its severity down honestly.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** **All four came back
clean — no new live finding.**

| Target | Vertical | The conservation invariant | Verdict |
|---|---|---|---|
| **Compound v3 (Comet)** | lending (single base asset) | `getReserves = balance − pvSupply(totalSupply) + pvBorrow(totalBorrow)`; dust to reserves | **clean** |
| **Balancer v3** | AMM (Vault rewrite) | transient net-zero (`_nonZeroDeltaCount==0`); buffer settled on measured deltas | **clean** |
| **Curve Stableswap-NG** | AMM (Vyper) | D/y rounds against the user; complete `@nonreentrant` lock map | **clean** |
| **Kelp rsETH** | LRT (restaking) | rsETH price stored + rate-limited; withdrawal = `min(req, claim)` value | **clean** (known oracle residual, de-risked) |

---

## 1. Compound v3 (Comet) — the signed-balance single-base model

**Repo:** `compound-finance/comet` (`d5a30b0`, `main`/"Curent Dev" — possibly ahead of the tag-pinned deployments,
flagged; also: the box's `/tmp/comet` already held the *CometBFT* clone from an earlier hunt — re-cloned fresh). The
distinct single-borrowable-base model's conservation holds:

- **Present-value/principal — clean.** Supply value floors both directions (`presentValueSupply`,
  `principalValueSupply`), borrow principal ceils — so the through-zero base moves drop the supplier's recorded value
  by **≥ amount** on withdraw and raise it by **≤ amount** on supply, dust strictly to reserves. Index accrual is
  monotonic, `safe64`-guarded, runs before every base mutation (reward-timing can't be gamed).
- **Absorb + buyCollateral — clean.** `absorb` gates on `liquidateCollateralFactor` (> the borrow factor, so healthy
  accounts can't be absorbed) and seizes collateral worth strictly *more* than the base credited — no value created.
  `buyCollateral` is `nonReentrant` (neutralizing the stale-reserves reentrancy the legacy comments warn about), with
  the discount `storeFrontPriceFactor·(1−liquidationFactor) ∈ [0,1)` so collateral can't be bought below the floor.
- **Collateral/caps/permissions — clean.** Collateralization re-checked after every collateral move; supply cap
  enforced; `allowBySig` EIP-712 with low-s/`v∈{27,28}` malleability guards + strict per-signer nonce.

**No live finding.** The "standard, non-rebasing collateral only" assumption is a governance-enforced protocol
assumption, not a code bug.

---

## 2. Balancer v3 — the Uniswap-v4-style Vault + the ERC4626 buffer

**Repo:** `balancer/balancer-v3-monorepo` (`80fd29c`, post-audit-hardened, audits through 2026-01). The rewrite mirrors
v4's transient accounting and defends the new high-risk surface:

- **Transient net-zero — clean.** `_nonZeroDeltaCount == 0` enforced at unlock close; `settle` credits the *measured*
  `balanceOf` reserve delta capped by the hint (can't over-credit, surplus discarded); `sendTo` decrements reserves
  before transfer. All `nonReentrant`.
- **ERC4626 buffer (the newest, highest-risk surface) — clean.** Every wrap/unwrap settles against measured
  `balanceOf` deltas with **revert-on-deficit**, plus deliberate **1-wei anti-manipulation haircuts**
  (`previewDeposit(amountGiven−1)−1` etc.), a `forceApprove(wrapper, 0)` after each op (blocks a malicious wrapper
  draining via leftover approval), and a min-wrap floor. The residual — per-wrapper ERC4626 rate trust — is the
  documented "buffer LPs bear that wrapper's rate risk" assumption, **not a vault-level drain**.
- **Pool math + hooks — clean.** Rounding favors the vault throughout (stable `D` Newton + a new `MAX_IMBALANCE_RATIO`
  guard; weighted powers rounded up); hook-adjusted amounts are per-pool-gated, re-validated against the user's
  slippage limit, and must net to zero through the transient system.

**No live finding.** (`WONTFIX.md` items — StableSurge exact-in/out non-equivalence, tiny-creator-fee rounding revert
— are known non-theft items.)

---

## 3. Curve Stableswap-NG — the Vyper-language read

**Repo:** `curvefi/stableswap-ng` (`2abe778`). The language-first read paid off:

- **Vyper surface — clean.** All contracts on **0.3.10** (clear of the 2023 reentrancy-lock compiler-bug
  `0.2.15–0.3.0` range); the lock map is complete on every state-mutating external *and* every price/supply getter an
  integrator trusts (`price_oracle`/`D_oracle`/`get_virtual_price`/`totalSupply` all `@nonreentrant('lock')`). The one
  deliberately-unlocked getter, `get_p`, is the documented instantaneous spot integrators are warned not to price
  against. The 70 `unsafe_*` sites are each guarded by a provably-non-zero divisor or a positivity guard.
- **D/y invariant — clean.** Newton iterations round uniformly against the user (the `dy = _xp[j] − y − 1` buffer,
  floor divisions, `+1` on imbalance burns); non-convergence raises (LPs still exit via the solve-free proportional
  `remove_liquidity`).
- **Rebasing/ERC4626 — clean.** Measured `balanceOf − admin_balances` deltas with admin fees tracked separately
  (rebase slashing can't touch them), and `exchange_received` is **hard-disabled for rebasing pools** — closing the
  stolen-rebase path.
- **EMA oracle — clean.** `upkeep_oracles` feeds the *previous* snapshot into the moving average and returns the
  unchanged stored EMA within a block, so a same-block trade can't move `price_oracle`.

**No live finding.** External rate/donation trust is documented as deployer/integrator responsibility.

---

## 4. Kelp rsETH — the oracle-staleness class, found again and calibrated

**Repo:** `Kelp-DAO/LRT-rsETH` (`3dded88`, v5.3.1; read via raw.githubusercontent since clone was network-blocked —
deployed-pin unverified). Clean at HEAD, no new bug — but the most instructive result of the batch.

- **rsETH price — known oracle risk, now mitigated by design.** The v5.3.1 oracle is *fundamentally different* from
  the 2023 C4-audited version: it **neutralizes the C4 HIGH** (the live-recompute arbitrage). `rsETHPrice` is now a
  **stored** state variable written only through a threshold-guarded `_updateRsETHPrice()` — an up-move beyond the
  daily band reverts (unless MANAGER), a down-move beyond it **auto-pauses** the deposit pool + withdrawal manager +
  oracle. Per-LST prices read the LSTs' own on-chain exchange rates (rETH `getExchangeRate`, sfrxETH `pricePerShare`,
  …), not flash-manipulable spot.
- **THE RECURRENCE (known, not novel, de-risked):** `ChainlinkPriceOracle.getAssetPrice` still does
  `latestRoundData()` with **no `updatedAt` staleness check and no `price > 0` check** — the *exact* consumer-side
  oracle-staleness class that is the corpus's one live finding (the redacted Silo disclosure). Here it is **known**
  (C4 upheld it HIGH; Kelp disputed it) and **materially de-risked**: the major LSTs use their own exchange-rate
  oracles, and `rsETHPrice` only moves through the auto-pausing updater, so Chainlink drift can't compound into the
  receipt price beyond the daily band before the pause trips. Characterize-only, route privately if wired to a live
  asset — **not published, not promoted to a fresh finding.**
- **Deposit/withdrawal — clean.** Mint truncates down (user gets ≤ fair rsETH) against the *stored* price (no
  same-block donate-then-mint); the withdrawal payout is `min(request-time value, claim-time value)` so a user can
  **never** receive more than the rsETH is worth at either point, with double-claim blocked by `delete` and the
  delay/nonce gates enforced.
- **Asset accounting — clean.** Idle-in-NDC (`balanceOf`) and staked-in-strategy (EigenLayer shares via
  `sharesToUnderlyingView`) are disjoint buckets; queued-withdrawal shares are tracked separately — no double-count or
  omission skews the price.

**No new live finding.**

---

## Synthesis — what the third deep round added

1. **The single architecture, confirmed a third time, now with a copied pattern.** Balancer v3 *literally adopted*
   Uniswap v4's transient net-zero settlement — the singleton + count==0 pattern is becoming the standard AMM safety
   model. Compound's reserves identity, Curve's D/y-against-the-user + lock map, Kelp's min(req,claim) withdrawal: the
   round-against-the-actor + conservation-backstop architecture holds across every vertical and every language.
2. **The corpus's live-finding class recurred — and the method handled it exactly right.** Kelp's
   `ChainlinkPriceOracle` missing-staleness is the Silo class. The deep read (a) *recognized* it, (b) labeled it
   **known not novel** (C4 history), (c) assessed the **residual as low** (the stored-price + auto-pause architecture),
   and (d) routed it as characterize-only rather than publishing or inflating. That is the whole discipline in one
   finding: recompute, attribute novelty honestly, calibrate severity to the actual exploitability, disclose
   privately.
3. **The newest mechanism is the tightest — again.** Kelp's v5.3.1 stored-rate-limited oracle, Balancer's buffer
   1-wei haircuts, Aave's v3.7 liquidation-rounding fix (prior batch): each protocol's *freshest* code is its most
   carefully constrained, often built specifically to close a prior audit's finding. The exploitable residual keeps
   migrating to the integration seam (the un-hardened oracle adapter) and the governance/trust boundary.
4. **"Looks like a bug, is known-and-mitigated" is its own verdict.** Not every flagged line is clean *or* a finding;
   Kelp's is a third category — a real weakness that prior auditing already named and the current architecture
   defangs. Reporting it as exactly that (worth flagging to the program, not a fresh disclosure) is more useful than
   either ignoring it or re-claiming it.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. The one
oracle residual (Kelp, known/de-risked) is characterize-only; any live exploitable instance would be private-first +
redacted. No new finding here.*
