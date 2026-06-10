# Deep hunts IV — ve(3,3), modular perps, and forks: the oracle-integration seam as the recurring residual

**Why this hunt exists.** A fourth depth round on four more live large/mid-cap protocols — **Aerodrome** (the
dominant Base ve(3,3) DEX), **Synthetix v3** (modular core + perps), **Frax v3** (frxETH/sfrxETH + FraxlendV3), and
**Spark** (SparkLend, an Aave-v3 fork + the ALM liquidity controller). Full state-machine + conservation reads. Two
through-lines emerged worth centering on: (1) the **fork-delta methodology** — on a fork, hunt only the delta from
upstream; (2) the **oracle-integration seam is the recurring residual** — in 3 of these 4 (and echoing the corpus's
one live finding), the *only* thing worth flagging was at the consumer-side oracle read, never the core math.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** **All four came back
clean — no live finding.**

| Target | Vertical | The conservation invariant | The residual (all by-design/known) | Verdict |
|---|---|---|---|---|
| **Aerodrome** | ve(3,3) DEX | k-invariant on post-fee balances; reward `earned` over complete epochs only | (none — Solidly fork-class bugs remediated) | **clean** |
| **Synthetix v3** | modular perps | Σ pool credit == Σ market debt (watermark delta distribution) | the configured **oracle node-graph** (off-chain) | **clean** |
| **Frax v3** | LSD + lending | xERC4626 `storedTotalAssets`; Fraxlend high-borrow/low-liquidate | Chainlink-stale → **UniV3-TWAP fallback** | **clean** |
| **Spark** | Aave-fork + ALM | per-route fail-closed rate limits; net-flow cancel accounting | (none — DSR/SSR rate sources non-manipulable) | **clean** |

---

## 1. Aerodrome — the Solidly fork-class bugs, all remediated

**Repo:** `aerodrome-finance/contracts` (`1ba3081`, the Velodrome V2 form; Base mainnet). The classes Solidly forks
historically bled from are each fixed:

- **k-invariant — clean.** Checked on **post-fee, freshly re-measured balances** (`_k(balance) < _k(reserve) →
  revert K()`, after fees are physically removed) — the corrected ordering, strictly more conservative than original
  Solidly's buggy inline-adjusted-reserves form. The stable `_get_y` Newton iteration rounds in the pool's favor;
  everything is balance-measured (fee-on-transfer safe).
- **Gauge/bribe rewards — clean.** `earned` iterates **complete epochs only**, reading balance at each epoch's *end*,
  with `_getReward` setting `lastEarn = block.timestamp` so an intra-epoch re-claim returns 0. No double-claim across
  the boundary, no claim-after-withdraw.
- **veNFT — clean.** Canonical Curve slope/bias decay; `merge`/`split`/`withdraw` are `voted`-guarded and conserve
  `supply`; the flash-NFT guard returns 0 balance if `ownershipChange == block.number`.
- **Voter/Minter — clean.** One vote per epoch, double-vote blocked, killed-gauge shares routed back to the minter
  (not stranded/stolen), the weekly emission flip runs exactly once.

**No live finding.** (Deployed==audited asserted by code-identity/authorship, not a bytecode diff — flagged.)

---

## 2. Synthetix v3 — modular debt conservation, and the oracle node-graph residual

**Repo:** `Synthetixio/synthetix-v3` (`23585f7`, v3.13.0 `main` — not a pinned tag; router is Cannon-generated). The
hard part — conservation across a complex modular system — holds:

- **Pool⇄Market — clean.** Market net debt (`reportedDebt + netIssuance − depositedCollateral`) is distributed to
  pools using a `lastDistributedMarketBalance` **watermark**, so only the *delta* is pushed (no double-count, no
  drift); a capped pool's accrued debt moves to `pendingDebtD18` and is reclaimed later. The invariant **Σ value into
  `poolsDebtDistribution` == market balance delta == Σ value pushed pool→vaults** holds, with per-actor
  `lastValuePerShare` checkpoints so no actor claims value accrued before it held shares.
- **Perps — clean.** `reportedDebt = max(0, collateralValue + Σ marketDebt − totalAccountsDebt)`, with `marketDebt`
  driven by a **debt-correction accumulator** updated symmetrically on every position change — **cannot under-report
  to drain the backing pools** (the canonical design). Settlement uses a fixed benchmark price at `commitmentTime +
  delay` (commit-reveal, no oracle-window timing extraction).
- **Liquidation — clean.** Seized collateral + debt socialized pro-rata to remaining stakers; no over-seize or dodge.

**No live finding. The residual is the oracle node-graph:** the oracle-manager node *primitives* (staleness +
deviation circuit breakers) are sound, but end-to-end safety depends on the *configured* node graph (a missing
staleness wrapper, a manipulable TWAP/reducer source) — an off-chain config question, correctly scoped out, and the
most productive next step.

---

## 3. Frax v3 — xERC4626, frxETH 1:1, and the Fraxlend TWAP-fallback residual

**Repos:** `frxETH-public` (`018eaf4`) + `fraxlend` (`2bed49d`); sFRAX repo unreachable (identical xERC4626 core,
covered). All clean:

