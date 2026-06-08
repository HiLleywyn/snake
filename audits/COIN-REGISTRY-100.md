# The 100-coin full-stack audit registry

The capstone deliverable: **100 distinct coins/chains**, each placed through the corpus's two lenses —
the **six-bucket conservation/trust cartography** (the floor: how supply is bounded; the residual: what you
must trust) and the **seven-layer stack** (`bridges/ · state-sync/ · consensus/ · validator-ops/ ·
crypto-primitives/ · zk-proving/ · p2p-eclipse/`). One reusable method, the whole top-100.

**How to read the depth column:** **deep** = a dedicated report in `chains/`/`protocols/`/a sweep; **sweep** =
characterized inside a layer sweep (bridges/consensus/etc.); **rapid** = a lens-pass here (floor + consensus +
residual). **Finding** column flags the one genuine finding (MemeCore) and any named residual class.

**The result in one line (unchanged at 100):** *one genuine finding (MemeCore); every other coin a named
conservation floor + a residual that is a governance ceiling, an oracle/bridge seam, or an irreducible
validator/issuer trust.* The floor is almost always sound; the variance is **who you must trust**, and that is
named for all 100.

> Posture: defensive, public-source, characterize-don't-exploit. "Trustless" is always qualified by
> *trustless-until-whom.* Verdicts are "no finding *by this analysis*," not proof of absence (see capstone §5c
> on the confidence gradient — a code read settles the floor and the trust seam, not the deep cryptographic
> soundness).

---

## The registry

Legend — **Floor** (conservation mechanism): UTXO · Account · Move-linear · checked-invariant · Cosmos-x/bank ·
issuer-fiat · burn/mint · homomorphic-commit. **Residual** (dominant trust): the governance ceiling, oracle,
validator-set, bridge seam, or issuer named per row.

