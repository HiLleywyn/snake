# Sei (SEI) — parallel execution (OCC) — the 3rd member of the OCC family, sound

**Target:** `sei-protocol/sei-cosmos`, cloned `/tmp/seicosmos`. Top-100 L1's parallel-execution core
(Go; the multiversion store + scheduler used by sei-chain). **Posture:** defensive; no exploit.
**Result: clean — no finding.** Audited via the Monad/Aptos OCC template (connection-driven).

## Structurally identical to Monad & Aptos Block-STM (3rd independent OCC, 3rd language)
Sei implements optimistic concurrency control with a multiversion store, the same shape verified in
`AUDIT-MONAD-PARALLEL.md` (C++) and `AUDIT-APTOS-COIN.md` Pass 2 (Rust):
| Element | Monad | Aptos | **Sei (this)** |
|---|---|---|---|
| read-set capture | `state.original()` | `captured_reads.rs` | `SetReadset`/`GetReadset`, `txReadSets` map (`store.go:210-219`) |
| conflict detector | `can_merge` | `validate_data_reads` | `ValidateTransactionState(idx)` → `(ok, mvConflicts)` (`scheduler.go:171`), validation iterator over the MV store (`store.go:277`) w/ an `occ.Abort` channel |
| re-execute on conflict | re-exec | new incarnation | `invalidateTask` + incarnations (`scheduler.go:127`, `maxIncarnation`) |
| deterministic ordered commit | `prev_` chain | `TxnIndex` order | dependency graph (`AppendDependencies`, `dependenciesValidated`) processed in index order |
| optimization | relaxed-merge | read-kind granularity | **write estimates** (`SetEstimatedWriteset`, `store.go:179`) = Block-STM ESTIMATE markers |
It even imports a package literally named `occ` (`occtypes.Abort`). **Verdict: sound, same OCC family
— parallel result == sequential via read-set validation + re-execute + ordered commit.**

## Connection — the OCC family is now confirmed across 3 languages / 3 codebases
Monad (C++), Aptos Block-STM (Rust), Sei (Go): three *independent* implementations of the **same**
parallel-execution-conservation algorithm — optimistic execution → multiversion read-set validation →
re-execute-on-conflict at a new incarnation → deterministic ordered commit. All three sound; in all
three the **load-bearing piece is the conflict detector** (`can_merge` / `compare_data_reads` /
`ValidateTransactionState`) over the captured read-set. This is now strong evidence that OCC +
ordered-commit is *the* universal approach to "parallel execution must equal sequential," and that
its correctness reduces to the read-set conflict detector in every case
(`AUDIT-CONNECTIONS-AND-SELFCHECK.md` Connection B, now a 3-member family). The negation of this
discipline — non-deterministic ordering into committed state — is exactly the MemeCore finding
(`AUDIT-MEMECORE-POSA.md`).

## What this audit did NOT cover (coverage honesty)
- The Sei **EVM** parallel path (sei-chain's EVM module) beyond the shared sei-cosmos OCC store; the
  read-kind/estimate-soundness deep dive (the analog of Monad's relaxed-merge residual) — read at the
  structural/rule level, not exhaustively.
- The `mergeiterator`/`trackediterator` correctness and the estimate-invalidation race handling in
  depth.

## Verdict
**Clean.** Sei's OCC is the third independent, structurally-identical implementation of the
parallel-execution-conservation pattern (after Monad and Aptos), sound at the structural level:
read-set validation + re-execute + deterministic ordered commit, with write estimates as the
performance optimization. Confirms OCC+ordered-commit as the universal parallel-conservation design.
No finding; nothing routed.
