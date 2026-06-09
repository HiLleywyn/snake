# Audits — directory

The full corpus: **~80 systems** audited with one reusable lens (six-bucket trust cartography +
conservation/solvency floor / governance ceiling / equivalence), now spanning ~40 chains, the full node
stack, bridges, and **~20 DeFi/infra/privacy verticals**. **One genuinely actionable finding** (MemeCore,
[`finding-memecore/`](finding-memecore/AUDIT-MEMECORE-POSA.md)); everything else resolved to a sound floor
+ a named residual.

**The map → [`CORPUS-INDEX.md`](CORPUS-INDEX.md)** (laws · the 5-class residual taxonomy · the own-vs-delete
dial · every doc by vertical). **The synthesis → [`methodology/AUDIT-CAPSTONE.md`](methodology/AUDIT-CAPSTONE.md)**
(§4 + §5a–§5j). Also: [`COIN-REGISTRY-100.md`](COIN-REGISTRY-100.md) (the 100-coin registry) ·
[`../DESIGN-PRINCIPLES.md`](../DESIGN-PRINCIPLES.md) (the constructive mirror) ·
[`methodology/AUDIT-METHODOLOGY.md`](methodology/AUDIT-METHODOLOGY.md) (the lens).

---

## 🧭 methodology/ — the lens and the synthesis
| File | What it is |
|---|---|
| [AUDIT-METHODOLOGY.md](methodology/AUDIT-METHODOLOGY.md) | The six-bucket trust-cartography lens + three coordinates |
| [AUDIT-METHODOLOGY-CHECKLIST.md](methodology/AUDIT-METHODOLOGY-CHECKLIST.md) | The per-target checklist |
| [AUDIT-METHODOLOGY-RETROSPECTIVE.md](methodology/AUDIT-METHODOLOGY-RETROSPECTIVE.md) | §1–11: equivalence, conservation ladder, governance ceiling |
| [AUDIT-CAPSTONE.md](methodology/AUDIT-CAPSTONE.md) | **The synthesis** — every target, the spectrums, the laws, the fail-safe-substrate boundary (§5b) |
| [AUDIT-CONNECTIONS-AND-SELFCHECK.md](methodology/AUDIT-CONNECTIONS-AND-SELFCHECK.md) | Cross-audit connections + epistemic self-audit |
| [AUDIT-REASONER-EPISTEMOLOGY.md](methodology/AUDIT-REASONER-EPISTEMOLOGY.md) | Recompute-don't-trust-the-summary discipline |
| [AUDIT-GOVERNANCE-CEILING.md](methodology/AUDIT-GOVERNANCE-CEILING.md) | The governance-ceiling spectrum (admin → vote → self-amendment) |
| [AUDIT-WEBAPP-GENERALIZATION.md](methodology/AUDIT-WEBAPP-GENERALIZATION.md) | Generalizing the lens beyond chains |
| [AUDIT-FINDINGS.md](methodology/AUDIT-FINDINGS.md) | Running findings log |

## 🎯 finding-memecore/ — the one finding
| File | What it is |
|---|---|
| [AUDIT-MEMECORE-POSA.md](finding-memecore/AUDIT-MEMECORE-POSA.md) | **The corpus's only finding** (5 passes): unsorted map → consensus-critical system call + swallowed error. Latent consensus landmine; disclosed fix-first. |

