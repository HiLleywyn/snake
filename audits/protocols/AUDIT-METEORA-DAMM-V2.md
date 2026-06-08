# Meteora DAMM v2 (cp-amm) — Six-Bucket Trust Audit

**Target:** `MeteoraAg/damm-v2`, program `programs/cp-amm` (~15.4K LOC Rust/Anchor), cloned
`/tmp/damm-v2` (shallow, latest). A Uniswap-v3-style concentrated-liquidity AMM with
positions (NFT-owned), fee/reward accrual, vesting, and Token-2022 support.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts
cite the exact constraint. Any untrusted-input→unvalidated→value path would route privately
to Meteora; none was found. This is a *focused* audit of the highest-value AMM surfaces
(swap invariant + rounding, liquidity, position split, Token-2022 accounting, governance),
not an exhaustive 15K-line read — coverage gaps are stated.

**Standing caveat (per the engagement steer):** this is mature, professionally-built code
and shows every sign of prior audit. The honest result is *"strong floor, residual trust in
governance + Token-2022 extension policy,"* not a vulnerability. Findings are proportional.

---

## Bucket 1 / 5 — Swap conservation & rounding direction (the AMM core; enforced)

The single most important property of an AMM is that **rounding always favors the pool/LPs,
never the swapper** — otherwise repeated tiny swaps drain reserves. I traced every rounding
decision in `liquidity_handler/concentrated_liquidity.rs` and it is consistently
pool-favorable, with doc-comments that correctly justify each direction:

| Path | Output/Input rounding | Price rounding | Direction |
|------|----------------------|----------------|-----------|
| exact-in A→B (`:66`) | output `Δb` **Down** (`:80`) | next √P up (`a_in_a_rounding_up`, `:438`) | swapper gets ≤ ; pool keeps dust ✓ |
| exact-in B→A (`:90`) | output `Δa` **Down** (`:103`) | next √P down (`:483`) | ✓ |
| exact-out A→B (`:193`) | input `Δa` **Up** (`:206`) | next √P (`:497` div_ceil) | swapper pays ≥ ✓ |
| exact-out B→A (`:214`) | input `Δb` **Up** (`:227`) | next √P up (`:454`) | ✓ |
| add liquidity (`ix_add_liquidity:106`) | amounts **Up** | — | LP deposits ≥ required ✓ |
| remove liquidity (`ix_remove_liquidity:115`) | amounts **Down** | — | LP withdraws ≤ entitled ✓ |
| reserves / init (`:27`,`:235`) | **Up** | — | pool holds ≥ ✓ |

The price-update functions round "to make sure that we don't pass the target price"
(`:379`), and the math is the standard v3 identities (`Δa = L(√P_u−√P_l)/(√P_u√P_l)`,
`Δb = L(√P_u−√P_l)`, `√P' = √P·L/(L±Δa·√P)`) implemented over `U256`. **Verdict: enforced
invariant** — rounding is pool-favorable on all six swap legs and both liquidity legs, so a
swapper cannot extract more than the curve allows; rounding dust accrues to the pool.

### Arithmetic discipline (Bucket 5; enforced)

All arithmetic goes through a `SafeMath` trait (`math/safe_math.rs`) of `checked_*`
operations returning `PoolError::MathOverflow`, with `#[track_caller]` + `Location::caller()`
logging the exact failing site. Delta results are bounded with `require!(result <=
u64::MAX, MathOverflow)` before the `u64` cast (`concentrated_liquidity.rs:300`,`:336`).
Intermediate products use `U256`/`U512` to avoid overflow before the bound check. **Verdict:
enforced** — no unchecked arithmetic on the value paths reviewed; overflow fails closed.

---

## Bucket 1 — Position split conservation (enforced *by construction*)

`split_position` exists in two versions (iteration). `pool.apply_split_position`
(`state/pool.rs:902`) moves value between two positions component-by-component — unlocked
liquidity, permanent-locked liquidity, vested liquidity, fee A/B, reward 0/1 — and for each
it computes **one `delta`** (`get_*_by_numerator`) then `remove`s it from `first_position`
and `add`s the *identical* `delta` to `second_position` (`:937`–`:1000`). Removed ≡ added by
construction → no value created or destroyed across the split; the same single-delta pattern
the methodology confirmed in TRON and Sui. Numerators are validated `≤
SPLIT_POSITION_DENOMINATOR` (each fraction ≤ 100%, `ix_split_position2.rs:63`–`:102`).

The account constraints (`SplitPositionCtx`) close the surrounding trust boundary:
- both positions carry `has_one = pool` (`:106`,`:122`) — liquidity can only be relabeled
  **within one pool**, so pool-level totals are untouched;
- `first_position.key() != second_position.key()` (`:107`) — no self-split double-count;
- **both** `first_owner` and `second_owner` are `Signer`s with NFT-bound authority
  (`amount == 1`, `mint == position.nft_mint`, `token::authority = owner`, `:113`,`:135`,
  `:138`) — you can neither split *from* a position you don't own nor force value *into*
  someone's position without consent.

**Verdict: enforced** — conserved single-delta transfer, same-pool constrained,
dual-owner-consented.

---

## Bucket 3 / 6 — Token-2022 integration accounting (enforced for fees)

The classic Token-2022 AMM bug is crediting *nominal* rather than *actually-received*
amounts when a mint has a transfer-fee extension, which shorts the pool. `utils/token.rs`
handles both directions:
- `calculate_transfer_fee_excluded_amount` (`:70`) — net-of-fee amount the pool actually
  receives (credit this, not the nominal);
