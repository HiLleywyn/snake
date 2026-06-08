# Audits — index

The full corpus: ~60 systems audited with one reusable lens (six-bucket trust cartography +
conservation floor / governance ceiling / equivalence), plus two dedicated bug-hunts. **One genuinely
actionable finding** (MemeCore, [`finding-memecore/`](finding-memecore/AUDIT-MEMECORE-POSA.md));
everything else resolved to a sound conservation floor + a named residual.

**Start here:** [`methodology/AUDIT-CAPSTONE.md`](methodology/AUDIT-CAPSTONE.md) (the synthesis) ·
[`../DESIGN-PRINCIPLES.md`](../DESIGN-PRINCIPLES.md) (the constructive mirror) ·
[`methodology/AUDIT-METHODOLOGY.md`](methodology/AUDIT-METHODOLOGY.md) (the lens itself).

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

## 💧 protocols/ — DeFi apps, identity, governance, tokens
| File | What it is |
|---|---|
| [AUDIT-DRIFT-PERP.md](protocols/AUDIT-DRIFT-PERP.md) | Drift perp — triple-capped PnL settlement |
| [AUDIT-MARGINFI-LENDING.md](protocols/AUDIT-MARGINFI-LENDING.md) | marginfi — rate decomposition + the "verify-the-effect" template |
| [AUDIT-MARINADE-LST.md](protocols/AUDIT-MARINADE-LST.md) | Marinade — ledger-priced LST exchange rate |
| [AUDIT-METEORA-DAMM-V2.md](protocols/AUDIT-METEORA-DAMM-V2.md) · [Alpha-Vault](protocols/AUDIT-METEORA-ALPHA-VAULT.md) · [Vault-SDK](protocols/AUDIT-METEORA-VAULT-SDK.md) | Meteora AMM/vaults — pool-favorable rounding |
| [AUDIT-CIVIC-TRANSFER-HOOK.md](protocols/AUDIT-CIVIC-TRANSFER-HOOK.md) | Civic — Token-2022 validate-before-use hook |
| [AUDIT-DEXE-GOVERNANCE.md](protocols/AUDIT-DEXE-GOVERNANCE.md) | DeXe — no-admin-key, vote-gated governance pole |
| [AUDIT-LETSBONK-LAUNCHLAB.md](protocols/AUDIT-LETSBONK-LAUNCHLAB.md) | LaunchLab — closed/mirror auditability floor |
| [AUDIT-OSMOSIS-SUPERFLUID-RECON.md](protocols/AUDIT-OSMOSIS-SUPERFLUID-RECON.md) | Osmosis — superfluid invariant recon |
| [AUDIT-TRADEPORT-NOTE.md](protocols/AUDIT-TRADEPORT-NOTE.md) | TradePort — closed NFT mkt mapped via on-chain ABI |
| [AUDIT-DEFIAPP-NOTE.md](protocols/AUDIT-DEFIAPP-NOTE.md) | Defi App — audit-PDFs-only auditability floor |
| [AUDIT-WORLDID.md](protocols/AUDIT-WORLDID.md) | World ID — ZK tree integrity + off-chain orb |
| [AUDIT-HUMANITY-HTOKEN.md](protocols/AUDIT-HUMANITY-HTOKEN.md) | Humanity — off-chain EAS proof-of-personhood |
| [AUDIT-PI-LAB-WLD-GOVERNANCE.md](protocols/AUDIT-PI-LAB-WLD-GOVERNANCE.md) | PI / LAB / WLD — supply-control & auditability triptych |
