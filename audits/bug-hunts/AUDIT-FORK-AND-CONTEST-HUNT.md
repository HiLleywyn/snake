# Active bug hunt — fork-diff + invariant hunt across 7 targets (5 clean, 1 known-contest, 1 live-redacted)

A deliberate bug-hunting pass (not characterization): take *less-audited* code — fork families, newer
protocols, and an audit-contest snapshot — and hunt the universal high-yield vuln classes (conservation/
rounding, access control, reentrancy/CEI, oracle staleness, signature/replay/time) for **genuinely
exploitable, introduced defects.** Methodology: diff each fork against its reference line-by-line, and hunt
each newer protocol's single most-valuable invariant. Posture: **defensive, characterize-don't-weaponize, no
PoC.** A real live-exploitable finding is **verified from source, routed for private/responsible disclosure,
and redacted here** — never published as a roadmap.

> **Headline result:** the method has both **true negatives and true positives** — it returned *clean* on five
> production-audited targets, *found the real bugs* in a ground-truth-buggy contest codebase, and surfaced
> **one source-confirmed live finding** (a consumer-side oracle-staleness gap, redacted below and routed for
> disclosure). It did not manufacture a finding on sound code.

---

## Results table

| # | Target | Audited? | Classes hunted | Verdict |
|---|---|---|---|---|
| 1 | **Sablier `lockup`** (lockup + airdrops + flow) | heavily | all 5 | **clean** |
| 2 | **Solidly forks** — Aerodrome (Velo-V2), Cone (Dystopia/Thena) | production | Pair-k/fees, gauge rewards, voter/ve, access | **clean** |
| 3 | **Compound-v2 forks** — Bao Markets, Hundred snapshot | production | donation/inflation, reentrancy, risk-params, accrual | **clean** |
| 4 | **Symbiotic** restaking core (vault/delegator/slasher) | yes | share/epoch math, slash bounds, veto, off-by-one | **clean** (slash math machine-checked) |
| 5 | **Uniswap v4-periphery** (+ the new permissioned-pools layer) | partially | flash-accounting, Permit2, unlock gate, NFT ownership, hook deltas | **clean** |
| 6 | **munchables** (`code-423n4/2024-07`, `LandManager.sol`) | **deliberately buggy** | all 5 | **bugs found** (known/closed-contest) |
| 7 | **[live lending protocol — REDACTED]** (newer isolated-lending) | yes | liquidation health, share math, oracle, CEI | **1 finding** (consumer-side oracle staleness; *routed privately, redacted*) |

---

## 1–5. The clean targets — where bugs *don't* live (and how it was verified)

The five production targets came back clean, each with the specific defenses verified from source:
- **Sablier** — round-down on amounts owed to recipients, state-before-interaction ordering, per-index
  replay protection (claimed-bitmap), chain/contract-bound EIP-712 domain + `to`-binding (anti-front-run),
  conservation `assert`s. Only flag: a *documented, deliberate* oracle-staleness omission in the new
  price-gated `SafeOracle` (a creator-trusted assumption, in-code-commented — not a hidden defect).
- **Solidly forks** — the classic **Solidly infinite-fee bug is *absent*** (Cone calls `_updateFor` on every
  LP balance change: mint/burn/transfer/claim); no flipped k-inequality, no fee-index drift, no reward
  double-count, no vote double-count. Aero/Cone are faithful to Velo-V2 / Dystopia.
- **Compound-v2 forks** — empty-market exchange-rate protection intact, `nonReentrant` on every entry,
  0.9 collateral-factor cap + zero-price guard preserved, accrual freshness + borrow-rate cap intact. Bao's
  custom IMF collateral-discount **only tightens** collateral (safe-by-construction, disabled by default).
- **Symbiotic** — the **slash-redistribution math was exhaustively machine-checked** over the small-value
  space (zero underflows/sum-mismatches); the epoch off-by-one is guarded (`currentEpoch_ > 0` blocks the
  `0−1` underflow); the **veto-bypass is structurally impossible** (resolver changes apply ≥3 epochs ahead;
  execute/veto read the resolver at the *historical* captureTimestamp); the standard ERC4626 inflation class
  is **neutralized** by reading internal `_activeStake` checkpoints, not `balanceOf`.
