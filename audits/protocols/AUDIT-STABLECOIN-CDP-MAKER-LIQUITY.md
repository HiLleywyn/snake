# Stablecoin CDPs — the peg as a conservation floor + the governance dial (MakerDAO vs Liquity)

**Scope.** The two archetypal collateralized-debt stablecoins, chosen to span the governance axis at
its extremes: MakerDAO `dss` (`makerdao/dss` @ `fa4f663`, governance-maximal, MKR backstop) and
Liquity v1 (`liquity/dev` @ checkout, **governance-zero / immutable**, redemption-pegged). Public
source, read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable
defect found**; factual concerns flagged for context. (Note: the `dss` mirror's headers state it is
the canonical-logic mirror, LibNote removed — logic intact, not byte-identical to mainnet bytecode.)

**Sources read (verbatim, line refs against those checkouts):** Maker `vat.sol`, `dog.sol`,
`spot.sol`, `vow.sol`, `flop.sol`, `pot.sol`, `end.sol`; Liquity `LiquityBase.sol`,
`BorrowerOperations.sol`, `TroveManager.sol`, `StabilityPool.sol`, `PriceFeed.sol`, `LUSDToken.sol`.

---

## 0. The one-paragraph result

A CDP stablecoin is a **conservation floor operating under an extra constraint the prior verticals
never had: a *peg*** — the debt token must stay worth ~$1, which the collateral ledger alone cannot
guarantee, because $1 is an external fact. So every CDP reduces to two questions: *(1) is the
collateral ledger conservative* (does `mintable ≤ collateral·ratio` hold by construction), and *(2)
what mechanism pins the peg* when collateral value moves. Both Maker and Liquity nail (1) the same way
— a checked-arithmetic CDP ledger with a hard safety invariant (`debt·rate ≤ collateral·spot` for
Maker, `ICR ≥ 110%` for Liquity). They differ totally on (2) and on *who is trusted*, and that
difference **is** the governance dial. Maker maintains the peg with a governance-tuned machine:
adjustable risk params, surplus/debt auctions, the DSR demand lever, and an **uncapped MKR-mint
backstop of last resort** — powerful and adaptive, but the safety ceiling is "MKR governance + the
OSM oracle delay," with no on-chain cap on what `auth` holders can change (they can even swap any
collateral's price feed). Liquity **deletes governance entirely**: ownership is renounced at deploy,
every parameter is a `constant`, and the peg is pinned not by policy but by a *permissionless
arbitrage* — **redemption**, where anyone can always swap 1 LUSD for $1 of ETH from the riskiest
troves, creating a hard floor that needs no admin and no discretionary intervention. So the stablecoin
law: *the collateral floor is conserve-by-construction in both; the peg is an oracle-dependent
constraint laid on top of it; and you can hold the peg by governable policy (Maker — maximal
flexibility, maximal trust) or by immutable arbitrage (Liquity — zero flexibility, zero governance
trust). It is the lean-in/delete dial again, now applied to the admin key itself.*

---

## 1. The collateral floor — checked-arithmetic CDP ledger. **Sound in both.**

**Maker (`vat.sol`)** is the purest expression: the entire system is a ledger of `Urn{ink, art}`
(collateral, normalized debt) per ilk, with `dai[]` [rad], `gem[]` [wad], and globals `debt`, `vice`,
`Line`. `frob (:143-180)` is the only user-facing mutation, and it enforces three invariants on every
call:
```solidity
require(either(dart<=0, both(mul(ilk.Art,ilk.rate)<=ilk.line, debt<=Line)), "Vat/ceiling-exceeded"); // :161
require(either(both(dart<=0,dink>=0), tab <= mul(urn.ink, ilk.spot)), "Vat/not-safe");                // :163  safety
require(either(urn.art==0, tab >= ilk.dust), "Vat/dust");                                             // :173
```
The safety invariant `art·rate ≤ ink·spot (:163)` is the floor; `debt = Σ(Art·rate)` is maintained
because `debt` only moves through `frob`/`fold`/`suck`/`heal`, and `vice` (unbacked Dai) only through
`grab`/`suck`/`heal`. The signed `_add/_sub/_mul (:74-97)` revert on overflow/sign violation — **the
conservation floor literally *is* checked arithmetic on a double-entry ledger.**

