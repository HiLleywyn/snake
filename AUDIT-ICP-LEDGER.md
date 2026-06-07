# Internet Computer (ICP) — ledger conservation audit (clean)

**Target:** `dfinity/ic`, sparse clone `/tmp/ic` (`rs/ledger_suite`). Audited the **token-ledger
conservation core** — `Balances` (`ledger_suite/common/ledger_core/src/balances.rs`), the generic
primitive under both the ICP ledger and the ICRC-1/2 ledgers, plus the `apply_transaction` dedup
wrapper (`ledger_canister_core/src/ledger.rs`). **Posture:** defensive; no exploit, no PoC. **Result:
clean — no finding, nothing to disclose.**

Chosen as the most genuinely *alien* model left in the queue (chain-key crypto, cycles, canisters).
The cleanly-auditable conservation floor is the token ledger, and it turns out to use a conservation
mechanism **not yet seen in the corpus**: a **complement-pool** where `total_supply` is *derived, not
stored*. Connection-driven placement against the by-construction family (Cosmos `x/bank`, Substrate
`Imbalance`).

## Conservation floor — the complement-pool ("un-minted potential") trick (Bucket 1 + 5)
`Balances` holds the account `store` and a single scalar `token_pool`, initialized to
`Tokens::max_value()` (`balances.rs:85`,`:98`). Crucially, **total supply is not a stored field** — it
is computed:
```
total_supply() = Tokens::max_value() - token_pool          // :212-217
```
`token_pool` is the *un-minted potential*. Every value operation is a **conservative move between the
pool and accounts**, so the invariant `token_pool + Σ account_balances == max_value` holds by
construction:
- **`mint(to, amt)`** (`:145-156`): `token_pool -= amt` (`checked_sub`, panics "total token supply
  exceeded" if it would go negative — you cannot mint past `max_value`), then `credit(to, amt)`. Pool
  ↓, accounts ↑ — supply ↑ by `amt`.
- **`burn(from, amt)`** (`:132-143`): `debit(from, amt)`, then `token_pool += amt`. Accounts ↓, pool ↑
  — supply ↓.
- **`transfer(from, to, amt, fee, fee_collector)`** (`:102-130`): `debit(from, amt+fee)`,
  `credit(to, amt)`, and the fee either goes to a `fee_collector` (`credit`) **or back to
  `token_pool`** (i.e. *burned*, supply ↓ by `fee`). Either branch is conservative.
Walk any op and `token_pool + Σ balances` is unchanged. This is conceptually a **closed double-entry
system with the pool as the mint/burn counterparty account** — tokens are never created or destroyed in
absolute terms (`max_value` is fixed); they only move in or out of circulation. A distinct, elegant
variant of conserve-by-construction: where Cosmos stores `TotalSupply` and matches it to mint/burn, and
Substrate books deltas to `TotalIssuance` on `Drop`, ICP makes supply a *derived complement* so it
**cannot drift from the books** — there is no separately-stored number to disagree. **enforced.**

## Arithmetic & failure philosophy — checked everywhere; panics trap-and-roll-back (correct)
- `Tokens: TokensType` requires `CheckedAdd`/`CheckedSub` (`tokens.rs:18-47,74`) — no raw `+`/`-`.
- **User-facing** under/overflow is returned gracefully: `debit` checks `balance < amount` →
  `BalanceError::InsufficientFunds` (`:174-176`); `transfer`'s `amount.checked_add(&fee)` overflow →
  `InsufficientFunds` (`:110-114`).
- **"Cannot-happen-unless-bug"** paths use `.expect(...)` panics: `credit` overflow
  ("bug: overflow in credit", `:198`), `mint` past supply ("total token supply exceeded", `:153`),
  fee-to-pool overflow (`:125`). On the IC, a canister **trap (panic) rolls back all state changes from
  the current message** — so a conservation-violating op aborts atomically and reverts, never leaving
  partial/broken books. This is the halt-over-corruption discipline verified positively in
  Sui/MonadBFT and absent in the MemeCore finding (`AUDIT-MEMECORE-POSA.md`). **enforced.**

## Replay / dedup — separate layer, correct (Bucket 5)
`apply_transaction` (`ledger.rs:214`) wraps the balance ops with deduplication keyed on
`created_at_time + tx_hash`: rejects `TxTooOld` if `created_at_time + transaction_window < now`
(`:239-240`), rejects `TxDuplicate` if the same tx hash is already recorded (`:250`), bounds future
drift by `PERMITTED_DRIFT` (`:245`), and throttles under load (`:227`,`:341`). So a signed transfer
can't be replayed within or beyond the window. This is the IC analog of the nonce/sequence and the
domain-separated `usedMessages` guards seen across the settlement-seam audits (Hyperliquid, IBC). I
verified it exists and gates the conserved ops; I did **not** open the block-hash-chain (`blockchain.rs`)
or the candid endpoint argument validation.

## Connections to the corpus
| Mechanism | How supply is tracked | Drift possible? |
|---|---|---|
| **ICP ledger** | **derived** `max_value − token_pool` (complement pool) | **no** — nothing stored to drift |
| Cosmos `x/bank` | stored `TotalSupply`, matched to mint/burn | only via unsafe low-level setters (post-invariant-removal) |
| Substrate | stored `TotalIssuance`, booked on `Imbalance::Drop` | only via `Unsafe*Accounting` |
| Algorand | not stored; **recomputed** `totals.All()` each block + compared | caught by the recompute gate |
ICP and Algorand are the two "can't silently drift" designs, by opposite means: Algorand *recomputes
and compares* every block; ICP makes the supply a *derived complement* so there's no second number to
reconcile. Both are stronger than the stored-counter designs against a future-bug class. The
trap-and-rollback failure mode is the IC's version of the conservation-violation-halts philosophy.

## What this audit did NOT cover (coverage honesty)
- **Cycles** — the IC's *compute fuel* is a separate conservation system (cycles minted by burning ICP
  via the Cycles Minting Canister at an XDR-pegged rate); not the token ledger, not opened here. The
  ICP↔cycles peg is the IC's notable internal settlement seam (Bucket 6-ish).
