# Thales / Overtime — AMM-priced markets + the completed prediction-market taxonomy

**Scope.** Thales/Overtime on-chain core (`thales-markets/contracts`): `PositionalMarket`
(binary options, mint-pair conservation, Chainlink resolution) and `ThalesAMM` +
`ThalesAMMLiquidityPool` (single-sided AMM pricing against a round-based LP). Read as the
**fourth pole** completing the prediction-market study with
`AUDIT-POLYMARKET-PREDICTION-MARKET.md`, `AUDIT-AUGUR-V2-VS-POLYMARKET-ORACLE-SEAM.md`, and
`AUDIT-AZURO-V2-POOL-COUNTERPARTY-AND-3POLE-SYNTHESIS.md`. Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found.**

**Sources read (verbatim):** `Positions/PositionalMarket.sol` (`mint`, `exerciseOptions`,
`resolve`, `_oraclePrice` → `priceFeed.rateForCurrency`), `AMM/ThalesAMM.sol`
(`buyFromAMM`/`availableToBuyFromAMM`/`price`/`spentOnMarket`/`capPerMarket`/`max_spread`,
`liquidityPool.commitTrade`).

---

## 0. What this pole adds

The first three poles populated the map but left two cells empty: a **deterministic
data-feed oracle** (no game, no vote, no human discretion over the outcome) and an
**AMM/scoring-rule floor** (a market maker that prices *single* outcomes and stays solvent by
*explicit caps* rather than by full collateral or pre-locked liability). Thales/Overtime fills
both — and, usefully, it does so while resting its conservation on the **same mint-pair floor**
as Polymarket and Augur, so it isolates the two new variables cleanly.

---

## 1. The floor — two layers. Conservation underneath, bounded-loss-by-caps on top. **Sound.**

**Layer A — `PositionalMarket`: the same conservation floor, a third time.**
- `mint(value)` mints `value` **UP** *and* `value` **DOWN** and pulls exactly `value` sUSD
  (`_incrementDeposited(value)` + `transferSusdTo`). One collateral unit ⇔ one full UP+DOWN
  pair. Identical in shape to CTF `splitPosition` and Augur `buyCompleteSets`.
- `exerciseOptions` pays the **winning** side `1` each from `deposited`
  (`_decrementDeposited(payout)`; the losing side is worthless). Because every mint deposited
  exactly `value` and only one side of `value` is ever paid, `deposited` always covers all
  winning exercises. **Conserve-by-construction. Zero house risk at this layer.**

**Layer B — `ThalesAMM`: a market maker that prices single sides, solvent by caps.**
Unlike a peer-to-peer book, the AMM sells you a *single* UP (or DOWN) below its full `1`
collateral value, taking the other side via the LP. Its solvency is **not** a conservation
identity and **not** Azuro-style pre-locked max liability — it is **explicit bounded loss**:
- `price(market, position)` derives the option price from a model (`ThalesAMMUtils`, a
  Black-Scholes-style implied-vol/skew computation), then applies `max_spread`-bounded price
  impact (`_buyPriceImpact`/`midImpact`). The AMM never quotes outside `[0,1]`-anchored bounds.
- **Per-market spend cap.** `spentOnMarket[market]` accumulates the AMM's net exposure;
  `availableToBuyFromAMM`/`_availableToBuyFromAMMWithBasePrice` refuse any buy that would push
  `spentOnMarket[market] + willPay` past `_capOnMarket(market)` (= `capPerMarket` or a per-asset
  override). **The AMM's maximum loss on any single market is bounded by that cap**, regardless
  of how the event resolves.
- The AMM mints full pairs from the `PositionalMarket` (so it can always deliver the side it
  sold and bank the complement), and routes capital through `ThalesAMMLiquidityPool`
  (`commitTrade`, round-based). **LPs earn the AMM's edge and bear its bounded losses.**

**Verdict:** the floor is sound but is a **fourth mechanism** — *bounded-loss-by-caps* layered
on a conservation base. Reading it as "conserves" (true only of Layer A) or as Azuro-style
"reserve-locking" (it does *not* pre-lock per-bet max liability; it caps cumulative exposure
instead) would both be category errors. The auditor's job here is the **caps + the pricing
model**: if `capPerMarket`/`spentOnMarket` accounting under-counts exposure, or the price model
quotes a mispriced option, the LP — not the bettor — is the one at risk. That read as
consistent (exposure is accumulated and checked on every buy; pairs are minted to back sales).

---

## 2. The oracle — a deterministic decentralized data feed. **A disclosed trust, lowest discretion.**

`PositionalMarket.resolve()` is `onlyOwner` but the owner has **no discretion over the
outcome**: it reads `_oraclePriceAndTimestamp()` → `priceFeed.rateForCurrency(key)` (Chainlink
DON aggregated feed) and sets `_result()` = `Up` iff `finalPrice ≥ strike`. The owner can only
*trigger* resolution after maturity; the *answer* is whatever the feed says. This is a **fourth
oracle type**: a decentralized data feed — no proposer/disputer game, no token vote, no human
adjudication of the result.