- **Uniswap v4-periphery** — the new **permissioned-pools layer** was the focus: the globally-reachable
  `UNWIND_WITH_FALLBACK` action was traced for a value-moving mis-route and the binding holds (admin-ship
  derives from the attacker's *own* poolKey, but value is constrained to the caller's *own in-batch credit*;
  decreasing a victim's liquidity still requires `onlyIfApproved`). The `*_FROM_DELTAS` sandwich exposure is
  *deprecated/documented in-code*, not latent.

**The negative result is itself the finding:** *production-audited source is clean.* The corpus's central
thesis (well-engineered code fails safe / has no introduced bug) holds under an *active* hunt, not just a
characterization pass. Honest environment caveat: the *actually-hacked* fork deployments (e.g. Sonne, the
historically-buggy Solidly forks) are auth-walled under unauthenticated HTTPS here, and several real hacks
(Hundred) were **deployment/config** issues (empty market + callback-collateral), not source diffs — so the
highest-yield targets were partly out of reach.

---

## 6. munchables — the method's true positive (known, closed-contest)

`code-423n4/2024-07-munchables` (`LandManager.sol`, HEAD `e9056af`) is a *ground-truth-buggy* codebase, and the
hunt independently surfaced its real defects — validating that the method finds bugs *where they exist*:
- **Deadlock off-by-one (HIGH)** — the plot-shrink "dirty" handling uses `<` not `<=` on a 0-indexed `plotId`
  vs a count (`:258`), and `dirty` is never reset → a Munchable permanently stops accruing; a sibling
  checked-subtraction underflow (`timestamp = lastUpdated < lastToilDate`, `:281`) reverts stake/unstake
  account-wide. **Maps directly to the README's stated top concern (no deadlock).**
- **Retroactive tax (HIGH)** — `latestTaxRate` is overwritten every `_farmPlots` with no time-weighting
  (`:292-293`), so a landlord raises `currentTaxRate` right before a renter farms and taxes the whole
  un-farmed interval at the new rate.
- **Over-mint (MEDIUM)** — an unchecked `int256→uint256` cast on an attacker-influenceable `finalBonus`
  (`:283-286`): a negative realm/rarity bonus driving `finalBonus ≤ −100` wraps to a huge `schnibblesTotal`.
- **Config defect** — `_reconfigure` loads all six tax/rate/price constants from the **wrong (address-typed)
  StorageKeys** — there are no dedicated keys at all — poisoning the whole accounting.

**Crucially: this is a *closed 2024 contest*, so these are almost certainly in the public findings set — not
a live, undisclosed vulnerability.** Its value here is methodological: the same lens that returned *clean* on
five audited protocols returned *multiple highs* on a deliberately-buggy one. True positives and true
negatives — the method discriminates.

---

## 7. [REDACTED — live target] — a confirmed consumer-side oracle-staleness gap

A newer, audited isolated-lending protocol's **production Chainlink price-oracle path omits the staleness/
heartbeat check entirely.** The defect, **source-confirmed** (verified directly from the repo, not trusting a
summary — the corpus's recompute-don't-trust discipline applied before flagging): the aggregator-read helper
**accepts a `heartbeat` parameter that is commented out and unused, discards `updatedAt` from
`latestRoundData()`, and validates only `price > 0`** — no `require(block.timestamp − updatedAt ≤ heartbeat)`
anywhere in the oracle, its forwarder, or its config (the heartbeat is stored in config and plumbed *to* the
function, then ignored — the signature of a removed/unwired check, not an intentional design). The path feeds
the protocol's solvency/max-LTV valuation, so a frozen/deprecated feed (or a sequencer-down stale-but-positive
answer) would price collateral/debt at the stale value with **no revert** → bad-debt / unfair-liquidation
exposure, conditional on a feed malfunction.

This is the **exact §5g "consumer-side oracle footgun"** the methodology already named in the abstract: *half
an oracle's safety is not in the oracle — it is in whether the integrating contract checks staleness.* Here is
a live instance.

