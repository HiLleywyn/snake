# Curve veCRV + gauges — governance as a market (vote-escrow → emissions → the bribe layer)

**Scope.** Curve's vote-escrow + gauge-emission governance: `VotingEscrow` (veCRV), `GaugeController`,
`Minter`, `LiquidityGauge` (`curvefi/curve-dao-contracts`, Vyper `0.2.4`). This adds a **new governance
sub-model** to the corpus — *governance-as-a-market*, where locked tokens directly direct token
emissions, making votes a tradable economic good and spawning an (off-chain) bribe market. Companion to
the §5f governance dissection (OZ/Compound) and the §4c governance-ceiling spectrum. Public source,
read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**;
the governance-capture-as-feature and admin gauge-control surfaces are characterized factually.

**Sources (verbatim, line refs):** `VotingEscrow.vy`, `GaugeController.vy`, `Minter.vy`,
`gauges/LiquidityGauge.vy`.

---

## 0. The one-paragraph result

The §5f governance audit (OZ/Compound) characterized governance as *control of a treasury/upgrade key,
defended by a vote-weight snapshot and a timelock delay*. Curve's veCRV model is a **different species of
governance entirely**, and it is the canonical one for DeFi emissions: votes don't (primarily) pass
proposals — **they direct a continuous, valuable stream of token emissions.** Voting power is **veCRV** —
CRV locked for up to 4 years, weighted by remaining lock time and **decaying linearly to zero at unlock**
(`balanceOf = amount · time_remaining / 4yr`), **non-transferable** (you must lock real, illiquid
capital). veCRV holders then `vote_for_gauge_weights` to set each liquidity gauge's `relative_weight`,
and that weight is a **direct multiplier on the CRV minted to that gauge's LPs** (`gauge weight → rate·w·dt
→ integrate_fraction → Minter mints CRV`). The consequence is the whole point: **a vote literally re-routes
real, ongoing CRV emissions, so vote weight has measurable monetary value to whoever owns the target
pool** — which is the structural precondition for the **bribe market** (Votium/Hidden Hand, *off-chain,
external to these contracts*): a rational protocol pays veCRV holders to vote its gauge up. None of this is
a contract bug — the contracts behave exactly as written; the "vote-buying" is an *emergent economic
layer* that the design's vote→emissions→value coupling makes inevitable. The remaining trust is a single
**`admin`** (the Curve DAO's Aragon agent) that gatekeeps *which* gauges can ever earn emissions
(`add_gauge`) and can `kill` any gauge to zero — so veCRV votes only redistribute weight *among gauges the
admin already admitted*. So the veToken law: *this is governance recast as a market — voting power is
illiquid locked capital, votes are a tradable faucet on real emissions, and "governance capture" is not an
attack but a feature (anyone who accumulates or rents enough veCRV durably steers the money) — bounded only
by the capital cost of locking and by an admin who decides what's votable in the first place.*

---

## 1. Vote-escrow — non-transferable, time-decaying voting power. **Commitment by capital lockup.**

`VotingEscrow.vy` makes voting power a function of *locked CRV × remaining lock time* (max
`MAXTIME = 4 years`). The `Point{bias, slope}` checkpoint derives it (`:250-255`):
```vyper
u_new.slope = new_locked.amount / MAXTIME            # CRV per 4yr
u_new.bias  = u_new.slope * (new_locked.end - block.timestamp)   # current power = slope · time_remaining
```
and `balanceOf (:525-541)` decays it linearly to zero at unlock (`bias -= slope·(t − ts)`, floored at 0).
Locks are created/extended via `create_lock`/`increase_amount`/`increase_unlock_time` (`:412-464`, capped
at 4 years). **veCRV is non-transferable** — the contract exposes no transfer of the *ve* balance; it
exists only as a derived `balanceOf`, and a `set_smart_wallet_checker` whitelist (`:168`) blocks arbitrary
contracts from locking.

**Characterization:** voting power = illiquid, time-committed capital that *decays* — more influence
requires longer locks. This is the intended Sybil/commitment defense (you can't flash-borrow veCRV; it's
the antithesis of the §5f snapshot model — here power *is* locked stake, not a past-block balance), and
also the friction the bribe market later arbitrages.

---

## 2. Gauge controller — votes direct emissions. **What makes a vote valuable.**

`GaugeController.vote_for_gauge_weights (:485-553)`: a holder allocates up to 10000 bps of their veCRV
*slope* across gauges (`new_slope.slope = slope · _user_weight / 10000`), rate-limited to once per
`WEIGHT_VOTE_DELAY = 10 days` (`:498`) and requiring the lock to outlast the vote (`:496`). The vote sets
each gauge's `gauge_relative_weight (:347-363)` — its fraction of total weight, normalized to 1e18 — and
the docstring is explicit: *"Inflation which will be received by it is `inflation_rate · relative_weight /
1e18`."*

**Characterization:** this is the mechanism that turns a governance vote into money. `relative_weight` is
a **direct multiplier on CRV inflation** to that gauge's LPs, so **controlling veCRV = controlling a yield
faucet.** The vote decays with the lock (`end = lock_end`), so sustained influence needs sustained lockup.

---

## 3. The minter — CRV paid strictly by gauge weight. **The loop closes.**

`LiquidityGauge.vy (:183-217)` accumulates `integrate_fraction[user] += working_balance · (rate · w · dt)`
where `w = Controller.gauge_relative_weight(self, ...)` — emissions are literally `rate × (vote-set weight)
× time`. Killed gauges zero the rate (`:175-176`). `Minter._mint_for (:42-50)` is the **sole** minter of
CRV to LPs and pays `integrate_fraction − already_minted`. **The full loop:** `veCRV vote → GaugeController
weight w → gauge integral rate·w·dt → integrate_fraction → Minter mints CRV to that pool's LPs.` Every CRV
emitted to liquidity is, by construction, allocated by a veCRV vote.

