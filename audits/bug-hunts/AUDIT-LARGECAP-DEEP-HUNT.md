# Deep large/mid-cap hunts — the active verticals: lending, synthetic-dollar, yield, perps

**Why this hunt exists.** A change of method, not just target: instead of breadth (one target per exotic taxonomy),
this round is **depth** — a full-lifecycle read of four live, large/mid-cap protocols in the most active DeFi
verticals, each tracing the entire state machine and the end-to-end conservation invariant rather than spot-checking.
The targets: **Morpho** (lending), **Ethena** (synthetic dollar), **Pendle** (yield tokenization), **GMX v2**
(perps). All live mainnet, all multi-hundred-million-to-multi-billion TVL, all large bounties.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute every rounding
direction and conservation invariant from source. Anything real and live would be stopped and routed for private
disclosure (redacted here). **All four came back clean — no live finding.** The unifying structure each deep read
confirmed: *every value-moving path rounds against the actor, and a conservation invariant backstops the residual.*

| Target | Vertical | The conservation invariant | Verdict |
|---|---|---|---|
| **Morpho Blue + MetaMorpho** | lending | `totalBorrowAssets ≤ totalSupplyAssets`; interest/bad-debt adjust both sides equally | **clean** |
| **Ethena** (USDe/sUSDe **V2 live**) | synthetic dollar | mint/redeem gated by whitelist+nonce+limits; sUSDe price = balance − unvested | **clean** |
| **Pendle** (PT/YT v6, Market V7) | yield tokenization | `totalPT == totalYT`; `value(PT)+value(YT) == value(SY-asset)` | **clean** |
| **GMX v2 / Synthetics** | perps | `validateMarketTokenBalance` ≥ Σ all accounting buckets, every tx | **clean** |

---

## 1. Morpho — the lending conservation, rounding table, and the bad-debt sandwich

**Repos:** `morpho-blue` (`1478e9c`, immutable singleton `0xBBBB…EEFFCb`, identical multi-chain) + `metamorpho`
(`163eb2a`, **v1.0** — no `lostAssets`). A full read of `Morpho.sol` produced an 8-row rounding table proving **every
core conversion favors the protocol**: the "give shares" direction rounds down, the "take/owe" direction rounds up,
the health check counts debt high + collateral low.

- **Interest** adds equally to `totalBorrowAssets` and `totalSupplyAssets` (conserving borrower-owes==supplier-earns);
  `elapsed==0` early-returns (no double-accrual); a malicious IRM can only *brick its own market* (overflow reverts,
  state is per-`Id`, no cross-market contamination), and there is no rate cap in core — by-design, isolated.
- **Bad-debt write-down** (collateral==0 after seizure) zeroes the residual borrow shares and subtracts equally from
  *both* totals — the loss socialized atomically, keeping the invariant.
- **Callbacks** have no global guard by design; safety is **state-before-callback-before-transfer**, closed by a
  mandatory post-callback `transferFrom`. `flashLoan` touches no market accounting and withdraw/borrow gate on
  `totalBorrowAssets ≤ totalSupplyAssets` (not raw balance), so flash liquidity can't be double-counted.
- **MetaMorpho v1.0** — every ERC4626 direction favors the vault; `totalAssets` reads *Morpho supply-share value*
  (not raw balance) so a direct donation can't inflate the price; `reallocate` asserts `withdrawn == supplied`
  (pure reshuffle). The one real risk, traced and resolved to **not a bug**: a Morpho-market bad-debt realization
  drops the vault share price atomically, so a foreknowledgeable actor could redeem-before/deposit-after — but the
  loss is **conserved (a redistribution, not a leak)**, withdrawals are liquidity-bounded, and it's the documented
  "bad debt socialized to current LPs" behavior that motivated v1.1's `lostAssets` smoothing.

**No live finding.** Honestly named: no IRM rate cap (isolated brick), v1.0 has no bad-debt smoothing, 18-decimal
first-depositor residual (documented, deployer-seeded).