- **Strength:** for objective, feed-expressible questions ("was BTC ≥ \$X at time T"),
  resolution is deterministic, fast, and discretion-free — the least *governance* trust of the
  four.
- **The residual it carries instead:** trust shifts to the **feed itself** — Chainlink DON
  honesty/liveness, the correctness of the configured `key`/`strike`/`maturity`, and feed-
  manipulation resistance at the resolution timestamp. This oracle works *only* for questions a
  price feed can answer; it cannot express the subjective/real-world questions that *require*
  UMA's or REP's human/economic games. So it is not "better" — it occupies a different point:
  **maximum determinism, minimum expressiveness.**

---

## 3. The completed taxonomy — two axes, four poles

| Protocol | **Floor mechanism** | Floor risk | **Oracle type** | Discretion | House/LP risk |
|---|---|---|---|---|---|
| **Polymarket** | Conservation — CTF complete sets (peer-to-peer) | none (identity) | Optimistic attestation + UMA **DVM** (external-token vote) + bounded admin | medium | none |
| **Augur v2** | Conservation — ShareToken complete sets | none (identity) | Staked reporting + **own-token fork**, no admin | low (trustless) | none |
| **Azuro v2** | **Reserve-locking solvency** — pool is counterparty, lock max liability or revert | live invariant | Trusted per-condition **data provider** + DAO-adjudicated dispute | high | LP P&L + pricing |
| **Thales/Overtime** | Conservation base + **bounded-loss-by-caps** AMM on top | live invariant (caps + model) | **Chainlink DON** price feed, deterministic | minimal (no outcome discretion) | LP bounded P&L + model |

**The law, in its final form (four samples, both axes spanned):**

1. **Oracle is always the dominant residual — universal.** Every pole collapses all economic
   trust onto the actor/mechanism that sets the outcome. The four oracle types span a clean
   **expressiveness ↔ determinism** trade-off:
   *Augur fork* (most trustless, can answer anything, nuclear backstop) →
   *Polymarket UMA* (external-token vote + bounded admin, subjective questions) →
   *Azuro provider+DAO* (trusted, fast, subjective) →
   *Thales Chainlink* (zero outcome-discretion, but **only** feed-expressible questions).
   You cannot maximize trustlessness, expressiveness, and speed at once; each design picks a
   corner.

2. **The floor is NOT one law — it is one *goal* met by four mechanisms.** The goal is always
   *the market maker can honor every resolved position*. The mechanisms:
   - **Conservation** (peer-to-peer mint-pair / complete sets): locked = max payout by
     identity. Zero house risk. CTF, Augur, Thales `PositionalMarket`.
   - **Reserve-locking solvency** (house): lock worst-case liability before accepting the bet,
     ring-fence it from LP withdrawal, or revert. Azuro. LP bears P&L.
   - **Bounded-loss-by-caps** (AMM/scoring-rule): price single outcomes by a model, bound the
     maker's cumulative exposure with explicit per-market caps + spread, backed by a
     conservation base. Thales `ThalesAMM`. LP bears *bounded* P&L.
   - *(Parimutuel — the degenerate conservation case where odds form only at resolution and the
     pool splits pro-rata — is the same goal via a fourth route; not separately audited here.)*

3. **Identifying the floor mechanism is the load-bearing audit judgment.** In the conservation
   family, a share-accounting "finding" is almost always a read error and there is **no LP-risk
   bucket**. In the solvency/caps families the floor is a **live, breakable invariant** (under-
   locked liability, withdrawable reserves, under-counted AMM exposure, mispriced model) and a
   **distinct LP-capital risk** exists that the conservation family does not have at all. An
   auditor who carries the wrong family's instinct will either hunt a phantom conservation leak
   or bless a solvency invariant as "conserving" without recomputing the lock/cap math.

---

## 4. Posture & conclusion

- **No exploitable contract defect found** in the Thales/Overtime core read. The conservation
  base is sound; the AMM bounds cumulative exposure per market and mints pairs to back single-
  sided sales; resolution is a discretion-free feed read.
- Not a disclosure. The value is the **completed two-axis taxonomy** in §3: four oracle types on
  an expressiveness↔determinism trade-off, and four floor mechanisms all serving the single goal
  *winners can always be paid* — with LP capital as a risk bucket present in exactly the
  non-conservation floors. The prediction-market vertical is now mapped, not just sampled.
- Method note: the temptation at pole four was to call it "Azuro again" (both have an LP). It is
  not — Azuro pre-locks *per-bet worst-case liability*; Thales caps *cumulative per-market
  exposure* on a model-priced book. Same goal, different mechanism, different failure mode
  (Azuro fails by mis-locking; Thales fails by mis-capping/mis-pricing). Naming that distinction
  precisely — rather than collapsing both into "pool-backed" — is the audit.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
