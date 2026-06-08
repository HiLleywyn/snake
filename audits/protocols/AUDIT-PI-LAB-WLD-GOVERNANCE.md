# PI / LAB / WLD — governance-ceiling & auditability-floor triptych

Three targets that aren't conservation-*mechanism* studies (like the L1 sweep) but **governance-ceiling
/ supply-control / auditability-floor** cases — and together they form a clean spectrum from
"can't verify anything" to "open and strongly bounded." **Posture:** defensive; no exploit, no PoC; I
distinguish *what I verified on-chain* from *what is publicly reported* and *what I could not examine*.
**Result: no exploitable finding in what's auditable; the story for each is where the trust lives.**

The unifying question (Law 4): *trustless until whom?* For supply-controlled tokens the answer is
either (a) the code (if mint/owner powers are bounded), (b) the distribution (if the token is fixed but
the float is concentrated), or (c) entirely an off-chain team (if the core is closed). PI/LAB/WLD land
on c / b / a respectively.

---

## WLD (Worldcoin / World token) — open + strongly bounded supply (the good end)
**Verified** against `worldcoin/worldcoin-token` (`src/WLD.sol`, cloned). Complements the *protocol*
audit in `AUDIT-WORLDID.md` (this is the *token*). The supply authority is tightly constrained in code:
- **Hard cap + one-time initial mint.** `INITIAL_SUPPLY_CAP = 10_000_000_000e18` (`:29`); `mintOnce`
  is `onlyOwner` and guarded `require(initialMintDone == false)` + `require(totalSupply() <=
  INITIAL_SUPPLY_CAP)` (`:134-153`) — the owner can seed the initial allocation **once**, never above
  10B.
- **15-year mint lock, then rate-limited inflation.** No address can mint until `inflationUnlockTime`
  (`mintInflation` requires `block.timestamp >= inflationUnlockTime`, `:209`); after that, only the
  `minter` (set once by `setMinter`, `onlyOwner`, `:165`) can mint, and each period is capped:
  `currentPeriodSupplyCap = initialSupply + initialSupply*inflationCapWad/WAD` and
  `require(totalSupply() <= currentPeriodSupplyCap)` (`:214-226`) — i.e. **≤~1.5%/period**, enforced in
  code (the doc-comment even bounds the worst-case period-boundary overshoot to `(1+cap)^2−1`).
- **Non-upgradeable.** No proxy; the only post-deploy lever is `setMinter` (and `renounceOwnership` is
  overridden, `:171`). So **no one can inflate WLD beyond the coded schedule, ever.**
**Verdict: the token's supply floor is strong and self-bounding** — capped, time-locked, rate-limited,
non-upgradeable. The governance ceiling is narrow: the **owner (World Foundation/World Assets)** does
the one-time allocation and (post-15y) names the inflation minter. **The real residual is off-chain
distribution**, not the contract: the 7.5B "community" allocation is granted to **orb-verified humans**,
and *who is a unique human* is the same off-chain orb/operator trust named in `AUDIT-WORLDID.md`. So:
**code-bounded supply; off-chain-bounded distribution.** No finding.

## LAB — clean token contract, distributional risk lives elsewhere (the middle)
**Verified** the token contract on BSC (`0x7ec43cf65f1663f820427c62a5780b8f2e25593a`, source verified
"exact match"). The token itself is **a plain fixed-supply ERC-20**:
- **No `mint`/`_mint` (post-construction), no `owner`/`onlyOwner`, no pause, no blacklist, no
  fee-on-transfer, no proxy.** Supply is `_mint`-ed once in the constructor (1,000,000,000 × 1e18) and
  is otherwise immutable; holders can `burn` (supply only ↓). **So the token cannot be inflated,
  paused, frozen, or rugged *through the token contract* — there is no privileged authority on it.**
- **This corrects the headline.** Public reporting flags ~95% insider supply control, vesting-schedule
  changes "without consent," and a 77% / ~$6B two-hour collapse. Crucially, **none of those are
  powers of the token contract** — a fixed-supply, ownerless ERC-20 has no mint to abuse. They are
  **distributional**: a function of *who holds the 1B fixed tokens* and *what separate vesting
  contracts permit*, i.e. concentration + vesting terms, not minting.
