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
| 14 | Shiba Inu (SHIB) | ERC-20 + Shibarium L2 | account (SHIB inherits Ethereum's floor); Shibarium = Heimdall/Bor PoS | host **Ethereum** (token) + **Shibarium** validator set (L2) | SHIB has no own floor (ERC-20); Shibarium = small-validator-set L2 + the SHIB↔Shibarium bridge | rapid |
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
| 53 | Bittensor (TAO) | L1 DePIN/AI | account (21M cap, halving) | Subtensor PoS (Substrate) + **Yuma Consensus** scoring | **subjective validator scoring** gates reward-mint (attestation-not-proof) + root subnet | rapid |
| 54 | Render (RNDR) | DePIN (Solana) | burn-mint-equilibrium (render-work burns RNDR) | host (Solana) | **off-chain proof-of-render** (job verification attested, not proven) + foundation | rapid |
| 55 | Helium (HNT) | DePIN (Solana) | account (HNT→Data Credits burn; PoC mint) | host (Solana) | **proof-of-coverage** oracle — historically *gameable* (attestation-not-proof) | rapid ⚠ |
| 56 | The Graph (GRT) | indexing (Eth/Arb) | account (indexing rewards minted; query fees) | host | indexer/curator economic game + the **Arbitrator** (dispute resolution) | rapid |
| 57 | Flow (FLOW) | L1 | **Cadence resource types** (Move-like linear) | multi-role HotStuff (collect/consensus/exec/verify) | the multi-role node sets + foundation (node-operator permissioning) | rapid |
| 58 | Moonbeam (GLMR) | Polkadot parachain | account EVM | **Polkadot shared security** (collators + relay validators) | relay-chain validators (inherited) + the collator set | rapid |
| 59 | Astar (ASTR) | Polkadot parachain | account (EVM+WASM) | Polkadot shared security + collators | relay validators + collators + dApp-staking governance | rapid |
| 60 | Kujira (KUJI) | L1 Cosmos | x/bank (+ USK over-collat stablecoin) | Tendermint BFT (>2/3) | the validator set + its own DeFi (FIN/USK) collateral | rapid |
| 61 | Story (IP) | L1 Cosmos+EVM | account | CometBFT PoS (>2/3) | validator set + **off-chain IP/licensing attestation** (the IP graph) | rapid |
| 62 | Jupiter (JUP) | DEX aggregator (Solana) | n/a (routes AMMs; no pooled custody) | host (Solana) | governance + (Jupiter **Perps** = oracle + JLP pool, GMX-class) | rapid |
| 63 | Cronos (CRO) | L1 Cosmos-EVM | account | Ethermint/Tendermint PoS (>2/3) | the validator set + Crypto.com governance | sweep (largecap) |
| 64 | Kaspa (KAS) | L1 blockDAG PoW | UTXO + **GHOSTDAG** ordering | kHeavyHash PoW (parallel blocks) | 51% hashrate (the DAG ordering is canonicalize-before-consensus) | deep |
| 65 | Arbitrum (ARB) | L2 optimistic | account; withdrawal = confirmed node | **BoLD fraud proof** + 7d window | the dispute-game system + Security Council | sweep (bridges B11) |
| 66 | Filecoin (FIL) | L1 storage | account + **storage-collateral** | Expected Consensus (PoSt) | the storage-proof (PoRep/PoSt) + the actor governance | deep |
| 67 | Algorand (ALGO) | L1 Pure-PoS | **`totals.All()` recomputed invariant** | PPoS (VRF sortition), no fork | >2/3 of *online* stake (the VRF + the relays) | deep |
| 68 | Cosmos Hub (ATOM) | L1 | **x/bank** (conserve-by-construction) | Tendermint BFT (>2/3) | the validator set + IBC counterparties | deep + sweep |
| 69 | Optimism (OP) | L2 optimistic | account (lock-release via ETHLockbox) | **fault proof (Cannon)** + 7d + Security Council | the dispute-game + the Council (vkey/governance) | deep + sweep (B6) |
| 70 | Injective (INJ) | L1 Cosmos | x/bank | Tendermint BFT (>2/3) | validator set + the (partly off-chain) orderbook | deep |
| 71 | Sonic (S) | L1 DAG | account | **Lachesis aBFT** (DAG, sortedArray canonicalize) | the validator set | sweep (largecap) |
| 72 | Hedera (HBAR) | L1 | **zero-sum journal** invariant | Hashgraph aBFT (gossip-about-gossip) | the **Governing Council** (permissioned ~30 enterprises) | deep |
| 73 | Stacks (STX) | L1 (BTC-anchored) | **caller-scoped post-conditions** | PoX (Nakamoto, anchored to Bitcoin) | the sBTC signer set + the BTC anchor | sweep (state-sync, sBTC) |
| 74 | Sei (SEI) | L1 parallel-EVM | account + **OCC** ordered-commit | Tendermint BFT (>2/3) | the validator set | deep |
| 75 | Tezos (XTZ) | L1 | **typed source/sink** conservation | Tenderbake (LPoS) | bakers (>2/3) + **self-amendment governance** | deep |
| 76 | Polygon zkEVM | L2 ZK | account; claim vs proven exit root | **validity (ZK) proof** + verifier | the verifier-upgrade governance (RBAC/timelock) | sweep (bridges B11) |
| 77 | EOS / Vaulta (EOS) | L1 DPoS | **RAM Bancor** + account | DPoS (**21 Block Producers**) | the 21 BPs | deep |
| 78 | Pyth (PYTH) | pull oracle | n/a | n/a (Solana/Pythnet) | the publisher set + Wormhole guardians (the attestation) | sweep (validator-ops) |
| 79 | Starknet (STRK) | L2 ZK (Cairo) | account; withdraw via proven message | **STARK validity proof** | the STARK verifier (in StarknetCore) + governance | sweep (bridges B11) |
| 80 | Berachain (BERA) | L1 | account + **Proof-of-Liquidity** | BeaconKit/CometBFT (>2/3) | the validator set + the PoL emission/bribe market | deep |
| 81 | Celestia (TIA) | L1 DA | account + **DAS** (data-availability sampling) | Tendermint BFT (>2/3) | the validator set; DA = sample-or-fraud-proof (Blobstream = committee) | sweep (DA, S7/B21) |
| 82 | Mina (MINA) | L1 succinct | account + **recursive-SNARK** state (~22 KB) | Ouroboros Samasika PoS | the SNARK soundness + the prover + >50% stake | deep |
| 83 | Worldcoin (WLD) | identity (World Chain) | account + **Orb proof-of-personhood** (ZK tree) | host (OP-stack) | the **Orb operator** (off-chain biometric) + the ZK Semaphore tree | deep |
| 84 | THORChain (RUNE) | L1 cross-chain | continuous-pool + **TSS vaults** (native assets) | Tendermint BFT (>2/3) | the validator **TSS** (vault control, >2/3 keyshare) | sweep (midcap, bridges) |
| 85 | Osmosis (OSMO) | L1 Cosmos DEX | x/bank + superfluid | Tendermint BFT (>2/3) | the validator set + the AMM/superfluid invariants | deep + sweep |
| 86 | Monad (MON) | L1 parallel-EVM | account + **OCC** ordered-commit | **MonadBFT** (>2/3, `2/3+1`) | the validator set | deep |
| 87 | Namada (NAM) | L1 privacy | **MASP** shielded (homomorphic) | CometBFT PoS (>2/3) | the MASP crypto + validator set | deep |
| 88 | Penumbra (UM) | L1 privacy | shielded (ZK amounts) | Tendermint BFT (>2/3) | the ZK soundness + validator set | deep |
| 89 | Aleo (ALEO) | L1 ZK | account + **snarkVM** (ZK execution) | AleoBFT (Bullshark-like) | the prover/coinbase puzzle + the ZK + validators | deep |
| 90 | Aztec | L2 ZK privacy | shielded notes (ZK) | **validity proof** + sequencer | the proof + the sequencer/governance | deep |
| 91 | Base | L2 optimistic | account (OP-stack) | **fault proof** + 7d + Security Council | the dispute-game + Coinbase/Council | deep + sweep |
| 92 | Scroll | L2 ZK | account; withdraw vs proven root | **validity (ZK) proof** (withdrawRoot = public input) | the verifier-upgrade governance | sweep (bridges B11) |
| 93 | zkSync Era (ZK) | L2 ZK | account; finalize vs executed-batch root | **validity (ZK) proof** (verify→execute→withdraw) | the verifier-upgrade governance (CTM + timelock) | sweep (bridges B11) |
| 94 | EigenLayer (EIGEN) | restaking (Eth) | n/a (restaked ETH) | n/a (AVS layer) | the **AVS slashing** (only as real as the slasher wired) + Eth | sweep (validator-ops B19) |
| 95 | Synthetix (SNX) | DeFi synths (Eth/OP) | **debt-pool** invariant (pooled-counterparty) | host | **oracle** (price feeds) + governance (the SCCP/SIP) | sweep (midcap) |
| 96 | Curve (CRV) | AMM (Eth+) | **StableSwap** invariant (per-pool self-conserving) | host | governance (the gauge/admin) + oracle (for lending) | sweep (midcap) |
| 97 | Compound (COMP) | DeFi money market | per-position collateral-factor invariant | host | **oracle** + governance (the Timelock) — *donation-attack class noted* | sweep (midcap) |
| 98 | Pendle (PENDLE) | yield tokenization | PT/YT split (principal+yield = asset) | host | **oracle** (the yield-source rate) + governance | sweep (midcap) |
| 99 | Reserve (RSR) | DeFi stablecoin | **RToken basket** over-collateralization | host | the basket composition + governance (the RSR backstop) | sweep (midcap) |
| 100 | Canton (CC) | L1 privacy/RWA | privacy-enabled ledger (sub-transaction privacy) | **Splice/CometBFT** (super-validators) | the **super-validator** set + the closed app-provider domains | deep |

---

## Coverage

**100 of 100 rows filled.** Depth split: **deep** (dedicated report) + **sweep** (layer-sweep entry) for the
~55 already-audited chains/protocols; **rapid** (docs/spec/incident-history lens-pass) for the ~45 added here to
complete the top-100. Beyond the 100, the corpus also covers chains/protocols that didn't make a top-100 row but
appear in the sweeps (Meson, Canton/Splice, Marinade/Drift/marginfi/Meteora, DeXe, Liquity/Alchemix, Mantle,
Celo, Polkadot relay, etc.) — see [`README.md`](README.md) for the full index.

---

## Rapid lens-pass notes (per batch) — how the gap rows were characterized

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

### Batch 4 — new L1/L2/DePIN/appchain (rows 53–62) ✅
The novel residual here is the **DePIN attestation gap** — *is the reward-minting gated by a real proof, or by an
off-chain attestation of physical work?* — almost always the latter:
- **Bittensor** (subjective **Yuma** validator scoring decides miner rewards), **Helium** (**proof-of-coverage**,
  historically *gameable*), **Render** (off-chain render-job verification) — the DePIN reward is **attested, not
  proven**, which is the `bridges/`-style "proven vs. attested" axis at the *minting* layer. **The Graph** is the
  cleaner case (disputes resolved by an Arbitrator). **Story** adds off-chain IP/licensing attestation.
- **Parachains** (Moonbeam, Astar) inherit **Polkadot relay-chain security** — the residual is the relay validators,
  not the parachain. **Flow** uses Cadence resource types (a Move-like linear floor) with a multi-role node split.
  **Kujira** is standard Cosmos BFT + its own collateral. **Jupiter** is a Solana aggregator (no custody) whose only
  sharp residual is Jupiter Perps' oracle (GMX-class).

### Rows 63–100 — the already-deep-audited corpus, folded in ✅
Rows 63–100 are the **chains/protocols already given a dedicated report or layer-sweep entry** (linked in
`README.md`): the conservation-mechanism families (UTXO/DAG, x/bank, Move-linear, checked-invariant, zero-sum
journal, RAM-Bancor, recursive-SNARK, MASP/ZK-shielded, storage-collateral, caller-scoped post-conditions), the
rollups (validity vs. fraud proof + the verifier/Council governance ceiling), the privacy chains, and the DeFi
midcap sweep. Each row's depth column points at where the full read lives.

---

## The 100, synthesized — what a top-100 audit through one lens actually shows

**Conservation floor:** sound almost everywhere, and it comes in a small number of *kinds* — UTXO/DAG (BTC, BCH,
DOGE, LTC, Kaspa, Dash, Decred, Zcash, Nervos, Ravencoin), account+state (the EVM/BFT L1s), **type-enforced** (Move:
Aptos/Sui/IOTA; Cadence: Flow; linear types make conservation a *compiler* guarantee), **checked-invariant** (Algorand
`totals.All()`, Hedera zero-sum, XRPL/Stellar), **conserve-by-construction** (Cosmos x/bank), **homomorphic/ZK**
(Monero, Zcash, Namada, Penumbra, Mina), **issuer-fiat** (USDT, USDC), and **collateral invariants** (the DeFi rows).

**The variance is *always* the residual — and it sorts into exactly the corpus's classes:**
1. **Hashrate / stake concentration** — the PoW small-coins (ETC, BCH, Ravencoin have *realized* 51%), the small-N
   BFT/DPoS sets (TRON 27, EOS 21, Neo ~7, the permissioned councils).
2. **Governance ceiling** — the rollup verifier-upgrade keys + Security Councils, the DeFi admin/timelocks, the
   treasury/dev-fund keys, ICP's NNS, Tezos self-amendment.
3. **Oracle / attestation seam** — the DeFi oracles (Aave, GMX, Compound, Synthetix), the DePIN proofs-of-physical-work
   (Helium, Render, Bittensor), Flare's enshrined oracles, the pull oracles (Pyth).
4. **Bridge / cross-chain & custodian** — the wrapped-asset bridges, Lombard-class custody, Ondo/Ethena off-chain
   backing, Waves's Gravity bridge, the TSS vaults (THORChain).
5. **Hardware / proof root** — Oasis's SGX, the ZK chains' proof soundness + the trusted setup (Zcash legacy).

**The one genuine finding remains MemeCore.** Across 100 coins, the floor held (the historical floor *breaks* —
Ravencoin asset-inflation, Zcash BCTV14 — were upstream and patched; not found live here), and **every coin reduced to
a named conservation floor + a residual that is a hashrate/stake threshold, a governance ceiling, an oracle/attestation
seam, a bridge/custodian, or a hardware/proof root.** No bare "safe"; "trustless" qualified by *trustless-until-whom*
for all 100. The Hyperliquid Bridge2 duplicate-set item (`bridges/AUDIT-HYPERLIQUID-BRIDGE.md`, Medium/latent, with a
passive verification tool) is the sharpest *defense-in-depth* residual surfaced, and it corrected a prior over-claim of
my own — the method, applied to the method.

*Confidence (per capstone §5c): rows with a **deep**/**sweep** depth are source-read; **rapid** rows are
docs/spec/incident-history derived (Medium) — the incident flags (ETC, Ravencoin, Zcash, GMX, Waves) are the documented
public record, the consensus/floor families are robust, and live mainnet parameters (validator counts, custodians,
collateral ratios) drift with governance and should be re-checked against current state before relying on a figure.*