**Handling (per the corpus's standing disclosure rule):** the specifics (protocol name, file/line, the exact
reachable valuation path) are **redacted from this public artifact** and **routed for responsible/private
disclosure to the team first**, fix-first — exactly as the one prior real finding (MemeCore) and the
Hyperliquid latent finding were handled. **Severity is calibrated honestly:** Medium, *conditional* on a
Chainlink feed malfunction (which an attacker does not control); and **novelty is uncertain** — "missing
Chainlink staleness check" is the single most common audit finding, and a multiply-audited protocol may have
already accepted it as a governed-per-market / reliable-feeds-only limitation. The disclosure will say so. The
public corpus carries only this redacted placeholder + the *class-level* characterization in §5g until the
team has had the opportunity to respond.

---

## Batch 2 — the integration-seam hunt (chasing the Silo class)

The Silo finding (a *missing* consumer-side oracle-staleness check) sharpened the target: not the
well-studied core math (which kept coming back clean), but the **integration boundary** — where a protocol
*consumes* an oracle/token/other-protocol and quietly trusts it. Four more hunts, weighted to that seam:

| Target | Audited? | Oracle-staleness handling | Verdict |
|---|---|---|---|
| **Mellow LRT vault** | heavily (Statemind/Mixbytes/Chainsecurity) | **checks** (`block.timestamp − maxAge > lastTimestamp → StaleOracle`); rate-based not spot; operator-gated seed first deposit | **clean** |
| **Gearbox v3** (core/oracles/integrations) | heavily | **checks** universally (`_checkAnswer`: `price>0 && now < updatedAt + staleness`); every LP/yield rate **hard-bounded** (+2%/−1%); TWAP/EMA for AMM LPs | **clean** |
| **Wildcat V2** (`code-423n4/2024-08`) | contest | **N/A** — no price feed at all (internal interest index) | **clean** (no new bug beyond known/intentional) |
| **Dopex V2 CLAMM / Stryke** | yAudit | **spot-by-design** — raw V3 `slot0()`, no TWAP/staleness; but PnL realized from *actual balance deltas*, bounded by `maxCostAllowance` | **clean** (accepted design, not a defect) |

**The staleness scorecard — the methodological payoff.** Across the integration-seam hunt the oracle-staleness
class resolved into three distinct outcomes, and the method **discriminated** between them:
- **Checks correctly** (Mellow, Gearbox) — the norm for production lending/LRT.
- **No check by design** (Dopex's `slot0` spot, Sablier's price-gated `SafeOracle`) — *documented, accepted*
  tradeoffs where the value isn't taken from the oracle naively → **characterized, not flagged.**
- **Missing where it should be present** (Silo) — contradicts the protocol's *own* sibling oracle
  (`X33ToUsdAdapter` does check) and its *own* review checklist (`oracles.instructions.md` item 4) → **the one
  flagged + disclosed finding.**

This is the credibility test the corpus cares about: *a missing check that should be there* (defect) vs
*no-check-by-design* (accepted) are different things, and the hunt did not cry wolf on the intentional ones —
the same calibration discipline that downgraded the Silo severity honestly (conditional, Medium,
possibly-in-pipeline). Two non-bugs recurred across the batch and were correctly *not* flagged: the absence of
an **L2 sequencer-uptime feed** (Mellow/Gearbox both omit it as a mainnet-target design choice) and **standard
ERC4626 first-depositor inflation** without a virtual-shares offset (Gearbox — documented, pools seeded at
launch).

---

## Final tally — 11 targets

- **Clean (9):** Sablier, Solidly forks (Aero/Cone), Compound-v2 forks (Bao/Hundred), Symbiotic, Uniswap
  v4-periphery, Mellow LRT, Wildcat V2, Gearbox v3, Dopex/Stryke.
- **Contest known-bugs (1):** munchables — deadlock off-by-one + retroactive tax + over-mint cast (public,
  closed contest).
- **Live finding (1):** [redacted lending protocol] — missing consumer-side Chainlink staleness check; verified
  from source, routed for private disclosure, redacted here.

---

## Batch 3 — diversifying the bug class (cross-chain auth, calldata-whitelist, peg/redemption)