**Verdict (precise, and the honest distinction):** the token's **conservation floor is sound** (fixed
supply, no privileged mint). The **risk is entirely distributional and lives off the token contract**:
(i) holder concentration (checkable on-chain via the BSC holders list — the methodology's
"verify-the-effect"), and (ii) the **separate vesting contract(s)** whose mutability would determine
whether unlocks can be altered — **which I did not examine** (addresses not in hand; that is the
decisive unaudited surface). A clean token with a concentrated float is "trustless code, trusted
float." **No finding in the token; the reported concerns require auditing the vesting contracts and the
holder distribution, named here as the open items.** *(I treat the 95%/vesting/crash items as
**reported allegations**, not verified facts — I confirmed only that the token contract grants no
authority to do those things via itself.)*

## PI (Pi Network) — closed core (the bad end / auditability floor)
**Cannot verify.** As of mid-2026 Pi's **core protocol/ledger code is not open-sourced** (the
"Open Mainnet vs Open Source" transition is still in progress); the public `pi-node` repo is an
**operational wrapper** (like Hyperliquid's node repo — runs the core, isn't the core), and the
network is **KYC-gated with centrally-dictated protocol upgrades** (all node operators forced to a
specific protocol version by a deadline). Pi's consensus is a Stellar/SCP fork, but the *running*
mainnet code — issuance, the migration/lockup logic, the validator/quorum configuration — is **closed
and centrally operated.**
**Verdict: auditability floor — conservation is unverifiable from the outside; the trust is the Pi Core
Team, entirely.** There is no on-chain artifact I can recompute against: not a "clean" or "dirty"
verdict but a **"cannot be audited"** one. This is the worst position on the auditability spectrum
(`AUDIT-CAPSTONE.md` §4d) — worse than a closed *enforcing program* with an open client, because here
even the client/ledger is closed and the operator controls upgrades and identity. **Nothing to clear;
the honest output is: you are trusting an off-chain team with no verifiable floor.**

---

## The spectrum (why these three together)
| | Supply authority | Verifiable? | Trust lives in |
|---|---|---|---|
| **WLD** | capped 10B, 15-yr lock, ≤1.5%/yr, **non-upgradeable** | **yes** (open `WLD.sol`) | code (supply) + off-chain orb (distribution) |
| **LAB** | **fixed 1B, ownerless, burn-only** token | **yes** (token); **no** (vesting/float) | the *distribution* — concentration + separate vesting |
| **PI** | unknown (closed) | **no** | the Pi Core Team, entirely |
This is the "auditability is not one thing" lesson made concrete: **WLD** is code-bounded (the strong
case), **LAB** has a clean token but the danger is relocated to off-contract distribution (verify the
holders + vesting, not the token), and **PI** can't be audited at all. None presents an *exploitable
contract bug* in what's auditable; the differences are entirely **where the trust sits and whether you
can see it.**

## Self-check (epistemic hygiene)
- **Recompute, not trust the headline.** For LAB I did **not** repeat the "insider rug" framing as a
  contract fact — I read the verified contract and found it ownerless/fixed-supply, which *contradicts*
  a token-level mint rug and *relocates* the real risk to distribution/vesting (separate, unaudited).
- **Verified vs reported vs not-examined, kept distinct.** Verified: WLD.sol mint bounds; LAB token has
  no privileged authority; PI core is closed. Reported (not verified): LAB's 95%/vesting/crash. Not
  examined: LAB's vesting contracts + on-chain holder distribution; PI's closed core (unobtainable).
- **Exposure to reversal.** WLD's "strong" rests on the deployed contract matching the audited
  `WLD.sol` and the constructor params (inflation cap/period) being the intended ~1.5%/yr — I read the
  source, not the live deployment's immutables. LAB's "token is clean" would not save users from a
  malicious *vesting* contract or a concentrated dump — that's the point (the risk is off-token). PI is
  unfalsifiable from outside by construction.

## Verdict
No exploitable finding in any auditable surface. **WLD**: open, capped, rate-limited, non-upgradeable
supply — strong by design; residual is the off-chain orb-gated distribution (per `AUDIT-WORLDID.md`).
**LAB**: the token contract is a clean fixed-supply ownerless ERC-20 (cannot be inflated/paused/frozen)
— so the verified risk is **distributional**, living in separate vesting contracts and holder
concentration that must be audited on-chain (named open items), not in the token; reported insider/
vesting concerns are flagged as allegations, not confirmed. **PI**: closed core — **auditability
floor**, conservation unverifiable, trust is the Pi Core Team entirely. The three are a textbook
spectrum of *trustless-until-whom*: code → distribution → off-chain team.
