# Stellar (XLM) — conservation via the Invariant framework (+ the liabilities model) — clean

**Target:** `stellar/stellar-core`, cloned `/tmp/stellar`, HEAD `02fa313`. Top-100 L1 (C++); trust-line
+ on-chain DEX (the XRPL sibling). Audited the **Invariant framework** — post-operation runtime
conservation checks. **Posture:** defensive; no exploit. **Result: clean — no finding.** Connections +
self-check applied.

## XLM conservation as an exact, runtime-checked invariant
`ConservationOfLumens::checkOnOperationApply` (`src/invariant/ConservationOfLumens.cpp:91`) sums the
per-account lumen deltas (with overflow/underflow guards, `:117/122`) and enforces:
```
deltaTotalCoins = lhCurr.totalCoins - lhPrev.totalCoins      (:99)
deltaFeePool    = lhCurr.feePool   - lhPrev.feePool          (:100)
if (deltaTotalCoins != inflationPayouts + deltaFeePool) → InvariantDoesNotHold   (:137)
```
So **total XLM changes *only* by inflation payouts (now 0 — inflation disabled) plus the fee-pool
movement** — exact, re-derived after every operation, fails the operation on violation. Same tightness
class as XRPL's `XRPNotCreated` (`AUDIT-XRPL-INVARIANTS.md`).

## The liabilities model — `LiabilitiesMatchOffers` (the fresh twist)
Stellar tracks per-account/trustline **buying/selling liabilities** = the value committed to open DEX
offers. `LiabilitiesMatchOffers` enforces (`:223-231`): if an account's **balance decreased**, its
liabilities **cannot increase**, and liabilities must match the sum of its offers and stay within the
balance/reserve bounds. So **open offers can never promise more than the account actually holds** — a
first-class invariant on offer-commitment conservation (the DEX equivalent of "escrow can't exceed
balance"). Plus `OrderBookIsNotCrossed` (no matchable offers remain post-op), `SponsorshipCountIsValid`,
`AccountSubEntriesCountIsValid` — a richer invariant suite than XRPL's. **enforced.**

## Connections
- **Checked-invariant family — and a cross-confirmation.** Stellar joins XRPL / Cardano / Berachain /
  Osmosis / Aptos / marginfi. Crucially, **both trust-line DEX chains (Stellar + XRPL) independently
  converged on explicit invariant frameworks** (`ConservationOfLumens` ≈ `XRPNotCreated`) — the
  lineage that pioneered on-chain order books arrived at "conservation as a checked invariant" twice,
  independently. Strong evidence the pattern is design-fundamental for that class.
- **Offer-commitment conservation = first-class escrow invariant.** `LiabilitiesMatchOffers`
  ("committed-to-offers ≤ held") is the invariant-framework version of the escrow-conservation seen
  ad-hoc in AMMs/marketplaces (Meteora, Drift, TradePort `AUDIT-TRADEPORT-NOTE.md`): committed funds
  must be backed. Stellar makes it a checked ledger invariant rather than per-tx logic.
- **"Re-derive conservation after the operation, fail if wrong"** pattern: Stellar `checkOnOperationApply`
  ≡ XRPL `InvariantCheck` ≡ Sui expensive check ≡ Monad `MONAD_ASSERT` — post-execution re-derivation
  as defense-in-depth (`AUDIT-CONNECTIONS-AND-SELFCHECK.md`).

## What this audit did NOT cover (coverage honesty)
- The **path-payment / offer-crossing engine** (`OfferExchange`, path payments) — *how* value moves
  through offers/trust-lines; the invariants are the backstop over it, not a proof of the engine.
- **Issued-asset (non-XLM) conservation** — governed by issuers/trustlines, not `ConservationOfLumens`
  (which is XLM-only); `LiabilitiesMatchOffers` covers their offer-commitment bound.
- **Soroban** (smart contracts) and **SCP** consensus — separate surfaces.
- Whether the invariant framework runs in production by default vs test-only (the checks exist;
  their always-on enablement is a config/deployment fact, like XRPL's).

## Verdict
**Clean.** Stellar enforces XLM conservation as an exact post-operation invariant (`deltaTotalCoins ==
inflation + deltaFeePool`) and adds a first-class **liabilities** invariant ensuring open offers never
promise more than held — a richer checked-invariant suite than XRPL, on the same trust-line-DEX
lineage. Second independent trust-line chain to converge on the checked-invariant design. No finding;
nothing routed.