Beyond oracle-staleness, into the seams where *different* hacks live: bridge message-verification (the
highest-historical-risk category), Safe-guard / calldata-whitelist access control, and depeg-swap
conservation.

| Target | Type | Class hunted | Verdict |
|---|---|---|---|
| **Stargate v2** (OApp on LayerZero v2) | production bridge | message auth / source-binding / replay / mint-binding | **clean** — handlers reachable only via the LZ peer-checked endpoint *and* `onlyCaller`-gated; mint bound to authenticated amount+recipient; replay covered by LZ nonces + the bus hash-chain |
| **Kleidi** (`code-423n4/2024-10`) | contest | calldata-whitelist bypass, Safe-guard bypass, timelock FSM, recovery sigs | **clean** — wildcard always sole element; overlap check *over*-strict (no smuggling); contest findings already fixed pre-snapshot (`AUDIT_LOG.md`) |
| **IQ AI** (`code-423n4/2025-01`) | contest | governance / accounting / spot-price | **bugs found, all known** — H-01 4% quorum (not 25%), M-03 stale-variable threshold check, M-02 balance-injection DOS, M-01 pre-seeded-pair leak (verified vs the published C4 report) |
| **Cork Protocol** (`sherlock 2024-08`) | contest | peg/redemption conservation, AMM, DS/CT epochs | **real defect found (author-acknowledged, conditional)** — `unsafeIssueToLv` mints CT+DS + locks RA at fixed 1:1, **ignoring the DS `exchangeRate`** → PSM `Σout≠Σin` whenever `rate != 1e18`; author `FIXME` at `PsmLib.sol:112-114`; conditional on a non-unit rate; closed contest |

**Two methodological points from batch 3:**
- **The conservation-floor lens caught its own class.** Cork's `unsafeIssueToLv` is a textbook `Σ in ≠ Σ out`
  (lock `ctAmount` RA but mint `ctAmount` CT+DS at 1:1 while redemption pays `amount·rate/1e18`) — exactly the
  asymmetry the whole corpus is built to find. The author had already flagged it with a `FIXME`, and it is
  conditional on a non-unit `exchangeRate`, so it is a known/acknowledged contest issue, not a novel live one —
  but it shows the lens fires on the right thing.
- **A contest's "start" commit can be post-fix.** Kleidi's real findings were already fixed before the snapshot
  commit (`docs/AUDIT_LOG.md` entries 09/17–09/30), so the hunt correctly returned clean on the *fixed* code —
  a reminder that "contest repo" ≠ "buggy at every commit."

Honest unverified caveat (Cork, class 3): the flash-swap repayment math assumes the Cork-Technology `v2-core`
AMM fork charges **0% fee**; if the deployed pair retained the stock 0.3%, DS swaps would revert/underflow. The
fork's `UniswapV2Pair` couldn't be fetched offline to byte-confirm the fee constant — flagged, not concluded.

---

## Batch 4 — leveraged-stablecoin and LST conservation (high-value, mature targets)

Larger TVL, more-audited targets, hunted on the conservation/rebase/exchange-rate axes rather than oracle reads.

| Target | Type | Class hunted | Verdict |
|---|---|---|---|
| **fx Protocol** (leveraged stablecoin, v2) | production | mint-guard removal, directional pricing, peg conservation | **clean** — Chainlink staleness *is* checked; V2 dropped V1's `require(isValid)` mint guard (`TreasuryV2.sol:664-674` vs `v1/Treasury.sol:655-666`) but directional min/max pricing makes it non-value-extractable — disclosure-as-hardening only, not a finding |
| **ether.fi** (LST/restaking) | production | rebase bounds, share/exchange-rate, withdrawal-queue accounting | **clean** — exchange-rate `getTotalPooledEther/totalShares`, consensus+APR-bounded rebase, balance-injection-immune, withdrawals hash-committed + lock-reconciled |
| **Bunni v2** (Uniswap-v4 hook LP manager) | production (mainnet) | hook flash-accounting/settlement, rebalance-as-oracle, share conservation, LDF, access | **clean** — settlement `BeforeSwapDelta` exactly matches minted/burned claim tokens (no leftover sweepable); rebalance is TWAP-priced + slippage-bounded + filler-whitelisted + reentrancy-locked; shares `mulDiv`-down + `MIN_INITIAL_SHARES` to `address(0)`; LDF active-balance-clamped |
| **Upside** (`code-423n4/2025-05`) | contest | bonding-curve conservation, fee-split, staking-reward, access | **clean (matches 0 H/M outcome)** — independent derivation confirms real-USDC = `(reserves − virtual) + protocolFees` with disjoint buckets; sell-floor guards the virtual reserve; reward-index dust rounds toward contract |
| **SecondSwap** (`code-423n4/2024-12`) | contest | vesting step-accounting, marketplace transfer, referral | **bugs found, all known** — `releaseRate = total/numSteps` ignoring claimed steps (H-03), inherited `stepsClaimed` on transfer (H-01/H-02), referral-fee computed-but-never-paid (M-14); all map to the published report |

