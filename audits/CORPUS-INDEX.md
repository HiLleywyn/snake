# Corpus index — the whole body of work, mapped

One reusable lens applied across **~80 systems** — L1s, L2s, rollups, privacy chains, bridges, the
full node stack (sync → consensus → validator-ops → crypto-primitives → zk-proving → p2p), and **~20
DeFi/infra/privacy verticals** (~40 protocol audits). This index is the map: the *laws* the corpus
converged on, the *taxonomy* it built, and a *navigable directory* of every document.

> **Start here:** [`methodology/AUDIT-CAPSTONE.md`](methodology/AUDIT-CAPSTONE.md) (the synthesis, §4 +
> §5a–§5j) · [`methodology/AUDIT-METHODOLOGY.md`](methodology/AUDIT-METHODOLOGY.md) (the lens) ·
> [`../DESIGN-PRINCIPLES.md`](../DESIGN-PRINCIPLES.md) (the constructive mirror).

---

## 1. The unified result (one paragraph)

**Every system reduces to a conservation/solvency *floor* + a precisely-named *residual*.** The floor
answers "can value leak / can the system always honor what it owes"; the residual is *what's left to
trust once the floor holds*. Across the whole corpus there is **one genuinely actionable finding**
(MemeCore — a latent consensus landmine, disclosed fix-first); everything else resolved to *a sound
floor + a named residual*, never a bare "safe." The two deepest cross-cuts:
- **The fail-safe-substrate boundary** (L1 layer): every real defect in a well-engineered chain *fails
  safe* (a tx aborts, a node hangs, stake sticks) because the substrate forces it; the one chain whose
  substrate let a defect fail *unsafe* is the one finding.
- **The own-vs-delete dial** (DeFi layer): for every residual, a designer either *takes the trust and
  bounds it* (governance, oracles, optimistic attestation) or *deletes the trust and pays in
  flexibility* (immutability, atomicity, redemption arbitrage). Auditing = name the floor's mechanism,
  name the dominant residual class, name which side of the dial the design chose, then verify the bound
  or the structural substitute actually holds.

---

## 2. The residual type system (5 classes)

Every "what's left to trust" reduces to one or more of these (capstone §5e, §5h):

| # | Residual class | The question it answers | Canonical examples |
|---|---|---|---|
| 1 | **Conservation / 6b-equivalence** | can value leak *by construction*? | CTF, AMM `x·y≥k`, UTXO, share vaults |
| 2 | **Governance ceiling** | what can the admin / upgrade key do? | timelock+vote (§5f), Maker `wards`, proxy admin |
| 3 | **Oracle / attestation** | who sets the truth/price, and is the consumer checking it? | Chainlink/Pyth, UMA, beacon-balance committees, **+ off-chain-actor sub-type** (bundler, dataworker, proposer) |
| 4 | **Liquidation / solvency-enforcement timeliness** | does the house stay solvent under price motion? | discrete auction · keeper seizure · SP-offset · ADL · **continuous soft-liq (LLAMMA)** |
| 5 | **Destructible principal** | can a third party deliberately reduce what you're owed? | slashing (EigenLayer), issuer seizure (USDT `destroyBlackFunds`) |

---

## 3. The own-vs-delete dial (capstone §5f, §5i, §5j)

The same choice recurs at every layer — settlement, the admin key, the oracle, the attestor, the token:

```
   DELETE THE TRUST  ◄──────────────────────────────────────────►  OWN THE TRUST
   (pay in flexibility)                                            (bound it, regulatory/UX gain)
   Uniswap v2/v3 ·  Liquity ·  ERC-4337 EntryPoint                 Maker governance · UMA optimistic
   UniswapX (atomic) · Morpho immutable                           Azuro provider+DAO · LayerZero DVN
   Augur self-token fork                                           USDC (split roles) · USDT (single owner,
                                                                    seize+fee+forward-upgrade)
```

