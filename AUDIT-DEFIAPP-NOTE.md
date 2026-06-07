# Defi App (`github.com/defi-app`) — Auditability Note + one off-chain observation

**Scope checked:** the `defi-app` org. **Posture:** defensive, passive (public repos only). No
exploit. Short note — proportional to what's actually here.

## The org is closed-source for the protocol (audited, but not published)

`defi-app` contains **no protocol smart-contract source.** It is:
- **`defi-app-audits`** — **PDF reports only** (Pashov 2025-04 airdrop, Cantina 2025-03 smart
  contracts, Sela 2025-01 infra, Halborn 2025-06 webapp, a MiCAR token whitepaper). So the
  contracts *are* professionally audited — by reputable firms — but the **code is not open** here.
- asset/data repos and forks: `trustwallet-assets`, `tokenAssets`, `uniswap-assets`,
  `DefiLlama-Adapters`, `dimension-adapters`, `brand`/`assets`, and `snapshot-strategies`.

So, like the Solana SDK-mirrors and Raydium LaunchLab, this is an **auditability floor** case:
the enforcing contracts can't be reviewed from public artifacts; trust in their conservation rests
on the four named audit firms' reports + whoever holds the contracts' admin/upgrade keys (not
visible here). A source-level six-bucket pass is not possible. The protocol token is "HOME" with an
MFD-style (Radiant/Geist-lineage) locking contract (`getUserLocks`).

## The one piece of DeFi App code: the Snapshot voting strategy

`snapshot-strategies/src/strategies/defi-app-voting/index.ts` computes off-chain (advisory)
governance voting power:

```
sHome = Σ lock.amount  (from getUserLocks on the MFD locking contract)
home  = HOME.balanceOf(address)
weightedPower = sHome * 4 + home        # locked HOME ×4, liquid HOME ×1
```

**Observation (low severity, off-chain):** the strategy fetches each lock's `multiplier`,
`duration`, and `unlockTime` (in the ABI, `:9`) but **uses none of them** — it applies a **flat 4×
to all locked HOME** regardless of the per-lock multiplier or remaining duration. If the on-chain
locking contract's design intends *duration/multiplier-weighted* voting power, the Snapshot weight
diverges from it (e.g. a soon-to-expire lock and a long lock get identical 4× weight). Whether 4×
is the intended flat weight or an oversight is **unverifiable** (the locking contract isn't open).
Impact is bounded — Snapshot is off-chain signaling unless wired to on-chain execution — but it is
worth the team confirming the intended voting weight matches the on-chain lock economics. Minor
precision note: `parseFloat(formatUnits(bn))` casts balances to JS float (fine for ranking, lossy
for exact amounts) — standard for Snapshot strategies. No double-count (locked tokens sit in the
MFD contract, not in `balanceOf`).

## Verdict

Nothing routed privately. The protocol is closed-source (audited by Pashov/Cantina/Sela/Halborn;
not reviewable here) — an auditability-floor case. The only DeFi App-authored code present is an
off-chain Snapshot strategy with one low-severity weighting observation (flat 4× ignores the
fetched per-lock multiplier/duration). Companion to `AUDIT-LETSBONK-LAUNCHLAB.md` /
`AUDIT-METEORA-VAULT-SDK.md` (other "no public source for the enforcing logic" cases) and
`AUDIT-GOVERNANCE-CEILING.md` (trust = the audit firms' reports + the unseen admin keys).
