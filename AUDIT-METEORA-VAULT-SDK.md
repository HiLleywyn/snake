# Meteora Vault (legacy yield aggregator) — Partial-Source Audit + the "SDK-open, program-closed" pattern

**Target:** `MeteoraAg/vault-sdk`, program `24Uqj9JCLxUeoC3hGfh5W3s9FM9uCHDS2SG3LYwBpyTi`.
A Yearn-style yield-aggregator vault: users deposit a token for LP shares; idle liquidity is
parked in lending strategies (Solend, Port, Apricot, Marginfi, Kamino, Frakt, …) and profit
is reported back.
**Auditability:** **partial source.** The repo ships the real **account layouts** and the
real **pure share-math** (`state.rs`), but the **instruction bodies in `lib.rs` are stubbed
`Ok(())`** and the `strategy/*.rs` files are **PDA-derivation helpers only** (7–13 lines
each) — the deposit/withdraw/rebalance orchestration and the strategy CPI/value-reporting are
**not published**. So the *enforcing* program is effectively closed; what's public is the
client-side mirror plus the genuine math helpers.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe." Verdicts are
scoped to what the published code actually shows.

---

## What IS auditable (real code in `state.rs`) — and it's sound

The published `impl Vault` / `LockedProfitTracker` math is the real logic the program uses
for share pricing. Three properties, each verifiable from source:

1. **Rounding is pool-favorable on both legs.** `get_unmint_amount` (deposit → shares:
   `out_token * total_supply / total_amount`, `:94`) and `get_amount_by_share` (shares →
   underlying: `share * total_amount / total_supply`, `:79`) both use `checked_div` → **round
   down**. Depositors mint ≤ fair shares; withdrawers receive ≤ fair underlying; dust accrues
   to the pool. **enforced (in the math helper).**
