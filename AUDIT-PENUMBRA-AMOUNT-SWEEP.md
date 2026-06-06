# Penumbra — Non-DEX `Amount` Arithmetic Conservation Sweep

**Target:** `penumbra-zone/penumbra` @ `36a31c1`. **Scope:** every non-DEX use
of native `Amount`/`Balance` addition/subtraction and any
`saturating`/`wrapping`/raw-`u128` arithmetic touching balances, fees, rewards,
penalties, claims, supply, escrow, staking, IBC, or shielded values.
**Read-only.** No exploit code, PoCs, or invalid-transaction tests.
**Verdicts (strict):** `checked/fail-closed` · `capped/unreachable` ·
`non-value-bearing` · `VCB-backstopped` · `unclear needs human review` ·
`value-bearing unchecked`.

---

## Answer

**No `value-bearing unchecked` site was found in any consensus-critical path.**
Every value-bearing native `Amount +/-` is one of: on the `Balance` type (which
is **fail-closed — panics, never wraps**), **capped** by an enforced upstream
bound, **backstopped** by a per-component Value Circuit Breaker or a checked
budget drawdown, **guarded** by a prior comparison, or **non-consensus**
(client-side planning / RPC views / heights / counts / vote tallies).

The single systemic recommendation is unchanged from the DEX review: set
`overflow-checks = true` on the release/dist profiles, which converts every
"capped/unreachable (relies on a bound)" site into "fail-closed."

---

## Foundational types (apply everywhere)

| Type | File:line | Overflow behavior in release | Verdict |
|---|---|---|---|
| `Balance` / `Imbalance<NonZeroU128>` add | `core/asset/src/balance/imbalance.rs:32-62` | same-sign `checked_add` then **`panic!`**; opposite-sign is "lesser-from-greater" subtraction (cannot underflow) | **checked/fail-closed** |
| `Balance` sub | `imbalance.rs:64-69` | `self + (-other)` → same as above | **checked/fail-closed** |
| `Amount` `+`/`-` operators | `core/num/src/amount.rs:385-409` | plain `u128` — **wraps** (no `overflow-checks`) | per-call-site (below) |
| `Amount::checked_add/sub` | `amount.rs:54-64` | `Option` (None on over/underflow) | **checked/fail-closed** |

Because most action/transaction value balances are computed on `Balance`, the
bulk of value accounting is fail-closed by construction.

---

## IBC ICS-20 escrow (`shielded-pool/src/component/transfer.rs`)

| File:line | Operation | Value? | Upstream guard | Downstream check | Release overflow | Verdict |
|---|---|---|---|---|---|---|
| `transfer.rs:111` | `value_balance.checked_add(&withdrawal.amount)` | yes (escrow) | — | `.ok_or_else` err | errors | **checked/fail-closed** |
| `transfer.rs:164` | `value_balance.checked_sub(&withdrawal.amount)` | yes (escrow) | `if value_balance < amount { bail }` `:158` | err | errors | **checked/fail-closed** |
| `transfer.rs:392` | `value_balance.checked_sub(&receiver_amount)` | yes (unescrow) | `bail` at `:370` | ctx err | errors | **checked/fail-closed** |
| `transfer.rs:537` | `value_balance.checked_sub(&amount)` | yes (unescrow) | `bail` at `:517` | ctx err | errors | **checked/fail-closed** |
| `transfer.rs:456` | `value_balance.saturating_add(&value.amount)` | yes (escrow ↑) | — | — | **saturates** | **capped/unreachable** |
| `transfer.rs:580` | `value_balance.saturating_add(&value.amount)` | yes (escrow ↑) | — | — | **saturates** | **capped/unreachable** |

**Note:** every value-*creating* direction (unescrow/decrement) is `checked_sub`
behind a `< amount` bail. The two `saturating_add` are escrow *increments*: on
the (unreachable) `u128::MAX` boundary they **cap**, which under-counts escrow in
the *chain's* favor — never mints claimable value. `bank_query.rs:115`
(`*a += amount`) is an **RPC supply aggregation** (Cosmos-bank view), not
consensus state → **non-value-bearing**.

---

## Staking / funding / distributions

| File:line | Operation | Value? | Guard / backstop | Release overflow | Verdict |
|---|---|---|---|---|---|
| `stake/.../validator_store.rs:262,441,465` | `checked_add`/`checked_sub` pool supply | yes | err/None | errors | **checked/fail-closed** |
| `stake/.../stake.rs:434` | `checked_add` total active stake | yes | err | errors | **checked/fail-closed** |
| `stake/.../epoch_handler.rs:60,68` | `saturating_add(&delegation_amount)` tallies | yes | feeds checked pool ops (`validator_store`) | saturates | **capped/unreachable** |
| `stake/.../epoch_handler.rs:215` | `(d as i128) - (u as i128)` delta | yes | `unsigned_abs` → checked pool ops `:230-237` | wraps (i128) | **VCB-backstopped** (downstream checked) |
| `stake/.../stake.rs:78` | `+= value.amount` genesis allocations | yes | genesis config (trusted, one-time) | wraps | **capped/unreachable** (trusted genesis input) |
| `funding/.../component.rs:115` | `saturating_add(reward_for_stream)` | yes | compared vs `staking_issuance_budget` `:174` | saturates | **VCB-backstopped** |
| `funding/.../rewards/mod.rs:40,101` | `+=` vote-power / volume (share denominators) | yes | payout is `checked_sub` from withdrawn budget `:178,216` | wraps | **VCB-backstopped** |
| `funding/.../rewards/mod.rs:178,216` | `checked_sub` reward budget ("exceeded budget") | yes | err | errors | **checked/fail-closed** |
| `distributions/.../component.rs:138,163` | `checked_mul`/`checked_add` issuance | yes | expect/err | errors | **checked/fail-closed** |
| `stake/.../rate.rs` rate/penalty `*`,`+` (U128x128) | exchange-rate / reward-rate math | no (rates) | `.expect`, bounded ≤ small | errors | **non-value-bearing** (rates; token application reviewed separately) |

