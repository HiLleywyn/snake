# Cosmos SDK `x/bank` — the canonical conservation substrate (clean, with a version-specific note)

**Target:** `cosmos/cosmos-sdk`, sparse clone `/tmp/csdk`, HEAD `e57dc5e`. Audited the **`x/bank`
keeper** — `SendCoins`/`subUnlockedCoins`/`addCoins` (`x/bank/keeper/send.go`) and
`MintCoins`/`BurnCoins`/`setSupply` (`x/bank/keeper/keeper.go`). **Posture:** defensive; no exploit,
no PoC. **Result: clean — no finding, nothing to disclose**, plus one honest version-specific
observation (the registered supply invariant has been removed from HEAD; conservation now rests on
by-construction discipline).

Chosen because `x/bank` is the **conservation substrate that a large slice of the top-100 inherits** —
Cosmos Hub (ATOM), Celestia, Injective, dYdX, Sei, Osmosis, Fetch, and every Cosmos-SDK chain. I have
already audited *derivatives* of this module (`AUDIT-OSMOSIS-SUPERFLUID-RECON.md`,
`AUDIT-SEI-OCC.md`, `AUDIT-FETCHD-COSMOS.md`); auditing the reference itself was the obvious gap, and
connection-driven (it grounds all three).

## Conservation floor — `SendCoins` is exactly 1:1 (Bucket 1 + Bucket 5)
`SendCoins(from, to, amt)` (`send.go:229-255`): `subUnlockedCoins(from, amt)` then
`addCoins(to, amt)` — **the same `amt` both legs**, so a transfer neither creates nor destroys value.
- **Debit** `subUnlockedCoins` (`:304-344`): computes `spendable = balance − lockedCoins` via
  `SafeSub` with a `hasNeg` flag; if `spendable.SafeSub(coin)` underflows → `ErrInsufficientFunds`
  (`:320-329`). You cannot spend below your unlocked balance. `newBalance := balance.Sub(coin)`.
- **Credit** `addCoins` (`:351-369`): `newBalance := balance.Add(coin)`.
- Both write via `UncheckedSetBalance`, which still enforces `balance.IsValid()` (non-negative, valid
  denom) and refuses to persist zero balances (`:374+`).