- **Chain-key / consensus / the NNS** — the agreement and governance layers (the analog of the
  MonadBFT/consensus audits); orthogonal to this validity floor, not opened.
- **The block hash-chain & archiving** (`blockchain.rs`, `archive.rs`) — integrity/history, read only
  at interface.
- **ICRC-2 approvals** (`approvals.rs`) — allowance accounting (the approve/transfer_from surface),
  noted not opened.
- **Candid decoding / inter-canister call surface** — the endpoint input-validation boundary.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I did not assume "Balances conserves" — I walked each of
  mint/burn/transfer and confirmed `token_pool + Σ balances` is invariant, and confirmed
  `total_supply()` is *derived* (no stored field to drift). I confirmed the arithmetic is the checked
  `TokensType` variant and distinguished the graceful-error paths from the trap-on-bug paths.
- **Exposure to reversal.** This verdict rests on: (a) IC trap semantics genuinely rolling back the
  message's state (the documented platform behavior — if a panic could leave partial state, a
  mid-`transfer` panic between `debit` and the pool update could break conservation; I relied on the
  platform guarantee, did not test it); and (b) all balance mutations routing through `Balances`
  methods (I read the core; I did not enumerate every caller for a path that mutates `store` directly).
  Both stated as bounded reads.

## Verdict
**Clean.** The ICP ledger conserves value by construction via a complement-pool: `total_supply` is the
*derived* `max_value − token_pool`, every mint/burn/transfer-fee moves tokens conservatively between
the pool and accounts (so `token_pool + Σ balances == max_value` cannot drift), arithmetic is checked
throughout, and conservation-violating "impossible" cases panic — which on the IC traps and rolls back
the whole message. Replay is blocked by a separate `created_at_time`+hash dedup window. A novel
corpus data point — supply-as-derived-complement, the "no second number to reconcile" design alongside
Algorand's recompute gate. No untrusted-input→value path in the ledger core; nothing to disclose. Next
pulls (separate surfaces): the ICP↔cycles minting peg (CMC) and ICRC-2 approvals.