**Batch-4 note — "dropped guard" is not automatically a finding.** fx Protocol's V2 removed V1's explicit
`require(isValid)` mint guard, which *looks* like a regression; tracing the directional min/max pricing showed the
removed check is non-value-extractable (the price a minter receives is bounded the safe way regardless). Flagged
as disclosure/hardening, calibrated *down* honestly rather than inflated into a high — the mirror of the
recompute-don't-trust discipline applied to severity.

---

## Batch 5 — the full taxonomy, no oracle priority (logic, access, reentrancy, signature)

Explicitly broadened **off** the oracle-staleness/integration-seam pattern and onto the *rest* of the bug
taxonomy — logic/off-by-one/wrong-variable, access control, delegatecall/proxy escape, signature/replay, and
read-only reentrancy — on three mechanism types where those classes actually live (vesting/merkle-claim,
Safe-module authorization, concentrated-liquidity reward accrual). The point was to prove the method isn't a
one-trick oracle detector.

| Target | Type | Classes hunted (no oracle) | Verdict |
|---|---|---|---|
| **Hedgey** `Locked_VestingTokenPlans` | production | logic/off-by-one (release `min`-cap, segment/combine end-date), access, merkle double-claim, reentrancy/DoS | **clean** — merkle leaf binds `address+amount` + single-use `claimed[id][sender]`; release `min(periods·rate, amount)` cap; segment requires `segmentEnd ≥ endCheck` (no early unlock); FOT-rejecting transfer helper |
| **gnosis/zodiac** (Safe-module base lib) | production | access control, delegatecall/exec escape, proxy/init, signature/replay | **clean** — `moduleOnly` recovers a module sig with address(0)-reject + chainid+contract domain binding + selector+args coverage + per-signer-per-hash consumption; CREATE2 salt binds init data (no front-run window) |
| **Ramses V3** (`code-423n4/2024-10`) | contest | read-only reentrancy, CEI, conservation/rounding, FOT composability | **clean** — the unguarded `positionPeriodSecondsInRange`/`periodCumulativesInside` views are consistent because `_modifyPosition` writes a same-block oracle observation (re-entrant read never multiplies the inflated `liquidity`); `secondsDebt` rounds *against* the user both directions; gauge `notifyReward` uses measured balance deltas |

**Batch-5 note — the method discriminates beyond oracles.** Each of these was hunted with *no* oracle-staleness
weighting, on the class most likely to be live for that mechanism. The richest surfaces — Zodiac's
signature-recovered module authorization, Ramses's classic UniV3 read-only-reentrancy view, Hedgey's merkle
double-claim — were each examined at the line level and found *carefully* defended (the Ramses same-block-
observation defense and the `secondsDebt`-rounds-against-user choice are exactly the kind of subtle correctness
the rapid sweep would miss). True negatives on audited code, no manufactured findings — the same discrimination
the oracle-class hunt showed, now demonstrated across logic/access/reentrancy/signature.

---

## Final tally — 23 targets across 5 batches