---

## 4. Floor-enforcement mechanisms (4) & oracle/attestation types (the spectrum)

**The floor's job is never "conserve" per se — it is "the system can always honor what it owes,"** met
by one of (capstone §5d, §5g):
1. **Conservation-by-identity** — peer-to-peer, locked = max payout (CTF, Augur, Thales PositionalMarket); zero house risk.
2. **Reserve-locking solvency** — house pre-locks worst-case liability or reverts (Azuro, GMX `reserved≤pool≤balance`); LP bears P&L.
3. **Bounded-loss-by-caps** — AMM/scoring-rule maker capped per market (Thales AMM); LP bounded P&L.
4. **Conservation-by-deferred-settlement** — books may be imbalanced mid-tx, forced to net to zero at the boundary (Uniswap v4 net-zero-delta, Euler EVC deferred checks).

**Oracle/attestation types**, on an *expressiveness ↔ determinism ↔ trustlessness* surface: cryptographic-proof (EigenPod beacon, Semaphore) · keeper-clamp (GMX↔Chainlink) · optimistic (UMA/Polymarket/Across) · token-vote (Augur fork, UMA DVM) · trusted-feed (Azuro, Chainlink, Circle CCTP) · committee-attested (Lido/RocketPool beacon, ether.fi rate) · configurable-quorum (LayerZero DVN) · monolithic-quorum (Wormhole 13/19 — *the same set under Pyth = correlated residual*).

---

## 5. The DeFi / infra / privacy verticals (protocols/ + the deep-dives)

