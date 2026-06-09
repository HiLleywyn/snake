# Azuro v2 — pool-as-counterparty prediction market + the three-pole synthesis

**Scope.** Azuro v2 on-chain core (`Azuro-protocol/Azuro-v2-public`): the `LP` liquidity
pool, `CoreBase`/`PrematchCore` betting + resolution engine, `LiquidityTree` LP accounting,
and the `SafeOracle` dispute extension. Read as the **third pole** in the prediction-market
oracle-seam study, alongside `AUDIT-POLYMARKET-PREDICTION-MARKET.md` and
`AUDIT-AUGUR-V2-VS-POLYMARKET-ORACLE-SEAM.md`. Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found.**

**Sources read (verbatim):** `LP.sol` (`changeLockedLiquidity`, `addReserve`,
`withdrawPayout`, `withdrawLiquidity`), `CoreBase.sol` (`_resolveCondition`, `_calcReserve`,
`_changeLockedLiquidity`/odds application, resolve authorization), `PrematchCore.sol`
(`resolveCondition`), `extensions/SafeOracle.sol` (propose/dispute/approve/applyProposal).

---

## 0. Why a third pole was needed

The first two poles agreed *too* well. Polymarket (UMA) and Augur (REP) have **opposite
oracles** but the **same floor**: peer-to-peer, fully-collateralized outcome/complete sets
that conserve by construction (`Σ numerators = denominator`/`numTicks`). That agreement made
"the floor always conserves" look like a law — but both samples were drawn from the *same
floor family*. A law proven only inside one family isn't a law; it's a family trait.

Azuro is built on the **other** floor family: a **liquidity pool is the counterparty**
("the house"). LPs take the other side of every bet. This is the pole that tests whether
"the floor conserves" is universal — and it is **not**. Finding the boundary of the earlier
claim is the entire value of this audit.

---

## 1. The floor is NOT conserve-by-construction — it is solvency-by-reserve-locking. **Sound, but different.**