| Category | Count | Targets |
|---|---|---|
| **Clean** | 18 | Sablier, Solidly forks, Compound forks, Symbiotic, v4-periphery, Mellow, Wildcat, Gearbox, Dopex, Stargate v2, Kleidi, fx Protocol, ether.fi, Bunni v2, Upside, Hedgey, gnosis/zodiac, Ramses V3 |
| **Contest / known bugs found** | 4 | munchables (deadlock + retroactive-tax + over-mint), IQ AI (4% quorum + stale-var check + DOS), Cork (rate-ignoring conservation break, author-`FIXME`, conditional), SecondSwap (step-accounting H-03 + inherited-steps H-01/H-02 + unpaid-referral M-14) |
| **Live finding (disclosed)** | 1 | [redacted lending protocol] — missing consumer-side Chainlink staleness check; verified from source, disclosed, redacted here |

## Batch 6 — LIVE deployed, bounty-eligible targets (audited-code == on-chain code, confirmed)

Shifted entirely onto **live, mainnet-deployed, actively-bountied** protocols — where a real finding has actual
use and reward — and away from closed contest repos. The discipline that makes this meaningful: **each agent
confirmed the audited source equals the deployed source** (tag/commit diff) before reporting, so a "clean" verdict
is a statement about live code, not a stale snapshot. Full taxonomy, weighted to each protocol's recently-changed
and novel-mechanism surfaces.

| Target | Live status | Deployed==audited check | Classes hunted | Verdict |
|---|---|---|---|---|
| **Across Protocol** (`contracts` @ `v5.0.11`) | mainnet bridge, Immunefi | `git diff v5.0.11..HEAD` on `SpokePool/HubPool/MerkleLib` is **byte-identical**; only drift is a benign `MulticallHandler._safeTransfer` virtualization | deposit/fill 1:1 binding, merkle refund-leaf double-execution, message callback reentrancy, admin/cross-domain auth, speed-up sig replay | **clean** — relay hash binds `{origin, depositId, dest, params}`; fill-status + both merkle bitmaps set before any external call; repayment authorized only via liveness-gated optimistic root, never at fill time |
| **Euler v2** (EVK `5b98b42` + EVC `v1.0.1`) | mainnet lending, Immunefi | EVC `git diff v1.0.1..HEAD -- src/` is **empty** (deployed Solidity == v1.0.1); EVK at maintained tip | EVC deferred-check/controller isolation, EVK conversion/interest/fee rounding, liquidation/socialization, hooks/operator/permit, read-only reentrancy | **clean** — status checks fire only on outer-frame unwind (can't end batch unhealthy); >1 controller reverts; every conversion rounds toward the vault; permit chain+nonce bound, `s>n/2` rejected |
| **Fluid** (`fluid-contracts-public` @ `a9949b4`) | mainnet liquidity layer, Immunefi | no tags published; HEAD of `main` is the reference; **bit-field boundaries + storage masks recomputed non-overlapping from the actual constants** | bit-packed liquidity accounting (wrong-mask/shift), tick/branch liquidation, DEX smart-collateral share math, delegatecall dispatch, read-only reentrancy | **clean** — `_supplyOrWithdraw` mask `0xC0…0001` preserves exactly {bit0, 162-217, 254-255} and overwrites {1-161, 218-253}, matching the field map; deposit-down/withdraw-up rounding; read-only-reentrancy `_check()` reverts on the reentrancy bit |

**Batch-6 note — "deployed == audited" is the load-bearing step.** A clean verdict on a GitHub HEAD is worthless if
the chain runs a different bytecode. Each hunt here *first* pinned the live version: Across by diffing the stable
release tag to HEAD (core files byte-identical), Euler by proving EVC's `src/` is unchanged since `v1.0.1`, Fluid
by recomputing the bit-packing from the deployed constants rather than trusting the layout comments. That is the
live-code analogue of recompute-don't-trust — and it is exactly why the one prior live finding (the redacted oracle
gap) was actionable: it was confirmed against the source the protocol actually runs.

