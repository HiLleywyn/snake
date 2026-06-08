# Tezos (XTZ) — typed source/sink conservation + self-amendment audit (clean)

**Target:** `tezos/tezos` (Octez, cloned from **GitLab** `/tmp/tez` — the GitHub mirror is a README
stub), `src/proto_alpha/lib_protocol`. Audited the **`Token` module** (`token.ml`) — the value-flow
conservation core — and confirmed the **self-amendment** governance surface (`amendment.ml`,
`voting_period_*`). **Posture:** defensive; no exploit, no PoC. **Result: clean — no finding, nothing
to disclose.**

Chosen for two distinct contributions: (1) a **conservation primitive new to the corpus** — a *typed
source/sink double-entry* where only explicitly-typed "infinite" endpoints can move the total supply,
and (2) the **governance-ceiling endpoint** — a chain whose entire protocol (including the voting
rules) is replaceable by stakeholder vote.

## Conservation floor — typed source/sink double-entry (Bucket 1 + 5)
Tezos models every value movement as flowing between *named, typed* endpoints (`token.ml`):
- **`container`** — real balance-holding locations: `Contract`, `Frozen_deposits`,
  `Collected_commitments`, `Block_fees`, `Frozen_bonds`, … (have actual stored balances).
- **`infinite_source`** — issuance origins: `Minted`, `Baking_rewards`, `Attesting_rewards`,
  `Bootstrap`, `Liquidity_baking_subsidies`, … (where new tokens come from).
- **`infinite_sink`** — burn destinations: `Burned`, `Storage_fees`,
  `Sc_rollup_refutation_punishments`, ….

The supply discipline is the elegant part:
- **`spend ctxt giver amount`** (`:153-239`): from a `#container`, decreases that container's stored
  balance (`spend_only_call_from_token`, which checks sufficiency). From an **`#infinite_source`**, it
  instead **raises `Total_supply`**: `new_total_supply = old +? amount` (`:173-177`) — minting is the
  *only* way supply grows, and it's modeled as spending *from* a named infinite source.
- **`credit ctxt receiver amount`** (`:69-151`): to a `#container`, increases its balance. To an
  **`#infinite_sink`**, it **lowers `Total_supply`**: `new_total_supply = old -? amount` — burning is
  the only way supply shrinks.
- **Container → container transfers are supply-neutral by construction** (neither side touches
  `Total_supply`).

So `Total_supply` moves **iff** an infinite source/sink is one endpoint, and you *cannot* mint or burn
without naming such an endpoint in the typed flow. This is conserve-by-construction with the strongest
*legibility* in the corpus: it's a typed chart-of-accounts where "real accounts" (containers) net to
zero and only "issuance/equity accounts" (infinite source/sink) change the supply. **enforced.**

## Transfers conserve exactly — `transfer_n` (the structural Σin = Σout)
`transfer_n ctxt givers receiver` (`:241-277`): spends `amount_i` from each giver while accumulating
`total = Σ amount_i` (`+?` checked, `:254`), then credits **exactly `total`** to the single receiver
(`:259`). So a multi-giver transfer debits the givers and credits the receiver the *same summed
amount* — Σ debited == credited, by construction. The result is a `balance_updates` receipt list
`[debit_logs…, credit_log]` (`:276`). **enforced.**

## The audit trail — `balance_updates` receipts (Bucket 2-ish, exposed)
Every `Token` operation returns `Receipt_repr` items tagging each endpoint with `Credited`/`Debited`
amount + origin. These `balance_updates` are emitted in block/operation metadata — an **exposed,
must-balance ledger trail** (within a transfer, Σ debits = the credit; across a block, supply deltas
equal the net of infinite-source/sink receipts). Where XRPL/Stellar/Algorand *assert/recompute* an
invariant internally, Tezos *publishes the double-entry receipts* so the conservation is externally
re-derivable from chain metadata — the most transparent variant of the checked-invariant idea.

## Arithmetic — checked, halts on overflow
`Tez_repr` mutez is a 63-bit `Int64`-backed amount; `( +? )` returns `Addition_overflow`
(`tez_repr.ml:135-140`) and `( -? )` returns an error on underflow (`:125`). Every supply/balance
update uses these checked ops (`token.ml:174`,`:254`, the `-?` in credit). A value can never silently
wrap — it errors and the operation fails. Halt-over-corruption, the discipline absent in MemeCore. **enforced.**

