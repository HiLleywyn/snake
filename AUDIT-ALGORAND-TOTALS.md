# Algorand (ALGO) — account-model money-conservation audit (clean)

**Target:** `algorand/go-algorand`, cloned `/tmp/algo` (shallow, HEAD current). Top-100 L1.
Audited the **value-conservation core of the account ledger** — the `Move` transfer primitive
(`ledger/eval/eval.go:567`), the per-block global conservation invariant `CalculateTotals`
(`ledger/eval/cow.go:373`), and the `MinBalance` floor (`eval.go:1142`). **Posture:** defensive;
no exploit, no PoC. **Result: clean — no finding, nothing to disclose.**

Chosen as a standout because it is an **account model with an explicit, first-class per-block
conservation invariant** — the same "conservation as a checked invariant" design verified for XRPL
(`AUDIT-XRPL-INVARIANTS.md`), Stellar (`AUDIT-STELLAR-INVARIANTS.md`), Cardano POV
(`AUDIT-CARDANO-POV.md`), Berachain BGT (`AUDIT-BERACHAIN-POL.md`), Osmosis
(`AUDIT-OSMOSIS-SUPERFLUID-RECON.md`) and Aptos Move-Prover specs. Connection-driven: I already
mapped that family on UTXO and EVM chains; Algorand tests whether the invariant re-derives on a
*non-EVM account L1* in a *fourth* language stance (Go, distinct from the Avalanche Go I just read).

## The transfer primitive — `Move`, overflow/underflow-checked, exact 1:1 (Bucket 1 + Bucket 5)
`Move(from, to, amt, ...)` (`eval.go:567-633`) is the single Algo-transfer primitive:
- **Debit:** `fromBalNew.MicroAlgos, overflowed = basics.OSubA(fromBalNew.MicroAlgos, amt)` (`:588`);
  on underflow → `&ledgercore.OverspendError{...}` (`:590-595`). You cannot spend more than you hold.
- **Credit:** `toBalNew.MicroAlgos, overflowed = basics.OAddA(toBalNew.MicroAlgos, amt)` (`:621`);
  on overflow → error (`:622-624`).
- Both legs move **the same `amt`**, so a `Move` is exactly conservative (rewards are tracked
  separately and funded by the rewards pool, see below). `OSubA`/`OAddA` (`data/basics/overflow.go:131,137`)
  are the overflow-returning variants — not raw `+`/`−` — so a balance can never wrap. **enforced.**

## The global invariant — per-block "sum of money changed" rejection (the strong positive)
`CalculateTotals` (`cow.go:373-401`) runs on the top-level state delta each block. It starts from
`prevTotals`, applies the round's rewards level, then for **every** modified account subtracts the
previous balance and adds the new one:
```
totals.DelAccount(proto.RewardUnit, previousAccountData, &ot)
totals.AddAccount(proto.RewardUnit, updatedAccountData, &ot)
...
if ot.Overflowed { return error("overflowed totals") }          // :392-394
if totals.All() != cb.prevTotals.All() {
    return error("sum of money changed from %d to %d")          // :395-397
}
```
So **if a block's transactions net-create or net-destroy any Algos, the block is rejected.** This is
a *recomputed* invariant (it doesn't trust the per-tx bookkeeping — it re-sums and compares to the
prior total), which is exactly the epistemic-hygiene discipline I hold for myself, implemented in the
protocol. `AccountTotals` arithmetic uses the same `OverflowTracker` (`totals.go:37-93`), and `All()`
panics on overflow (`totals.go:107-109`) rather than silently wrapping — halt-over-divergence, the
correct failure philosophy (the discipline MemeCore lacked, `AUDIT-MEMECORE-POSA.md`). **enforced.**

## The MinBalance floor (anti-dust / state-rent, not a conservation hole)
`checkMinBalance` (`eval.go:1142-1183`) rejects any tx that leaves an affected account below its
`effectiveMinBalance` (`MinBalanceError`, `:1168-1172`), and caps the requirement at
`MaximumMinimumBalance` (`:1179-1180`). FeeSink/RewardsPool/StateProofSender are exempt (`:1149`).
This is a state-growth bound (each asset/app opt-in raises the floor), orthogonal to conservation but
worth noting: it's the Bucket-5 bound that keeps account state from being created for free.

