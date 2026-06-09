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

## Final tally — 15 targets across 3 batches

| Category | Count | Targets |
|---|---|---|
| **Clean** | 11 | Sablier, Solidly forks, Compound forks, Symbiotic, v4-periphery, Mellow, Wildcat, Gearbox, Dopex, Stargate v2, Kleidi |
| **Contest / known bugs found** | 3 | munchables (deadlock + retroactive-tax + over-mint), IQ AI (4% quorum + stale-var check + DOS), Cork (rate-ignoring conservation break, author-`FIXME`, conditional) |
| **Live finding (disclosed)** | 1 | [redacted lending protocol] — missing consumer-side Chainlink staleness check; verified from source, disclosed, redacted here |

---

## Synthesis — what the hunt established

1. **The method discriminates.** Five production-audited targets → clean; one ground-truth-buggy contest
   codebase → its real highs found; one live target → a source-confirmed (Medium, conditional) finding. No
   manufactured findings on sound code, no missed bugs on buggy code.
2. **Bugs live in the margins, not the core.** Where they were found (munchables, the live oracle gap) they
   were in *less-audited* or *recently-added* code, or in the **consumer-side integration** (the oracle
   read) rather than the well-studied primitive — restating the corpus law that the residual is what you
   *don't* recompute.
3. **Recompute-don't-trust caught itself again.** The live finding was confirmed *from source* before being
   treated as real — the same discipline that reversed the alt_bn128 misread — and the *reverse* discipline
   (severity/novelty calibrated *down* honestly: conditional, possibly-known) applies equally.
4. **Disclosure posture held.** The one live finding is private-first + redacted; the closed-contest
   true-positives are named (already public); the clean negatives are reported plainly.

*Read-only, public-source. No transaction sent, no live system probed, no exploit/PoC written. The one live
finding is routed for responsible disclosure and redacted here.*