- `calculate_transfer_fee_included_amount` (`:93`) — gross-up so the pool receives the
  intended net (for required-input / exact-out), with the `MAX_FEE_BASIS_POINTS` (100% fee)
  edge case handled per the SPL reference (`:106`–`:108`).

**Verdict: enforced** for transfer-*fee* accounting. **Residual (named, not a finding):**
arbitrary Token-2022 *transfer-hook* mints add CPI surface — the AMM is the transfer
initiator and a malicious hook executes during its CPI. The mitigation in this codebase is
the **`token_badge`** allowlist (admin-gated `create_token_badge` /
`ix_create_token_badge.rs`): which Token-2022 mints/extensions may enter pools is a
governance decision, not open. Confirming the badge policy gates hook-bearing mints (and
that pool state follows checks-effects-interactions around the transfer CPIs) is the
highest-value remaining review item for the Token-2022 surface — exactly the area flagged
in the engagement steer.

---

## Bucket 2 — Witnessed objects / access

- **Positions are NFT-owned** — authority is proven by holding the position NFT
  (`amount == 1`, `mint == nft_mint`, `token::authority`), checked at the Anchor account
  layer on every position-mutating instruction. **enforced.**
- **Pool action gating** — `get_pool_access_validator(&pool)` + `can_*()` checks
  (`pool_action_access/`) gate swap/split/liquidity on pool status before any state change
  (e.g. `can_split_position()`, `ix_split_position2.rs:131`). **enforced.**

---

## Bucket 4 / governance ceiling — where the residual trust actually sits

The arithmetic/conservation floor is strong; the ceiling is the operator/admin surface
(`instructions/operator/`, `instructions/admin/`):
- `ix_set_pool_status` (pause/limit pool actions), `ix_update_pool_fees`,
  `ix_fix_pool_fee_params`, `ix_fix_config_fee_params`, `ix_fix_pool_layout_version`,
  `ix_zap_protocol_fee`, `ix_claim_protocol_fee*`, `ix_create_static/dynamic_config`,
  `ix_create_token_badge` — privileged parameter/lifecycle control gated by an
  **operator/admin** authority (`instructions/admin/auth.rs`, `access_control.rs`).
- The **BPF upgrade authority** (off-repo) is the apex power, per
  `AUDIT-GOVERNANCE-CEILING.md`: an upgradeable program means every verdict here carries the
  silent suffix *"…as of this bytecode."*

These are by-design administrative capabilities (fee tuning, emergency pause, token-badge
allowlisting), and they are the correct place to concentrate "what could change the rules."
Their threshold/key-custody (multisig? timelock?) is the governance fact a deployment review
must establish on-chain — not derivable from source. **trust-boundary debt (by design).**

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1/5 | Swap rounding (6 legs) + liquidity (2 legs) | **enforced invariant** — uniformly pool-favorable; v3-faithful |
| 5 | `SafeMath` checked arithmetic + U256 intermediates + u64 bound | **enforced** — overflow fails closed, caller-tracked |
| 1 | Position split | **enforced by construction** — single-delta remove≡add; same-pool; dual-owner-signed |
| 3/6 | Token-2022 transfer-**fee** accounting | **enforced** — credits net / grosses-up; 100%-fee edge handled |
| 6 | Token-2022 transfer-**hook** mints | **named residual** — `token_badge` allowlist is the gate; confirm policy + CEI |
| 2 | NFT-owned positions; pool-action access gating | **enforced** at Anchor account layer |
| 4 / ceiling | Operator/admin params + BPF upgrade authority | **trust-boundary debt (by design)** — the real residual |

## What this audit did NOT cover (coverage honesty)

- The dynamic-fee / volatility-accumulator math (`base_fee/`, `update_post_swap`) and the
  fee-scheduler / rate-limiter variants — read only at their call boundaries.
- Reward accrual & vesting (`ix_fund_reward`, `ix_claim_reward`, `refresh_vesting`,
  `state/vesting.rs`) beyond confirming the split conserves them.
- The full operator/admin authorization graph (who exactly may call each privileged ix) —
  enumerated, not each verified against its `auth.rs` constraint.
- `u128x128_math` / `mul_div_u256` internals beyond confirming the rounding-mode plumbing.
- The other Meteora repos (`alpha-vault-sdk`, `vault-sdk`) — both ship real program source
  and remain available for follow-up; this pass prioritized the AMM (highest invariant
  density) per the steer.

## Nothing routed privately — and the honest result

No untrusted-input→value path was found. The swap invariant rounds pool-favorably on every
leg, liquidity add/remove round correctly, the position split is a conserved single-delta
transfer fenced by same-pool + dual-owner-signature constraints, arithmetic is checked-and-
bounded, and Token-2022 transfer fees are accounted in both directions. This is a strong
conservation/arithmetic **floor**. The residual trust is where the corpus consistently
finds it: the **governance ceiling** (operator/admin fee+status+badge powers and the BPF
upgrade authority) and the **Token-2022 extension-policy seam** (the `token_badge` allowlist
deciding which exotic mints — including hook-bearing ones — may enter pools). Those are the
two places a deployment-level review and a Token-2022-focused follow-up should concentrate.
Companion to `AUDIT-CIVIC-TRANSFER-HOOK.md` (the hook side of Token-2022),
`AUDIT-GOVERNANCE-CEILING.md`, and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §11 (conservation
floor: here a *runtime, pool-favorable-rounding* floor, faithfully implemented).