2. **Locked-profit degradation (anti-sandwich).** `calculate_locked_profit` (`:53`, a faithful
   port of Yearn's vault) linearly drips reported profit over 6 h
   (`LOCKED_PROFIT_DEGRADATION_DENOMINATOR / (6*3600)`), and `get_unlocked_amount`
   (`:72`) prices shares on `total_amount − locked_profit`. This blocks the classic
   deposit-just-before-profit-report / withdraw-just-after sandwich. All `checked_*`; clamps
   `locked_fund_ratio > DENOMINATOR → 0`. **enforced (in the math helper).**
3. **Donation / first-depositor inflation resistance — by design.** Share pricing reads the
   internal **ledger field** `self.total_amount`, **not** the token-account balance. A direct
   transfer into `token_vault` therefore does **not** move the share price — defeating the
   ERC-4626-style inflation attack *at the design level*. Division by `total_supply==0` /
   `total_amount==0` returns `None` (fails closed) so the first-deposit path must special-case
   it. **design is donation-resistant** — *conditional on* the (unpublished) orchestration
   maintaining the ledger correctly (next section).

---

## What is NOT auditable here (and is exactly where vault bugs live)

The high-risk surfaces the engagement steer named for vaults — "share accounting, deposits,
withdrawals, fee accrual, authority management, strategy integrations" — are in the
**unpublished** orchestration. From source I cannot verify:

- **Ledger maintenance.** That `total_amount` is updated *only* via deposit (`+=`), withdraw
  (`−=`), and strategy profit/loss reports — and is **never re-derived from the raw token
  balance**. The donation-resistance in §3 holds *only if* this is true; it's in the stubbed
  `deposit`/`withdraw`/rebalance bodies. **unverifiable.**
- **First-deposit handling.** Whether `total_supply==0` mints shares 1:1 (and whether a
  tiny first deposit + rounding can strand or mis-seed the pool). **unverifiable.**
- **Strategy value-reporting integrity (the top vault risk).** `Strategy.current_liquidity`
  is the vault's claim of how much underlying sits in each external lending protocol; profit
  = new reported liquidity − old. If a strategy over-reports (or the external protocol's
  collateral-to-underlying conversion is stale/manipulable), `total_amount` inflates and
  **every share misprices**. The CPI + conversion logic for each adapter
  (`strategy/{marginfi,apricot,frakt,…}.rs`) is **not in this repo** — only `get_*_account`
  PDA helpers and program-ID constants are. This is precisely the "third-party adapter drift"
  surface, and it is closed-source. **unverifiable — highest-value bytecode/devnet target.**
- **Performance fee (5%) accrual** (`PERFORMANCE_FEE_NUMERATOR`, `lib.rs:20`) — applied in
  the stubbed rebalance path; whether it dilutes correctly is **unverifiable.**
- **Authority.** `admin` / `operator` gating of rebalance and parameter changes — the
  `RebalanceStrategy` context constraints exist but the handler bodies are stubbed.

**Invariant checklist for a bytecode/devnet review** (the deliverable):
`Σ shares · price == total_amount` after every op; `total_amount` never reads raw balance;
first-deposit 1:1 with a minimum-liquidity floor; profit only via reported strategy delta,
fee-diluted, locked-profit-tracked; `current_liquidity` reconciles to the external
protocol's actual redeemable amount (withdraw-favorable rounding); rebalance/`report`
gated to `operator`/`admin`.

---

## The cross-target pattern: Solana DeFi is *SDK-open, program-closed*

Three consecutive Solana targets, one shape:

| Target | Published | Withheld (the enforcing logic) |
|--------|-----------|-------------------------------|
| Raydium LaunchLab | TS SDK + IDL | entire program (Rust) |
| Meteora Alpha Vault | `declare_program!` stub + IDL | entire program |
| Meteora Vault (this) | account layouts + **pure share-math** + PDA helpers | instruction orchestration + strategy CPI |

> **Observation:** in this ecosystem "open source" routinely means *the client mirror is
> open, the on-chain program is closed.* The published artifacts let you compute what the
> program *should* do; they do not let you verify what it *does*. And the withheld layer is
> consistently the **orchestration + external-CPI** layer — exactly where conservation is
> enforced or broken.

This sharpens the auditability ladder from `AUDIT-GOVERNANCE-CEILING.md` (apex = "verified ≠
running"): these targets sit *below* even WLFI, because there is **no verified program at
all** — only a vendor SDK whose correspondence to the deployed BPF is asserted, never
checked on-chain. For the methodology's three coordinates this means the **6b
"SDK == bytecode" equivalence is discharged by vendor trust**, and any conservation verdict
must be explicitly scoped to "the published mirror," never to the running program.

**Practical consequence for the weekend-review thesis:** for these targets the
expected-value-per-line of *source* review is low (the bug-bearing lines aren't published).
The real options are (a) bytecode/devnet differential testing against the invariant
checklists, or (b) the genuinely-full-source targets — of the set reviewed, **DAMM v2**
(audited, strong floor) and **Civic transfer-hook** (audited) were the only complete-source
programs; the SDK-named "vault/alpha-vault/launchpad" targets are mirrors.

---

## Summary

| Item | Verdict |
|---|---|
| Share-math rounding (deposit & withdraw) | **enforced in the published helper** — both round down, pool-favorable |
| Locked-profit degradation | **enforced in the published helper** — Yearn-port, 6 h linear drip, checked |
| Donation/first-depositor resistance | **donation-resistant by design** (ledger-priced) — conditional on unpublished ledger maintenance |
| Ledger maintenance / first-deposit / fees / authority | **unverifiable** — orchestration stubbed |
| Strategy value-reporting (adapter CPIs) | **unverifiable & highest-value** — not published; only PDA helpers + program IDs |
| Auditability posture | **partial source (SDK-open, program-closed)** — below "verified ≠ running" |

## Nothing routed privately

No exploitable path found, and none findable: the conservation-enforcing orchestration and
the strategy-reporting CPIs are not in the repo. The published share-math is sound and
correctly pool-favorable, with the right donation-resistant *design* (internal-ledger
pricing + Yearn locked-profit). The honest result is the partial-source scoping, the
invariant checklist for a deeper review, and the **SDK-open/program-closed** cross-target
pattern — which is itself the most useful output of this Meteora pass. Companion to
`AUDIT-METEORA-DAMM-V2.md` (the full-source counterexample), `AUDIT-METEORA-ALPHA-VAULT.md`
and `AUDIT-LETSBONK-LAUNCHLAB.md` (the IDL-only instances), and
`AUDIT-GOVERNANCE-CEILING.md` (the auditability ladder this extends downward).