## 🔨 bug-hunts/ — stress-testing the "one finding" claim
| File | What it is |
|---|---|
| [AUDIT-LARGECAP-BUGHUNT.md](bug-hunts/AUDIT-LARGECAP-BUGHUNT.md) | The MemeCore lens applied to 6 large-cap consensus deltas (BSC, Polygon, Sonic, Celo, Cronos, Berachain) — all clean |
| [AUDIT-RECENT-COMMITS-HUNT.md](bug-hunts/AUDIT-RECENT-COMMITS-HUNT.md) | 15 fresh-code reads (geth/reth/op-stack + Solana/Sui/Aptos/Cosmos/Celestia); the real recent bugs all fail safe |
| [AUDIT-MIDCAP-SWEEP.md](bug-hunts/AUDIT-MIDCAP-SWEEP.md) | 9 distinct DeFi mechanisms (Synthetix, Pendle, THORChain, Liquity, Alchemix, Reserve, EigenLayer, Curve, GMX) + fork-diffs |
| [AUDIT-ROLLUP-ORACLES-RESIDUALS.md](bug-hunts/AUDIT-ROLLUP-ORACLES-RESIDUALS.md) | Opening the named oracles: Optimism Cannon FPVM + zkSync Verifier |
| [AUDIT-FORK-AND-CONTEST-HUNT.md](bug-hunts/AUDIT-FORK-AND-CONTEST-HUNT.md) | Active fork-diff + invariant hunt across 26 targets in 6 batches (forks, contests, then **live bounty-eligible** Across/Euler v2/Fluid); discriminates across the full taxonomy — 21 clean, 4 contest-known, 1 live-disclosed-redacted |
| [AUDIT-CROSS-VM-LIVE-HUNT.md](bug-hunts/AUDIT-CROSS-VM-LIVE-HUNT.md) | Beyond Solidity: live hunts on **6 different VMs/paradigms** — crvUSD (**Vyper**), Kamino (**Solana**), Privacy Pools (**zk**), Cetus (**Move**/Sui), Osmosis (**Cosmos-SDK**/Go), EntryPoint+Kernel (**ERC-4337**) — each on its own native bug taxonomy; all clean |
| [AUDIT-OFFCHAIN-INFRA-HUNT.md](bug-hunts/AUDIT-OFFCHAIN-INFRA-HUNT.md) | Dropping to the **engine layer** (Go): CometBFT (BFT **consensus**-safety — fork/halt taxonomy) + mev-boost (**PBS** block-building trust); both clean, recent CVEs confirmed patched |
| [AUDIT-CHAIN-SECURITY-FRONTIER.md](bug-hunts/AUDIT-CHAIN-SECURITY-FRONTIER.md) | The highest altitude: **Reth** (execution client — chain-split/DoS), **OP Stack FaultDisputeGame** (interactive **fraud proof**), **Babylon** (**Bitcoin-staking** hybrid); a bug = fork / forged withdrawal / unslashable BTC. All clean |
| [AUDIT-VERIFICATION-LAYER-HUNT.md](bug-hunts/AUDIT-VERIFICATION-LAYER-HUNT.md) | The **verify-external-truth** cut: **Lighthouse** (beacon/attestation + fork-choice), **tBTC v2** (BTC SPV bridge — Σ tBTC ≡ SPV-proven BTC), **Automata DCAP** (on-chain **TEE attestation** — HEAD *is* the cert-chain-bypass fix). All clean |
| [AUDIT-COORDINATION-LAYER-HUNT.md](bug-hunts/AUDIT-COORDINATION-LAYER-HUNT.md) | **Admission gates**: **Hyperlane** (interop message verify), **Celestia** (NMT/DA soundness — GHSA-r9fq completeness bypass present-and-patched), **Arbitrum DAO** (governance + cross-chain timelock). All clean |
| [AUDIT-SECURITY-PRIMITIVES-HUNT.md](bug-hunts/AUDIT-SECURITY-PRIMITIVES-HUNT.md) | **The bottom turtles**: **Pyth** (pull-oracle authenticity), **ZF FROST** (threshold-Schnorr unforgeability — RFC 9591 Drijvers defense), **EigenLayer** (slashable-stake conservation — the two delays set equal). All clean |

## ⛓️ chains/ — L1 / L2 / rollup / privacy / cross-chain
Grouped by conservation mechanism:

**Type-system floors (linear types / imbalance):** [Sui](chains/AUDIT-SUI-SIX-BUCKET.md) ·
[Aptos](chains/AUDIT-APTOS-COIN.md) · [Polkadot](chains/AUDIT-POLKADOT-IMBALANCE.md)
**Recomputed/checked invariants:** [Algorand](chains/AUDIT-ALGORAND-TOTALS.md) ·
[XRPL](chains/AUDIT-XRPL-INVARIANTS.md) · [Stellar](chains/AUDIT-STELLAR-INVARIANTS.md) ·
[Berachain](chains/AUDIT-BERACHAIN-POL.md) · [ICP](chains/AUDIT-ICP-LEDGER.md) ·
[Tezos](chains/AUDIT-TEZOS-TOKEN.md) · [Hedera](chains/AUDIT-HEDERA-ZEROSUM.md)
**UTXO equation:** [Cardano](chains/AUDIT-CARDANO-POV.md) · [Avalanche](chains/AUDIT-AVALANCHE-AVM.md) ·
[Kaspa](chains/AUDIT-KASPA-GHOSTDAG.md) · [Litecoin+MWEB](chains/AUDIT-LITECOIN-SIX-BUCKET.md)
**Account / EVM:** [Ethereum (EIP-1559 burn)](chains/AUDIT-ETHEREUM-EIP1559.md) ·
[Cosmos x/bank](chains/AUDIT-COSMOS-BANK.md) · [fetchd](chains/AUDIT-FETCHD-COSMOS.md) ·
[Base (OP Stack)](chains/AUDIT-BASE-SIX-BUCKET.md) · [EOS RAM](chains/AUDIT-EOS-RAM-BANCOR.md)
**Parallel-execution OCC + BFT:** [Monad](chains/AUDIT-MONAD-PARALLEL.md) ·
[MonadBFT](chains/AUDIT-MONADBFT-CONSENSUS.md) · [Sei](chains/AUDIT-SEI-OCC.md)
**Rollups (validity / fraud):** [zkSync](chains/AUDIT-ZKSYNC-VALIDITY-PROOF.md) ·
[Optimism](chains/AUDIT-OPTIMISM-FRAUD-PROOF.md)
**Async / sharded:** [NEAR](chains/AUDIT-NEAR-RECEIPTS.md) · [TON](chains/AUDIT-TON-BOUNCE.md)
**Cross-chain seams (→ see [bridges/](#-bridges--the-weak-link-audited)):** [Canton/Splice](chains/AUDIT-CANTON-SPLICE.md)
**Storage / caller-scoped:** [Filecoin](chains/AUDIT-FILECOIN-ACTORS.md) ·
[Stacks (post-conditions)](chains/AUDIT-STACKS-POSTCONDITIONS.md)
**ZK / privacy chains:** [Namada MASP](chains/AUDIT-NAMADA-MASP.md) ·
[Namada call-sites](chains/AUDIT-NAMADA-CALLSITES.md) · [Penumbra](chains/AUDIT-PENUMBRA.md) ·
[Penumbra amounts](chains/AUDIT-PENUMBRA-AMOUNT-SWEEP.md) ·
[Penumbra DEX/stake](chains/AUDIT-PENUMBRA-DEX-STAKE.md) · [Aztec rep](chains/AUDIT-AZTEC-PASS1-REPRESENTATION.md) ·
[Aztec conservation](chains/AUDIT-AZTEC-PASS2-CONSERVATION.md) · [Aztec 6b](chains/AUDIT-AZTEC-AVM-BUCKET6-TEST.md) ·
[Aleo/Mina](chains/AUDIT-ALEO-SIX-BUCKET.md) · [Mina](chains/AUDIT-MINA-SIX-BUCKET.md) ·
[Monero RingCT](chains/AUDIT-MONERO-RINGCT.md)

## 🌉 bridges/ — the weak link, audited
The corpus's highest-risk category (every nine-figure hack lives at the settlement seam). Two-question
lens: **who authorizes the mint, and what does the mint check.**
| File | What it is |
|---|---|
| [AUDIT-BRIDGES-SWEEP.md](bridges/AUDIT-BRIDGES-SWEEP.md) | **The dedicated sweep** — bridge trust-model taxonomy + per-bridge contract reads (B1 Wormhole, …) |
| [AUDIT-BRIDGES-SIX-BUCKET.md](bridges/AUDIT-BRIDGES-SIX-BUCKET.md) | Wormhole / LayerZero / Hyperlane through the six-bucket lens |
| [AUDIT-MESON-FREETUNNEL.md](bridges/AUDIT-MESON-FREETUNNEL.md) | Meson HTLC (trust-minimized) vs Free Tunnel lock-mint (high-risk) |
| [AUDIT-HYPERLIQUID-BRIDGE.md](bridges/AUDIT-HYPERLIQUID-BRIDGE.md) | Hyperliquid Bridge2 — validator-multisig withdrawal |
| [AUDIT-IBC-TRANSFER.md](bridges/AUDIT-IBC-TRANSFER.md) | IBC ics20 — light-client native-proof seam |

## 🔄 state-sync/ — the bootstrap seam (snapshot / checkpoint / range sync)
Where a node trusts a *summary of its own chain's history* served by untrusted peers, often written toward
persistent storage before full verification. Threat model: a malicious peer driving an honest node to
**diverge / accept-invalid / corrupt-storage / stall.** Two questions: *what's the trust anchor* and *is
network data verified before it touches persistent state.*
| File | What it is |
|---|---|
| [README.md](state-sync/README.md) | The sync threat model + the verify-before-persist lens |
| [AUDIT-STATE-SYNC-SWEEP.md](state-sync/AUDIT-STATE-SYNC-SWEEP.md) | The sweep — geth snap sync (S1, the proven end), then reth/erigon, beacon checkpoint, Cosmos/CometBFT, Solana/Bitcoin snapshots |

## 🧩 consensus/ — the agreement boundary (fork choice · EL↔CL · equivocation)
The rules by which honest nodes converge on *one* canonical chain despite adversarial validators/peers.
Threat model: **safety violation / reorg / liveness stall / unjust slashing / EL↔CL split.** Lens: *does the
code enforce exactly the safety assumption, and can one actor move fork choice beyond their stake.*
| File | What it is |
|---|---|
| [README.md](consensus/README.md) | The consensus-safety threat model + the agreement-layer lens |
| [AUDIT-CONSENSUS-SWEEP.md](consensus/AUDIT-CONSENSUS-SWEEP.md) | The sweep — engine API EL↔CL seam (C1), then ETH fork choice, CometBFT, Solana/DAG |

## 🛡️ validator-ops/ — the validator's trust surface beyond consensus
MEV/PBS relays (Ethereum's one trusted intermediary), randomness/leader-election bias, and key management.
Threat model: the validator gets **exploited** — robbed of MEV, slashed, key-compromised, or leader-predicted.
Lens: *what must the validator trust, is it minimized or assumed, and can one counterparty rob/slash it.*
| File | What it is |
|---|---|
| [README.md](validator-ops/README.md) | The validator-ops threat model + the "minimize the trust, name the residual" lens |
| [AUDIT-VALIDATOR-OPS-SWEEP.md](validator-ops/AUDIT-VALIDATOR-OPS-SWEEP.md) | The sweep — mev-boost proposer (V1) + relay (V2), RANDAO/VRF (V3), slashing protection (V4) |

## 🔢 crypto-primitives/ — the verifier's own correctness (precompiles, curves, KZG)
The bottom of the stack: the EVM precompiles and curve/pairing/KZG ops where **every client must compute
bit-for-bit identically** (a divergence is a consensus split) and **every malformed input must be rejected the
same way** (a missing subgroup check is a forgery). Lens: *is every malformed input rejected deterministically
and identically across clients, and is every computation bounded.*
| File | What it is |
|---|---|
| [README.md](crypto-primitives/README.md) | The primitive-layer threat model (DIVERGE / FORGE / DoS / MALLEABLE) |
| [AUDIT-CRYPTO-PRIMITIVES-SWEEP.md](crypto-primitives/AUDIT-CRYPTO-PRIMITIVES-SWEEP.md) | The sweep — geth modexp+bn256 (P1), BLS12-381+KZG (P2), reth/revm cross-client consistency (P3) |

## 🔮 zk-proving/ — proving-system soundness (does the verifier accept only the truth?)
The deepest verifier layer: the zkVMs (SP1, RISC Zero) and proof backends (Plonky3/FRI, Halo2, Groth16).
Threat model: a malicious prover convincing an honest verifier of a **false** statement. Audits the
*checkable* soundness properties where the real historical breaks lived — **Fiat-Shamir honesty (Frozen-Heart)
+ public-input binding** — honest about the line to deep math-soundness (a security-proof question).
| File | What it is |
|---|---|
| [README.md](zk-proving/README.md) | The proving-system threat model (SOUNDNESS / FROZEN-HEART / UNDER-CONSTRAINED / INPUT-BINDING) |
| [AUDIT-ZK-PROVING-SWEEP.md](zk-proving/AUDIT-ZK-PROVING-SWEEP.md) | The sweep — Plonky3/FRI (Z1), Halo2/Groth16 (Z2), SP1 (Z3), RISC Zero (Z4) |

## 🕸️ p2p-eclipse/ — the networking floor (can the node reach the honest network?)
The most upstream layer: discovery + peer management. Threat model: **eclipse** (own all a node's peers →
control its reality), table-poison, DoS, amplification. Lens: *is the peer set diversified and hard to
monopolize, and is every spoofable input liveness-checked and bounded.* The floor that guarantees a node can
reach an honest observer — the precondition every sweep above assumes.
| File | What it is |
|---|---|
| [README.md](p2p-eclipse/README.md) | The eclipse/amplification threat model + the network-floor lens |
| [AUDIT-P2P-ECLIPSE-SWEEP.md](p2p-eclipse/AUDIT-P2P-ECLIPSE-SWEEP.md) | The sweep — Bitcoin addrman (E1), Ethereum discv5 (E2), libp2p gossipsub (E3) |

## 💧 protocols/ — ~40 DeFi / infra / privacy audits (~20 verticals)
Grouped by vertical; full per-finding map in [`CORPUS-INDEX.md`](CORPUS-INDEX.md) §5.

**Prediction markets** (one goal, four floors, four oracles — capstone §5d):
[Polymarket](protocols/AUDIT-POLYMARKET-PREDICTION-MARKET.md) ·
[Augur v2 vs Polymarket](protocols/AUDIT-AUGUR-V2-VS-POLYMARKET-ORACLE-SEAM.md) ·
[Azuro (3-pole)](protocols/AUDIT-AZURO-V2-POOL-COUNTERPARTY-AND-3POLE-SYNTHESIS.md) ·
[Thales/Overtime (4-pole taxonomy)](protocols/AUDIT-THALES-OVERTIME-AMM-AND-4POLE-TAXONOMY.md)

**Stablecoins / CDPs** (no dollar is an on-chain invariant — §5j):
[Maker vs Liquity](protocols/AUDIT-STABLECOIN-CDP-MAKER-LIQUITY.md) ·
[USDC vs USDT (deep)](protocols/AUDIT-LARGECAP-STABLES-USDC-USDT.md) ·
[DAI-as-USDC-wrapper + CCTP](protocols/AUDIT-DECENTRALIZED-DOLLARS-DAI-CCTP.md) ·
[FRAX (fractional-algo + AMO)](protocols/AUDIT-FRAX-FRACTIONAL-ALGO-AMO.md) ·
[Ethena USDe (off-chain custody)](protocols/AUDIT-ETHENA-USDE-OFFCHAIN-CUSTODY.md) ·
[crvUSD LLAMMA (soft-liq)](protocols/AUDIT-CRVUSD-LLAMMA-SOFT-LIQUIDATION.md)

**Perps & liquidation:** [GMX v1/v2](protocols/AUDIT-PERPS-LIQUIDATION-GMX.md) ·
[Drift](protocols/AUDIT-DRIFT-PERP.md)
**Lending:** [NFT — BendDAO/NFTfi/Blend](protocols/AUDIT-NFT-LENDING-BENDDAO-NFTFI-BLEND.md) ·
[Isolated — Morpho/Euler](protocols/AUDIT-ISOLATED-LENDING-MORPHO-EULER.md) ·
[marginfi](protocols/AUDIT-MARGINFI-LENDING.md)
**Restaking & LST** (destructible-principal residual): [EigenLayer + LRT](protocols/AUDIT-RESTAKING-EIGENLAYER-LRT.md) ·
[Lido/RocketPool](protocols/AUDIT-LST-LIDO-ROCKETPOOL.md) · [Marinade](protocols/AUDIT-MARINADE-LST.md)
**AMM / DEX:** [Uniswap v2/v3/v4](protocols/AUDIT-AMM-UNISWAP-V2-V3-V4.md) ·
[Meteora DAMM](protocols/AUDIT-METEORA-DAMM-V2.md) · [Alpha-Vault](protocols/AUDIT-METEORA-ALPHA-VAULT.md) ·
[Vault-SDK](protocols/AUDIT-METEORA-VAULT-SDK.md)
**Intents / cross-chain / oracles:** [UniswapX vs Across](protocols/AUDIT-INTENTS-UNISWAPX-ACROSS.md) ·
[LayerZero vs Wormhole](protocols/AUDIT-CROSSCHAIN-MESSAGING-LAYERZERO-WORMHOLE.md) ·
[Chainlink vs Pyth](protocols/AUDIT-ORACLE-NETWORKS-CHAINLINK-PYTH.md)
**Governance / AA / tokens / privacy:** [Governance+timelock (OZ/Compound)](protocols/AUDIT-GOVERNANCE-TIMELOCK-ATTACK-SURFACE.md) ·
[DeXe](protocols/AUDIT-DEXE-GOVERNANCE.md) · [ERC-4337 AA](protocols/AUDIT-ACCOUNT-ABSTRACTION-ERC4337.md) ·
[Permissioned tokens (USDC/ERC-3643)](protocols/AUDIT-PERMISSIONED-TOKENS-USDC-ERC3643.md) ·
[Semaphore (ZK anonymity set)](protocols/AUDIT-SEMAPHORE-ZK-ANONYMITY-SET.md)
**Identity / PoP:** [World ID](protocols/AUDIT-WORLDID.md) · [Humanity](protocols/AUDIT-HUMANITY-HTOKEN.md) ·
[PI/LAB/WLD](protocols/AUDIT-PI-LAB-WLD-GOVERNANCE.md)
**Solana / closed / mirror-audited:** [Civic hook](protocols/AUDIT-CIVIC-TRANSFER-HOOK.md) ·
[LaunchLab](protocols/AUDIT-LETSBONK-LAUNCHLAB.md) · [Osmosis SF](protocols/AUDIT-OSMOSIS-SUPERFLUID-RECON.md) ·
[TradePort](protocols/AUDIT-TRADEPORT-NOTE.md) · [Defi App](protocols/AUDIT-DEFIAPP-NOTE.md)