## The governance-ceiling endpoint — self-amendment
Tezos's on-chain governance (`amendment.ml`, `voting_period_*`, `vote_storage.ml`) lets stakeholders
**replace the protocol's own code** through a multi-period, stake-weighted process
(Proposal → Exploration → Cooldown → Promotion → Adoption). This is the **far pole of the
governance-ceiling spectrum** (`AUDIT-GOVERNANCE-CEILING.md`): where DeXe is "no admin key, every
privileged action is a vote" and most chains have a multisig/Guardian, Tezos makes *the entire
enforcing protocol — including the voting rules themselves — replaceable by supermajority stake vote*.
The trust root is the stakeholder supermajority over the amendment periods; there is no fixed admin and
no off-chain upgrade key. I confirmed the module's presence and role; I did **not** deep-audit the
voting-period state machine or quorum (the `votes_EMA`/participation logic) — named, not opened.

## Connections to the corpus
| Supply mechanism | How supply changes | Legibility |
|---|---|---|
| **Tezos** | only via typed `infinite_source`/`infinite_sink` endpoints; receipts exposed | **highest** — published double-entry |
| ICP | derived `max − token_pool` (complement) | high — nothing to drift |
| Algorand | recomputed `totals.All()` each block | high — recompute gate |
| Cosmos `x/bank` | matched mint/burn + stored `TotalSupply` | medium — by-construction |
| Substrate | `Imbalance::Drop` books `TotalIssuance` | medium — self-accounting |
Tezos joins the "supply can't drift" group (with ICP/Algorand) by a *third* means: making every
supply-affecting flow name a typed issuance/burn endpoint and **exposing the balance-update receipts**,
so conservation is externally auditable from metadata. On governance it sits opposite the admin-key
chains: self-amendment is the logical end of "trust the vote."

## What this audit did NOT cover (coverage honesty)
- **The Michelson VM / smart-contract execution** — contract-internal value handling beyond the
  `Contract_storage` debit/credit primitives; a separate surface.
- **The voting-period state machine & quorum** (`amendment.ml`, `votes_EMA_repr`) — confirmed present
  as the governance endpoint, not line-audited (the quorum/participation EMA is the residual).
- **Staking/frozen-deposits/slashing accounting** (the many `*_storage` containers) — read at the
  Token-endpoint level, not each container's internal bookkeeping.
- **Tenderbake consensus** and **Smart Rollups** (the optimistic-rollup settlement seam) — orthogonal
  surfaces.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I confirmed the *direction* of each supply move (spend from
  infinite_source → `+?` Total_supply; credit to infinite_sink → `-?` Total_supply; container moves
  neutral) by reading both branches, and confirmed `transfer_n` credits exactly the summed debits. I
  verified `+?`/`-?` are the error-returning checked ops, not raw `Int64` add.
- **Exposure to reversal.** The conservation rests on *every* value movement routing through `Token`
  (the `_only_call_from_token` naming convention enforces that container storages are mutated only via
  this module — a strong signal I relied on but did not exhaustively prove for every storage). The
  supply guarantee assumes the set of `infinite_source`/`infinite_sink` constructors is exactly the
  intended issuance/burn set (I enumerated them from the match arms). The governance verdict is a
  *placement*, not a full audit of the voting machine.

## Verdict
**Clean.** Tezos conserves value through a typed source/sink double-entry: container-to-container
transfers are supply-neutral and credit exactly the summed debits (`transfer_n`), while `Total_supply`
changes *only* when a typed `infinite_source` (mint) or `infinite_sink` (burn) is an endpoint — all
with checked, halt-on-overflow mutez arithmetic and an **exposed `balance_updates` receipt trail** that
makes conservation externally re-derivable. It joins ICP/Algorand as a "supply can't drift" design, by
the most transparent means in the corpus. Its governance is the **self-amendment endpoint** of the
ceiling spectrum — the protocol, voting rules included, is replaceable by stake vote. No
untrusted-input→value path found; nothing to disclose. Residuals: the Michelson VM value handling and
the amendment voting-period/quorum machine. Next pulls: the voting EMA/quorum and Smart Rollup
settlement.