- **xERC4626 rewards cycle — clean.** `totalAssets = storedTotalAssets + unlockedRewards` (never `balanceOf`), so a
  donation can't move the share price; rewards unlock **linearly** (not a step), so deposit-before-sync earns only the
  forward slice and deposit→immediate-withdraw captures only a sub-second slice (paying round-against-user on exit).
  No instant-capture front-run.
- **frxETHMinter — clean.** 1:1 backing by construction (`minter_mint(recipient, msg.value)`, `onlyMinters`),
  `activeValidators[pubKey]` blocks double-deposit, the beacon deposit contract independently validates the
  `depositDataRoot`.
- **FraxlendV3 — clean.** The dual-oracle asymmetry is conservative: borrow/collateral-removal uses the **high** rate
  (more collateral required), liquidation uses the **low** rate (harder to flag insolvent), with a `maxOracleDeviation`
  gate blocking new borrows when low/high diverge; share math rounds against the user throughout.

**No live finding. The residual is the oracle fallback:** Fraxlend collapses to the UniV3 TWAP when Chainlink returns
stale/bad data (emitting only `WarnOracleData`) — the documented "TWAP backstop" accepted design, governed per-pair.

---

## 4. Spark — the fork-delta methodology, and the ALM controller conservation

**Repos:** `sparklend-advanced` (`cf5bc26`, the custom rate strategies) + `spark-alm-controller` (`0fee4b5`, v1.10.0)
+ `dss-direct-deposit` + `sparklend-conduits`. **Fork-delta focus:** the SparkLend core is a near-verbatim Aave-v3
fork (covered by Aave's audits — deprioritized); the hunt targeted only Spark's custom code.

- **Rate strategies — clean.** `PotRateSource`/`SSRRateSource` read the DSR/SSR from the immutable Maker/Sky
  `pot`/`susds` (not per-block manipulable); `CappedFallbackRateSource` bounds `[lower, upper]` with an OOG-griefing
  try/catch guard; negative slopes clamp to 0.
- **ALM controller (highest) — clean (conservation holds).** Every relayer action is keyed `(asset, destination)` so
  funds move only to admin-pre-funded destinations (not arbitrary), CCTP `mintRecipient` is admin-set per-domain, and
  receivers are hard-coded to `address(proxy)`. PSM/DaiUsds swaps are 1:1 with paired rate-limit decrement/increment
  (net-flow cancel accounting); ERC4626 deposits enforce a `maxExchangeRate` donation guard; the `doDelegateCall` is
  **never invoked** and CONTROLLER-gated (no relayer-reachable delegatecall). Rate limits **fail closed**
  (un-configured route → revert), the FREEZER can instantly `removeRelayer`, and RELAYER has no self-escalation.
- **D3M — clean.** A rogue operator is debt-ceiling-bounded — can't mint unbacked DAI; the USDS-pool join/exit hop is
  guarded by strict post-conditions.

**No live finding.** The OTC-desk and D3M-operator surfaces carry documented, bounded, by-design trust assumptions
(max loss = one outstanding OTC swap / debt-ceiling-bounded operator), not defects.

---

## Synthesis — the oracle-integration seam, named

1. **On a fork, hunt the delta — and only the delta.** Spark made this explicit: the SparkLend core is verbatim
   Aave-v3 (Aave's audits cover it), so the productive surface is the *net-new* code — the rate sources, the ALM
   controller, the D3M USDS pool. Aerodrome is the mirror case: a Velodrome/Solidly fork where the delta from *original
   Solidly* is the set of remediations (the post-fee k-check), and confirming those fixes are present is the hunt.
2. **The oracle-integration seam is where the residual lives — every time.** This round: Synthetix's configured node
   graph, Frax's Chainlink→TWAP fallback. Prior rounds: Kelp's missing `updatedAt`/`price>0` (the corpus's live-finding
   class, found known+de-risked), and the redacted Silo disclosure itself. The pattern is now unmistakable — the core
   math (k-invariant, debt conservation, share rounding) is *correct* in heavily-audited large-caps, and the
   exploitable-or-not question has migrated almost entirely to **whether the consuming contract trusts its price source
   correctly**. "Half of an oracle's safety is the integrating contract's staleness check" is the corpus's single
   most-reused law, and this round restates it three more times.
3. **The residual's severity is a function of the surrounding architecture.** Frax's TWAP fallback and Synthetix's node
   graph are *accepted design* because the rest of the system bounds their blast radius (per-pair governance, deviation
   gates); Kelp's missing-staleness was *de-risked* by the stored-rate-limited oracle. The same line of code is a
   finding, a residual, or a non-issue depending on what surrounds it — which is exactly why severity must be computed
   from the whole lifecycle, not pattern-matched.
4. **Conservation is solved; integration is the frontier.** Across 16 deep large/mid-cap reads now (4 rounds), not one
   had a core-conservation defect. The round-against-the-actor + conservation-backstop architecture is universal and
   correct. The live risk is the seam: the oracle read, the cross-protocol route, the fork-delta, the governance
   parameter — the places where one contract trusts another.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. The oracle
residuals (Synthetix node-graph, Frax TWAP-fallback) are by-design/accepted; any live exploitable instance would be
private-first + redacted. No new finding here.*
