# Augur v2 — prediction-market audit + comparative oracle-seam study (vs Polymarket)

**Scope.** Augur v2 on-chain core (`AugurProject/augur`, `packages/augur-core`): the
ShareToken complete-set conservation floor, the Market reporting state machine, the
DisputeCrowdsourcer escalation game, and the Universe forking backstop. Read in direct
companion to `AUDIT-POLYMARKET-PREDICTION-MARKET.md`. Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found.**

**Sources read (verbatim):** `reporting/ShareToken.sol`
(`buyCompleteSetsInternal`, `burnCompleteSets`, `claimTradingProceedsInternal`,
`calculateProceeds`, `assertBalances`), `reporting/Market.sol` (`doInitialReport`,
`contribute`, `finalize`, `derivePayoutDistributionHash`, `redistributeLosingReputation`),
`Augur.sol` (`derivePayoutDistributionHash`), `reporting/Universe.sol` (`fork`,
`updateForkValues`), `reporting/Reporting.sol` (constants).

---

## 0. Why this audit exists

The Polymarket audit ended on a claim: *every prediction market telescopes all its trust onto
the resolution oracle; the conservation floor is always airtight by construction.* A claim
proven on one architecture is a coincidence. To make it a **law** I re-ran it against a
prediction market built on the **opposite** oracle philosophy. Polymarket resolves via an
*optimistic attestation backed by a separate token's vote* (UMA OO → DVM) plus a *bounded
human admin override*. Augur resolves via a *staked reporting escalation that ends, in
extremis, by forking its own security token* — and has **no admin override at all**. If the
same floor-conserves / oracle-is-the-residual shape holds across both, it is structural.

It holds. Here is the proof, and the sharpened result.

---

## 1. The conservation floor — identical law, different name. **Sound.**

Augur's "complete set" is the exact analog of CTF's outcome-token set.

- **Mint** (`buyCompleteSetsInternal`): `_cost = _amount · numTicks`, deposits `_cost` cash,
  `_mintBatch` mints `_amount` of **every** outcome share. One complete set ⇔ `numTicks` cash.
- **Burn** (`burnCompleteSets`): burns one of each outcome, `_payout = _amount · numTicks`
  (minus creator/reporting fees), withdraws cash. Inverse of mint, 1:1.
- **Redeem** (`claimTradingProceedsInternal` → `calculateProceeds`):
  `proceeds = numShares · getWinningPayoutNumerator(outcome)`.
- **The invariant that makes it conserve** is enforced in `Augur.derivePayoutDistributionHash`:
  ```solidity
  require(_payoutNumerators[0] == 0 || _payoutNumerators[0] == _numTicks); // Invalid is all-or-nothing
  for (...) _sum = _sum.add(_payoutNumerators[i]);
  require(_sum == _numTicks, "Malformed payout sum");
  ```
  **Every** payout array — initial report, every dispute round, every fork outcome — must sum
  to `numTicks`. So a complete set, which cost `numTicks`, always redeems for exactly
  `numTicks` distributed across its outcomes. This is **literally** the CTF law
  `payoutDenominator = Σ payoutNumerators`, with `numTicks` playing the role of the denominator.
- **Belt-and-suspenders:** `assertBalances` (called after every mint/burn/claim) requires the
  contract's cash holding to equal `Σ_outcome totalSupply(outcome) · winningPayoutNumerator`
  (or `totalSupply(0) · numTicks` pre-finalization). The floor cannot drift even by rounding.

**Verdict:** conserve-by-construction. Cannot leak. *Same conclusion, same mechanism, as
Polymarket's CTF.* Two independent teams, two codebases, one floor.

---

## 2. The oracle seam — same role, opposite architecture. **The contrast.**

Both protocols collapse all economic trust onto "who sets the winning payout numerators."
That actor is the resolution oracle. **The seam is in completely different places:**

| | **Polymarket (UMA)** | **Augur v2 (REP)** |
|---|---|---|
| **Truth source** | Optimistic Oracle: a proposer posts the outcome + bond; stands if undisputed through liveness | Designated/initial **reporter** posts outcome backed by **REP stake** |
| **Dispute** | Anyone disputes → escalates to **UMA DVM**, a vote of a **separate** token (UMA) | Anyone disputes by **staking REP** on an alternative via `DisputeCrowdsourcer`; each round's bond must **≈ double** (geometric escalation, ≤ `MAXIMUM_DISPUTE_ROUNDS = 20`) |
| **Ultimate backstop** | UMA DVM token-holder vote (external token), commit-reveal | **Universe `fork()`** — triggered when one dispute bond fills `≥ 2.5%` of total REP (`FORK_THRESHOLD_DIVISOR = 40`). REP holders **migrate** their tokens into the child universe of the outcome they believe; the child with `> 50%` migrated REP wins; **losing-universe REP becomes worthless.** Duration `FORK_DURATION_SECONDS = 60 days`. |
| **Skin in the game** | Proposer's bond + UMA voters' (separate) stake | **Maximal & self-referential:** REP *is* the oracle *and* the security token. Mis-report → your own REP is slashed/burned (`redistributeLosingReputation` liquidates losers + **burns 20%** to deny griefing) and, on fork, can be stranded in a dead universe. |
| **Admin override** | **Yes, bounded:** `resolveManually` (admin sets payouts directly), but only after `flag` + `SAFETY_PERIOD` elapsed, on-chain-announced, conservation-bounded; plus pause/reset | **None.** `Market.sol` / `Universe.sol` have **zero** `onlyOwner`/admin/pause/force-resolve. The fork *is* the only escape hatch, and it is decided by token migration, not a privileged key. |