- **Arithmetic is bounded:** `math.Int` is a 256-bit-range big.Int (`math/int.go:90` "256 bit range
  bound"); `Int.Add` → `SafeAdd` and **panics on overflow** (`:277-284`), same for construction
  (`NewIntFromBigInt() out of bound`). So a balance/supply can never silently wrap — it halts. **enforced.**

## Supply tracking — only Mint/Burn move supply, both permission-gated (governance/Bucket 5)
`TotalSupply[denom]` changes in exactly two places, each adjusting a balance by the *same* amount:
- `MintCoins` (`keeper.go:357-397`): gated by `mintCoinsRestrictionFn` **and** the module account must
  hold the `Minter` permission (panic otherwise, `:370-372`); then `addCoins(acc, amt)` **and**
  `supply += amount` (`:383-387`). Balance and supply rise together.
- `BurnCoins` (`:401-434`): gated by the `Burner` permission (panic otherwise, `:407-409`); then
  `subUnlockedCoins(acc, amt)` **and** `supply −= amount` (`:419-423`). Balance and supply fall
  together.
- `SendCoins` never touches supply.
Therefore the invariant **`TotalSupply[denom] == Σ balances[denom]` holds by construction**: the only
supply-changing ops are matched 1:1 with a balance change, and transfers are internally conservative.
This is also the exact mechanism behind the `AUDIT-FETCHD-COSMOS.md` finding that the bridge can
*mint* (it holds `Minter`) but cannot *seize* — minting is `Minter`-permissioned here, and there is no
`x/bank` primitive to move another account's coins without its signature. **enforced.**

## Honest version-specific observation — the registered invariant is gone in HEAD
Historically, `x/bank/keeper/invariants.go` registered a **`TotalSupply` invariant** (recompute
`Σ balances` and compare to stored supply) and a **`NonnegativeBalanceInvariant`**, run via the
`x/crisis` module — i.e. Cosmos was a member of the **checked-invariant family** (XRPL/Stellar/
Algorand). **In this HEAD that file is removed** (`find` shows only the unrelated
`iavl/internal/invariants.go`; no `RegisterInvariants`/`NonnegativeBalanceInvariant` anywhere in
`x/bank`). The `x/crisis` invariant-checking framework has been deprecated/removed in recent SDK
lines. So **current `x/bank` conserves *by construction* (the Mint/Burn/Send discipline + `IsValid()`
+ panic-on-overflow), not by a periodic recompute-and-compare.** This is a real shift on the
conservation-location ladder: Cosmos moved *down* from "recomputed global invariant" toward
"conserve-by-construction imperative with per-op checks." Not a defect — the by-construction argument
is sound and the arithmetic halts rather than wraps — but it means there is **no longer an in-protocol
backstop that would catch a future bug** in a custom module that manipulated balances via the unsafe
low-level setters. **Stated as an honest observation, not a finding** (parallel to the NEAR
named-global-check gap in `AUDIT-NEAR-RECEIPTS.md`).

## Connections to the corpus
- **Grounds the Cosmos cluster.** Osmosis/Sei/Fetch all sit on this `SendCoins`/supply core; the Fetch
  "bridge can mint, not seize" property is precisely the `Minter`-permission gate + absence of a
  force-transfer primitive seen here.
- **Conservation-ladder data point.** Where Algorand *recomputes* `totals.All()` each block and XRPL
  *asserts* per-tx, current Cosmos *constructs* (matched mint/burn + safe per-op arithmetic). Three
  rungs of the same ladder, now with Cosmos's rung re-placed after the invariant removal.
- **Overflow = halt, not wrap.** The `math.Int` panic-on-256-bit-overflow is the same
  halt-over-corruption philosophy verified in Sui/MonadBFT and *absent* in the MemeCore finding.

## What this audit did NOT cover (coverage honesty)
- **`SendRestriction`/`LockedCoins`/vesting** beyond the spendable check — the hooks that gate sends
  (the `sendRestriction.apply` at `send.go:235`, used by e.g. permissioned-token chains).
- **`x/staking`/`x/distribution`/`x/mint`** — the modules that actually *call* `MintCoins`/`BurnCoins`
  (where issuance policy lives); I verified the bank-level gate, not each caller's economics.
- **IBC transfer (`ics20`)** — the cross-chain conservation seam (escrow/mint on transfer), the
  Bucket-6 residual for the whole Cosmos ecosystem, not opened here.
- **The DA/consensus (CometBFT)** layers — orthogonal.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read `SendCoins` to confirm both legs use the same `amt`, read
  `subUnlockedCoins` to confirm the `SafeSub`/`hasNeg` underflow guard, and read `MintCoins`/`BurnCoins`
  to confirm supply moves *only* with a matched balance change under a permission gate. I did **not**
  assume the registered invariant exists — I checked, found it removed, and recorded that rather than
  citing a check that isn't there.
- **Exposure to reversal.** The by-construction verdict would weaken if a custom module used
  `UncheckedSetBalance` (explicitly documented as *not* updating supply, `send.go:373-374`) without
  maintaining supply itself — there is now no invariant sweep to catch the resulting drift. That is
  the precise residual the invariant removal introduces; I flag it as the place a downstream chain
  could break conservation, not a bug in `x/bank` itself.

## Verdict
**Clean.** Cosmos SDK `x/bank` conserves value by construction: `SendCoins` is exactly 1:1 with an
underflow-guarded debit, supply moves only via permission-gated `MintCoins`/`BurnCoins` each matched
to a balance change, and `math.Int` halts (panics) rather than wraps on overflow — so
`TotalSupply == Σ balances` holds without needing a recompute. The honest caveat: the historical
registered `TotalSupply`/`NonnegativeBalance` invariant has been **removed** from HEAD, moving Cosmos
from "checked invariant" to "conserve-by-construction" and leaving no in-protocol backstop for a
downstream module that misuses the unsafe low-level setters. No untrusted-input→value path in `x/bank`
itself; nothing to disclose. Next pulls: IBC ics20 escrow conservation (the Cosmos cross-chain seam)
and the `x/mint`/`x/staking` issuance callers.