---

## 4. Governance — an admin gatekeeps *what is votable*. **The residual above the market.**

`add_gauge (:290-324)` is `assert msg.sender == self.admin` — **only the admin admits a gauge**, and only
admitted gauges can ever receive emissions (Minter `:43`, gauge checkpoint `:185`). `change_type_weight`/
`add_type` are likewise admin-only, and each gauge's `kill_me (:332)` (admin) zeroes its rate. Ownership is
a standard 2-step `commit_/apply_transfer_ownership` on all three contracts; `admin` is intended to be the
Curve DAO's Aragon agent (a contract, external to this repo).

**Characterization:** veCRV holders vote *weights among already-admitted gauges*; **admission itself is a
privileged DAO action.** So there are two governance layers stacked: a **market** (veCRV votes redistribute
emissions among gauges, capturable by capital/bribes) sitting *inside* a **ceiling** (the admin decides the
gauge set and can kill any gauge). Trust concentrates in that admin key for the *menu*; the *allocation* is
the market.

---

## 5. The bribe-market residual — emergent, off-chain, not a bug

Nothing in `curve-dao-contracts` implements bribes — Votium/Hidden Hand/Warden are **external** markets.
The residual is purely emergent from the on-chain facts: because `vote_for_gauge_weights` deterministically
re-routes real CRV emissions, a veCRV vote has measurable monetary value to whoever owns the target pool,
so a rational protocol *pays* veCRV holders to vote its gauge up. **Characterization (factual):** this is
*governance-as-a-market* — votes are a tradable economic good, and vote-buying lives entirely outside the
codebase. It is not a defect; it is the inevitable economic consequence of coupling votes to emissions, and
it is *the* defining property of the veToken model (replicated by Balancer veBAL, Frax veFXS, etc.).

**Factual concerns (defensive, no exploit):** (1) **governance-capture-as-feature** — concentrated or
*rented* veCRV can durably steer emissions; a structural property, not a bug, but it means the system is
economically capturable by anyone who accumulates/rents enough vote weight. (2) **Admin gauge-add + kill**
— the admin defines what can ever earn CRV and can zero any gauge; veCRV voting only operates within that
admin-set menu. (3) **Lock-decay friction** — non-transferable, decaying, max-4-year-locked power is the
Sybil/commitment defense and simultaneously the friction the bribe market monetizes.

---

## 6. Where this sits in the corpus

Curve veCRV adds a **third governance model** to the corpus alongside §5f's two (OZ Governor / Compound
Bravo): not *propose-vote-timelock over a treasury*, but **vote-escrow-direct-emissions as a market**. It
inverts the §5f flash-loan defense — there, power is a *past-block snapshot* (so borrowed tokens don't
count); here, power *is* illiquid locked stake (so you can't borrow it cheaply, but you *can* rent its
*output*, the vote, via bribes). It extends the **governance-ceiling** residual (§5e class 2) with a
sub-type — *governance-as-a-market* — where the residual isn't "what can the admin do" but "who can afford
to direct the emissions," and the honest characterization is economic, not a code finding: **the contracts
are exactly correct; the trust is that vote weight ends up allocated by genuine long-term stakeholders
rather than by whoever pays the most to rent it.** It also re-confirms the own-vs-delete dial at the
emissions layer: Curve *owns* the menu (admin gauge-add) and *markets* the allocation (veCRV votes) —
neither fully delegated nor fully fixed. The honest user statement: *CRV emissions are steered by a market
in locked-capital votes; that market is capturable by accumulation or bribery (a feature, not a flaw), and
sitting above it is a DAO admin that decides which pools are even eligible — so where the rewards flow is a
question of vote economics and admin curation, not of any on-chain conservation guarantee.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
