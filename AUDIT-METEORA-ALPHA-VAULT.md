# Meteora Alpha Vault — Trust-Surface Map & Invariant Checklist (IDL-only)

**Target:** `MeteoraAg/alpha-vault-sdk`, program `vaU6kP7iNEGkbmPkLmZfGwiGxd4Mob24QQCie5R9kd2`.
**Auditability:** the repo's `programs/alpha-vault/src/lib.rs` is a 5-line `declare_program!`
**stub** — the actual program is **closed-source**; only the **IDL** (`idls/alpha_vault.json`,
3022 lines) and a TS client are public. **Same rung as Raydium LaunchLab** on the
auditability ladder (`AUDIT-LETSBONK-LAUNCHLAB.md` §0): no source, vendor-published IDL of
opaque bytecode. **A conservation verdict is therefore not derivable from public artifacts.**

What *is* derivable from the IDL is a precise **structural map** and an **invariant
checklist** — the exact properties the closed program must enforce, written so a later review
with the bytecode or a devnet can test each one. That checklist is the deliverable.

---

## What Alpha Vault is

A launch-allocation / anti-bot escrow vault: depositors put **quote** into per-user
`Escrow`s (optionally merkle-whitelisted with a per-user cap); at launch the vault `fill_*`s
the pooled quote into one of three Meteora pool types (`fill_damm_v2`, `fill_dlmm`,
`fill_dynamic_amm`); depositors then `claim_token` their share of **base** bought (on a
vesting schedule) and `withdraw`/`withdraw_remaining_quote` any unfilled overflow. Two
allocation modes: **FCFS** (first-come-first-served caps) and **Prorata** (over-subscription
refunded pro-rata).

### Instruction surface (from IDL)
`initialize_{fcfs,prorata}_vault`, `initialize_vault_with_{fcfs,prorata}_config`,
`create_{fcfs,prorata}_config`, `create_new_escrow`, `create_permissioned_escrow{,_with_authority}`
(merkle cap+proof), `create_merkle_root_config`, `deposit(max_amount)`, `withdraw(amount)`,
`withdraw_remaining_quote`, `fill_{damm_v2,dlmm,dynamic_amm}(max_amount)`, `claim_token`,
`transfer_vault_authority(new_authority)`, `update_{fcfs,prorata}_vault_parameters`,
crank-fee-whitelist ix.

### State accounting (from IDL — the conservation ledger)
- **`Vault`**: `max_buying_cap`, `total_deposit`, `total_escrow`, `swapped_amount`,
  `bought_token`, `total_refund`, `total_claimed_token`, `start/end_vesting_point`,
  `max_depositing_cap`, `individual_depositing_cap`, `escrow_fee`, `total_escrow_fee`,
  `vault_mode`, `whitelist_mode`, `vault_authority`, `owner`.
- **`Escrow`**: `total_deposit`, `claimed_token`, `last_claimed_point`, `refunded`,
  `max_cap`, `withdrawn_deposit_overflow`.

These field names *imply* the intended invariants but **do not demonstrate their
enforcement** — that is in the bytecode.

---

## Invariant checklist (what the closed program MUST enforce — test each)

Mapped to the engagement steer (allocation math / cap enforcement / claim / rounding /
partial-fill / authority / vault accounting). Each is stated as a property to **verify**,
not asserted as holding:

1. **Deposit conservation.** `Σ Escrow.total_deposit == Vault.total_deposit`, updated
   atomically per `deposit`/`withdraw`. *Test:* concurrent deposits/withdraws across escrows.
2. **Cap enforcement (both modes).** `deposit` must reject/clamp at
   `Escrow.max_cap`, `Vault.individual_depositing_cap`, and `Vault.max_depositing_cap`.
   FCFS: late deposits past the cap rejected; Prorata: accepted then pro-rata refunded.
   *Test:* deposit straddling each cap; `max_amount` vs actual clamp; off-by-one at the cap.
3. **Fill conservation.** `Vault.swapped_amount` (quote spent) `+ Vault.total_refund`
   (overflow) `== Vault.total_deposit` (− fees), and `Vault.bought_token` equals base
   actually received from the pool. *Test:* partial fill (`fill_*(max_amount)` < needed),
   multiple fills, fill into each of the 3 pool types; that the AMM's slippage/price can't
   leave the ledger inconsistent.
4. **Pro-rata claim correctness & rounding.** Each escrow's `claim_token` ≤
   `bought_token * (escrow_used_deposit / total_used_deposit)`, vested by
   `last_claimed_point` against `start/end_vesting_point`; **rounding must favor the vault**
   (claim down) so `Σ claimed ≤ bought_token`. *Test:* dust escrows; claim at vesting
   boundaries; repeated `claim_token` (no double-claim past entitlement);
   `Σ Escrow.claimed_token == Vault.total_claimed_token ≤ Vault.bought_token`.
5. **Overflow refund correctness.** `withdraw_remaining_quote` / `withdrawn_deposit_overflow`
   returns exactly the un-filled portion once; `refunded` flag prevents replay. *Test:*
   double-refund; refund + claim interaction.
6. **Authority transition.** `transfer_vault_authority` gated to the current
   `vault_authority`/`owner` only; `update_*_vault_parameters` likewise; cannot retroactively
   change caps/vesting to strand or over-allocate already-deposited funds. *Test:* parameter
   updates after deposits; authority handoff edge cases.
7. **Whitelist / merkle proof.** `create_permissioned_escrow(max_cap, proof)` must verify
   the proof against `MerkleRootConfig` and bind `max_cap` to the leaf — a forged proof or
   cap-substitution would defeat the anti-bot allocation. *Test:* proof for wrong
   leaf/cap; `create_permissioned_escrow_with_authority` (no-proof path) authorization.

---

## Three coordinates (structural level only)

- **Equivalence / 6b:** dominant equivalence is again *"IDL/SDK behavior == deployed
  bytecode,"* discharged by **vendor trust** — no source, weakest discharge (tied with
  LaunchLab).
- **Conservation floor:** *intended* runtime arithmetic floor (the §-checklist invariants).
  **Not establishable from public artifacts.**
- **Governance ceiling:** `vault_authority`/`owner` (parameter + authority control) plus the
  **BPF upgrade authority** (closed-source program → apex power over unviewable code). High,
  per `AUDIT-GOVERNANCE-CEILING.md`.

---

## Honest result & where to spend effort

No conservation verdict and nothing routed privately — **there is no source to find a bug
in** from public artifacts, and I will not fabricate one. The deliverable is the structural
map + the seven-point invariant checklist above, which is exactly what a bytecode- or
devnet-level review of Alpha Vault should drive against (the pro-rata claim rounding (#4) and
the merkle-cap binding (#7) are the highest-value targets — claim rounding is where launch
vaults leak base tokens, and cap binding is the anti-bot guarantee itself).

**For source-level review effort this engagement, the readable target is the legacy
`MeteoraAg/vault-sdk`** (real program source: `programs/vault/src/{state,context,...}.rs`
plus `strategy/{mango,apricot,frakt,...}.rs` adapters) — proceeding there next, since
third-party strategy adapters are the classic place vault accounting drifts as external
protocols change underneath them.

Companion to `AUDIT-LETSBONK-LAUNCHLAB.md` (the other IDL-only instance) and
`AUDIT-GOVERNANCE-CEILING.md` (no-source = sharpest ceiling).
