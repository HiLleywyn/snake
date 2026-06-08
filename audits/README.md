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