**Liquity** enforces the same shape with a fixed ratio instead of a per-ilk `spot`: every
`BorrowerOperations` entry requires `ICR ≥ MCR = 110%` (`:182-188,535`), and **mint authority is
hard-restricted** — `LUSDToken.mint` calls `_requireCallerIsBorrowerOperations() (:99-102)`, with
**no governance mint path at all**. MCR/CCR/fee floors are `constant (LiquityBase.sol:19-36)`.

**Verdict:** both floors conserve by construction. The difference is entirely in the peg mechanism
and the trust model laid on top — which is the whole story.

---

## 2. The peg mechanism — governable policy (Maker) vs immutable arbitrage (Liquity). **The contrast.**

**Maker — a governance-tuned peg machine + MKR backstop of last resort.** When collateral value
drops, `dog.bark (:170-237)` checks `mul(ink,spot) < mul(art,rate) (:181)` and Dutch-auctions the
seized collateral via Clip, pushing the debt (plus the `chop ≥ 100%` penalty) to the Vow. The Vow then
runs the peg-defense auctions: **`flap`** sells surplus Dai for MKR (burned) above a `hump` buffer;
**`flop`** mints MKR to cover bad debt — and the actual mint is **uncapped at the contract level**
(`flop.sol:165 gem.mint(bids[id].guy, bids[id].lot)`). The DSR (`pot.sol`) is the demand-side lever,
accruing interest via `vat.suck` against the Vow. **The backstop of last resort is unbounded MKR
dilution** — adaptive and powerful, but it means the peg's ultimate guarantor is the *market value of
the governance token*, and the whole machine is steered by `auth`-gated parameters.

**Liquity — the peg is a permissionless arbitrage, no policy.** `TroveManager.redeemCollateral
(:925-1023)` lets **anyone** swap LUSD for ETH **at face value** ($1 of ETH per LUSD,
`ETHLot = LUSDLot·1e18/price (:831)`), consuming the **riskiest troves first** (`:967` skips troves
below MCR). This creates a *hard lower peg floor*: if LUSD trades below $1, arbitrageurs buy it cheap
and redeem it for a full $1 of ETH, profiting until the peg recovers — **no admin, no auction, no
discretion**. The upside is pinned by the 110% collateralization (you can always mint LUSD against ETH
if it trades above $1). Liquidation is Stability-Pool *offset* first
(`debtToOffset = min(debt, LUSDInSP) (:452)`, SP burns LUSD and absorbs ETH) then *redistribution* to
remaining troves, with Recovery Mode (TCR < CCR = 150%) tightening requirements. **The peg is held by
mechanism, not by management.**

---

## 3. The oracle seam — both depend on it; both fail *toward safety*, differently

- **Maker (`spot.sol`):** `poke (:98-103)` sets `spot = val/par/mat` from the `pip` feed (an OSM/median
  in production — the **time-delay lives in that external OSM, not in `spot.sol`**), scaled by the
  governance-set liquidation ratio `mat`. Fail-mode: if the feed returns `has == false`, **`spot` is
  set to 0**, marking the entire ilk unsafe/liquidatable. Fails *closed* (toward liquidation).
- **Liquity (`PriceFeed.sol`):** Chainlink primary + Tellor fallback, a 5-state machine with a 4h
  `TIMEOUT` and a **50% inter-round deviation guard**; on both-oracles-untrusted it **keeps operating on
  `lastGoodPrice` (:142,150,163,180)** rather than halting. Fails *open* (toward last-known), because
  there is no admin to pause — the oracle-failure *heuristics* substitute for a governance halt.

