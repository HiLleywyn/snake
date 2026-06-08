# Berachain (BERA) — Proof-of-Liquidity (BGT) conservation — clean (strong positive)

**Target:** `berachain/contracts`, cloned `/tmp/bera`. Top-100 newer L1; custom **Proof-of-Liquidity**:
BGT (reward token) emitted to liquidity providers via reward vaults, redeemable 1:1 for BERA (gas
token). **Posture:** defensive; no exploit. **Result: clean — no finding** (came for custom-reward-glue
risk; found a hard-invariant design). Self-check + connections applied.

## BGT is fully BERA-backed by an explicit invariant (the headline)
`src/pol/BGT.sol` wraps every state-changing op in an `invariantCheck` modifier (`:150`):
```
_invariantCheck: if (address(this).balance < totalSupply()) revert InvariantCheckFailed   (:463-464)
mint:   onlyBlockRewardController invariantCheck   (:177)   // mint must keep balance >= supply
redeem: burn BGT → send BERA 1:1, invariantCheck   (:366)
burnExceedingReserves: backing must cover totalSupply() + potentialMintableBGT  (:382-386)
```
So **every BGT is ≥1:1 backed by BERA held in the contract, re-checked on every mint/redeem.** BGT
cannot be minted unless the BERA backing is present (the post-mint invariant reverts otherwise), and
`burnExceedingReserves` requires backing for *current supply plus still-mintable* BGT (no race where
emission outpaces backing). This is a hard, self-enforcing reserve invariant — the **opposite** of the
owner-mint-anything EVM tokens in the corpus (`AUDIT-HUMANITY-HTOKEN.md` HToken, WLFI).

## Emission is bounded + system-gated
- **Bounded inflation:** `BlockRewardController` emits `computeReward = baseRate + rewardRate·boost`
  with `baseRate ≤ MAX_BASE_RATE` (`:109`), `rewardRate ≤ MAX_REWARD_RATE` (`:118`), and a boost
  "inflation cap" (`:60`). The owner tunes the rates but only within hard MAX caps.
- **System-gated minting:** `Distributor.distributeFor(pubkey)` is `onlySystemCall` (`:155`) — only the
  consensus layer triggers per-block minting+distribution; "if governance has not set the default
  reward allocation, the rewards are not minted" (no orphan emission). Distribution is weight-
  proportional to reward vaults via `BeraChef`.
**enforced — bounded, system-gated emission; every minted unit backed.**

## Connections
- **"Conservation as a first-class *checked* invariant" family — the EVM-Solidity member.** Berachain
  BGT (`balance >= totalSupply`, reverted per write) joins XRPL (`delta == −fee`), Cardano (`consumed
  == produced`), Osmosis (registered invariant), Aptos (Move Prover specs), marginfi (rate
  decomposition). Most EVM tokens *don't* do this — BGT is the strong-positive counter-example to
  HToken/WLFI's owner-mint-anything (`AUDIT-GOVERNANCE-CEILING.md` spectrum).
- **Backed-redeemable-claim model:** BGT↔BERA 1:1 reserve ≈ the wrapped-asset / Sui-staking-pool
  ledger-backed-claim pattern — a redemption right fully reserved, enforced structurally.
- **Bounded + system-gated emission** ≈ Sui (subsidy bounded from genesis + native mint gated to the
  `@0x0` system tx, `AUDIT-SUI-SIX-BUCKET.md`) and MemeCore's *intended* fixed reward — except
  Berachain adds the backing invariant MemeCore's reward path lacked.

## What this audit did NOT cover (coverage honesty)
- The **RewardVault** staking accounting (LP stake → BGT accrual; the per-vault reward math) and
  **BeraChef** weight allocation beyond confirming the distribution is weight-proportional and
  system-gated.
- **beacon-kit** consensus (separate repo; the per-block trigger and the validator set).
- The boost/delegation mechanics (BGT delegated to validators for emission boosts) and
  `BGTIncentiveDistributor` (third-party incentive markets) internals.

## Verdict
**Clean.** Berachain's PoL token is well-architected: BGT is fully BERA-backed by an invariant
re-checked on every mint/redeem (mint impossible without backing), emission is hard-capped and
system(consensus)-gated, distribution is weight-proportional. A strong positive — the EVM member of
the explicit-checked-invariant family and the counter-example to owner-mint-anything tokens. No
finding; nothing routed.