The LQT reward path is the key pattern: the unchecked `+=` accumulators are only
**share denominators**; the actual payout is drawn from a budget withdrawn from
the community pool and decremented with `checked_sub` that errors on
"rewards exceeded budget" — so the minted total is **budget-capped/fail-closed**.

---

## Auction (Dutch)

| File:line | Operation | Value? | Upstream cap | Downstream check | Release overflow | Verdict |
|---|---|---|---|---|---|---|
| `auction/.../auction.rs:144,177` | `checked_add`/`checked_sub` auction VCB | yes | zero-skip | err | errors | **checked/fail-closed** |
| `dutch_auction.rs:208,209,354,355` | `+=`/`+` reserves | yes | input/max/min ≤ `2⁵²` enforced `schedule.rs:40,61,70` | auction VCB | wraps | **capped/unreachable** + VCB-backstopped |
| `dutch_auction.rs:621,623` | `*`/`+`/`-` price interpolation | yes | reserves ≤ `2⁵²`; "infallible interpolation" by design (`schedule.rs:9`) | — | wraps | **capped/unreachable** |

`MAX_AUCTION_AMOUNT_RESERVES = (1<<52)-1` is enforced for `input`, `max_output`,
`min_output` via `ensure!` in the schedule action handler — chosen specifically
to give headroom for overflow-free interpolation.

---

## Governance / community-pool / fee

| File:line | Operation | Value? | Guard | Release overflow | Verdict |
|---|---|---|---|---|---|
| `governance/proposal_submit/action.rs:39` | `Balance - Balance` (deposit) | yes | `Balance` type | **panics** | **checked/fail-closed** |
| `governance/proposal_deposit_claim/action.rs:125,129` | `Balance -`/`+=` (refund) | yes | `Balance` type | **panics** | **checked/fail-closed** |
| `governance/.../view.rs:549,550,553,826` | `saturating_sub`/`+=` voting-power `Tally` | no (vote power, not claimable tokens) | — | saturates/wraps | **non-value-bearing** |
| `community-pool/.../view.rs:62` | `current + value.amount` (deposit ↑) | yes | bounded by supply; deposit is tx-balance-backed | wraps | **capped/unreachable** |
| `community-pool/.../view.rs:68` | `checked_sub` (withdrawal) | yes | `Some/None` err | errors | **checked/fail-closed** |
| `fee/.../fee_pay.rs:57` | `fee - base_fee` (tip) | yes | `ensure fee >= base_fee` `:48-52` | wraps | **checked/fail-closed** (guarded) |
| `fee/.../view.rs:89,101`, `component.rs:57` | `+` fee/tip accumulation | yes | bounded by per-block fee value ≤ supply | wraps | **capped/unreachable** |

`Tally` arithmetic is voting power, not mintable value; the only value in
governance (the proposal deposit + refund) flows through `Balance`
(fail-closed).

---

## Transaction planning / app (non-consensus)

| File:line | Operation | Why not consensus-critical | Verdict |
|---|---|---|---|
| `transaction/.../action_list.rs:105,226,237` | `+=` / `saturating_sub` on change/fee during **plan building** | client-side `TransactionPlan` builder; final tx conservation is enforced cryptographically by the binding signature | **non-value-bearing** (planning) |
| `transaction/.../action_list.rs:185,188,197` | `Balance +=` / `Balance -` | `Balance` type (fail-closed) **and** client-side | **checked/fail-closed** |
| `app/.../app/mod.rs:206,271,287`, `server/info.rs:111` | `saturating_*` on byte sizes / heights | not token amounts | **non-value-bearing** |

`action_list.rs:237`'s `saturating_sub` is client-side change computation
(insufficient change is handled by dropping zero-amount notes); it cannot affect
consensus value balance.

---

## Bottom line

- **Zero `value-bearing unchecked` consensus paths.** The value-creating
  directions are uniformly `checked_*`/guarded/`Balance`-typed (fail-closed), and
  the unchecked native `Amount` ops that remain are **capped** by enforced bounds
  (auction `2⁵²`, reserves `2⁸⁰`, supply `<2¹²⁸`) or **backstopped** by a VCB /
  checked budget drawdown.
- **Two component Value Circuit Breakers** (DEX `value.rs`, auction `auction.rs`)
  plus the **funding/LQT budget `checked_sub`** are the hard per-asset
  conservation backstops.
- **Single systemic hardening recommendation (unchanged):** enable
  `overflow-checks = true` on the `release`/`dist` profiles. Today the
  "capped/unreachable" verdicts *rely on* their upstream bounds being correct;
  with overflow-checks on, any future bound regression fails closed (panic)
  instead of silently wrapping. This is the one change that would let every site
  in this sweep be graded `checked/fail-closed` outright.

## Disclosure posture
Defensive arithmetic sweep of public code at a named commit; no value-creating
path demonstrated, no exploit/PoC. The recommendation is a one-line profile flag.
Anything concrete would go to Penumbra's security channel under coordinated
disclosure, not a public PR.

## Method
Three scoped read-only sweeps (shielded-pool+ibc; stake+funding+distributions;
auction+community-pool+governance+fee+transaction+app) plus direct verification
of `core/asset` `Balance`/`Imbalance`, the IBC escrow paths, the LQT reward
budget cap, and the auction `2⁵²` reserve bound.