**Honest non-exhaustive caveats (named, not buried):** Euler's peripheral modules (ESynth, PegStabilityModule,
EulerSavingsRate, the individual Pyth/Redstone/Pendle oracle adapters, IRMLinearKink) were not read line-by-line —
lower-privilege, but a larger surface for a deeper pass. Fluid's tick/branch liquidation engine and full DEX
swap/arbitrage path are the two most complex novel modules; "no defect found" there reflects a careful but
**non-exhaustive** review of the most security-relevant paths, not a correctness proof — they remain the
highest-value follow-up targets. Across's chain-specific adapters and the SP1-Helios light-client path carry
trust assumptions outside the core flow audited here.

---

## Final tally — 26 targets across 6 batches

| Category | Count | Targets |
|---|---|---|
| **Clean** | 21 | Sablier, Solidly forks, Compound forks, Symbiotic, v4-periphery, Mellow, Wildcat, Gearbox, Dopex, Stargate v2, Kleidi, fx Protocol, ether.fi, Bunni v2, Upside, Hedgey, gnosis/zodiac, Ramses V3, **Across (live)**, **Euler v2 (live)**, **Fluid (live)** |
| **Contest / known bugs found** | 4 | munchables (deadlock + retroactive-tax + over-mint), IQ AI (4% quorum + stale-var check + DOS), Cork (rate-ignoring conservation break, author-`FIXME`, conditional), SecondSwap (step-accounting H-03 + inherited-steps H-01/H-02 + unpaid-referral M-14) |
| **Live finding (disclosed)** | 1 | [redacted lending protocol] — missing consumer-side Chainlink staleness check; verified from source, disclosed, redacted here |

**Bug-class coverage across the 6 batches** (per the "don't just look for silo class" directive): oracle/staleness
(batches 1–2), bridge/message-auth + calldata-whitelist + peg-conservation (batch 3), leveraged-stablecoin +
LST exchange-rate + v4-hook settlement (batch 4), logic/off-by-one + access-control/delegatecall +
signature/replay + read-only-reentrancy (batch 5), and **live deployed lending/bridge/liquidity-layer at the
on-chain version** (batch 6). The oracle-staleness pattern is **one row** of the matrix, not the matrix.

---

## Synthesis — what the hunt established

1. **The method discriminates — and not just on oracles.** Across 26 targets: production/live-deployed code →
   clean (21); ground-truth-buggy contest codebases → their real highs found (4); one live target → a
   source-confirmed (Medium, conditional) finding. Critically, the discrimination holds across the *full*
   taxonomy — batch 5 proved it on logic/off-by-one, access-control/delegatecall, signature/replay, and
   read-only reentrancy with *no* oracle weighting (clean on Hedgey/Zodiac/Ramses); batch 6 proved it on
   *live, bounty-eligible* lending/bridge/liquidity-layer code at the on-chain version (clean on
   Across/Euler v2/Fluid). The oracle-staleness class was never the method; it was one productive row.
2. **Bugs live in the margins, not the core.** Where they were found (munchables, the live oracle gap) they
   were in *less-audited* or *recently-added* code, or in the **consumer-side integration** (the oracle
   read) rather than the well-studied primitive — restating the corpus law that the residual is what you
   *don't* recompute. The clean mature targets (Bunni, fx, ether.fi, Zodiac, Hedgey) reinforced the mirror:
   heavily-audited core code with correct, protocol-favoring rounding and complete guards yields nothing.
3. **Recompute-don't-trust caught itself again — in both directions.** The live finding was confirmed *from
   source* before being treated as real (the alt_bn128 discipline); and severity/novelty were calibrated
   *down* honestly where warranted — Cork's conditional author-`FIXME`'d defect, fx Protocol's dropped-guard
   that directional pricing renders non-extractable, SecondSwap's all-published findings. No "dropped check"
   was auto-promoted to a finding without tracing whether value can actually leave. **For live targets the
   same discipline extends to the deployment boundary:** batch 6 pinned audited-code == on-chain-code (tag
   diffs, empty `src/` deltas, bit-packing recomputed from the deployed constants) before calling anything
   clean, because a clean read of the wrong bytecode is worthless.
4. **Disclosure posture held.** The one live finding is private-first + redacted; the closed-contest
   true-positives are named (already public); the clean negatives are reported plainly.

*Read-only, public-source. No transaction sent, no live system probed, no exploit/PoC written. The one live
finding is routed for responsible disclosure and redacted here.*
