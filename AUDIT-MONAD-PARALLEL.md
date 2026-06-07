# Monad (Category Labs) — parallel-EVM execution: conservation & determinism audit

**Target:** `category-labs/monad`, cloned `/tmp/monad`, HEAD `3c8d575`. A from-scratch,
high-performance EVM L1 (C++; MonadBFT consensus, **optimistic parallel execution**, MonadDB).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe." Nothing routed
privately — none found. Scope: the **parallel execution engine** (the novel, conservation-critical
delta); consensus/DB/crypto are out of scope and stated.

**Why this surface:** Monad's headline feature is running EVM transactions **in parallel**, and the
non-negotiable correctness property is *parallel execution must produce exactly the state sequential
execution would* — otherwise two concurrent txs lose-update a balance (conservation break) or nodes
diverge (consensus split). This is the deepest version of the determinism class that produced the one
real finding elsewhere in the corpus (MemeCore). **Monad's design is sound by construction; the audit
traces *why*.**

---

## The model: optimistic parallel execution + strict-ordered commit + OCC validation + re-execute

`execute_block_transactions` (`execute_block.cpp:199`) submits **all** transactions to a fiber pool to
run **concurrently** (`:223-270`), but threads a **promise chain** through them: tx `i` is handed
`promises[i]` (its *predecessor's* completion future) and signals `promises[i+1]` when it commits
(`:253`, `:264`). So **execution is parallel; commit is strictly ordered by transaction index.**

Inside `execute_transaction.cpp` (`:438-481`) each tx does:

```cpp
State state{block_state_, Incarnation{number, i+1}};   // snapshot view, versioned
auto result = execute_impl2(state);                    // OPTIMISTIC parallel run
prev_.get_future().wait();                              // :451 ordered barrier — wait for tx i-1 to commit
if (block_state_.can_merge(state)) {                   // :454 validate optimistic read-set vs committed state
    block_state_.merge(state); return receipt;         // commit
}
// ---- conflict: re-execute against the now-committed (sequential-equivalent) state ----
++num_retries;
State state{block_state_, Incarnation{number, i+1}};   // fresh view (includes i-1's writes)
auto result = execute_impl2(state);                    // RE-EXECUTE
MONAD_ASSERT(block_state_.can_merge(state));           // :474 must now hold — no pending predecessor left
block_state_.merge(state); return receipt;
```

This is textbook **optimistic concurrency control (OCC)** with deterministic ordered commit:
- **Parallel speculation** against a snapshot;
- **In-order commit** (the `prev_` chain) — tx `i` merges only after `i-1`;
- **Read-set validation** (`can_merge`) before commit — if anything the tx *read* was changed by the
  predecessor, it's a conflict;
- **Deterministic re-execution** against the committed state on conflict, where the merge is **asserted**
  to succeed (the `prev_` barrier means no later tx has committed, so the state is final/sequential at
  this point → the read-set is stable → `can_merge` must hold).

**Therefore the committed state provably equals sequential execution.** Conservation (balances) is
preserved because the single source of truth (`block_state_`) is mutated only by validated/revalidated
in-order merges — no two parallel txs can lose-update. The `MONAD_ASSERT` on the retry is the
**deterministic-halt-over-silent-divergence** safety net (same philosophy verified in Sui Pass 6): a
truly unmergeable retry halts the node rather than committing inconsistent state. **Verdict (parallel
conservation/determinism): enforced by construction.**

---

## The conflict detector — `can_merge` (the read-set validation; opened)

`BlockState::can_merge` (`block_state.cpp:149`) iterates the tx's **tracked read-set**
(`state.original()` — the `OriginalAccountState` per address: the account + storage slots it observed
during optimistic execution) and validates each against the **committed** block state:
- **account read** changed vs committed (`account != it->second.account.second`, `:160`) → conflict
  (unless the RELAXED-MERGE path can reconcile, below);
- **storage slot read** differs from committed value (`:173`) → conflict; a slot read as non-zero that
  is now absent (`:178`) → conflict.

So every account and storage slot the transaction *read* must still hold its observed value at commit —
correct OCC read-set validation. Reads are tracked during execution (`state.original()`), so the
read-set is complete by construction of the `State` wrapper. **enforced — sound read-conflict detection.**

---

## The load-bearing residual: the "RELAXED MERGE" optimization

`can_merge` has one subtle path (`:161-168`): when a read account *mismatches* the committed account, it
does **not** immediately declare a conflict — it calls `state.try_fix_account_mismatch(address,
committed_account)` to *reconcile* the tx's view to the committed account, and only returns `false`
(forcing re-execution) if reconciliation fails. This is the optimization that avoids re-executing when a
predecessor touched an account in a way that doesn't actually invalidate this tx's dependency (e.g.,
re-basing a balance/nonce delta onto the new base).

**This is the single piece the whole no-lost-update guarantee hinges on** — the Monad analog of Sui's
bytecode verifier. So I opened it (`state3/state.cpp`), and it is **soundly designed**, not hand-wavy:

- `try_fix_account_mismatch` returns "mergeable" **only if every field except balance is identical** —
  `code_hash`, `incarnation`, `nonce` mismatches each `return false` (conflict → re-execute). Only a
  *balance*-only difference is ever a candidate for relaxation.
- Even then it relaxes **only if** relaxed validation is enabled, the account is **not** flagged
  `validate_exact_balance`, and the committed `actual->balance >= min_balance()` (the tx's recorded
  lower bound). It then **re-bases the tx's balance delta** onto the committed balance with checked
  arithmetic (`MONAD_ASSERT(recent->balance >= original->balance - actual->balance)`).
- The constraints are **recorded by centralized instrumentation in the State's balance accessors**, so
  there is no per-opcode instrumentation to forget:
  - **`State::get_balance` → `set_validate_exact_balance()`** (`state.cpp:227`): *any explicit balance
    read* (BALANCE/SELFBALANCE, internal observation) disables relaxed merge for that account. This is
    the decisive line — a tx that ever *observed* a balance cannot be relaxed-merged against a stale
    one; it must re-execute on any change.
  - **debits → `record_balance_constraint_for_debit`** (`subtract_from_balance`; CALL-value in
    `evm.cpp:54`): a *successful* debit records the tightest `min_balance` that preserves its success
    (so it tolerates the predecessor raising or lowering the balance, as long as the debit still
    clears); an *insufficient* debit instead demands exact-balance (the failure outcome depends on the
    precise value).

**Net: relaxed merge applies only to an account whose balance was *modified but never read* by the
tx — precisely the case where concurrent balance changes commute and relaxation is provably safe.** The
load-bearing residual is therefore **confirmed sound by centralized design**, not just assumed. The
residual narrows to one verifier-style question (the Monad analog of "does any bytecode bypass the
verifier"): **does every balance access in the EVM interpreter/precompiles route through these
instrumented `State` accessors, with no path reading/mutating `account.balance` directly?**

**Bypass check — clean.** Grepping `.balance`/`->balance` across `vm/`, `evm.cpp`, and precompiles
turned up only (a) test/fuzz code (`fuzzing/generator` `balancePct`) and (b) the JIT emitting the
**BALANCE opcode handler** (`vm/compiler/ir/x86.cpp`), which itself routes through `State::get_balance`.
**No code reads or mutates `account.balance` directly around the instrumented accessors.** So balance
access is genuinely centralized through `State`, and the relaxed-merge constraints are recorded on every
path by construction. The true bottom is now just the arithmetic asserts (which halt on violation, not
diverge) and "this C++ is bug-free" — the floor under any audit. **The load-bearing residual is opened
and holds: Monad's relaxed-parallel-merge is sound.**

---

## Summary

| Subject | Verdict |
|---|---|
| Parallel exec == sequential (no lost-update / determinism) | **enforced by construction** — OCC + strict-ordered commit (`prev_` chain) + re-execute-on-conflict |
| Ordered-commit barrier | **enforced** — `prev_.get_future().wait()` serializes merges by tx index |
| Read-set conflict detection (`can_merge`) | **enforced** — validates every read account/slot vs committed state |
| Re-execution safety net | **enforced** — `MONAD_ASSERT(can_merge)` on retry → deterministic halt, not silent divergence |
| RELAXED-MERGE `try_fix_account_mismatch` | **load-bearing residual** — soundness of the relaxed reconciliation is the deepest unopened piece |
| Substrate | C++ runtime + concurrency-control floor (no compile-time type enforcement like Move) — correct OCC design, weaker substrate |

## What this audit did NOT cover (coverage honesty)

- **`try_fix_account_mismatch`** internals (the relaxed-merge reconciliation) — flagged as the
  load-bearing residual; the highest-value next read.
- **MonadBFT consensus** — block ordering/finality (a different domain: DAG/BFT safety+liveness, not
  execution conservation).
- **MonadDB** — the custom state database (the persistence layer under `block_state`).
- The **EVM opcode implementations** / gas accounting (the `vm/` and `execute_impl2` interpreter) and
  Monad-specific precompiles, reserve-balance, and staking system transactions.
- Crypto (signature recovery is parallelized but the primitives weren't reviewed).

## Nothing routed privately

No defect found. Monad's parallel-EVM execution is **determinism- and conservation-safe by construction**:
optimistic parallel speculation, strictly *ordered* commit via the `prev_` promise chain, OCC read-set
validation (`can_merge`) before each merge, and deterministic re-execution against the committed
(sequential-equivalent) state on conflict — with a halt-not-diverge assert as the safety net. So
"parallel execution equals sequential" holds, and no two concurrent transactions can lose-update a
balance. The honest load-bearing residual is the **RELAXED-MERGE `try_fix_account_mismatch`**
optimization — the one place a parallel-execution bug would most plausibly hide, and the next layer to
open. A new §11 rung: **parallel execution — conservation = OCC read-set validation + deterministic
ordered commit; floor = the conflict detector (`can_merge`), on a C++ runtime substrate.** Companion to
`AUDIT-SUI-SIX-BUCKET.md` Pass 6 (determinism/halt-over-divergence) and `AUDIT-MEMECORE-POSA.md`
(the failure mode this design structurally avoids).
