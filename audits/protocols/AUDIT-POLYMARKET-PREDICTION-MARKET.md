# Polymarket — prediction-market stack audit (CTF · CLOB · UMA resolution · neg-risk)

**Scope.** The on-chain contract stack behind Polymarket: Gnosis Conditional Tokens
Framework (CTF), the Polymarket CTF-Exchange (non-custodial CLOB), the UMA-CTF
optimistic-oracle resolution adapter, and the neg-risk (mutually-exclusive multi-outcome)
adapter. Public source, read-only, recompute-don't-trust. Posture: **defensive,
characterize-don't-exploit.** No transaction sent; no live target probed. **No exploitable
contract defect was found** — this is a trust-cartography characterization, not a disclosure.

**Sources read (verbatim):**
- `gnosis/conditional-tokens-contracts` → `ConditionalTokens.sol` (`splitPosition`,
  `mergePositions`, `reportPayouts`, `redeemPositions`).
- `Polymarket/ctf-exchange` → `CTFExchange.sol`, `mixins/Trading.sol`, `mixins/Fees.sol`,
  `mixins/Auth.sol`, `libraries/CalculatorHelper.sol`.
- `Polymarket/uma-ctf-adapter` → `UmaCtfAdapter.sol` (full).
- `Polymarket/neg-risk-ctf-adapter` → `NegRiskAdapter.sol` (`reportOutcome`, convert path).

---

## 0. The one-paragraph result

Polymarket is, structurally, **three conservation-preserving layers stacked on one
irreducible truth-oracle seam.** The CTF floor conserves collateral by construction
(redeem pays `Σ stake·numerator / denominator`, `denominator = Σ numerators`). The CLOB
settles **non-custodially** off maker-signed EIP-712 orders — the operator is a
liveness/ordering trust, never a custody trust, and cannot move funds except along a
maker's own signed order at the maker's own price, fee bounded at 10%. The neg-risk adapter
preserves the same invariant for mutually-exclusive multi-outcome markets. **Every layer
above the floor ultimately collapses onto one question — *who calls `reportPayouts`, and
with what numbers* — and that is the UMA optimistic oracle plus a time-delayed admin
override.** The contracts conserve value perfectly; they cannot, and do not pretend to,
adjudicate whether "YES" actually happened in the real world. That adjudication — the
optimistic-oracle game, its UMA-DVM dispute backstop, and the admin emergency powers — **is
the whole-protocol trust residual.** It is a B22-class ("name your oracle") seam, and for a
real-world-events prediction market it is irreducible by design, not a bug.

---

## 1. Layer 1 — the conservation floor (CTF). **Sound.**

`ConditionalTokens.sol`:

- **`splitPosition`** (collateral → full set of outcome tokens) and **`mergePositions`**
  (inverse) move 1:1 against collateral. Mint a full outcome set ⇔ lock one collateral
  unit; burn the full set ⇔ release one. Conserve by construction.
- **`reportPayouts(questionID, payouts)`** sets
  `payoutDenominator[conditionId] = Σ payoutNumerators`, and is **guarded against
  re-resolution** (`require(payoutDenominator == 0, "payout denominator already set")`).
  Resolution is write-once.
- **`redeemPositions`** pays `totalPayout = Σ_i (stake_i · payoutNumerator_i) / denominator`,
  then burns the redeemed positions and transfers collateral out. Because
  `denominator = Σ numerators`, the sum of all holders' redemptions equals exactly the
  collateral locked. **No over- or under-payment is representable.**

**The floor cannot leak.** The entire economic trust of the protocol therefore telescopes
into a single input: the `payouts` array handed to `reportPayouts`. Whoever controls that
input controls who gets paid. The rest of this audit is about *who that is*.

---

## 2. Layer 2 — the CLOB (CTF-Exchange). **Non-custodial. Sound; operator is liveness-trust only.**

Entry points (`CTFExchange.sol`) — `fillOrder`, `fillOrders`, `matchOrders` — are all
`onlyOperator nonReentrant notPaused`. The operator is a **permissioned matcher**, but the
matcher's *power is bounded by maker signatures*, not by trust:

- **Orders are maker-signed EIP-712** (`_validateOrder` → `validateOrderSignature`). Funds
  are only ever pulled **from the maker who signed**, and only along that order's terms.