---

## 2. Ethena — the V2 live EIP-1271 + delegated-signer delta (got the right source)

**Source:** the **live deployed V2**, `EthenaMinting` "Mint and Redeem V2" at **`0xe3490297…`** + `StakedUSDeV2` at
`0x9D39A5DE…`. *(A first pass mistakenly read the Code4rena Oct-2023 snapshot, which lacks the live EIP-1271 path;
the corrected pass confirmed the live source contains `SignatureType.EIP1271` + the two-step delegated signer, and
corrected the address — the V1 contract `0x2CC4…` has no 1271 path.)* The hunt weighted to the **live-only delta**.

- **EIP-1271 path (highest) — safe.** When the signer is a contract, `verifyOrder` calls
  `IERC1271(order.benefactor).isValidSignature(...)` — the 1271 target is **the benefactor itself, not an
  attacker-supplied address** — and the decisive gate is `_whitelistedBenefactors.contains(order.benefactor)`
  (admin-only). A malicious contract can't be a benefactor unless admin-whitelisted, so "a contract that returns the
  magic value for everything" buys nothing. The magic value is checked by exact equality (`0x1626ba7e`).
- **Delegated-signer — safe (genuine two-sided handshake).** The live model (upgraded from the 2023 one-step) keys
  `delegatedSigner[delegate][benefactor]`: the benefactor sets `PENDING` for itself, the delegate must
  `confirmDelegatedSigner` to reach `ACCEPTED`, and `verifyOrder` checks that exact key. **No forced delegation** (you
  can only write rows where you are the benefactor), and a removed delegate flips to `REJECTED` immediately.
- **Order / nonce / limits — safe and stronger than 2023.** EIP-712 binds all fields + chainId + contract;
  order_type prevents mint↔redeem cross-use; the nonce bitmap blocks replay; limits are now **dual** (global +
  per-asset block caps) plus a stables-delta bps bound.
- **sUSDe — safe.** 8h linear vesting subtracted from `totalAssets` (blocks reward-front-running), `MIN_SHARES = 1e18`
  inflation defense on both legs, the cooldown silo isolates pending withdrawals and is vault-gated.

**No live finding.** Two cosmetic, non-exploitable, pre-existing discrepancies named: the 64-bit nonce truncation
(reduced but astronomically-large nonce space, no replay impact) and the swapped `uint128/uint120` widths in the
`ORDER_TYPE` type-string (no hash mismatch under `abi.encode` 32-byte padding). The off-chain delta-hedging custody is
the inherent, out-of-scope trust boundary — not a contract bug. *Provenance caveat: source read from an Etherscan
mirror (direct fetch sandbox-blocked); re-pull from Etherscan for byte-exact assurance before acting.*

---

## 3. Pendle — the PT+YT==SY conservation through the full lifecycle

**Repo:** `pendle-core-v2-public` (`fdcfe39`), **PT/YT v6 + Market V7** (matching the in-repo audit reports). The core
conservation holds exactly end-to-end.

- **Mint/redeem — clean.** `_mintPY` mints the *same* amount to PT and YT (so `totalPT == totalYT` always pre-expiry,
  PT mint/burn strictly gated to the YT contract); `syToAsset`/`assetToSy` both round **down**, so a mint→redeem
  round-trip can never return more SY than deposited.
- **Interest index — clean.** `index = max(SY.exchangeRate(), stored)` is a monotonically non-decreasing ratchet;
  per-user index advances on each settlement (no double-claim) and fresh YT minters get their index set at mint (can't
  claim pre-mint interest).
- **Rewards — clean.** Settled in `_beforeTokenTransfer` using *old* balances *before* `_balances` mutate — closing
  the deposit/transfer-timing reward-capture vector; the gauge `lastBalance` tracking prevents re-count.
