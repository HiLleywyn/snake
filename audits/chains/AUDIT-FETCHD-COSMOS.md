# fetchd (Fetch.ai / ASI Cosmos chain) — Six-Bucket Trust Audit

**Target:** `fetchai/fetchd`, cloned `/tmp/fetchd`, HEAD `2e47e25` ("Upgrade to fetchai
Cosmos-SDK v0.20.0 (canonical v0.53.7)"). The FET-chain node binary: a **thin Cosmos SDK app**
that wires **fetchai's forks** of cosmos-sdk and tokenfactory.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite the
exact constraint. Nothing routed privately — none found. Scope: fetchd's **own** delta (app
wiring, the v0.53 upgrade handler, tokenfactory config); the cosmos-sdk fork is too large to diff
here and is the stated residual.

**Why this shape:** `go.mod` shows `replace cosmos-sdk => fetchai/cosmos-sdk v0.20.0` and
`tokenfactory => fetchai/tokenfactory v0.1.0`. So the conservation-critical modules
(`x/bank`, `x/mint`, `x/staking`) live in **forks**, not here — Bucket 4 (fork lineage) is the
whole game, and fetchd's *own* auditable code is the app assembly + upgrade migration.

---

## Bucket 1 / 6 / governance ceiling — native FET is bridge-mintable (the headline)

The v0.53 upgrade handler (`app/upgrades.go:92`) makes the **native staking denom a tokenfactory
denom whose admin is the bridge contract**, on mainnet:

```go
case "fetchhub-4":
  Admins: []DenomAdmin{ { Denom: bondDenom, Address: "fetch1qxxlalvsdjd07p07y3rc5fu6ll8k4tmetpha8n" } }  // mainnet bridge
...
udc := keeper.NewUnboundDenomCreator(app.TokenFactoryKeeper)
udc.CreateDenom(sdkCtx, bridgeAddress, bondDenom)   // grant tokenfactory admin over afet to the bridge
```

and the tokenfactory fork is configured (`app/app.go:168`) with:

```go
tokenFactoryCapabilities = []string{
    tokenfactorytypes.EnableSudoMint,        // admin can MINT the denom
    tokenfactorytypes.EnableBurnOwn,         // admin can burn its OWN holdings
    // EnableBurnFrom            — COMMENTED OUT (admin cannot burn others')
    // EnableForceTransfer       — COMMENTED OUT (admin cannot seize others')
    tokenfactorytypes.EnableSetMetadata, tokenfactorytypes.EnableCommunityPoolFeeFunding,
}
```

