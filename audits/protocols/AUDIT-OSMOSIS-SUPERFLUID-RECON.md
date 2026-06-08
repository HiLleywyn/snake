# Osmosis (OSMO) superfluid staking — recon checkpoint (no finding)

**Target:** `osmosis-labs/osmosis`, cloned `/tmp/osmo`, HEAD `2df8d8e`. Top-100 Cosmos DeFi L1 with
custom Go modules (concentrated-liquidity, gamm, **superfluid**, lockup, protorev, …). **This is a
reconnaissance checkpoint, not a complete audit** — recorded honestly as such. **Posture:** defensive;
no exploit. **Result so far: nothing found.**

## Why superfluid is the standout surface
Superfluid staking ("stake your LP shares") is a genuinely novel conservation surface: an LP position
is given an *OSMO-equivalent* value and **synthetic OSMO is minted and delegated** on the staker's
behalf, refreshed each epoch. The risks are (a) the OSMO-equivalent multiplier over-valuing an LP
(over-rewarding vs real stakers) and (b) the synthetic mint/burn not being symmetric on refresh/unbond
(real-supply inflation).

## What the recon showed (sound design)
- **Risk-adjusted, epoch-refreshed multiplier:** `UpdateOsmoEquivalentMultipliers` (epoch.go:124);
  CL multiplier = `osmoPoolAsset / fullRangeLiquidity` (epoch.go:214); gamm via
  `calculateOsmoBackingPerShare` (epoch.go:150). The multiplier is recomputed each epoch and
  rewards follow it (epoch.go:59), so a moving LP value can't accrue stale over-rewards indefinitely.
- **Mint/burn on refresh:** `RefreshIntermediaryDelegationAmounts` + `mintOsmoTokensAndDelegate`
  (stake.go:37,56,93) adjust the synthetic delegation to match the refreshed value (mint if up).
- **Registered runtime conservation invariant:** `TotalSuperfluidDelegationInvariant`
  (invariants.go:27) — *"sum of intermediary account delegation == sum of individual lockup
  delegation."* Osmosis explicitly checks the synthetic delegation conserves against the lockups at
  runtime — the right defensive instrument.

## Honest status & where a full audit would dig
Recon found a sound design with an explicit conservation invariant; **nothing exploitable surfaced.**
A complete pass (not done here) should verify: (1) the multiplier **rounding direction** favors the
protocol (LP under-valued, not over) at epoch.go:190/214; (2) **mint/burn symmetry** — every synthetic
OSMO minted on refresh is burned on unbond/slash with no residual; (3) the **slashing** path for
superfluid (a misbehaving validator's superfluid delegation slashed correctly against the LP); (4) the
concentrated-liquidity superfluid path (`concentrated_liquidity.go`), the newest/most complex. These
are the EV targets; Osmosis is mature and heavily audited, so expectations are calibrated accordingly.
**No finding; not routed.**