**This is the governance dial visible in the oracle layer itself:** Maker can swap the `pip` for any
ilk (an admin power), and its fail-closed mode is acceptable because governance can intervene; Liquity
*cannot* intervene, so it hard-codes degradation heuristics and accepts running on stale price as the
price of immutability. Same external dependency, opposite failure philosophy dictated by the presence
or absence of an admin.

---

## 4. The governance ceiling — the sharpest lean-in/delete in the corpus

| | MakerDAO | Liquity |
|---|---|---|
| **Admin model** | `wards`/`rely`/`deny` `auth` on every module | `onlyOwner` for a one-time `setAddresses`, then **`_renounceOwnership()`** |
| **Risk params** | governance sets `line`/`mat`/`chop`/`dust`/`dsr` live | `constant` (MCR 110%, CCR 150%, fee floors) |
| **Oracle** | governance can **swap any ilk's `pip`** (`spot.sol:81`) | fixed Chainlink+Tellor, no swap |
| **Peg backstop** | **uncapped MKR mint** (`flop.sol:165`) + global settlement (`end.sol`) | none — redemption arbitrage only |
| **Ceiling** | **very high** — `auth` can rewrite every param, swap feeds, trigger `cage()`; bounded only by MKR governance + OSM delay | **none** — immutable post-deploy; trust rests on code + 2 oracle providers |

Maker is the **lean-in** pole: maximal adaptability (it can onboard new collateral, retune risk in a
crisis, and mint its way out of insolvency) bought with maximal governance trust and no on-chain cap on
admin power. Liquity is the **delete** pole: it removes the admin entirely, so there is no governance
attack surface, no oracle-swap risk, no parameter-capture risk — at the cost of zero flexibility (it
cannot add collateral types, cannot adjust to changed conditions, and must accept running on
`lastGoodPrice` when oracles fail). **Per the §5f-class governance dissection, Maker's ceiling is
"MKR-weighted vote + OSM delay"; Liquity's ceiling does not exist because it renounced the key.**

---

## 5. Where this sits in the corpus

Stablecoin CDPs add the **peg** as a new flavor of residual: a conservation floor is *necessary but not
sufficient* for a stablecoin, because conserving collateral does not pin the token's *external value* —
that requires either a governable policy machine or a permissionless arbitrage, and both ultimately
lean on a price oracle to know when collateral is short. The Maker/Liquity split is the **governance
dial** (capstone §4c, §5f) applied to the admin key itself, and it is the cleanest instance in the
whole corpus: one protocol makes governance its core peg-defense tool (uncapped MKR mint, live risk
retuning), the other proves a stablecoin can hold its peg with **no governance at all** by replacing
discretionary defense with a structural arbitrage (redemption). This mirrors the NFT-lending
lean-in/refuse/replace and the intent atomic/optimistic split: **the same residual — here "who keeps
the peg / who can change the rules" — can be owned (Maker), or engineered away (Liquity), and the
choice is the entire risk profile.** The universal law holds: trust telescopes onto the
oracle + the ceiling; the novelty is a design (Liquity) that shrinks the ceiling to *nothing* and pays
for it in adaptability.

**Factual concerns flagged (defensive, no exploit):** (1) Maker — a single `auth` holder can swap any
ilk's `pip` and rewrite `line`/`mat`/`chop`; this is by design and is the dominant trust assumption
(safety = MKR governance + the OSM delay, which is the actual external timelock). (2) Maker —
`Flopper.deal` MKR minting is contract-level uncapped (intentional last-resort dilution; noted for
completeness). (3) Maker — `spot`'s fail-closed-to-0 means a stalled feed wrapper has *systemic*
liquidation impact for that ilk, not just a frob block. (4) Liquity — redemption imposes its cost on
the lowest-ICR troves first (documented; the reason borrowers keep buffers above 110%), and the
oracle-degradation-to-`lastGoodPrice` is the deliberate price of having no admin to pause.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
