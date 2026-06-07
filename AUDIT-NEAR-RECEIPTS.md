# NEAR — async cross-shard receipt value conservation (refund-on-failure) — clean

**Target:** `near/nearcore`, cloned `/tmp/near`, HEAD `01b95d0`. Top-100 sharded L1 (Rust). Audited
the runtime's async value flow: receipts carry attached deposits across shards; failure refunds them.
**Posture:** defensive; no exploit. **Result: clean — no finding.** Connections + self-check applied.

## Async value conservation via refund receipts (verified) — the TON-bounce analog
Like TON, NEAR moves value **asynchronously**: a transaction spawns *receipts* that execute on the
receiver's shard, and a function call/transfer can attach a *deposit*. `refund_unspent_gas_and_deposits`
(`runtime/runtime/src/lib.rs:1047`):
```
deposit_refund = if result.result.is_err() { total_deposit } else { Balance::ZERO }   (:1063)
gas_balance_refund = gas_price * net_gas_refund                                        (:1086)
refund_penalty     = gas_price * refund_penalty                                        (:1091)
if deposit_refund > 0 → emit refund receipt (→ predecessor)                            (:1108-1111)
```
So **on a failed receipt the entire attached deposit is refunded** to the sender via a refund receipt,
and unspent gas is refunded minus a penalty (the penalty + burnt gas + price surplus + tokens_burnt
go to `tx_burnt_amount`, `:874-879`). Value is conserved across the async receipt lifecycle: an
attached deposit is either consumed by a successful action or returned; gas is consumed or
refunded-minus-penalty. **enforced — async value-in-flight conserved by deterministic on-chain
refund.**

## Connection — the second member of the async-refund family (with TON)
NEAR's **refund receipt** ≡ TON's **bounce message** (`AUDIT-TON-BOUNCE.md`): both async, sharded
actor models conserve in-flight value by *deterministically returning it on failure, on-chain* —
a **reduced 6a** (protocol-closed), NOT a cross-chain bridge's irreducible off-chain 6b. With NEAR
added, the §11 rung **"async-actor value conservation = deterministic on-chain refund"** has two
independent implementations (TON bounce, NEAR refund receipt), confirming it as the general pattern
for sharded/async chains. The fee model differs (NEAR keeps a refund *penalty*; TON deducts
*forward fees*) but the conservation shape is identical: `in = consumed + fees(burnt) + refunded`.

## Self-check / coverage honesty (epistemic hygiene)
- **Did NOT claim the "global checked-invariant" connection.** Older nearcore had a named
  `check_balance` → `BalanceMismatchError` total-conservation check (`balance_checker.rs`). In *this*
  revision I located the per-chunk burnt-balance accounting (`stats.balance.tx_burnt_amount`,
  `lib.rs:874-913`) but **did not find a named global `check_balance` invariant** — likely refactored
  or relocated. I am *not* asserting NEAR is/ isn't in the checked-invariant family (XRPL/Cardano/
  Berachain) because I could not verify it here. Honest gap, not a claim.
- Did not cover: the **chunk apply()** end-to-end balance reconciliation, cross-shard receipt
  *delivery* guarantees (exactly-once across resharding — the deeper analog of TON's open question),
  gas metering, and Nightshade consensus.

## Verdict
**Clean** (for what was read). NEAR conserves async cross-shard value via refund receipts: a failed
receipt's attached deposit is fully returned and unspent gas refunded minus a penalty — the TON-bounce
pattern, making it the second confirmed member of the deterministic-on-chain-refund family. The global
total-balance invariant (historically `check_balance`) was not located in this revision and is the
stated coverage gap. No finding; nothing routed.