In the CTF/REP family, a full outcome set is fully collateralized: locked collateral = max
payout, so the house has **zero** directional risk and the floor is a pure conservation
identity. **Azuro has no such identity.** A bettor stakes `S`; if they win they receive
`S · odds > S`, paid from **LP capital**. The pool can *win* a book (keep losers' stakes) or
*lose* one (pay winners out of LP funds). There is no conservation law to lean on. What
replaces it is a **live solvency invariant**, enforced at three points:

1. **Lock max liability at bet time.** Every bet recomputes the condition's required reserve
   via `_calcReserve = max(maxSum(payouts, winningOutcomesCount), totalNetBets) − totalNetBets`
   — the pool's worst-case payout on that condition net of stakes already collected — and calls
   `lp.changeLockedLiquidity(Δreserve)`. That function **reverts `NotEnoughLiquidity`** if
   `lockedLiquidity > reserve` (pool can't cover globally) or if a single core exceeds its
   `reinforcementAbility · reserve` cap (`LP.sol:435-438`). **The pool can never accept a bet
   whose worst-case payout it cannot already cover.**
2. **Locked funds can't be pulled out from under open bets.** `withdrawLiquidity` rejects any
   LP withdrawal exceeding `topNodeAmount − lockedLiquidity` (`LP.sol:326`). Reserved liability
   is ring-fenced from LPs until the condition resolves.
3. **P&L settled to LPs on resolve.** `_resolveCondition` computes
   `profitReserve = lockedReserve + fund − reinforcement − payout` and calls `lp.addReserve`:
   if `finalReserve > lockedReserve` the surplus is **added** to LP liquidity (minus DAO/
   data-provider/affiliate fees); otherwise the loss is **removed** from LP liquidity
   (`_remove(loss)`), borne collectively by depositors via the `LiquidityTree`.

**Verdict — the bettor-protection floor is sound:** because liability is locked and
ring-fenced before a bet is accepted, **a resolved winner can always be paid.** But this is a
*solvency* guarantee, not a *conservation* one, and it explicitly does **not** protect LPs:
LPs bear the book's directional P&L by design. The "floor" coordinate here means something
different than in the CTF family, and reading it as "conserve-by-construction" would be a
**category error** — the very kind the methodology exists to catch.

**Where the floor's risk actually lives (the new bucket):** because the pool is the
counterparty, two risks appear that simply do not exist in CTF/REP markets:
- **Pricing/lock-math correctness.** The solvency guarantee is only as good as `_calcReserve`/
  `Math.maxSum`/odds math. If the lock under-computes worst-case liability, the pool can be
  drained despite the revert-guard (the guard checks the *computed* number). This is the part
  an auditor must recompute hardest — and it read as correct here (`maxSum` over winning
  outcomes, floored at `totalNetBets`, recomputed as a delta on every bet).
- **LP directional risk.** Even with perfect solvency, LPs lose money to better-informed
  bettors if odds are mispriced. That is an economic exposure, not a bug — but it is a real,
  first-class risk that the peer-to-peer designs *structurally do not have*.

---

## 2. The oracle seam — the most centralized of the three. **A disclosed trust, not a bug.**

Resolution authority in Azuro is the **most trusted** of the three poles:
- **Per-condition trusted oracle.** `condition.oracle` is set to `msg.sender` at condition
  creation (`CoreBase.sol:385`); only that address can resolve it
  (`require(msg.sender == condition.oracle)` at `:46-47`, `:102`). Resolution is a **trusted
  data-provider push** — no proposer/disputer game, no token vote at the base layer.
- **`SafeOracle` optionally adds an optimistic challenge layer** *on top*: the oracle
  **proposes** a resolution backed by an insurance stake; a `disputePeriod` opens; anyone may
  `dispute` (staking); if undisputed past the deadline, `applyProposal` finalizes; if disputed,
  the **DAO/owner adjudicates** (`approve` rejects the dispute and applies the oracle's
  solution, or `cancelCondition`). Structurally this is UMA's optimistic shape — propose,
  challenge window, escalate — **but the final adjudicator is the DAO/owner, not a token
  vote.** Most centralized backstop of the three.

This is a genuine, **disclosed** trust: bettors and LPs are trusting (a) the data provider to
report honestly, and (b) under SafeOracle, the DAO to adjudicate disputes fairly within the
decision period. It is not a contract defect — it is the protocol's stated trust model, and
the SafeOracle staking/dispute machinery is a real (if owner-backstopped) mitigation.

---

## 3. The three-pole synthesis — the law, with its boundary

Three prediction markets, deliberately chosen to disagree on **both** axes:

| | **Floor family** | **Floor guarantee** | **Resolution oracle** | **Ultimate backstop** | **House/LP risk** |
|---|---|---|---|---|---|
| **Polymarket** | CTF complete sets (peer-to-peer) | **Conserve-by-construction** (`Σnum = den`) | UMA optimistic OO | UMA **DVM** (separate-token vote) + **bounded admin** override | **None** |
| **Augur v2** | ShareToken complete sets (peer-to-peer) | **Conserve-by-construction** (`Σnum = numTicks`) | REP staked reporting + dispute escalation | **Fork** (own-token schism), **no admin** | **None** |
| **Azuro v2** | LP pool is counterparty (house) | **Solvency-by-reserve-locking** (lock max liability or revert) | **Trusted per-condition data provider** | `SafeOracle` propose→dispute→**DAO adjudicates** | **LPs bear book P&L + pricing risk** |

**The law, corrected and sharpened:**

1. **"All prediction-market trust telescopes onto the resolution oracle" — holds universally.**
   In every pole, the actor that sets the outcome is the dominant residual. Only its *shape*
   varies, along a trustlessness gradient: Augur (own-token fork, no human) → Polymarket
   (external-token DVM + bounded admin) → Azuro (trusted data provider + DAO-adjudicated
   challenge). **This is the structural invariant.**

2. **"The floor always conserves" — FALSE in general; it is a trait of the *peer-to-peer
   fully-collateralized* family only.** The real, family-independent statement is: **the floor
   must guarantee that resolved winners can always be paid**, and it does so by one of two
   mechanisms —
   - *conservation* (peer-to-peer: locked = max payout by identity; CTF, Augur), or
   - *reserve-locking solvency* (pool-backed: lock max liability before accepting the bet, or
     revert; Azuro).
   Recognizing **which floor mechanism you are auditing** is the load-bearing judgment. In the
   conservation family a share-accounting "finding" is almost always a read error; in the
   pool-backed family the floor is a **live invariant** that *can* genuinely break (under-locked
   liability, withdrawable reserves, mispriced odds), and there is a **whole extra risk bucket
   — LP capital — that the conservation family does not have at all.**

3. **The two design axes are independent and each is a real trade-off:**
   - *Floor:* peer-to-peer (no house risk, capital-inefficient, needs full collateral) vs
     pool-backed (capital-efficient, LPs earn yield, LPs bear directional + pricing risk).
   - *Oracle:* trustless-but-nuclear (Augur fork) ↔ external-vote + bounded-admin (Polymarket)
     ↔ trusted-provider + DAO-adjudication (Azuro). Cheaper/faster resolution buys more trust.

---

## 4. Posture & conclusion

- **No exploitable contract defect found** in Azuro v2 core. The solvency invariant is enforced
  at bet time (`changeLockedLiquidity` revert), reserves are ring-fenced from LP withdrawal,
  and resolution P&L settles consistently to the `LiquidityTree`. The trusted-oracle and
  DAO-adjudication powers are the protocol's **disclosed** trust model, with SafeOracle staking
  as a real mitigation — not bugs.
- Not a disclosure. The value is the **corrected law** in §3: the oracle-is-the-residual claim
  is universal; the floor-conserves claim was a family trait, and the honest invariant is
  *winners-can-always-be-paid*, met by **conservation** in peer-to-peer markets and
  **reserve-locking solvency** in pool-backed ones — with LP capital as a distinct risk bucket
  unique to the house model.
- Method note (the discipline that mattered, again): the trap on a pool-backed market is to
  carry over the CTF instinct and either (a) hunt for a conservation leak that *by design isn't
  there* in that form, or (b) declare the floor "sound, conserves" without noticing it conserves
  *nothing* — it stays solvent by a live, breakable lock. Naming the floor's actual mechanism,
  and the LP-risk bucket it introduces, is the audit. Finding the boundary of yesterday's law
  was worth more than re-confirming it a third time.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
