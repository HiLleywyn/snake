# TON (Toncoin) — async value conservation (the bounce mechanism) — clean

**Target:** `ton-blockchain/ton`, cloned `/tmp/ton`, HEAD `8e6f091`. Top-100 L1; async sharded
actor model (the hardest cross-boundary value-conservation shape in the corpus). Audited the
transaction executor's value flow + the **bounce** mechanism (`crypto/block/transaction.cpp`).
**Posture:** defensive; no exploit. **Result: clean — no finding.** Self-check + connections applied
per the standing discipline.

## Why TON is a distinct conservation problem
In TON, value moves **asynchronously** between contracts/shards as message value. When a message
fails (compute/action error) and is *bounceable*, its value must be returned to the sender via a
**bounce message** — so value is genuinely *in flight*, and conservation must hold across the async
gap (no double-spend, no loss, correct fee deduction, correct refund-on-failure).

## The bounce conservation (verified, `prepare_bounce_phase`, transaction.cpp:3334)
```
msg_balance = msg_balance_remaining − compute.gas_fees − action.action_fine   (:3413–3418)
if msg_balance.grams < 0  ||  msg_balance < fwd_fee:  bp.nofunds = true; return  (:3420–3425)
balance -= msg_balance;  FAIL_UNLESS(balance.is_valid())                        (:3427–3428)
msg_balance -= fwd_fees;  fwd_fees_collected → total_fees                       (:3430–3433)
→ serialize bounce msg (bounced=true, src/dest swapped) with value = msg_balance (:3442)
```
So **`in_value = gas_fees + action_fines + fwd_fees (→ validators) + bounced_value (→ sender)`** —
exactly conserved. Three guards make it safe: (1) **negative guard** — can't bounce a `< 0` value
(it's just consumed by fees, `nofunds`, no bounce emitted); (2) **`balance.is_valid()`** after the
debit — the account cannot go negative (no underflow/forge); (3) the receiving account is **debited
by `msg_balance`** so it keeps *none* of the bounced value. Value is neither created nor lost across
the failure. **enforced.**

## Connection (and why it's a *reduced* seam, not an irreducible one)
This is value crossing a boundary asynchronously — structurally like a bridge / rollup **6b** seam
(`AUDIT-BASE-SIX-BUCKET.md`, `AUDIT-BRIDGES-SIX-BUCKET.md`). But TON's is **reduced to a
protocol-closed 6a**: the async gap is reconciled *deterministically on-chain* by the bounce protocol,
not by an off-chain attester/oracle. So unlike a cross-chain bridge (irreducible off-chain 6b), TON's
async value-in-flight is conserved by the chain itself. New §11 rung: **async-actor value
conservation = deterministic on-chain bounce/refund** (the value is always accounted to sender, fees,
or the failed-and-consumed case). The guard-over-silent-loss philosophy (negative-guard +
`is_valid()`) is the same one verified in Sui/Monad/MonadBFT (`AUDIT-CONNECTIONS-AND-SELFCHECK.md`
Part 2A) — here applied to refunds.

## What this audit did NOT cover (coverage honesty)
- The **full phase sequence** balance accounting end-to-end (storage→credit→compute→action) — read
  the bounce/credit value points, not every phase's arithmetic.
- **Inter-shard message delivery exactly-once** — the deeper TON-specific conservation: an out-msg's
  value must be delivered to the destination shard **exactly once**, surviving shard split/merge (the
  outbound message queues + hypercube routing in the collator/validator). This is the hardest TON
  property and a separate surface (not the per-tx executor); the real next pull.
- The TVM gas metering and the masterchain/config.

## Verdict
**Clean.** TON's async value conservation (the bounce) correctly returns failed-message value to the
sender minus incurred fees, with negative-guards and balance-validity preventing forge/underflow;
value is conserved across the async failure. The deeper inter-shard *delivery-exactly-once* property
(message queues across shard reshaping) is the next target. No finding; nothing routed.