**What this means.** The native token's supply is **mintable by the bridge contract** (via
tokenfactory `SudoMint`), which is the mechanism for Ethereum→Fetch bridging: the bridge mints
native FET to credit tokens locked on Ethereum, and burns its own to release them. So **native FET
supply conservation = (the bridge contract's mint controls) + (the Ethereum-side peg)** — the
classic cross-chain **6b** seam (a representation, "locked on Ethereum," the chain cannot itself
prove), and the bridge contract (plus whoever can upgrade/admin it) is the **apex trust root** for
native supply (`AUDIT-GOVERNANCE-CEILING.md`).

**What bounds it (and it's deliberately bounded).** `EnableBurnFrom` and `EnableForceTransfer`
are **explicitly disabled**. So the bridge/native-denom admin can **inflate** supply (mint) and
burn *its own* balance, but **cannot seize, force-transfer, or burn specific users' funds**. That
is a meaningful, intentional restriction: the trust is "the bridge won't over-mint against the
peg," not "the admin can take your tokens." **trust-boundary debt (by design), correctly scoped.**

---

## Bucket 1 — the v0.53 upgrade handler does NOT bend user-balance conservation (verified)

Upgrade handlers are the #1 place Cosmos chains move/mint funds during a migration. This one
(`UpgradeNameV053`, `app/upgrades.go:92–226`) was read end-to-end; it is a **structural** migration
with no user-balance manipulation:

- ICA controller capability migration; IBC denom-trace migration; `RunMigrations` (inherited
  per-module).
- **consensus-params migration** (`migrateConsensusParamsFromParamsStore`, `:251`) — reads the old
  params store and writes to `x/consensus` + BaseApp; standard v0.47+ migration, parses numbers
  correctly.
- **liquid-staking bootstrap** — iterates validators and creates `LiquidValidator{ LiquidShares = 0 }`
  (`:122`): **zero shares minted**, no value created.
- **tokenfactory setup** — sets denom-creation params and grants the denom-admin rights above.

No `MintCoins`/`SendCoins`/balance edits on user accounts; the liquid bootstrap is zero-valued. So
the migration itself is conservation-neutral (the only supply-relevant act is granting the bridge
its by-design mint authority, above). **enforced/clean** for the migration.

---

## Bucket 2 / 4 — module permissions & inherited conservation

- Standard module account perms (`app.go:220+`): `mint → Minter`, `ibctransfer → Minter+Burner`,
  `tokenfactory → Minter+Burner` — conventional.
- The **conservation engines** (`x/bank` supply invariant, `x/mint` inflation schedule, `x/staking`
  bonding/slashing) are **inherited from the fetchai cosmos-sdk fork** — high evidence depth as
  canonical cosmos-sdk, but the *fork delta* (what fetchai changed vs canonical v0.53.7) is **not
  diffed here** and is the primary residual. The `go.mod` comments cite cosmos-sdk issues #13134 /
  #10409 as fork motivations (gas/store fixes), suggesting infra rather than tokenomics changes —
  but that should be confirmed by diffing the fork.

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1/6/ceiling | Native FET mintable by bridge via tokenfactory `SudoMint` | **trust-boundary debt (by design)** — supply = bridge mint controls + ETH peg (6b); apex root = bridge contract/admin |
| 1/ceiling | `EnableBurnFrom`/`EnableForceTransfer` disabled | **enforced restriction** — admin can inflate/burn-own but **cannot seize user funds** |
| 1 | v0.53 upgrade handler | **clean** — structural migration, no user-balance bending; liquid bootstrap zero-valued; consensus-params migration correct |
| 2 | Module account permissions | **conventional** |
| 4 | Conservation modules (bank/mint/staking) | **inherited from fetchai cosmos-sdk fork** — fork delta **not diffed (primary residual)** |

## What this audit did NOT cover (coverage honesty)

- The **fetchai cosmos-sdk fork** (`fetchai/cosmos-sdk v0.20.0`) vs canonical v0.53.7 — where
  `x/bank`/`x/mint`/`x/staking` conservation actually lives; the main residual (a dedicated diff).
- The **fetchai tokenfactory fork** internals (`SudoMint` implementation, admin auth) beyond the
  capability flags and the bridge-admin grant.
- The **bridge contract** itself (CosmWasm/EVM) and its peg/mint authorization — the cross-chain 6b
  counterpart, off this repo.
- The `ica_migration` capability logic, the genesis-migration tooling (`migrate_genesis.go`), and
  CosmWasm (`x/wasm`) configuration beyond proposal flags.
- Other Fetch.ai org repos (uAgents, CosmPy, etc.) — not blockchains; out of conservation scope.

## Nothing routed privately

No untrusted-input→value path found. fetchd is a thin Cosmos SDK app; its own delta — the v0.53
upgrade handler — is a clean structural migration that does not bend user-balance conservation. The
real conservation logic is inherited from fetchai's cosmos-sdk fork (the stated residual). The
headline trust fact is by-design and correctly scoped: **native FET supply is mintable by the
bridge contract (tokenfactory `SudoMint`), so its conservation rests on the bridge + the Ethereum
peg (a cross-chain 6b seam) — but the admin is deliberately denied `BurnFrom`/`ForceTransfer`, so it
can inflate against the peg yet cannot seize users' funds.** A new §11/§9 data point: a Cosmos chain
where the native-token trust root is a *bridge with capability-restricted tokenfactory mint
authority*. Companion to `AUDIT-GOVERNANCE-CEILING.md` and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9
(the bridge 6b) / §11 (conservation-location: here, relocated to a bridge + an SDK fork).
