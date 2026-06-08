# Polkadot / Substrate (DOT) — conservation-via-type-system audit (clean, strong positive)

**Target:** `paritytech/polkadot-sdk` (sparse clone `/tmp/psdk`: `frame/balances` +
`frame/support/.../tokens`). Top-100 L1 + the framework under hundreds of parachains. Audited the
**`Imbalance` type** (`frame/support/src/traits/tokens/imbalance.rs`) and its concrete
`PositiveImbalance`/`NegativeImbalance` implementations in the balances pallet
(`frame/balances/src/impl_currency.rs`). **Posture:** defensive; no exploit, no PoC. **Result:
clean — no finding, nothing to disclose.**

Chosen as a standout because Substrate enforces value conservation through a **type-system
mechanism** — the closest non-Move analog in the corpus to Sui/Aptos's linear-type floor
(`AUDIT-SUI-SIX-BUCKET.md` Pass 7, `AUDIT-APTOS-COIN.md`). The trait doc literally calls it *"a trait
for a not-quite Linear Type that tracks an imbalance."* Connection-driven: I verified Move's
"unforgeable/un-vanishable balance" floor; Substrate tests whether the same guarantee re-derives in
Rust *without* a Move-style verifier, using `#[must_use]` + a custom `Drop`.

## The mechanism — every balance change emits an `Imbalance` that must be booked (Bucket 1 + 2)
The invariant maintained is **`TotalIssuance == Σ all account balances`**, at all times. The
enforcement is structural, not a periodic check:
- Any operation that alters an account balance returns an `Imbalance` object (`#[must_use]`,
  `imbalance.rs:65-66`). **Positive** = funds appeared without a matching subtraction (reward/mint);
  **Negative** = funds removed without a matching addition (slash/fee/burn).
- The **only** ways to discharge an imbalance are: `drop_zero` (succeeds *only* if value is zero,
  `imbalance.rs:74`), `offset`/`merge` against its opposite, route it via `OnUnbalanced` (re-deposit
  elsewhere — i.e. move it to another account), or **let it `Drop`** — and `Drop` *books it to
  `TotalIssuance`*:
  - `PositiveImbalance::drop` → `TotalIssuance += self.0` (+ `Issued` event) (`impl_currency.rs:257-264`)
  - `NegativeImbalance::drop` → `TotalIssuance -= self.0` (+ `Rescinded` event) (`:267-274`)
- So a balance delta can **never silently vanish**: if you increase an account and drop the resulting
  `PositiveImbalance` without cancelling it, `TotalIssuance` rises by exactly the same amount, keeping
  `TotalIssuance == Σ balances` true. `#[must_use]` makes "forgetting" a compile-time warning, nudging
  modules to handle it explicitly (e.g. send a fee to the treasury via `OnUnbalanced`). **enforced.**

## The load-bearing detail — `offset` and `mem::forget` (the transfer cancellation, correct)
A transfer debits A (`NegativeImbalance(amt)`) and credits B (`PositiveImbalance(amt)`); these are
cancelled with `offset` (`impl_currency.rs:164-175`):
```
fn offset(self, other) -> SameOrOther {
    let (a, b) = (self.0, other.0);
    mem::forget((self, other));        // <-- both Drop handlers suppressed
    if a > b      { Same(Self(a - b)) }
    else if b > a { Other(NegativeImbalance::new(b - a)) }
    else          { None }
}
```
The `mem::forget` is the critical correctness point: when cancelling a Positive against a Negative you
**must not** let either `Drop` run (each would adjust `TotalIssuance`, double-counting); instead the
net residual carries the only remaining accounting. For a balanced transfer (`a == b`) it returns
`None` → `TotalIssuance` unchanged → **exact conservation.** The subtraction here is plain `-`, guarded
by the `>` comparisons (no underflow). **enforced — and the `mem::forget` is exactly where a naive
re-implementation would leak issuance.**

## Connections to the corpus
| Floor | How "can't forge / can't vanish" is achieved |
|---|---|
| **Substrate `Imbalance`** | `#[must_use]` + `Drop` books delta to `TotalIssuance` (Rust) |
| Sui `Balance` / Aptos `Coin` | linear type: `store` w/o `copy`/`drop`, verifier-enforced (Move) |
| Cardano / Avalanche | UTXO equation: `consumed == / ≥ produced` |
| Algorand | per-block recomputed `totals.All()` equality gate |
| XRPL / Stellar | per-tx/ledger invariant-check finalizers |
Substrate occupies a distinct cell: **conservation is woven into the value type itself** (like Move),
but where Move *forbids* dropping a `Balance`, Substrate *permits* the drop and **accounts for it** —
the `Drop` impl is what keeps `TotalIssuance == Σ balances`. Same guarantee ("a balance delta is never
lost"), opposite implementation strategy. This refines the §11 conservation-ladder: Move and Substrate
are both "type-system floors," but Move's is *prohibitive* and Substrate's is *self-accounting*.

## What this audit did NOT cover (coverage honesty)
- **The balances pallet account-mutation paths** (`mutate_account`, ED/`ExistenceRequirement`,
  reserves/holds/freezes) — I verified the imbalance bookkeeping; the per-account dust/existential-
  deposit logic and the locks/holds accounting are a deeper surface, read only where it produces
  imbalances.
- **Staking slashing / reward distribution** (the biggest `OnUnbalanced` consumers) and the
  **treasury** — where imbalances are routed in practice.
- **XCM cross-chain asset transfers** (the multi-chain settlement seam; teleport vs reserve-transfer
  conservation) — the Bucket-6 residual, not opened.
- **GRANDPA/BABE consensus** — the agreement layer (cf. `AUDIT-MONADBFT-CONSENSUS.md`), orthogonal.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I did not take "Imbalance" on faith — I read both `Drop` impls
  to confirm the *direction* (Positive→`+=`, Negative→`-=` on `TotalIssuance`) and read `offset` to
  confirm the `mem::forget` suppresses double-accounting and that a balanced transfer nets to `None`.
- **Exposure to reversal.** This verdict would weaken if: (a) the `saturating_add`/`saturating_sub`
  in `merge`/`subsume`/`Drop` could *actually* saturate — a real saturation would silently break
  `TotalIssuance == Σ balances` (the books would no longer balance). It's unreachable while all
  balances and their sum fit in `u128` (the standard `Balance` type), and the codebase uses
  `defensive_saturating_*` (which panics in debug) on the account paths — but the plain `saturating_*`
  on the imbalance merge path is a **stated residual**, not a closed proof. (b) Some balance write
  bypassed the imbalance return entirely (an `UnsafeManualAccounting`/`UnsafeConstructorDestructor`
  path exists in `imbalance_accounting.rs` — named "unsafe" precisely because it sidesteps this; I did
  not audit its callers). Both stated as bounded reads.

## Verdict
**Clean, strong positive.** Substrate conserves value by making every balance change return a
`#[must_use]` `Imbalance` whose only silent disposal route (`Drop`) books the delta straight into
`TotalIssuance`, keeping `TotalIssuance == Σ balances` invariant; transfers cancel via an `offset`
that correctly `mem::forget`s both halves to avoid double-counting. It is the corpus's cleanest
**Rust** re-derivation of the Move linear-type floor — same "a balance delta can't vanish" guarantee,
achieved by self-accounting drop rather than prohibition. No untrusted-input→value path found,
nothing to disclose. Residuals: the `saturating_*` merge arithmetic (unreachable-but-unproven) and the
explicitly-named `Unsafe*Accounting` bypass callers.