## Rewards — money-neutral at the totals level (read, with an honest residual)
Algorand pays participation rewards from the **RewardsPool** account: the pool drains
(`poolNew.MicroAlgos = ot.SubA(poolOld.MicroAlgos, rewardsPerUnit * RewardUnits)`, `eval.go:840`) as
the rewards level rises, and `Move`/`WithUpdatedRewards` credit accrued rewards to reward-unit
holders. Because the invariant check (`totals.All() == prevTotals.All()`) holds *after*
`ApplyRewards`, rewards minted to accounts must be exactly offset by the pool's decrease — i.e. the
rewards mechanism is conservative by construction, not new issuance. **Residual (honest gap):** I
read the pool-drain and the totals check at the structural level and confirmed the equality gate, but
did **not** line-by-line prove the rewards-level rounding offsets the pool to the last microAlgo
across all edge cases (truncation in `rewardsPerUnit`). The invariant *gate* would catch any net
mismatch by rejecting the block, so this is a residual on the *mechanism*, not an unchecked path.

## Connections to the corpus
| Chain | Conservation invariant | Form |
|---|---|---|
| **Algorand** | `totals.All() != prevTotals.All()` → reject block (`cow.go:395`) | recomputed per-block money sum |
| XRPL | `XRPNotCreated`: Δdrops `== −fee` exactly | per-tx invariant check |
| Stellar | `ConservationOfLumens`: Δcoins `== payouts + ΔfeePool` | per-ledger invariant |
| Cardano | `consumed == produced` (`MaryValue`) | per-tx UTXO equation |
| Berachain | revert if `balance < totalSupply()` (BGT) | per-call modifier |
| Avalanche | `produced ≤ consumed` per asset (`FlowChecker`) | per-tx UTXO inequality |
Algorand's variant is distinctive in that it's a **whole-ledger re-sum** (not per-tx): it recomputes
the global total from the account deltas and compares to the previous total, catching *any* leak
regardless of which tx caused it. Strongest "recompute, don't trust" stance in the family.

## What this audit did NOT cover (coverage honesty)
- **ASA (Algorand Standard Asset) conservation** — non-Algo assets have a fixed total at creation and
  transfer via the asset-holding path; a separate conservation surface (analogous to Avalanche's
  multi-asset / Cardano's multiasset), not opened here.
- **The AVM (TEAL) + inner transactions** (`data/transactions/logic/eval.go`) — app-call execution
  and inner-txn issuance; the deepest Algorand-specific surface (an inner txn still routes through
  `Move`/asset transfer, so it's bounded by the same primitives, but the opcode-level budget/recursion
  bounds are not opened).
- **State Proofs / consensus (Algorand BA⋆)** — the agreement layer (cf.
  `AUDIT-MONADBFT-CONSENSUS.md`), orthogonal to this validity floor.
- The precise rewards-level rounding offset (the residual noted above).

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read the `Move` debit/credit to confirm both legs are the
  overflow-checked `O*A` variants moving the same `amt`, and I read `CalculateTotals` to confirm the
  comparison is `!=` against `prevTotals.All()` (a true equality gate), not a logged-and-ignored
  warning. The `All()` overflow path panics rather than wrapping — confirmed at `totals.go:107`.
- **Exposure to reversal.** This verdict flips if: (a) some balance write bypassed both `Move` and
  the account-delta tracking that feeds `CalculateTotals` (I did not exhaustively enumerate every
  `putAccount` caller); or (b) the rewards rounding could net-mint within a single block without
  tripping the `totals.All()` gate (I argued the gate catches it, but did not prove the rounding
  identity). Both stated as bounded reads.

## Verdict
**Clean, strong positive.** Algorand conserves value through an overflow/underflow-checked `Move`
primitive (exact 1:1, `OverspendError` on underflow) and enforces a **per-block, recomputed global
money-conservation invariant** that rejects any block whose total Algos changed — a member of the
checked-invariant family and arguably its most "recompute-don't-trust" instance. No
untrusted-input→value path found, nothing to disclose. The next pulls are ASA/AVM inner-txn
conservation and the rewards-rounding identity (the stated residual).