**The two designs are duals.** Polymarket **externalizes** the truth-vote (a different token,
UMA, decides; and a human admin holds a bounded emergency key). Augur **internalizes** it (the
protocol's own token holders decide by schism; no human key exists). Polymarket buys cheap,
fast operation at the cost of a trusted-but-bounded admin and an external oracle's honesty.
Augur buys full trustlessness — *no privileged resolver anywhere* — at the cost of a backstop
(the fork) that is **nuclear, slow (60 days), and economically catastrophic** by design, so that
invoking it is rare and reporters are deterred from lying by the threat of destroying their own
capital.

---

## 3. Where Augur's residual actually lives (and why it's not a contract bug)

The on-chain code conserves and the escalation game is mechanically sound (stake doubling,
20-round bound to forced fork, 20% loser-burn against round-tripping griefs, Invalid forced
to all-or-nothing). The **irreducible residual is the same class as Polymarket's** — the
*truth-input*, not the math:

- **Reporter/disputer game economics.** Resolution correctness rests on it being more
  profitable to report truthfully than to lie, across every dispute round up to a fork. This is
  a crypto-economic assumption (REP market cap ≥ value-at-stake in open markets — the "P vs
  market-cap" security condition), not a contract invariant.
- **The fork is a real, if rarely-pulled, tail risk.** A 60-day fork freezes the universe,
  splits liquidity, and forces every REP holder and every open market to migrate. It is the
  backstop *and* the systemic-risk concentration point. The contracts implement it correctly;
  whether the *community* coordinates correctly through one is off-chain.
- **No admin escape is a double-edged design choice.** Augur's governance ceiling is **lower**
  than Polymarket's (no key can override a market) — strictly better for censorship-resistance
  and trustlessness — but it also means a genuinely-ambiguous or mis-specified market has **no
  graceful manual fix**; it can only be resolved Invalid or fought to a fork. Polymarket's
  bounded `resolveManually` is exactly the trust Augur refuses to take.

---

## 4. The sharpened law (the methodology payoff)

Running the six-bucket lens across **two** prediction markets with **opposite** oracle
philosophies yields a result stronger than either audit alone:

1. **The conservation floor of a prediction market is always conserve-by-construction, and it
   is always the *same* law:** the per-outcome payout numerators must sum to a fixed
   denominator (`numTicks` ≡ CTF `payoutDenominator`), so a full outcome set costs and redeems
   for exactly that denominator. Found identically in Gnosis CTF and Augur ShareToken. **This
   is not where prediction-market risk lives — and a finding here would almost certainly be a
   read error, not a real bug.**

2. **All prediction-market trust telescopes onto the resolution oracle** — the actor that sets
   those numerators. This is invariant across architectures.

3. **Only the *shape* of the oracle seam varies, along two axes that trade off against each
   other:**
   - **Whose token decides the disputed truth** — a *separate* token (UMA/Polymarket) vs the
     protocol's *own* security token by schism (REP/Augur). Self-token forking maximizes
     skin-in-the-game but makes the backstop systemically catastrophic.
   - **Whether a human admin holds a bounded override** — yes-but-bounded (Polymarket
     `resolveManually`, time-delayed/announced/conservation-capped) vs none-at-all (Augur).
     This is the cheap-and-trusted vs nuclear-and-trustless dial.

The honest user-facing risk statement is therefore identical in *kind* for both, and differs
only in *who you are trusting*: **"your payout is only as correct as the oracle's resolution of
your specific market — for Polymarket, UMA's optimistic game + DVM vote + a bounded admin key;
for Augur, the REP reporting/dispute game ending, if pushed, in a 60-day fork with no admin key
at all."** The contracts conserve perfectly in both; neither can tell you whether the answer is
*true*.

---

## 5. Posture & conclusion

- **No exploitable contract defect found** in Augur v2 core. Floor conserves (sum-to-numTicks +
  `assertBalances`); the dispute game is bounded and economically guarded; the fork is correctly
  gated; there is no privileged resolver to abuse.
- Not a disclosure. This is a trust-cartography characterization whose value is the **confirmed
  law** in §4 — proven now on two opposite oracle architectures, so it is structural rather than
  incidental to one codebase.
- Method note (the discipline that mattered): the temptation on Augur, as on Polymarket, is to
  hunt the share-accounting for a leak. There isn't one — both designs *deliberately* push all
  risk to the oracle. The correct audit output is to **name the seam and bound the backstop**,
  and — across the pair — to state the dial (self-token-fork vs external-vote; trustless vs
  bounded-admin) so a reader can see the design choice instead of a phantom bug.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
