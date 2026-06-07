# Kaspa (KAS) — BlockDAG ordering-determinism audit (clean)

**Target:** `kaspanet/rusty-kaspa`, sparse clone `/tmp/kaspa` (`consensus`). Audited two things: the
**UTXO conservation floor** (`processes/transaction_validator/tx_validation_in_utxo_context.rs`) and —
the reason Kaspa is a standout — the **GHOSTDAG ordering determinism**
(`processes/ghostdag/{ordering,mergeset}.rs`) that linearizes a *parallel BlockDAG* into one canonical
order. **Posture:** defensive; no exploit, no PoC. **Result: clean — no finding, nothing to disclose.**

Chosen because Kaspa's conservation floor is ordinary UTXO (well-trodden in this corpus), but its
**consensus is a DAG, not a chain** — blocks are produced in parallel and *merged*. That makes it the
sharpest possible test of the **determinism spine** (capstone §4g): a system that *embraces*
parallelism at the block level yet must still produce a single deterministic transaction order, or
conservation is meaningless. It is the consensus-layer analog of the OCC "parallel == sequential"
result (Monad/Aptos/Sei) and the pointed positive inverse of the MemeCore finding (non-deterministic
ordering, `AUDIT-MEMECORE-POSA.md`).

## Conservation floor — standard UTXO `output ≤ input`, overflow-checked (Bucket 1)
`check_transaction_in_context` (`tx_validation_in_utxo_context.rs:47-49`):
```
let total_in  = self.check_transaction_input_amounts(tx)?;     // Σ input UTXO values (overflow-checked)
let total_out = Self::check_transaction_output_values(tx, total_in)?;
let fee = total_in - total_out;
```
and `check_transaction_output_values` (`:116-123`): `if total_in < total_out { return
SpendTooHigh(total_out, total_in) }` — **outputs can never exceed inputs**; the difference is the fee.
Input/output value ranges and sums are overflow-guarded (`:117` notes the range check done in
isolation; `tx_validation_in_isolation.rs:90,102` exist "to avoid overflows when calculating … mass").
Same conservation law as Bitcoin/Litecoin, Cardano, and Avalanche — the UTXO-equation rung of the §11
ladder. **enforced.** (Not the interesting part — the ordering is.)

## The standout — deterministic DAG linearization (Bucket 4 / the determinism spine)
In a BlockDAG, a new block has multiple parents and "merges" a set of recent blocks. For every node to
compute the *same* UTXO set (hence the same conservation outcome), they must agree on the *order* in
which those merged blocks' transactions apply. GHOSTDAG does this with a **total order**:

`SortableBlock::cmp` (`ordering.rs:38-42`):
```
self.blue_work.cmp(&other.blue_work).then_with(|| self.hash.cmp(&other.hash))
```
— order by cumulative **blue work**, ties broken by **block hash**. Because hashes are unique, this is
a *strict total order*: no two distinct blocks compare equal, so there is **never an ambiguous tie**.
`sort_blocks` (`:45-50`) applies it via `sort_by_cached_key`.

The actual linearization, `ordered_mergeset_without_selected_parent` (`mergeset.rs:43-45`):
```
self.sort_blocks(self.unordered_mergeset_without_selected_parent(selected_parent, parents))
```
The mergeset is first collected into a `BlockHashSet` (an *unordered* set, built by a BFS that uses
reachability to exclude the selected parent's past, `:9-40`) and **then deterministically sorted**.
This is the crucial design point: the result is **independent of the BFS traversal order** — whatever
order the graph walk happens to visit blocks, the output is re-sorted into the canonical (blue_work,
hash) order. So two honest nodes with the same DAG produce the *identical* ordered mergeset, hence the
identical transaction sequence, hence the identical UTXO set and conservation result. **enforced.**

## Why this is the pointed positive inverse of the MemeCore finding
The MemeCore defect was: a validator list built from a **Go map without sorting**, fed into a
state-changing call — non-deterministic iteration order risking a consensus split. Kaspa does the
*opposite* on a far harder problem: it takes an inherently parallel, unordered structure (a set of
DAG blocks) and **forces a canonical total order with an explicit unique-hash tiebreak** before any
state depends on it. Where MemeCore let map order leak into consensus, Kaspa *re-sorts a set* precisely
so traversal order cannot leak. It is the determinism discipline done right, at the layer where Kaspa
is most exposed to it. The unique-hash tiebreak is the detail that makes the order *total* (the same
role as Avalanche's sorted-unique inputs and MonadBFT's monotonic per-round vote).

## Connections to the corpus — the determinism spine, now 2 layers wide
| Layer | "parallel == sequential" mechanism | Examples |
|---|---|---|
| **Execution** | OCC: read-set capture → conflict validation → **ordered commit** | Monad, Aptos Block-STM, Sei |
| **Consensus / block order** | **DAG linearization** by total order (blue_work, hash) | **Kaspa GHOSTDAG** |
Both make a parallel process yield a single deterministic result; both bottom out on a *canonical
order* (commit in txn-index order; sort by blue_work+hash). Kaspa extends §4g from "parallel execution
over a linear chain" to "parallel *block production* itself," the most parallel point in the corpus —
and it still enforces determinism, confirming the spine: **a chain that can't agree on order can't
agree on balances.**

## What this audit did NOT cover (coverage honesty)
- **GHOSTDAG `protocol.rs`** — the blue/red classification (k-cluster coloring, the anticone/k
  parameter) that *assigns* blue_work; I verified the *ordering* is deterministic given blue_work, not
  the security of the coloring against a high-hashrate attacker (the GHOSTDAG security argument).
- **Reachability service** (`is_dag_ancestor_of`) — the interval/tree structure backing the past-set
  queries; read at interface.
- **Script execution / signature validation** and the **virtual processor** that applies the ordered
  chain to the UTXO set — the conservation *application*, read only at the value-sum level here.
- **Mass/fee-rate and the DAA (difficulty)** — economic/rate surfaces, not opened.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I confirmed the comparator is `blue_work` then `hash` (a strict
  total order via unique hashes, not a partial order with possible ties), and confirmed the mergeset is
  collected into an *unordered set* and *then* sorted — i.e. the determinism comes from the re-sort, not
  from a (fragile) assumption that the BFS is deterministic. I confirmed the UTXO floor is
  `total_in < total_out → SpendTooHigh` (outputs ≤ inputs), not the reverse.
- **Exposure to reversal.** The ordering-determinism verdict rests on `blue_work` itself being computed
  deterministically and identically across nodes (set in `protocol.rs`, which I did not fully open) —
  if two nodes could assign different blue_work to the same block, the order would diverge despite the
  correct comparator. I verified the *sort* is deterministic; the *inputs to the sort* being
  deterministic is assumed at the protocol layer (stated as a bounded read). The conservation verdict
  assumes the virtual processor applies exactly this order to the UTXO set (not re-verified here).

## Verdict
**Clean.** Kaspa's value conservation is the standard UTXO floor (`output ≤ input`, overflow-checked),
and — the reason it matters — its BlockDAG is linearized into a **canonical total order** (blue_work,
unique-hash tiebreak) by re-sorting the unordered mergeset, so parallel block production still yields
one deterministic transaction sequence and one agreed UTXO set. It extends the determinism spine to the
most parallel layer in the corpus and is the precise positive inverse of the MemeCore ordering defect.
No untrusted-input→value path found; nothing to disclose. Named residual: the GHOSTDAG blue/red
coloring that feeds blue_work (security of the ordering's *inputs*, not the ordering itself). Next
pulls: `protocol.rs` k-cluster coloring and the virtual-processor UTXO application.