| Vertical | Audits | Headline finding |
|---|---|---|
| **Prediction markets** | [Polymarket](protocols/AUDIT-POLYMARKET-PREDICTION-MARKET.md) · [Augur v2 vs Polymarket](protocols/AUDIT-AUGUR-V2-VS-POLYMARKET-ORACLE-SEAM.md) · [Azuro (3-pole)](protocols/AUDIT-AZURO-V2-POOL-COUNTERPARTY-AND-3POLE-SYNTHESIS.md) · [Thales/Overtime (4-pole)](protocols/AUDIT-THALES-OVERTIME-AMM-AND-4POLE-TAXONOMY.md) | floor always honors "winners paid" via 4 mechanisms; trust telescopes onto the resolution oracle |
| **Stablecoins / CDPs** | [Maker vs Liquity](protocols/AUDIT-STABLECOIN-CDP-MAKER-LIQUITY.md) · [USDC vs USDT (deep)](protocols/AUDIT-LARGECAP-STABLES-USDC-USDT.md) · [DAI/CCTP](protocols/AUDIT-DECENTRALIZED-DOLLARS-DAI-CCTP.md) · [FRAX](protocols/AUDIT-FRAX-FRACTIONAL-ALGO-AMO.md) · [Ethena USDe](protocols/AUDIT-ETHENA-USDE-OFFCHAIN-CUSTODY.md) · [crvUSD LLAMMA](protocols/AUDIT-CRVUSD-LLAMMA-SOFT-LIQUIDATION.md) | **no dollar is an on-chain invariant** — backing is off-chain / reflexive / redemption-arbitrage (§5j) |
| **Perps & liquidation** | [GMX v1/v2](protocols/AUDIT-PERPS-LIQUIDATION-GMX.md) · [Drift](protocols/AUDIT-DRIFT-PERP.md) · [crvUSD LLAMMA](protocols/AUDIT-CRVUSD-LLAMMA-SOFT-LIQUIDATION.md) | floor = continuously-moving solvency invariant; bad-debt backstop (LP-socialize → ADL → soft-liq) |
| **Lending** | [NFT (BendDAO/NFTfi/Blend)](protocols/AUDIT-NFT-LENDING-BENDDAO-NFTFI-BLEND.md) · [Isolated (Morpho/Euler)](protocols/AUDIT-ISOLATED-LENDING-MORPHO-EULER.md) · [marginfi](protocols/AUDIT-MARGINFI-LENDING.md) | oracle = lean-in / refuse / replace; isolation makes the oracle a per-market *choice* |
| **Restaking & LST** | [EigenLayer + LRT](protocols/AUDIT-RESTAKING-EIGENLAYER-LRT.md) · [Lido/RocketPool](protocols/AUDIT-LST-LIDO-ROCKETPOOL.md) · [Marinade](protocols/AUDIT-MARINADE-LST.md) | **destructible principal** (slashing); the residual migrates to whatever layer re-tokenizes the position |
| **AMM / DEX** | [Uniswap v2/v3/v4](protocols/AUDIT-AMM-UNISWAP-V2-V3-V4.md) · [Meteora DAMM](protocols/AUDIT-METEORA-DAMM-V2.md) · [Alpha-Vault](protocols/AUDIT-METEORA-ALPHA-VAULT.md) · [Vault-SDK](protocols/AUDIT-METEORA-VAULT-SDK.md) | the conservation floor in purest form; v4 hook = deliberately re-introduced residual |
| **Intents / settlement** | [UniswapX vs Across](protocols/AUDIT-INTENTS-UNISWAPX-ACROSS.md) | atomic = *empty* residual; cross-chain = optimistic attestation seam |
| **Cross-chain messaging** | [LayerZero vs Wormhole](protocols/AUDIT-CROSSCHAIN-MESSAGING-LAYERZERO-WORMHOLE.md) | configurable-DVN vs monolithic-13/19 guardian set (self-upgrading, under Pyth) |
| **Oracle networks** | [Chainlink vs Pyth](protocols/AUDIT-ORACLE-NETWORKS-CHAINLINK-PYTH.md) | the universal residual bottoms out in a (often *shared*) signer quorum + a consumer-side check |
| **Governance / timelock** | [OZ + Compound](protocols/AUDIT-GOVERNANCE-TIMELOCK-ATTACK-SURFACE.md) · [DeXe](protocols/AUDIT-DEXE-GOVERNANCE.md) · [PI/LAB/WLD](protocols/AUDIT-PI-LAB-WLD-GOVERNANCE.md) | ceiling = token-vote + minDelay exit window; flash-loan dead by snapshot; reduces to 4 params |
| **Account abstraction** | [ERC-4337](protocols/AUDIT-ACCOUNT-ABSTRACTION-ERC4337.md) | new actor-trust topology; off-chain bundler rules the contract can't enforce |
| **Permissioned tokens** | [USDC + ERC-3643](protocols/AUDIT-PERMISSIONED-TOKENS-USDC-ERC3643.md) | issuer-is-god; the freeze key is a meta-residual *under* all of DeFi |
| **Privacy / ZK** | [Semaphore](protocols/AUDIT-SEMAPHORE-ZK-ANONYMITY-SET.md) | anonymity-set floor; same trusted-setup residual as zk-rollups + the set-size term |
| **Identity / PoP** | [World ID](protocols/AUDIT-WORLDID.md) · [Humanity](protocols/AUDIT-HUMANITY-HTOKEN.md) | ZK tree integrity + an off-chain attestation (orb / EAS) residual |
| **Closed / mirror-audited** | [Civic](protocols/AUDIT-CIVIC-TRANSFER-HOOK.md) · [LaunchLab](protocols/AUDIT-LETSBONK-LAUNCHLAB.md) · [Osmosis SF](protocols/AUDIT-OSMOSIS-SUPERFLUID-RECON.md) · [TradePort](protocols/AUDIT-TRADEPORT-NOTE.md) · [Defi App](protocols/AUDIT-DEFIAPP-NOTE.md) | the auditability floor — what *cannot* be verified, named plainly |

---

## 6. The L1 / node-stack / bridge layer