- **Price is the maker's**, not the operator's. `calculateTakingAmount = making·takerAmount /
  makerAmount` is fixed by the signed order. `_validateTakerAndMaker` requires
  `isCrossing(...)` — the operator can only cross orders whose signed limit prices actually
  overlap (`priceA + priceB ≥ ONE` for two bids, `≤ ONE` for two asks, etc.). The operator
  **cannot invent a worse-than-signed price.**
- **Fee is bounded.** `_validateOrder` rejects `order.feeRateBps > getMaxFeeRate()` =
  `MAX_FEE_RATE_BIPS = 1000` (10%). The operator collects fee implicitly (deducted from
  proceeds), but only up to the maker's *own signed* `feeRateBps`, itself ≤ 10%.
- **Match settlement conserves.** `_matchOrders` pulls the taker's making amount into the
  Exchange, fills makers (`MINT` calls CTF `splitPosition`, `MERGE` calls `mergePositions`,
  `COMPLEMENTARY` is a direct swap), then `_updateTakingWithSurplus` requires the realized
  balance ≥ the minimum owed (`TooLittleTokensReceived` otherwise), pays the taker
  `taking − fee`, charges fee, and **refunds any leftover** maker-asset balance back to the
  taker. The Exchange holds no residual; tokens in = tokens out.
- **Replay/over-fill guarded.** `_updateOrderStatus` tracks `remaining`, reverts
  `MakingGtRemaining`, flips `isFilledOrCancelled` at full fill; nonces via `NonceManager`;
  expirations honored; orders cancelable only by maker.

**Residual at this layer:** the operator is a **censorship / ordering / liveness** trust
(it chooses which crossing orders to match and the fill amounts, and can decline service or
front its own fee within the signed cap) — and admin can `pause` and can `registerToken`
(binding `tokenId ↔ complement ↔ conditionId`; a mis-registration is an admin-integrity
concern, not a theft primitive against existing balances). **It is not a custody trust.**
This is the same shape as the intent/solver settlement model (B17): the privileged actor
sequences, it does not own.

---

## 3. Layer 3 — neg-risk (mutually-exclusive multi-outcome). **Conserves; same floor.**

`NegRiskAdapter.sol` wraps CTF for markets where exactly one of N questions resolves YES
("who wins the election"). `reportOutcome(questionId, outcome)` calls
`ctf.reportPayouts(questionId, Helpers.payouts(outcome))` — i.e. it feeds the **same
write-once, conserve-by-construction** CTF resolution. The convert/wrapped-collateral path
(`_splitPosition` over `Helpers.partition()`, `WrappedCollateral`) lets a holder of the full
NO-across-all-questions set reclaim collateral + the complementary YES exposure; this is the
documented neg-risk mechanism and it nets to the same 1:1 collateral conservation. **No new
leak introduced; the residual is again "who reports the outcome."**

---

## 4. The dominant residual — UMA optimistic-oracle resolution (`UmaCtfAdapter`). **The seam.**

This adapter is the thing that calls `reportPayouts`. Everything above converges here.

**The honest-path flow (well-formed, conserving):**
- `initialize` saves the question + sends a price request to the UMA Optimistic Oracle
  (`_requestPrice`: event-based, dispute callback on, custom bond/liveness).
- `resolve` is **permissionless** but gated: requires initialized, not paused, not resolved,
  and `_hasPrice` (the OO has a settled price). It calls `optimisticOracle.settleAndGetPrice`
  and feeds `_constructPayouts(price)` to CTF.
- **`_constructPayouts` is tightly constrained**: it reverts `InvalidOOPrice` unless price ∈
  `{0, 0.5e18, 1e18}`, mapping to `[YES,NO] = [0,1]`, `[1,1]` (50/50 tie), or `[1,0]`. **The
  OO path cannot emit an arbitrary skewed payout split** — only the three legal resolutions.
- **Disputes self-heal**: `priceDisputed` (only callable by the OO) resets the question and
  re-requests (at most 2 OO requests outstanding), refunding the creator's reward; an already
  -resolved question is left untouched and the reward refunded.
- The ignore-price (`type(int256).min`) triggers a reset rather than a bad resolution.

**Why this is the residual, not a defect:** the *correctness of the price itself* is not an
on-chain property. It rests on, in order: (a) the **optimistic proposer/disputer game** (a
proposer posts the outcome + bond; if undisputed through liveness it stands); (b) on dispute,
the **UMA DVM** — a token-holder vote — adjudicates. A prediction market about real-world
events **must** import off-chain truth, so this seam is structural. The classic Polymarket
resolution controversies (subjective or ambiguously-worded markets where the *social
consensus of UMA voters* diverges from a participant's reading of ground truth, and the
theoretical concern of a vote-weight whale swinging a disputed resolution) live **exactly
here** — they are governance/oracle-economics risks of the truth layer, not bugs in any
contract audited above. The contracts will conserve and pay out *whatever the oracle says*;
they cannot check whether the oracle is right.