- **AMM (Market V7) — clean.** The exchange rate is floored at `IONE` (≥1) at every computation site, proportion
  capped at 96%, fees round toward the protocol, and `rateScalar` grows toward expiry keeping the curve well-defined.
- **Post-expiry — clean.** PT redeems for exactly its underlying (never >1:1), the yield delta swept to treasury, YT
  interest frozen at `firstPYIndex` — no double-claim across the boundary.

**No live finding.** The `SY.exchangeRate()` trust is correctly characterized as **per-market isolated** (each
PT/YT/Market bound to one immutable SY, no cross-market contamination, no read-only-reentrancy on the index path) — a
documented design assumption, not a bug.

---

## 4. GMX v2 — round-against-the-trader, backstopped by a per-tx solvency invariant

**Repo:** `gmx-synthetics` (`919da19`). *(The pre-existing `/tmp/gmx` was the unrelated v1 repo; re-cloned the correct
synthetics repo.)* A full open→fund→impact→close→ADL lifecycle read confirmed the round-against-the-trader invariant.

- **PnL** prices at the trader's *least* favorable side (long `min`, short `max`); `sizeDeltaInTokens` and the
  collateral-cost path all round against the trader; the fee/cost ordering pays positive PnL at the *minimized* price.
- **GM token pricing** rounds against the user on *both* legs (deposit `maximize=true` → fewer GM; withdraw
  `maximize=false` → fewer tokens), and the two-step keeper execution prices each leg with **its own block's oracle**,
  defeating the single-price deposit→withdraw sandwich.
- **Price impact** — positive impact at increase is **not paid out**; it's stored as `pendingImpactAmount` and only
  realized (capped by the impact pool + a config-bounded lendable amount) at decrease — **structurally killing the
  open+close harvest**.
- **Funding** charges payers rounding up, credits claimants rounding down → total charged ≥ total claimable, dust to
  the pool; funding is settled on every position update (can't be dodged).
- **Oracle timing** — `minOracleTimestamp >= order.updatedAtTime` closes the stale-price frontrun; limit/stop use
  `max(orderUpdatedAt, positionIncreasedAt)`; ADL is keeper-gated and executes at the disadvantaged price.
- **The backstop (the elegant part):** `validateMarketTokenBalance` runs after *every* execution and asserts the real
  ERC20 balance ≥ Σ(pool + swap-impact + claimable collateral/fees/ui/affiliate), ≥ collateral sum, ≥ claimable
  funding — so **any rounding drift reverts the whole transaction**, converting per-step "round against the user"
  choices into a hard enforced solvency invariant.

**No live finding.**

---

## Synthesis — what the depth pass showed

1. **Large-cap DeFi shares one safety architecture: round-against-the-actor + a conservation backstop.** Morpho's
   per-path rounding table under `totalBorrow ≤ totalSupply`; Pendle's mint/redeem-rounds-down under `PT+YT==SY`;
   GMX's every-leg-against-the-trader under the per-tx `validateMarketTokenBalance`. The deep read's job was confirming
   the *whole lifecycle* is consistent with that architecture — not one path, all of them.
2. **The residual risk is redistribution, characterized not flagged.** Morpho's bad-debt sandwich is a *conserved
   redistribution* among LPs (the v1.1 `lostAssets` motivation), not an extractable leak — exactly the defect-vs-design
   discipline, applied to a subtle MEV-shaped edge.
3. **Getting the live source is half the hunt.** The Ethena pass only became real when it found the **V2** deployed
   contract with the EIP-1271 delta — the 2023 contest snapshot would have produced a confidently-clean verdict on
   code that isn't running. (It also corrected the analyst's own address.) Deployed==audited, enforced.
4. **The depth pays where the bug would hide.** Each hunt drove to the protocol's *newest/subtlest* mechanism — Ethena's
   1271+delegation, Morpho's bad-debt propagation, Pendle's index ratchet, GMX's stored-pending-impact — because that
   is where a live bug in a heavily-audited large-cap actually lives, not in the well-trodden core.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