- **Chains** ([`chains/`](README.md#️-chains--l1--l2--rollup--privacy--cross-chain)) — ~40 L1/L2/rollup/privacy audits, grouped by conservation mechanism (type-system floors, recomputed invariants, UTXO equation, account/EVM, parallel-OCC+BFT, rollups, async/sharded, ZK/privacy). Plus the [100-coin registry](COIN-REGISTRY-100.md).
- **Bridges** ([`bridges/`](README.md#-bridges--the-weak-link-audited)) — the highest-risk category; the two-question lens (*who authorizes the mint, what does the mint check*) + the Hyperliquid Bridge2 finding lifecycle.
- **The seven-layer node stack** (capstone §5c) — one law in seven masks, top→bottom:
  [state-sync](state-sync/AUDIT-STATE-SYNC-SWEEP.md) (verify-before-persist) ·
  [consensus](consensus/AUDIT-CONSENSUS-SWEEP.md) (recompute-the-fork-choice) ·
  [validator-ops](validator-ops/AUDIT-VALIDATOR-OPS-SWEEP.md) (record-before-sign) ·
  [crypto-primitives](crypto-primitives/AUDIT-CRYPTO-PRIMITIVES-SWEEP.md) (reject-identically) ·
  [zk-proving](zk-proving/AUDIT-ZK-PROVING-SWEEP.md) (observe-before-sample / prove-before-answer) ·
  [p2p-eclipse](p2p-eclipse/AUDIT-P2P-ECLIPSE-SWEEP.md) (observe-before-sample).
- **The one finding** — [MemeCore PoSA](finding-memecore/AUDIT-MEMECORE-POSA.md) (latent consensus landmine, 7 passes, disclosed fix-first).
- **Bug-hunts** ([`bug-hunts/`](README.md#-bug-hunts--stress-testing-the-one-finding-claim)) — stress-testing the one-finding claim across large-cap deltas, fresh commits, mid-cap DeFi, and rollup oracles.

---

## 7. The capstone section map

| § | Topic |
|---|---|
| §4 | The comparative spectrums (3 coordinates, conservation ladder, governance ceiling, settlement seam, determinism spine, oracle decomposition, consensus family) |
| §5a–§5b | The laws that held across every paradigm · the bug-hunt phase + the fail-safe-substrate boundary |
| §5c | The full-stack trust traversal — seven layers, one law |
| §5d | Prediction markets — one goal, four floors, four oracles |
| §5e | Slashing, continuous solvency, the unpriceable-collateral seam (→ the 5-class residual taxonomy) |
| §5f | Settlement seam, governance ceiling, the peg — the own-vs-delete dial |
| §5g | Opening the foundational boxes — oracle, staking rate, AMM floor, isolated market |
| §5h | Off-chain-actor residual, the attestor dial, continuous liquidation (AA / messaging / LLAMMA) |
| §5i | Three inverted trust models — issuer-is-god, off-chain backing, anonymity-set; the floor's 3 hidden dependencies |
| §5j | The stablecoin trust-model spectrum — what actually backs a "dollar" |

---

## 8. Posture

Defensive throughout — no exploit, no PoC, no weaponization. The single exploitable-class finding
(MemeCore) was routed **privately, fix-first**; live-system requests were declined for active testing and
redirected to passive analysis. Public audits used `git clone` / public artifacts only. Closed-source
targets are mapped to the trust surface with *what cannot be verified* stated plainly. Confidence is
graded (re-derived-from-source / functions-read-not-every-edge / deferred-needs-proofs), and "no finding"
means "none found by this analysis," not proof of absence — the corpus contains a live demonstration
(alt_bn128) that this analysis can err and self-correct. The discipline is one line: **recompute, don't
trust the summary** — extended, by the DeFi work, from "recompute the protocol's math" to "recompute the
*assumptions under* the protocol": the asset it holds, the backing behind that asset, the cryptography
under the proof.

> *Σ in == Σ out. Name the floor, name the residual, name who can break it.*