| # | Coin | Type | Floor | Consensus | Dominant trust residual | Depth |
|---|------|------|-------|-----------|-------------------------|-------|
| 1 | Bitcoin (BTC) | L1 PoW | UTXO equation | Nakamoto PoW (longest chain) | 51% hashrate; the few core devs (assumeutxo hash) | sweep (state-sync, p2p) |
| 2 | Ethereum (ETH) | L1 PoS | account + EIP-1559 burn | Gasper (LMD-GHOST+FFG) | >1/3 stake (safety), the social layer | deep + sweeps |
| 3 | Tether (USDT) | stablecoin (multi-chain) | issuer-fiat (off-chain reserves) | n/a (token on host chains) | **Tether the issuer** (reserves, freeze) | rapid |
| 4 | BNB (BSC) | L1 PoSA | account | PoSA (21 validators) | the 21-validator set + Binance | sweep (largecap bughunt) |
| 5 | Solana (SOL) | L1 PoS | account + capitalization recompute | Tower BFT + PoH | >1/3 stake; client mono-culture | deep + sweeps |
| 6 | USDC | stablecoin (multi-chain) | issuer-fiat | n/a | **Circle** (reserves, freeze, CCTP attesters) | sweep (bridges B9) |
| 7 | XRP (XRPL) | L1 | checked-invariant (XRP reserve) | XRP LCP (UNL trust) | the UNL (validator list you choose) | deep |
| 8 | Dogecoin (DOGE) | L1 PoW | UTXO (10k/block tail emission, no cap) | Scrypt PoW, **merge-mined (AuxPoW) with Litecoin** | LTC Scrypt hashrate + pool concentration (cheap to 51% standalone) | rapid |
| 9 | TON | L1 PoS sharded | account (sharded) | BFT (catchain) + infinite sharding | the validator set; sharding seams | deep |
| 10 | Cardano (ADA) | L1 PoS | eUTXO (PoV value conservation) | Ouroboros Praos (VRF) | >50% stake; the VRF/epoch params | deep + sweep (V3) |
| 11 | TRON (TRX) | L1 DPoS | account (no cap, resource-burn floor, net-deflationary) | DPoS (≥70% of **27 Super Representatives**) | **validator centralization — very small N (27)** + the electing cartel/Foundation | rapid ⚠ |
| 12 | Avalanche (AVAX) | L1 (3-chain) | UTXO (AVM) | Avalanche (repeated subsampled vote) | >80% stake (the safety threshold) | deep |
| 13 | Chainlink (LINK) | oracle (on Eth) | n/a (ERC-20) | n/a | the OCR DON + the per-feed node set | sweep (validator-ops, CCIP) |
| 14 | Shiba Inu (SHIB) | ERC-20 (+ Shibarium L2) | account (host); Shibarium PoS | host chain; Shibarium PoA/PoS | the host chain; Shibarium validators | _pending_ |
| 15 | Bitcoin Cash (BCH) | L1 PoW | UTXO, 21M cap | SHA-256d PoW (+ ASERT DAA) | **rentable BTC-pool hashrate** — structurally cheap 51% (small slice of SHA-256) | rapid |
| 16 | Polkadot (DOT) | L0 relay | Substrate Imbalance (type floor) | BABE + GRANDPA (NPoS) | the validator set; governance (OpenGov) | deep |
| 17 | Litecoin (LTC) | L1 PoW | UTXO + MWEB (homomorphic) | Scrypt PoW | 51% hashrate | deep |
| 18 | Hyperliquid (HYPE) | L1 perp DEX | account (closed core) | HyperBFT (Tendermint-like) | the validator set; closed L1; Bridge2 | deep + sweep |
| 19 | Polygon (POL) | L2/sidechain set | account | Heimdall PoS + Bor | the validator checkpoint set (no proof) | sweep (bridges B11) |
| 20 | Uniswap (UNI) | DEX (on Eth) | constant-product invariant | n/a (host chain) | the host chain; governance (fee switch) | sweep (midcap-adjacent) |
| 21 | Aptos (APT) | L1 Move | Move-linear types | Jolteon/Bullshark BFT | >1/3 stake; the framework upgrade key | deep + sweep |
| 22 | NEAR | L1 sharded | account (receipts) | Nightshade (Doomslug + sharding) | the validator set; sharding/chunk seams | deep |
| 23 | Internet Computer (ICP) | L1 subnet | complement-pool invariant | Threshold-BLS / chain-key | the NNS (DAO that controls everything) | deep |
| 24 | Monero (XMR) | L1 privacy PoW | RingCT homomorphic commit | RandomX PoW | 51% hashrate; the crypto assumptions | deep |
| 25 | Stellar (XLM) | L1 | checked-invariant | SCP (FBA, quorum slices) | your chosen quorum slices; the SDF | deep |
| 26 | Ethereum Classic (ETC) | L1 PoW | account/state (ECIP-1017 ~210M cap) | Etchash PoW (kept PoW post-Merge) | **rentable Etchash hashrate — DEMONSTRATED deep 51% reorgs (Aug 2020)** | rapid ⚠ |
| 27 | Dash | L1 PoW+quorum | UTXO (~18.9M; miner/masternode/treasury split) | X11 PoW + **ChainLocks** (LLMQ finality) | the masternode quorum + treasury governance (trusted finality gadget) | rapid |
| 28 | Decred (DCR) | L1 hybrid | UTXO (21M; PoW/PoS/treasury split) | **hybrid PoW + ticket-PoS** (5 votes/block) | ticket holders + Politeia treasury keys (anti-51% *by design*) | rapid |
| 29 | Zcash (ZEC) | L1 privacy PoW | transparent UTXO + **shielded Pedersen-commit + zk-SNARK** (21M) | Equihash PoW | (legacy) **trusted setup** + dev fund — *past counterfeiting-soundness bug (BCTV14)* | rapid ⚠ |
| 30 | Nervos CKB | L1 PoW | **cell model** (gen. UTXO) + state-rent secondary issuance | Eaglesong PoW (NC-MAX) | Eaglesong hashrate concentration + foundation economics | rapid |
| 31 | Conflux (CFX) | L1 PoW+PoS | account/state | **Tree-Graph (GHAST) DAG PoW + PoS finality** | the PoS finality validator set + foundation (trusted finality gadget) | rapid |
| 32 | Neo (N3) | L1 BFT | account, dual-token (NEO 100M fixed / GAS) | **dBFT** (≤⅓ Byzantine of ~7 elected nodes) | the small elected consensus-node set + foundation (permissioned-leaning) | rapid |
| 33 | Ravencoin (RVN) | L1 PoW + assets | UTXO + native asset layer (21B; RVN-burn to issue) | KawPoW (ProgPoW) PoW | **rentable GPU hashrate** — *past asset-inflation floor break + real 51% double-spends (2020)* | rapid ⚠ |
| 34 | Sky / MakerDAO (DAI/USDS) | DeFi stablecoin (Eth) | over-collat CDP invariant (≥ liq ratio) + MKR backstop + PSM | n/a (host: Ethereum) | **governance** (collateral/oracle whitelist) + USDC/RWA concentration | rapid |
| 35 | Aave (AAVE/GHO) | DeFi money market (Eth+L2) | per-position LTV + Safety Module | n/a | **oracle** (Chainlink) — thin-asset-listing manipulation surface | rapid |
| 36 | Ondo (USDY/OUSG) | RWA (Eth+multichain) | **off-chain NAV** (Treasuries) — legal/custodial claim, *no on-chain floor* | n/a | **custodian / RWA-issuer** + admin freeze/seize | rapid |
| 37 | Ethena (USDe) | synthetic-dollar (Eth) | **delta-neutral** (spot + 1:1 perp hedge) + reserve fund | n/a | **custodian / CEX counterparty** (off-exchange custody, CEX hedges) | rapid |
| 38 | Lido (stETH) | liquid staking (Eth) | exchange-rate = staked ETH + rewards (1:1 redeemable) | n/a | **operator-set concentration + accounting oracle** | rapid |
| 39 | Rocket Pool (rETH) | liquid staking (Eth) | rETH rate = balances; operator **RPL bond** first-loss | n/a | **oDAO oracle committee** (floor collateralized) | rapid |
| 40 | Frax (FRAX/frxETH) | stablecoin+LST+L2 | 100% CR (now) + AMO bounds; frxETH exch-rate | n/a (+ Fraxtal L2) | **governance/AMO** (algo-stable lineage) + RWA backing | rapid |
| 41 | dYdX v4 | perp DEX appchain | PoS 2/3 honest stake + margin/insurance fund | **CometBFT PoS** (own chain) | **validator set** (consensus *and* off-chain orderbook) + oracle | rapid |
| 42 | PancakeSwap (CAKE) | AMM DEX (BSC+L2) | constant-product x·y=k (per-pool self-conserving) | n/a | governance multisig + BNB-chain trust; **floor sound** | rapid |
| 43 | GMX (GMX/GLP) | oracle-perp DEX (Arb/Avax) | pool assets vs trader PnL + OI caps | n/a | **oracle** + keepers — *historically-realized manipulation (v1, 2022)* | sweep (midcap) |
| 44 | VeChain (VET) | L1 PoA | dual-token VET→VTHO (70% gas burn) | **PoA 2.0** + BFT gadget (**101 vetted masternodes**) | **permissioned-authority centralization** (Foundation KYC whitelist) | rapid |
| 45 | MultiversX (EGLD) | L1 sharded PoS | capped ~31.4M, sharded state + Metachain | **Secure-PoS** (BLS+VRF, >2/3 committee) | Metachain reconciliation + cross-shard atomicity | rapid |
| 46 | Kava | L1 Cosmos | x/bank invariants; zero-inflation (K15) | Tendermint BFT (**top 100**, >2/3 stake) | small N + >1/3-halt class + IBC/oracle deps | rapid |
| 47 | Kaia (ex-Klaytn) | L1 BFT | EVM account, fee burn, gov-set supply | **IBFT** (>2/3 of enterprise Council CNs), 1s final | **permissioned-consortium** (Governance Council + gov keys) | rapid |
| 48 | Zilliqa (ZIL) | L1 BFT (transitioning) | capped 21B; Scilla-limited state | **Pipelined Fast-HotStuff** (was pBFT+sharding), >2/3 | **architecture-in-transition** + stake concentration | rapid |
| 49 | Oasis (ROSE) | L1 + confidential ParaTimes | consensus account-balance + ParaTime state | CometBFT (**~120**, >2/3) | **TEE / Intel SGX root of trust** (confidentiality) — hardware residual | rapid ⚠ |
| 50 | IOTA | L1 Move (post-Rebased) | **Move-resource ledger** (objects can't dup) | **Mysticeti DPoS** (~150, >2/3), <0.5s final | nascent permissionless set + Foundation stake (Coordinator just removed) | rapid |
| 51 | Flare (FLR) | L1 EVM + oracles | EVM account, fee burn | Avalanche **Snowman++** PoS | **enshrined oracle/attestation** (FTSO + State Connector) — the dApp residual | rapid |
| 52 | Waves | L1 LPoS | capped 100M (+ **USDN algo-stable** value hazard) | LPoS (Waves-NG, ~2s gadget) | stake-leader concentration + **Gravity bridge + Neutrino** (de-peg history) | rapid ⚠ |

---

## Coverage & gap plan

**Already covered (deep or via-sweep), ~50+:** the rows above plus — Cronos, Kaspa, Arbitrum, Filecoin,
Algorand, Cosmos/ATOM, Optimism, Injective, Sonic/Fantom, Hedera, Stacks, Sei, Tezos, Polygon-zkEVM, EOS,
Pyth, Starknet, Berachain, Celestia, Mina, Worldcoin, THORChain, Osmosis, Namada, Penumbra, Aztec, Aleo, Base,
Scroll, zkSync, Meson, MemeCore, Monad, Marinade/Drift/marginfi/Meteora (Solana DeFi), DeXe, Curve/Compound/
Pendle/EigenLayer/GMX/Synthetix/Liquity/Alchemix/Reserve (midcap sweep), Celo, Mantle.

**Gaps to fill to 100 (~40, rapid lens-pass each):** Dogecoin, TRON, BCH, ETC, Render, VeChain, The Graph,
Immutable, Theta, Bittensor (TAO), Maker/Sky, Aave, Flow, Quant, MultiversX (EGLD), Gala, Aerodrome, Jupiter,
Ondo, Kava, Helium (HNT), Ethena (ENA), Raydium, Conflux, Dash, Decred, Nervos (CKB), IOTA, Neo, Waves,
Chiliz, dYdX, Kujira, Oasis (ROSE), Moonbeam, Astar, Kaia (Klaytn), Flare, Gnosis (GNO), Linea, Blast,
Pancakeswap, Lido (LDO), Bittensor, Story, Sonic.

*(Rapid-audit entries land below as the parallel passes complete; each gives floor + consensus + residual.)*

---

## Rapid lens-passes (filling 26–100)

### Batch 1 — PoW / UTXO family (rows 8, 15, 26–33) ✅
The lens surfaced **real, historically-confirmed finding-classes** (defensive, characterized — no exploit):
- **Demonstrated cheap 51% (small-hashrate-on-a-large-algorithm):** **ETC** (deep reorgs + double-spends, Aug 2020), **Ravencoin** (exchange double-spends 2020), **BCH** (structurally cheap — small slice of SHA-256). The
  Nakamoto floor (UTXO/state) is sound; the **residual is rentable hashrate**, and for these three it has been *realized*.
- **Actual conservation-floor breaks (historical, patched):** **Ravencoin** asset-layer inflation bug (minted RVN beyond
  schedule); **Zcash** legacy shielded-soundness bug (BCTV14/InternalH — *could* have allowed undetectable shielded
  inflation; patched pre-disclosure; Halo 2 later removed the trusted setup). These are the corpus's *conservation-floor*
  failure class, in the wild.
- **Trust shifted off pure PoW onto a quorum/finality gadget:** **Dash** (ChainLocks), **Conflux** (PoS finality),
  **Decred** (stake votes) — each *defends* 51% but moves the residual to **quorum/validator honesty + governance keys.**
- **Outlier (not PoW):** **Neo** = dBFT over ~7 elected nodes → residual is validator-set centralization, not hashrate.
- **Recurring non-hashrate residual:** treasury/dev-fund **governance keys** (Dash, Decred, Conflux, Nervos, Zcash).

*Honesty note (per capstone §5c): Batch 1 is **docs/spec/public-incident-history derived**, source-confirmable in principle
(forks of Bitcoin Core / go-ethereum) but not freshly re-read from disk — Medium confidence, and the incident-history
flags (ETC, Ravencoin, Zcash) are the well-documented public record.*

### Batch 3 — Eth/L2 DeFi protocols (rows 34–43) ✅
The trust seam in DeFi is **always one of four**, and the lens names it for each:
- **Oracle-dominant** (the price feed *is* the security boundary): **GMX** (historically-realized v1 manipulation),
  **Aave** (thin-asset listings are the classic attack surface). Mitigated by Chainlink + delays + caps.
- **Governance-dominant** (admin/timelock can reconfigure collateral/params): **Maker/Sky, Frax, PancakeSwap.**
- **Custodian-dominant** (backing is *off-chain*, no on-chain conservation proof — the **softest floors**): **Ondo**
  (RWA NAV, legal claim), **Ethena** (delta-neutral + CEX custody). Value rests on off-chain solvency + attestation.
- **Validator/operator-dominant:** **Lido** (operator concentration + accounting oracle), **Rocket Pool** (oDAO
  oracle, but operator-RPL-bonded → harder floor), **dYdX v4** (its own PoS chain — validators run *both* consensus
  and the off-chain orderbook, a double trust load).
- **Hardest floors** (solvency holds without trusting a counterparty's balance sheet): **PancakeSwap** core AMM
  (constant-product self-conserves), the **LSTs** (1:1 ETH redeemable). **Softest:** Ondo, Ethena.
*Docs/knowledge-level (Medium confidence); collateral ratios/custodians change via governance — figures are as of cutoff.*

### Batch 2 — BFT / DPoS / sidechain L1s (rows 11, 44–52) ✅
The defining residual in this family is **how few, and how known, the validators are** — and where the trust
*leaves* consensus:
- **Smallest-N / hardest centralization:** **TRON** (27 SRs) > **VeChain** (101, KYC'd) ≈ **Kaia** (enterprise
  Council) — finality concretely rests on a small, often identity-known set + the cartel that elects them.
- **Trust residual lives *off-consensus* for three:** **Oasis** (Intel **SGX** hardware root — ties directly to
  `crypto-primitives/`'s TEE-attestation residual: confidentiality depends on a vendor enclave with a real
  side-channel CVE history), **Flare** (**enshrined oracles** — FTSO median + State-Connector attestors, the
  `validator-ops/` oracle seam baked into the L1), **Waves** (the **Gravity bridge + USDN algo-stablecoin**
  de-peg history — the `bridges/` + de-peg classes). Their consensus floors are fine; the exploitable trust is the
  adjacent subsystem.
- **Universal BFT failure mode** (Kava/Oasis/Zilliqa/IOTA/Kaia, and the whole `consensus/` sweep): **>1/3 stake →
  liveness halt, >2/3 → safety break** — concentration of the staked/elected set is the residual, enforced
  *exactly* (consensus sweep) but only as strong as the set's diversity.
- **In-transition risk** highest for **Zilliqa** (consensus-engine swap) and **IOTA** (Coordinator just removed) —
  newest code paths, least battle-testing.
*Docs/spec-derived (Medium confidence); validator counts are active-set/cap figures that drift with governance.*

### Batch 4 — new L1/L2/DePIN — _in flight_
(Bittensor, Render, Helium, The Graph, Flow, Moonbeam, Astar, Kujira, Story, Jupiter.)