---

## 5. The governance ceiling — admin emergency powers (`onlyAdmin`)

`UmaCtfAdapter` admin can, in order of severity:

- **`pause` / `unpause`** a question (blocks `resolve`).
- **`flag`** → sets `manualResolutionTimestamp = block.timestamp + SAFETY_PERIOD` and pauses;
  **`unflag`** reverses it, but only *before* the safety period passes.
- **`reset`** → re-request from the OO (failsafe if the dispute callback reverts).
- **`resolveManually(questionID, payouts)`** → calls `ctf.reportPayouts` **directly, bypassing
  UMA**, with an **admin-chosen payout array**. This is the maximal-trust primitive: it can
  set *any* `_isValidPayoutArray`-valid split, not just the OO's three legal outcomes.

**Calibration (why this is a disclosed-by-design ceiling, not a finding):**
- `resolveManually` is **not** instantaneous or silent. It requires the question to be
  **flagged first** (`_isFlagged`), and `block.timestamp ≥ manualResolutionTimestamp` — i.e.
  the full `SAFETY_PERIOD` must elapse after an **on-chain, observable** `QuestionFlagged`
  event. There is a public, time-bounded window in which the community sees a manual
  resolution coming and can react.
- It is gated by `onlyAdmin`, and the Auth model (`addAdmin`/`removeAdmin`, typically a
  multisig/governance) is the named authorizer. This is the protocol's deliberate
  escape hatch for OO failure / mis-resolution / ambiguous markets.
- It still flows through the **conserving** `reportPayouts`, so it cannot *create* value — it
  can only **redistribute** a market's locked collateral among that market's holders.

This is the "name-the-authorizer" seam in its most honest form: a powerful, **time-delayed,
on-chain-announced, conservation-bounded** admin override. The trust is real and should be
stated plainly to users — *the admin can, after a public delay, override the oracle and set
a market's payouts* — but it is a known, bounded power, not a latent exploit.

---

## 6. Trust-cartography summary (six buckets / three coordinates)

| Coordinate | Where it lives in Polymarket | Verdict |
|---|---|---|
| **Conservation floor** | CTF `redeemPositions = Σ stake·numerator/den`, `den = Σ numerators`; write-once `reportPayouts`; CLOB settlement nets to zero residual; neg-risk same floor | **Sound — cannot leak** |
| **Equivalence / 6-bucket** | outcome tokens ≡ collateral claims; CLOB MINT/MERGE ≡ CTF split/merge; no double-mint (order `remaining`, nonces, fill caps) | **Holds** |
| **Governance ceiling** | `UmaCtfAdapter` admin: pause, flag→`resolveManually` (time-delayed, conservation-bounded), reset; Exchange admin: pause, `registerToken`, operator set | **Bounded; time-delayed & observable; disclose to users** |

**Six-bucket residual placement.** Custody: none (non-custodial CLOB; CTF holds only locked
collateral 1:1). Issuance/conservation: closed (CTF). **Oracle/attestation: the dominant
residual — UMA optimistic oracle + DVM dispute layer.** Governance: the admin emergency
override (bounded). Bridge/cross-domain: n/a (single-chain, Polygon). Upgrade: per
deployment (not in scope of source read here).

---

## 7. Posture & conclusion

- **No exploitable contract defect found.** Floor conserves; CLOB is non-custodial and fee-
  bounded; OO path can only emit the three legal resolutions; admin override is time-delayed,
  on-chain-announced, and conservation-bounded. Nothing here is a stop-and-disclose finding.
- **The honest user-facing statement of risk** is therefore *not* "the code can be drained,"
  but: **"your payout is only as correct as (1) the UMA optimistic-oracle resolution of your
  specific, possibly-ambiguous market question, and (2) the admin's bounded, time-delayed
  power to override it."** That is the irreducible nature of a real-world-events prediction
  market — the truth-oracle seam, characterized, not a bug.
- Method note (recompute-don't-trust): the interesting work here was *resisting* the instinct
  to hunt for a settlement-math leak. There isn't one — the design deliberately telescopes all
  risk onto the oracle. The correct audit output is to **name that seam precisely** and bound
  the admin ceiling, rather than to manufacture a finding where the conservation floor is
  airtight.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
