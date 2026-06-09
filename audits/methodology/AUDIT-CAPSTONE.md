# Trust-Cartography Capstone — Findings Across the Whole Corpus

*The wrap-up. One reusable lens — six buckets + three coordinates (equivalence / conservation
floor / governance ceiling) — applied to ~51 systems (+ a dedicated bug-hunt phase: 7 large-cap consensus deltas + 15 fresh-code reads across 5 non-EVM teams, §5b) across every major execution paradigm. This
records what was found, the comparative spectrums that emerged, and the laws that held.*

*(Updated to fold in the L1/rollup expansion sweep: Aptos, Monad + MonadBFT, Sei, Berachain, NEAR,
Stellar, Cardano, XRPL, TON, Osmosis, TradePort, Avalanche, Algorand, Hyperliquid, Polkadot, zkSync,
Optimism, Cosmos x/bank, IBC, Monero, ICP, Kaspa, Filecoin, Stacks, Tezos, Hedera, EOS, Ethereum — see the second evidence block in §2 and the new spectrums §4f/§4g.)*

---

## 1. Headline

> **One genuinely actionable finding, responsibly disclosed (MemeCore PoSA, §3). Everything else
> resolved to: a sound/strong conservation floor + a residual that is either by-design governance
> centralization or an irreducible off-chain/cross-chain equivalence (6b).** No bare "safe" was
> ever used; every verdict points at the exact constraint or the exact unverifiable seam.

The corpus is itself the result: the lens produced *proportional signal* on every paradigm —
finding the real bug where one existed, and naming the trust precisely where none did.

**Scope note (this capstone now spans the whole stack).** Beyond the original ~40 chain/protocol systems, the
lens was carried *vertically* through the entire node stack — **seven dedicated deep-sweep folders** (bridges,
state-sync, consensus, validator-ops, crypto-primitives, zk-proving, p2p-eclipse; consolidated in **§5c**),
~150 deep contract/source reads across many independent client and library implementations. The headline holds
unchanged across all of it: **still one genuine finding (MemeCore); every other system a sound floor + a named
residual** — plus, from the re-audit pass, *one corrected summary in the corpus's own output* (the alt_bn128 G2
subgroup re-read, §5c), which is the methodology demonstrated on itself.

---

## 2. Evidence table (every target, dominant locus, verdict)

| Target | Paradigm | Conservation floor | Residual / ceiling | Outcome |
|---|---|---|---|---|
| Namada MASP | ZK shielded | circuit value-balance | assets↔generator (governance) | constraint debt, no untrusted path |
| Penumbra | ZK shielded DEX | circuit + VCB | enable `overflow-checks` | hardening debt |
| Aztec | ZK rollup | proven AVM | spec↔circuit (6b) | 6a retired by proving |
| Aleo / Mina | ZK | replication / recursion | native↔circuit (6b) | enforced, 6b residue |
| Bridges (Wormhole/LZ/Hyperlane) | cross-chain | — | pure 6b | the 6b reference case |
| **Sui** (5 passes) | Move/Rust L1 | **linear types** (Σ=Supply by construction) | epoch delta in Rust/consensus; tautological local check | strongest floor in series |
| TRON (java-tron) | Java L1 | actuator↔processor equivalence | governance feature-gates | recompute-verified equivalent |
| WLFI | EVM token | OZ ERC20 | 3-of-5 Safe = proxy admin (verified≠running) | governance ceiling |
| Litecoin + MWEB | UTXO + MimbleWimble | tri-layer (scalar⇄pegs⇄commitments) | Bulletproofs soundness (6b) | enforced; inductive residual |
| **Base** | OP Stack rollup | ETHLockbox + fault proof | "DEFENDER_WINS ≠ valid" + Guardian | team-documented 6b |
| Civic | Token-2022 hook | validate-before-use gate | wallet↔token-account binding (off-chain) | enforced; 6b |
| Meteora DAMM v2 | AMM | pool-favorable rounding (all legs) | governance + Token-2022 hooks | strong floor |
| Marinade | LST | ledger-priced exchange rate | delegation (stake⇄validators) | strong floor |
| **Drift** | perp | **triple-capped PnL settlement** | the oracle | strong floor; oracle 6b |
| marginfi | lending | self-consistent rate decomposition | oracle + cross-protocol value-reporting | floor verified; verify-the-effect template |
| **MemeCore** | PoSA geth-fork | fixed/overflow-guarded reward | **§3 — see below** | **real finding, disclosed** |
| Canton / Splice | Daml consortium | balance check + ledger atomicity | DSO consortium | enforced |
| fetchd | Cosmos SDK | (forked modules) | bridge-mintable native (bounded) | by-design, capability-restricted |
| DeXe | DAO governance | voting-power integrity | proposal vote (no admin key) | self-governing pole |
| Humanity / World ID | proof-of-personhood | EAS (none) / ZK tree-integrity | off-chain orb/attester | see §5 comparison |
| LaunchLab / Alpha-Vault / Vault-SDK / Defi App | closed/mirror | — | unverifiable | auditability floor |

### Expansion sweep (L1/rollup data points added after the original ~25)

| Target | Paradigm | Conservation floor | Residual / ceiling | Outcome |
|---|---|---|---|---|
| **Aptos** | Move L1 | linear `Coin` + Move-Prover supply specs | copyable `MintCapability` (by design) | clean; floor verified on Aptos's own verifier |
| **Monad** | parallel EVM | OCC read-set + ordered commit | relaxed-merge comparator (6a) | clean; OCC = "parallel==sequential" |
| **MonadBFT** | BFT consensus | safety = no conflicting QC (monotonic vote + >2/3) | BLS aggregation, pacemaker liveness | clean; halt-on-violation `assert!` |
| **Sei** | parallel EVM (Go) | OCC multiversion store + validation | read-kind comparator (6a) | clean; 3rd OCC twin |
| **Berachain** | EVM (PoL) | BGT `invariantCheck`: `balance ≥ totalSupply` | BlockRewardController bounds | clean, strong positive |
| **NEAR** | sharded async | deterministic refund receipts | named global balance check (historical) | clean; honest gap noted |
| **Stellar** | trust-line DEX | `ConservationOfLumens` + `LiabilitiesMatchOffers` | inflation/fee-pool deltas | clean; rich invariant suite |
| **Cardano** | eUTXO multi-asset | `consumed == produced` (`MaryValue`) | Plutus script-gated mint | clean; most legible floor |
| **XRPL** | classic L1 | `XRPNotCreated`: Δdrops `== −fee` | — | clean; tightest floor |
| **TON** | async actor | deterministic on-chain bounce | — | clean; reduced-6a refund |
| **Osmosis** | Cosmos AMM | registered superfluid invariant | risk-adjusted multiplier | recon, no finding |
| **TradePort** | closed Aptos NFT mkt | bid escrow holds linear `Coin` (ABI-read) | closed program | auditability floor mapped via ABI |
| **Avalanche** | AVM multi-asset UTXO | `FlowChecker`: `produced ≤ consumed` per asset | atomic shared-memory seam (6) | clean |
| **Algorand** | account L1 | per-block recomputed `totals.All()` gate | rewards-rounding identity | clean, strong positive |
| **Hyperliquid** | perps L1 (closed core) | Bridge2: >2/3 quorum + dispute window | **closed HyperCore (6b)** | clean seam; core = irreducible trust |
| **Polkadot** | Substrate L1 | `Imbalance` type → `Drop` books `TotalIssuance` | `saturating_*` merge; `Unsafe*Accounting` | clean, strong positive |
| **zkSync** | ZK rollup | **validity proof** gates execute+withdraw | circuit + verifier + governance (6b) | clean gating; circuit = irreducible |
| **Optimism** | optimistic rollup | **fraud proof** (`DEFENDER_WINS` + window) | FPVM + honest challenger + Guardian (6b) | clean gating; FPVM = irreducible |
| **Cosmos `x/bank`** | Cosmos substrate | matched mint/burn + `SendCoins` 1:1; `math.Int` halts | **registered invariant removed in HEAD** | clean; conserve-by-construction note |
| **IBC ics20** | cross-chain (light client) | escrow/mint 1:1 + bank underflow backstop | counterparty consensus (4th seam model) | clean; blast-radius isolated |
| **Monero** | RingCT privacy | Pedersen `Σin = Σout + fee·H` + range proofs | range-proof + DL soundness (6b) | clean; completes privacy triad |
| **ICP** | canister ledger | **complement-pool** (`supply = max − token_pool`, derived) | trap-rollback platform guarantee | clean; can't-drift design |
| **Kaspa** | BlockDAG (GHOSTDAG) | UTXO `out ≤ in` | blue/red coloring feeding blue_work | clean; DAG linearized deterministically |
| **Filecoin** | storage-collateral | `balance ≥ locked+precommit+pledge`; capped baseline mint | PoRep/PoSt soundness (6b); FVM transfer (ref-fvm) | clean; collateral-backed + capped issuance |
| **Stacks** | Clarity (caller-scoped) | **post-conditions**: caller-declared asset bounds, Deny catch-all | `AssetMap` recorder completeness; mode-dependence | clean; novel *caller* conservation |
| **Tezos** | typed source/sink | supply moves only via typed infinite source/sink; `transfer_n` Σin=Σout; receipts exposed | Michelson VM; voting quorum machine | clean; self-amendment governance endpoint |
| **Hedera** | explicit balanced journal | tx adjustment list must `isNetZeroAdjustment` (BigInteger, per asset) + `Math.addExact` | TokenMint/Burn auth; hashgraph aBFT | clean; federated-council governance |
| **EOS/Antelope** | RAM Bancor curve | leak-free bonding curve; reserve-favorable rounding | **deterministic-float runtime guarantee** | clean (conditional); cautionary determinism entry |
| **Ethereum** | account EVM (reference) | gas lifecycle: tip→validator, **basefee burned**; refund capped; uint256 checked | CL issuance (separate); opcode-level ops | clean (EL fee/burn); reference EVM |

Across the expansion: **no new findings** — every target resolved to a sound conservation floor + a
named residual, exactly as the original 25 did. MemeCore remains the lone exploitable-class finding.

---

## 3. The one finding (MemeCore PoSA — disclosed to the team)

Two consensus-robustness items in `consensus/posa/contract.go::settleRewardsAndUpdateValidators`,
**routed privately** to the MemeCore foundation, written fix-first (no exploit):
- **B —** the `vmenv.Call` error is **swallowed** (`return nil` unconditionally); a reverting
  reward system-call (`timedTask`) silently produces a "valid" block. *Fix: propagate the error.*
- **C —** the validator list is built from a **Go map without sorting** and passed into the
  state-changing system call; map order is non-deterministic. With B and the fixed gas budget,
  order→gas→OOG-revert could cause a **silent consensus split**. *Fix: sort the list.*
Latent (a running chain implies it's currently order-insensitive), but consensus-adjacent — the one
target in the sweep that produced a real, fixable defect rather than a by-design trust boundary.

**Reachability refinement (Pass 4, `AUDIT-MEMECORE-POSA.md`):** two independent static analyses
reproduced B+C exactly, and the consensus path is confirmed (`Finalize → settle → state →
header.Root = IntermediateRoot`). Two corrections sharpen severity without overclaiming: (i) the
reward call's caller check almost certainly *passes* for the real system-address (`0xffff…fffe`)
invocation, so the array *is* reached; but (ii) the state root is **MPT write-order-invariant**, so
non-canonical calldata does **not** automatically diverge. The real split needs order to change the
*final state* — either the **gas-edge** (the call gas is a finite fixed **50M**, so order→OOG-vs-
success, and B lets the OOG node finalize a no-reward block while the other finalizes with rewards →
divergent "valid" roots) or an **order-dependent committed write** (accumulator/dust). Verdict stands:
credible possible consensus split, **not proven** without a gas-accurate live-implementation
simulation, and **not** provable by naive order→root comparison. Fix is unconditional either way (sort
+ propagate).

**Pass 5 (deeper static dig, re-cloned v1.15.3) reframes it as a *latent landmine*, not a live bug.**
Proven: both producer (`FinalizeAndAssemble→Finalize`) and every verifier (`Finalize` on import)
**rebuild the reward calldata locally** from their own `snap.Signers` *map* (the synthetic call isn't
stored in the block), so producer and verifiers feed `timedTask` differently-ordered arrays for the
same block. Strengthened latency proof: since this happens on *every* block, if `timedTask`'s state or
gas depended on order the chain would fork on ~every block — so a *live, finalizing* MemeCore proves
the current contract is **fully order-commutative** (conclusively latent, not "rare edge case"). The
re-arming vector isn't the gas-edge (EIP-2929 makes straight-loop gas order-invariant; 50M is ample)
but an **order-dependent committed write** in a future `timedTask` upgrade (remainder/dust to
`validatorList[0]`, pool-exhaustion early-exit). So the true characterization: the client **removed the
determinism invariant**, leaving consensus correctness resting entirely on the **closed, upgradeable**
contract staying order-commutative — a routine reward-logic upgrade would brick consensus, silently
(via B). Cheap fix restores the client-side guarantee.

---

## 4. The comparative spectrums (the synthesis)

### (a) Three trust coordinates — every system reduces to these
1. **Equivalence / 6b (§9):** *what must be believed equal, and who discharges it* — proven (zk),
   re-executed (Aleo/Sui), agreed (Base fault proof), signed (bridges/World ID operator), or trusted
   (closed source).
2. **Conservation floor (§11):** *where "no value created" is enforced, and how strong* — see (b).
3. **Governance ceiling:** *who can replace the mechanism* — see (c).
All three move **down and outward**, away from the code that looks in charge.

### (b) Conservation-location ladder (strongest → weakest enforcement)
type system — *prohibitive* (Sui/Aptos Move linear types: `Balance`/`Coin` can't be dropped) **and**
*self-accounting* (Substrate `Imbalance`: `#[must_use]` + `Drop` books the delta to `TotalIssuance`)
> cryptographic algebra (MWEB commitments, World ID ZK, **zkSync validity proof**) >
ledger-model atomicity (Daml) > recomputed/asserted global invariant (**Algorand `totals.All()`**,
XRPL/Stellar/Berachain invariant-checks, Aptos Move-Prover specs) > consensus re-derivation (Sui
epoch, MemeCore) > runtime balance check (UTXO equation Cardano/Avalanche, AMM rounding,
lending rate-decomposition, perp settlement cap) > account-balance mutation (EVM/Cosmos imperative).
**Strength is inversely correlated with how much you must trust the author** — and it determines the
residual's *shape*: type/crypto-enforced systems push fragility to **liveness** (abort/safe-mode);
imperative systems push it to **value** (a missing check = mintable supply). *Refinement from the
expansion:* the type-system rung now has two strategies — Move **forbids** the drop, Substrate
**permits and accounts for** it; same "a balance delta can't vanish" guarantee, opposite mechanism.

### (c) Governance-ceiling spectrum (most → least centralized)
**$H/HToken** (owner: uncapped mint + force-burn + upgrade) → **WLFI** (3-of-5 Safe swaps the impl)
→ **World ID** (owner can swap the verifier/upgrade — ZK conditional on owner) → **fetchd** (admin
*bounded*: bridge can mint, cannot seize — `BurnFrom`/`ForceTransfer` deliberately disabled) →
**DeXe** (no admin key; every privileged action is proposal-gated via `onlyThis` — trust root is the
vote) → **Tezos** (the *self-amendment endpoint*: not just privileged actions but the **entire
protocol, voting rules included, is replaceable by stakeholder supermajority vote** — no fixed admin,
no off-chain upgrade key). *Same coordinate, opposite poles* — and Tezos is the far end of the
"trust the vote" pole, where the vote can rewrite the chain itself.
*Off-axis third kind (Hedera):* a **federated enterprise council** — term-limited, *identity-bound*
named entities controlling upgrades/treasury/node admission. It is neither an anonymous multisig nor
open-stake governance: more accountable than the former, more permissioned than the latter. So the
ceiling isn't a single line — it has a *permissioned-but-accountable* branch alongside the
anonymous-key→stake-vote axis.

### (d) Auditability floor — "open source" is not one thing
full-source-and-running (Sui, Drift, marginfi, Marinade, DAMM v2, Civic, MemeCore, Canton, fetchd,
DeXe, World ID) → **verified-but-swappable** (WLFI: verified ≠ running) → **SDK/IDL mirror, program
closed** (LaunchLab, Alpha-Vault, Vault-SDK) → **audit-PDFs only** (Defi App) → no source. The
**withheld layer is consistently the orchestration / enforcing logic** — exactly where conservation
is enforced or broken.

### (f) Settlement-seam trust spectrum (how cross-layer withdrawals are made safe)
The expansion sweep nailed down the four ways a chain lets value *leave* to an L1/host while
keeping conservation — graded by the **honesty assumption** each needs for *safety* (not liveness):
- **Validity proof (zkSync)** — output trusted because a SNARK proves it valid; **0-of-N** honesty,
  purely cryptographic. A fully-malicious operator can halt but cannot steal. Irreducible oracle: the
  ZK circuit.
- **Fraud proof (Optimism)** — output trusted unless disproven in a challenge window; **1-of-N honest
  watcher + L1 liveness** (the watcher must be able to transact during the window). Irreducible
  oracle: the FPVM (Cannon) single-step proof.
- **Light client (IBC ics20)** — output trusted because the counterparty's *own* consensus signed it,
  Merkle-verified on-chain; **>2/3 of the *counterparty's* validators honest** (no separate appointed
  committee). Irreducible oracle: the counterparty's consensus + CometBFT commit verification.
- **Multisig + dispute (Hyperliquid Bridge2)** — output trusted because >2/3 of an *appointed*
  committee signed; **>2/3 honest stake** + watchers/lockers. Irreducible oracle: the closed L1 + the
  validator set.
This is the sharpest **cryptographic-vs-social** contrast in the corpus and the concrete realization
of the §9 equivalence coordinate. The four ascend in *who* you must trust: nobody (validity) → any one
honest watcher (fraud) → the counterparty's real validator set (light client) → an appointed committee
(multisig). Note the recurring shape *underneath* all four (and Avalanche's atomic seam, and
Canton/Splice): **request → verify → finalize, with an invalidation/fraud/freeze path** — the universal
optimistic-settlement skeleton. *Conservation backstop seen in IBC:* even if the seam's trust fails,
the bank-layer underflow guard bounds the blast radius (a chain can't unescrow more than it locked, and
a Byzantine counterparty can only inflate its *own* voucher denom) — defense-in-depth under the seam.

**Scaled out (the dedicated bridge sweep — `../bridges/AUDIT-BRIDGES-SWEEP.md`):** these four seams were
the seed of a **~85-system** sweep across five substrates (EVM, SVM, Cosmos-SDK, Move, Bitcoin) and the
adjacent frontier — bridges, DA layers, oracles, ZK coprocessors, MPC chain abstraction (NEAR), restaking,
TEE attestation (Intel DCAP), intent settlement, truth oracles, prover markets. **Every contract's
verification was clean; not one exploitable finding** (the only latent issue, Nomic's legacy-address
matching, *fails closed*). The variance was *entirely* in the trust root, and the whole spread collapsed
onto **one axis that generalizes the four seams above: proven vs. attested.** Does the consuming chain
**recompute** the source's claim (a validity proof, an SPV+PoW check, a re-verified consensus, a
SNARK-bound block hash) or **trust a summary** of it (a committee signature, a role attestation, a
custodial consortium's word)? The same split sorts *availability* (Avail proves / Blobstream attests),
*historical state* (Axiom proves / Herodotus relays), *key custody* (NEAR — the destination verifies
nothing, trust is the threshold), *cryptoeconomics* (restaking is only "secured" once a slasher is wired),
and even *hardware* (DCAP is "proven by Intel silicon, attested by Intel that the silicon is secure").
Three refinements the four-seam table lacked: **marginal trust** (CCTP/first-party-issuer adds *zero* trust
beyond holding the asset), **the multisig can live in the cryptography** (Chainflip's one Schnorr sig *is* a
FROST >2/3 threshold), and **the integrator's config is the security** (pull-oracle thresholds settable to
1). And the unifying observation, made explicit in the sweep's coda and threaded back into
`AUDIT-REASONER-EPISTEMOLOGY.md §9`: **"proven vs. attested" *is* the reasoner's own "recompute vs. trust
the summary"** — *a bridge is a summary*, and the taxonomy ranks how much each one bothers to recompute.

### (g) The determinism / parallel-execution spine (parallel == sequential)
A second cross-cutting family the expansion confirmed: **OCC + deterministic ordered commit** as the
universal "concurrent execution equals sequential" design — verified structurally identical across
three languages: **Monad** (C++), **Aptos Block-STM** (Rust), **Sei** (Go). Read-set capture →
conflict validation → re-execute at a new incarnation → commit in strict txn order. Its *negation* is
the lone finding: **MemeCore's non-deterministic map iteration** (§3) is exactly what this family
forbids. Determinism is conservation's quiet prerequisite — a chain that can't agree on *order* can't
agree on *balances*. (Avalanche's canonical input/output sort and MonadBFT's monotonic per-round vote
are the same discipline in the validity and consensus layers respectively.)
*Now two layers wide:* the spine extends from **execution** (OCC ordered-commit: Monad/Aptos/Sei,
"parallel execution == sequential") to **block production itself** — **Kaspa GHOSTDAG** linearizes a
*parallel BlockDAG* into one canonical order by re-sorting the unordered mergeset on `(blue_work,
unique-hash)` (a strict total order), so even parallel *blocks* yield one agreed transaction sequence
("DAG == linear chain"). Kaspa is the most parallel point in the corpus and still enforces a canonical
order — the pointed positive inverse of MemeCore. The recurring trick at both layers: **collect the
parallel/unordered set, then impose a total order with a unique tiebreak before any state depends on
it.**
*Cautionary third mode (EOS/Antelope):* the determinism hazard can also be **delegated to the
runtime** rather than avoided in code — EOS's RAM Bancor market computes in `double`/`std::pow` *inside
consensus* (structurally the MemeCore hazard) and is safe **only** because the Antelope WASM VM
mandates deterministic floating point (SoftFloat). The guarantee lives a layer below the contract, so
the floor is "trust the runtime's float determinism." The closest non-defective neighbor of the
MemeCore finding — same hazard, contained one level down instead of leaking up.

### (h) Opening the oracles — the residuals decomposition (residuals pass)
Law 6 says "name the oracle." A dedicated pass *opened* the named oracles
(`AUDIT-ROLLUP-ORACLES-RESIDUALS.md`, plus addenda to EOS/IBC/Filecoin/Monero). Every one decomposes
identically: a **verifiable on-chain enforcement half** (clean in *all* cases) + an **irreducible
off-chain semantics-binding half** — and the *kind* of remaining residual is one of two:
- **Equivalence residual** (reducible by testing): Optimism's `step()` is a **Merkle-authenticated**
  MIPS emulator (memory can't be faked) → residual = on-chain-vs-Cannon-Go emulator equivalence, a
  diff-testable 6a.
- **Cryptographic-soundness residual** (irreducible under hardness assumptions): zkSync's verifier does
  a **real BN254 pairing** (reverts on failure) → residual = circuit/VK + trusted setup; Filecoin's
  miner actor gates on a **non-grindable beacon-derived challenge** bound to the sealed CIDs →
  residual = `verify_post` SNARK + PoRep construction; Monero → range-proof + DL soundness.
- **Fully closed (no residual):** EOS's "trust the runtime's float determinism" was *discharged* by
  reading the VM — every WASM float opcode dispatches to Berkeley SoftFloat in both interpreter and
  JIT, so determinism is verifiable code, not an assumption.
The pattern: **enforcement is always auditable (and was clean); only the *meaning* of the accepted
input is irreducible**, and its residual-kind tracks the §4f settlement spectrum — fraud-proof oracles
leave *equivalence* residuals (testable), validity/crypto oracles leave *soundness* residuals
(assumption-bound). "Name the oracle" has a follow-through: *open* it, and you can usually verify the
gate's internal machinery and shrink the residual to a single, well-typed trust.

### (i) Consensus-family spectrum — "conservation" at the agreement layer
The corpus now spans the major consensus families. The agreement-layer analog of conservation is
**no forged/conflicting finalization**: an adversary can't manufacture agreement (block-production
rights or finality) beyond its resource share. How each family enforces it, and the trust bound:
- **BFT quorum (MonadBFT** — HotStuff/Jolteon): safety = no two conflicting QCs; monotonic one-vote-per-
  round + **>2/3 stake quorum intersection**, `assert!`-halt on violation. Bound: <1/3 Byzantine stake.
- **VRF-PoS leader lottery (Cardano Ouroboros Praos):** private, unbiasable, **stake-proportional**
  leadership (`Hash(slot‖epochNonce)` VRF, registered-key binding, `φ(σ)` threshold). Bound: honest
  >1/2 stake + security parameter k. *(Pass 2, this audit.)*
- **BlockDAG total-order (Kaspa GHOSTDAG):** embrace parallel blocks, then **linearize by
  `(blue_work, hash)`** into one canonical order. Bound: honest-majority hashrate (PoW under a DAG).
- **PoW Nakamoto (Bitcoin/Litecoin):** heaviest-chain; leadership ∝ hashrate. Bound: honest >1/2 hashrate.
- **hashgraph aBFT (Hedera):** gossip-about-gossip + virtual voting (named, not deeply opened). Bound:
  <1/3 Byzantine stake, asynchronous.
- **Light-client-relayed (IBC/Tendermint):** a chain trusts another's finality via verified
  signatures (§4f). Bound: >2/3 of the *counterparty's* validators.
Two cross-cutting invariants recur regardless of family: **(1) a canonical total order** (BFT round
numbers, GHOSTDAG blue_work+hash tiebreak, OCC txn-index) — the determinism spine (§4g); and **(2) a
resource-proportional, unforgeable right to participate** (stake quorum / VRF-with-registered-key /
hashpower) — the Sybil bound. The lone finding (MemeCore) is precisely a violation of (1) at the
execution-adjacent layer. Per §4h, every family's residual is the **soundness of its core primitive**
(BLS aggregation, VRF, hash power, signature scheme) — a cryptographic-soundness residual.

### (e) Proof-of-personhood, compared
**Humanity** keeps *all* sybil-resistance off-chain (vanilla EAS + an attester key). **World ID**
puts *tree integrity* under ZK on-chain (insertion proofs, fresh-root checks) but still rests on an
off-chain **orb + operator** for personhood and delegates **nullifier uniqueness to integrating
apps**. Both share the irreducible 6b of *any* PoP system: an off-chain biometric authority decides
who is a unique human; the chain can at best prove the bookkeeping is correct.

---

## 5. The laws that held across every paradigm

1. **The load-bearing guarantee is never where you first look.** It lived in Rust not Move (Sui),
   in `ApplyBlock` not `Block::Validate` (Litecoin), in the `split` assert not the reward formula
   (DAMM/Sui), in the system-snapshot not the rate math (Marinade/Sui staking), in the proxy admin
   not the token (WLFI/$H), in consensus not the entrypoint (MemeCore/Sui). **Locate the enforcement
   mechanism before reading the business logic.**
2. **"Verify the effect, don't trust the reported state."** The marginfi cross-protocol pass is the
   positive template: refresh → compute-conservatively → CPI → **verify what was actually
   received**. The detector for the *missing* version of this is the highest-EV bug hunt.
3. **Residual shape follows enforcement substrate** (§4b): liveness-shaped under type/crypto;
   value-shaped under imperative. The MemeCore finding is exactly an imperative-substrate
   value/liveness gap (swallowed error + nondeterminism) in otherwise-inherited code.
4. **"Trustless" names the mechanism; the honest question is *trustless until whom?*** Every system
   bottoms out at a named authority — a multisig, a Guardian, a DSO, an orb operator, a bridge key,
   or (best) the vote itself.
5. **Closed enforcing-logic is the modern default and the real frontier.** Across Solana
   launchpads/vaults and app-chains, the audited/published artifact is increasingly the *mirror*,
   not the *program* — so the discipline must include *naming what you cannot see* as a first-class
   output. *Expansion corollary (Hyperliquid):* auditability can **split** — the money-custody seam
   (Bridge2) was fully open while the *enforcing core* (HyperCore) was closed; map each layer
   separately rather than calling the whole system "closed" or "open."
6. **Every conservation guarantee bottoms out on one off-chain-correctness oracle — name it.** The
   expansion made this unmissable: zkSync's circuit, Optimism's FPVM, Hyperliquid's validators,
   Drift's price oracle, World ID's orb. The on-chain code can *correctly honor the verdict* (zkSync's
   `verifier.verify`, Optimism's `DEFENDER_WINS` gate, Bridge2's quorum) — auditing that wiring is
   tractable and was clean everywhere — but *whether the verdict itself is sound* is the irreducible
   trust. The honest deliverable is always: "the gate is correctly wired; here is the single oracle it
   trusts." Conservation-via-recompute (Algorand's `totals.All()`, Substrate's self-accounting `Drop`)
   is the one design that needs **no** external oracle — the strongest floors are the ones that
   re-derive the invariant in-protocol rather than trusting any reported state.
7. **Conservation has a *who-is-protected* dimension (system vs caller).** Almost every system enforces
   *system* conservation ("supply can't inflate"). Stacks/Clarity adds the orthogonal *caller*
   conservation: post-conditions let the sender declare the asset movements their tx may cause, and the
   VM aborts if a contract exceeds them (Deny mode rejects *any* unchecked movement). This is Law 2
   ("verify the effect") promoted from an auditor's pattern to a transaction-format guarantee — and a
   reminder that "conserved" should always be qualified by *for whom*: the global books can balance
   while an individual caller is still drained by a contract they under-constrained. The strongest
   posture combines both: system-level conserve-by-construction + caller-level declared bounds.

---

## 5b. The bug-hunt phase — delta-hunt + recent-commits, and the fail-safe-substrate boundary

After the conservation cartography, two dedicated **bug-hunts** stress-tested the corpus's central
claim ("MemeCore is the lone code-level finding") against the highest-EV surfaces. Both are logged in
`AUDIT-LARGECAP-BUGHUNT.md` (L1–L7) and `AUDIT-RECENT-COMMITS-HUNT.md` (R1–R15).

- **Delta-hunt (L1–L7):** apply the MemeCore lens (swallowed errors / nondeterministic map → consensus
  call / unverified system-tx replay) to the **custom consensus deltas** of large-cap geth/op-geth
  forks — where MemeCore's own bug lived. BSC, Polygon, Sonic, Celo, Cronos, Berachain — **all clean**;
  each implements the exact patterns MemeCore got wrong *correctly* (sort/canonicalize before
  consensus-critical use, validate ordering, propagate errors, verify replay). Sonic *contained* the
  MemeCore smell (a map-range in epoch sealing) but canonicalized it in `Build()`.
- **Recent-commits hunt (R1–R15):** read the **freshest code** (post-last-audit) across 3 EVM stacks
  (geth/reth EIP-7928 BAL; op-stack interop traced 3 layers deep: contract → supervisor → reorg) and
  **5 non-EVM teams** (Solana capitalization + Alpenglow; Sui address-balance + Mysticeti; Aptos
  compiler + Coin↔FA; Cosmos Block-STM + staking; Celestia DA). Determinism/conservation/consensus-safety
  primitives **clean** everywhere; the hunt surfaced **several real recent defects** — all *already
  fixed* by their teams.

**The finding of the bug-hunt is a measured boundary, not a vibe — the fail-safe-substrate law:**

> Every real recent defect found in well-engineered chains **failed safe** — it manifested as
> **liveness** (abort/hang/stuck) or **correctness** (wrong-constant), with **conservation and
> consensus-safety intact** — because the chain's *substrate* forces it: checked arithmetic (underflow
> → abort, not wrap), determinism / canonical ordering (no divergence), OCC ordered-commit, exact
> share/rational accounting. **MemeCore is the sole exception** — the one imperative-substrate case
> (geth-fork consensus, swallowed error + nondeterministic map) where the substrate did **not** force
> fail-safe, so its failure shape is **value/consensus** (potential silent divergence). That is exactly
> why it is the corpus's only finding.

The real recent defects, all fail-safe, all pre-fixed (the boundary's "safe" side):
| Defect | Chain | Class (capstone) | Failure shape |
|---|---|---|---|
| Address-balance gas-underflow at settlement | Sui (R8) | dual representation (§Bucket 3) | liveness (settlement abort) |
| Const-fold shift/modulo overflow | Aptos (R9) | compile≡runtime equivalence (§4h) | correctness (wrong constant) |
| Block-STM `CancelAll` ESTIMATE not cleared | Cosmos (R13) | OCC determinism spine (§4g) | liveness (executor hang) |
| Redelegate from removed source validator | Cosmos (R14) | stake accounting | liveness (stuck stake) |
| Proof-querier unbounded `square.Construct` | Celestia (R15) | DA query path | liveness (DoS) |
The two real bugs in *value* code (Sui R8, Aptos R9) landed on the **two predicted frontier classes**
(dual representation; cross-implementation equivalence) — and when the directly-analogous surfaces were
then checked (Aptos Coin↔FA R10, Sui Mysticeti R11), they were **clean**, proving these are *frontiers
where bugs appear*, not universal flaws. *(Meta: the Sui R8 fix is co-authored by this very model,
"Claude Opus 4.8," via Claude Code.)*

**Net:** the lens has run across **~60 systems + 7 large-cap deltas + 15 fresh-code reads (EVM &
non-EVM, 5 non-EVM teams)**, with **every real defect on the fail-safe side of the boundary and
MemeCore the only one across it.** The exploitable *code* surface at the top tier is, on this evidence,
essentially closed; the live risk concentrates at the **fail-safe frontier** (fresh
dual-representation/settlement/equivalence code — caught & fixed) and at the named **off-chain /
cross-client / governance / oracle** substrate.

---

## 5c. The full-stack trust traversal — seven layers, one law

After the chain/protocol corpus (§1–§5b) and the bridge sweep (§4f), the lens was pointed at the **entire
node stack, top to bottom** — seven dedicated deep-sweep folders, each with its own threat model and synthesis,
each reading live client/library source across multiple independent implementations and **recomputing every
load-bearing claim by hand** (the sub-agents only ever returned summaries):

| Layer (folder) | Trust question | The discipline that defends it | Worst failure mode | Residual / named outliers |
|---|---|---|---|---|
| **`bridges/`** | trust *another chain's* summary | name the authorizer; verify the mint (proof vs. attestation) | forged mint / total drain | the trust root (committee→staked→optimistic→proof→issuer→HTLC); ~23 EVM + 20 non-EVM + 7 BTC, all clean |
| **`state-sync/`** | trust a *peer's* summary of your own chain | **verify-before-persist** / bound-before-allocate; anchor to consensus | divergence / accept-invalid / corrupt-DB | **Erigon snapshot registry**, **Prysm checkpoint binding** (the two attested outliers) |
| **`consensus/`** | trust *no participant* | recompute the fork choice; enforce the assumption *exactly* | safety break / reorg / split | when the impossible happens it **halts, not forks** (Sui `panic!`, engine-API `SYNCING`) |
| **`validator-ops/`** | the validator's *economic* surface | minimize verifiable trust; **record before the irreversible step** | MEV-theft / slashing / leader-prediction | the MEV relay (Ethereum's one trusted intermediary); the 1-bit RANDAO bias |
| **`crypto-primitives/`** | the verifier's *own* correctness | reject every malformed input *identically* across clients | **DIVERGE** (clients disagree) | *(re-audited)* alt_bn128 G2 — **both clients subgroup-check**, no divergence |
| **`zk-proving/`** | does the verifier accept only *the truth* | Fiat-Shamir observe-before-sample; bind to the statement | soundness break (Frozen-Heart) | arkworks-groth16 caller-enforces-input-count (integration footgun) |
| **`p2p-eclipse/`** | can the node *reach* the honest network | diversify by network *group*; prove liveness before you answer | eclipse (own all peers → own reality) | discv5's /24-only grouping; gossipsub's operator-set thresholds |

**It is one law wearing seven masks.** Stated at each layer it reads differently — *verify-before-persist*
(sync), *recompute the fork choice* (consensus), *record-before-sign* (keys), *reject identically* (primitives),
*observe-before-sample* (proofs), *prove-liveness-before-answer* (p2p), *name-the-authorizer* (bridges) — but it
is the same instruction: **never act on a summary you have not recomputed, and when you cannot recompute, fail
safe (abort, halt, reject, re-request) rather than guess.** That is the §5b fail-safe-substrate law and the
`AUDIT-REASONER-EPISTEMOLOGY.md §9` *proven-vs-attested ≡ recompute-vs-trust-the-summary* axis, now **measured
end to end**: the same axis that sorts a committee bridge from a light client sorts an attested DA layer from a
KZG-proved one (`bridges/` ↔ `crypto-primitives/`), a checkpoint-trusting Prysm path from a state-root-binding
Lighthouse one (`state-sync/`), a Celestia inclusion-proof-plus-fraud-proof from a PeerDAS validity-proof
(`state-sync/` S7), and a no-PoW soundness parameter from a grinding-augmented one (`zk-proving/`). **The
distinction is scale-free: it is the organizing question of trust at every layer of the stack.**

And the bottom turns out to guard the top: **`p2p-eclipse/` is the precondition for everything above it** —
verify-before-persist verifies *the attacker's* data if every peer is the attacker, so the anti-eclipse layer's
job (diversify by network group, make eclipse cost identities across many ASNs) is the structural guarantee that
a node can reach the **decorrelated honest observer** the entire methodology depends on. The corpus closes its
own loop: the epistemology says *the only defense against a blind spot is an observer who doesn't share it*; the
networking floor is what ensures that observer is reachable.

**The re-audit pass (this is the methodology auditing itself).** Returning to the flagged residuals with the
full-stack picture produced one **self-correction** that is the whole discipline in miniature: the
`crypto-primitives/` entry had claimed *"geth does on-curve only, no alt_bn128 G2 subgroup check,"* and
reconciled the apparent divergence-with-revm by a hypothesis. **Re-reading the actual function body** —
`twistPoint.IsOnCurve()` does the on-curve check *and* a subgroup check (`r·Q == O`) inside a misleadingly-named
function — **reversed the conclusion: both clients subgroup-check, there is no divergence, and no hypothesis was
ever needed.** The error was reading a *call site* (`require IsOnCurve`) without opening the *function* — the
exact `recompute-don't-trust-the-summary` failure the corpus is built to catch, caught here in the corpus's own
output, exactly as MemeCore Pass 6 corrected its own earlier notes. The re-audit pass re-opened **five** flagged items by reading the *functions*, not the call sites: of the
five, **only the one I had explicitly flagged as a *hypothesis* (alt_bn128) was wrong** — and it was my error,
not an agent's — while every agent-reported claim I re-checked verified accurate: Prysm's body-root-only
checkpoint binding (**confirmed**), Erigon's registry trust (**confirmed, and *refined*** — it is registry-
trust-at-import *backstopped by* a fail-safe execution root check that halts rather than accepts a bad
snapshot), c-kzg's commitment+proof subgroup checks and canonical-field check (**confirmed** —
`validate_kzg_g1` does `blst_p1_in_g1`, `bytes_to_bls_field` rejects `≥ modulus`), and Omni's missing slasher
(**confirmed** — `0` slash references in the whole `avs/` dir). The pattern is itself a result: **the errors
clustered exactly where I had stopped recomputing** — a one-line summary I'd glossed — and re-applying the rule
fixed it, while the things I *had* verified, and the things sub-agents reported that I re-verified, held.
**Net result of the full-stack + re-audit pass: still one genuine finding in the entire corpus (MemeCore);
every other system a sound floor + a named residual; one corrected summary and one refined one — the method
demonstrated, and corrected, on its own work.**

A second re-audit wave traced the **observe-before-sample** ordering in the two zkVMs by reading the actual
verify *flow* (not the line-number summary): RISC Zero's `poly_mix` is gated behind the assertion that **all**
tap-group Merkle roots are committed, with the quotient committed *after* `poly_mix` and the DEEP point after
that (`verify/mod.rs:301-347`); SP1's `verify_shard` observes `public_values` + `main_commitment` + the chips
(`:468-488`) **before** it calls `verify_logup_gkr`/`verify_zerocheck`, which sample `alpha`/`lambda`
(`:304-309`). Both **confirmed** — Frozen-Heart closed, read end-to-end.

**An honest accounting of what is *not* settled (because sometimes the next look reverses the last one).** The
alt_bn128 episode is a standing reminder, so the confidence here is graded, not flat:
- **High (re-derived from source, multiple implementations):** the alt_bn128 G2 subgroup check (3 impls), the
  KZG/BLS subgroup+canonical checks, the wire-decoder bounds, the consensus quorum/PoLC/lockout arithmetic,
  the Fiat-Shamir observe-before-sample (Plonky3 + RISC Zero + SP1), the sync verify-before-persist.
- **Medium (read the relevant functions, but not every backend/edge):** the gossipsub scoring composition, the
  full SSZ-decoder edge matrix, the recursion-circuit verifiers, the substrate-bn vs arkworks backend actually
  compiled into each shipped client binary.
- **Deferred by construction (a code read *cannot* settle these — they need security proofs / formal
  verification / live differential fuzzing):** the *soundness bound* of every proof system (query count → bits,
  FRI list-decoding radius, sumcheck error), the *cryptographic* security of each pairing/hash, and the
  absence of an *under-constrained* gate in any large generated constraint system.
- **"No finding" means "none found by this analysis," not proof of absence** — and the corpus contains a
  live demonstration that this analysis can err (alt_bn128, where I read a call site instead of the function).
  That error happened to fail *safe* (I under-credited geth); the discipline's value is precisely that it does
  not assume the next error will. The single positive finding (MemeCore) is the most-scrutinized claim here
  (6 passes, disclosed); it is also the one most worth re-opening with fresh eyes on any future pass — because
  the place overconfidence hides is the conclusion you stopped re-checking.

---

## 5d. The prediction-market vertical — one goal, four floors, four oracles

A focused four-pole study (Polymarket, Augur v2, Azuro v2, Thales/Overtime; see the four
`audits/protocols/AUDIT-*PREDICTION*/*ORACLE*/*POOL*/*AMM*` reports) tested whether the
corpus-wide laws survive a single application domain sampled across **opposite architectures**.
They did — but the floor law had to be *corrected*, and the correction is the lesson.

**The trap, and the correction.** Two poles (Polymarket CTF, Augur ShareToken) agreed too well:
opposite oracles, identical *conserve-by-construction* floor (`Σ numerators = denominator`/`numTicks`).
That made "the floor always conserves" *look* like a law — but both were drawn from the same
floor family (peer-to-peer fully-collateralized complete sets). The third pole (Azuro) **broke
it**: a pool-as-counterparty "house" floor conserves *nothing* — it stays solvent by a *live,
breakable* reserve-locking invariant (`changeLockedLiquidity` reverts if the pool can't cover
worst-case liability; reserves ring-fenced from LP withdrawal), and it introduces an entire risk
bucket — **LP capital** — that the conservation family does not have. The fourth pole (Thales
AMM) added a *third* mechanism: model-priced single-sided positions kept solvent by **explicit
per-market spend caps + spread**, not by collateral identity nor pre-locked per-bet liability.

**The corrected, domain-independent statement of the floor coordinate:**

> The floor's job is never "conserve" per se — it is **"the market maker can honor every
> resolved position."** That goal is met by one of (at least) three mechanisms, and *identifying
> which one you are auditing is the load-bearing judgment*:
> | Mechanism | Guarantee | Examples | New risk it introduces |
> |---|---|---|---|
> | **Conservation** (peer-to-peer mint-pair / complete sets) | locked = max payout by *identity* | Polymarket CTF, Augur ShareToken, Thales `PositionalMarket` | none (no house) |
> | **Reserve-locking solvency** (house / pool counterparty) | lock worst-case liability before accepting, or revert | Azuro `LP` | LP directional P&L + odds-pricing |
> | **Bounded-loss-by-caps** (AMM / scoring rule) | cap cumulative maker exposure per market + spread | Thales `ThalesAMM` | LP *bounded* P&L + model mispricing |
>
> In the conservation family a share-accounting "finding" is almost always a **read error** and
> there is **no LP-risk bucket**. In the other two families the floor is a **live invariant that
> can genuinely break** (under-locked liability, withdrawable reserves, under-counted AMM
> exposure, mispriced model). An auditor carrying the wrong family's instinct will either hunt a
> phantom conservation leak or bless a solvency invariant as "conserving" without recomputing the
> lock/cap math.

**The oracle law held without correction — it is universal.** Every pole telescoped *all*
economic trust onto the actor/mechanism that sets the outcome. The four oracle types map a clean
**expressiveness ↔ determinism / trustlessness** trade-off (no design wins all three):

| Oracle type | Outcome discretion | Backstop | Answers |
|---|---|---|---|
| Augur REP — staked reporting + **own-token fork** | low (trustless) | nuclear fork, no admin | anything (subjective ok) |
| Polymarket UMA — optimistic + **external-token DVM vote** | medium | DVM vote + **bounded** admin override | subjective |
| Azuro — **trusted data provider** + DAO-adjudicated dispute | high | DAO/owner | subjective, fast |
| Thales — **Chainlink DON** price feed, deterministic | minimal (owner only triggers) | none (feed is the answer) | **only** feed-expressible |

This both **specializes** §5/§4(h) (the oracle is the universal residual; only its shape varies)
and **adds a missing axis** the L1/rollup corpus never exercised: the floor is *not one law* but
*one goal via several mechanisms*, and the choice of mechanism determines whether floor-risk is
*nonexistent* (conservation) or a *first-class live invariant + an LP-capital bucket*
(solvency/caps). Same discipline as the alt_bn128 episode (§5c): the win was finding the
**boundary** of an earlier claim, not re-confirming it a fourth time.

---

## 5e. Three DeFi verticals — slashing, continuous solvency, and the unpriceable-collateral seam

Three more domains (restaking/LRTs, on-chain perps, NFT-finance lending; see
`audits/protocols/AUDIT-RESTAKING-EIGENLAYER-LRT.md`, `AUDIT-PERPS-LIQUIDATION-GMX.md`,
`AUDIT-NFT-LENDING-BENDDAO-NFTFI-BLEND.md`) each added a *distinct* extension to the residual
taxonomy rather than re-confirming it. The unifying observation: **§5d's floor mechanisms recur,
but each vertical introduces one genuinely new dimension the prior work never exercised.**

**(a) Restaking — a fourth residual class: *destructible principal* (slashing).** EigenLayer's
floor is the strongest conservation member yet — an ERC4626 share vault with the virtual-shares
inflation guard (`StrategyBase.sol:38,42,118`, `(balance+1e3)/(shares+1e3)`). But above it sits
something no prior vertical had: a third party (an AVS's designated **slasher**) can *destroy* up
to 100% of an operator's allocated magnitude (`AllocationManager.slashOperator:72,428`),
propagated pro-rata to stakers and reaching into the withdrawal queue. Conservation floors answer
"can the system always pay what it owes"; **slashing answers a different question — "can a third
party deliberately reduce what you are owed" — and the answer is *yes, by design, bounded and
attributable.*** The vertical also inverts the oracle finding: EigenLayer's base "oracle" is the
**most trustless of the entire corpus** (a cryptographic EIP-4788 beacon-state proof,
`EigenPod.sol:36,736-745`), yet the LRT built on top (ether.fi) reintroduces a **committee-attested
exchange rate** with only a temporary APR-band guard (`EtherFiAdmin.sol:254-257`) as the weakest
link — proof that *the residual migrates to whatever layer re-tokenizes the position*, and that
wrapping a trustless primitive in a liquid token can **lower** the trust floor.

**(b) Perps — the floor becomes a *continuously-moving* solvency invariant.** GMX is the
house-counterparty family (Azuro's, §5d) under continuous price motion. The floor is a hard
on-chain invariant `reserved ≤ pool ≤ token balance` (`Vault.sol:1136,1143,1178`) that guarantees
*winners are paid* — but keeping the *pool* whole additionally requires **a liquidation engine
that fires in time** (`VaultUtils.validateLiquidation:61-105`) plus a **bad-debt backstop**. That
backstop is the perps-specific residual, and its v1→v2 evolution is the same "who bears the
shortfall" question §5d raised, now answered under time pressure: **v1 socializes the shortfall to
LPs with no insurance fund/no ADL; v2 adds ADL** (force-deleverage winners once trader PnL vs the
pool exceeds `MAX_PNL_FACTOR_FOR_ADL`, `AdlUtils.sol:105-133`). The oracle is a **fifth type** — a
low-latency keeper push **clamped to a Chainlink reference** (`FastPriceFeed.getPrice:272-330`;
v2 `Oracle._validateRefPrice:330-345`). New dimension: **timeliness** — a solvency invariant that
must be *continuously re-enforced*, not locked once.

**(c) NFT lending — when the collateral itself is unpriceable.** The cleanest demonstration that
**the oracle choice and the liquidation design are one decision, and the residual is conserved —
it only moves.** Three answers: BendDAO **leans in** (single admin-pushed floor oracle +
English-auction liquidation; residual = oracle key custody + thin-floor manipulation + auction
liveness; pool/LPs socialize bad debt — `NFTOracle.sol:186,355-384`, `LiquidateLogic.sol`);
NFTfi **refuses** (bilateral, no LTV, no oracle; lender seizes at maturity; **zero protocol bad
debt**; residual = lender underwriting — `DirectLoanBaseMinimal.sol:617-656`); Blend **replaces**
the oracle with a market (perpetual loan, rising-rate Dutch *refinance* auction — the NFT is
"underwater" only when no one will lend even at ~1000% APR; residual = lender vigilance + the
unconditioned UUPS upgrade key — `Blend.sol:328-374,251-283`, `CalculationHelpers.sol:43-94`). The
novelty: a design (Blend) that **deletes** the valuation seam by turning liquidation *itself* into
price discovery — paid for with a less-bounded upgrade key.

**The cross-vertical law, sharpened once more.** Every system still reduces to *a conservation/
solvency floor + a dominant residual*, and the residual is **conserved — it only relocates** with
the design choice. But the residual is now seen to come in **five distinguishable classes**, and a
mature audit names which one(s) a target carries:
1. **6b-equivalence / conservation-accounting** (can value leak by construction — the original);
2. **governance ceiling** (what the admin/upgrade key can do);
3. **oracle / attestation** (who sets the truth/price — now mapped across *seven* oracle types from
   cryptographic-proof ↔ keeper-clamp ↔ optimistic ↔ token-vote ↔ trusted-feed ↔ self-token-fork ↔
   committee-attested, on an expressiveness↔determinism↔trustlessness surface);
4. **liquidation/solvency-enforcement timeliness** (house floors under price motion — must be
   *continuously* re-enforced; backstop = LP-socialization vs ADL vs auction);
5. **destructible principal** (slashing — a third party can deliberately reduce what you are owed).
The discipline is unchanged: name the floor's *actual mechanism*, name *which residual class(es)*
dominate, grade confidence, and treat "found nothing" as "this analysis found nothing." The value
of these three verticals was not three more "sound" verdicts — it was discovering that the residual
**has a richer type system** than the L1/rollup corpus alone revealed.

---

## 5f. Settlement, governance, and the peg — closing three coordinates the corpus kept deferring

Three more domains (cross-chain intents/solvers, on-chain governance/timelock, stablecoin CDPs; see
`audits/protocols/AUDIT-INTENTS-UNISWAPX-ACROSS.md`,
`AUDIT-GOVERNANCE-TIMELOCK-ATTACK-SURFACE.md`, `AUDIT-STABLECOIN-CDP-MAKER-LIQUITY.md`). Unlike §5d/§5e,
these did not add *new* residual classes — they **dissected three the corpus had named but always
deferred to**: the settlement seam (B17), the governance ceiling, and the oracle, now seen through the
peg.

**(a) Intents — the settlement seam at both extremes, and the case where the residual is *empty*.**
UniswapX settles **same-chain atomically**: the resolved (Dutch-decayed) output is *forced* to the
swapper in the same tx the input is pulled via Permit2 (`BaseReactor.sol:116`), so **there is no
oracle, no attestation, no residual** — a fill that can't deliver simply reverts, and governance is
hardcoded out (immutable reactor, 5 bps fee cap, `ProtocolFees.sol:30`). This is the floor at its
theoretical best: *atomicity is the unique case where the residual relocates to nothing.* Across
settles **cross-chain optimistically**: a relayer fronts the destination payout out of pocket
(`SpokePool.fillRelay → :1669`), but **nothing on-chain proves that fill happened** — the refund is
asserted off-chain by a dataworker's Merkle root, admitted only via a UMA optimistic dispute window +
the canonical L1↔L2 bridge (`HubPool.proposeRootBundle:560`, `executeRootBundle` adapter
`delegatecall :678`). The instant settlement spans chains, the **destination-fill attestation**
residual reappears and dominates — and it is the *same* optimistic-oracle seam (UMA) used by Polymarket
and Azuro resolution, now answering "did the remote chain get paid" instead of "did the event happen."
**Unification: optimistic attestation is one reusable answer to the universal residual**, whatever the
question.

**(b) Governance/timelock — the mechanism *behind* the ceiling coordinate, finally opened.** Every
prior audit ended at "a governance ceiling" and deferred. This is the dissection, and it collapses to
one equation: **a protocol's security ceiling = the security of its token-weighted vote + the
timelock's minDelay exit window.** No privileged action exists above that line; an attacker who wins
the vote inherits the timelock's full authority over every downstream contract (incl. proxy upgrades
via a normal `call`). Two structural defenses make it survivable: **(i) vote weight is read at a *past
snapshot block*** (`Votes.getPastVotes` + `_validateTimepoint` revert on `≥ clock()`,
`Governor.sol`-side; Compound `Comp.getPriorVotes` `require(blockNumber < block.number)`) — which is the
*complete* answer to flash-loan vote-borrowing (borrowed-and-repaid tokens write no checkpoint at the
already-past snapshot ⇒ zero weight); and **(ii) the minDelay is a user *exit window***, not
anti-attacker — capture is total but observable and escapable. The real attack surface is **almost
entirely configuration**: `votingDelay == 0` (OZ allows it, collapses the snapshot gap; Compound floors
it at 1), `proposalThreshold == 0`, open `EXECUTOR_ROLE`/stray timelock proposers, cancel-griefing.
**This resolves the §4c most-to-least-centralized spectrum into four readable parameters**
(`votingDelay` / `proposalThreshold` / `minDelay` / role set) — "name the ceiling" now means name those,
not hand-wave at "the multisig."

**(c) Stablecoin CDPs — the peg as an oracle-constraint on a conservation floor, and the
governance dial at its sharpest.** Both Maker and Liquity have a *conserve-by-construction* collateral
floor — Maker's `vat.frob` enforces `art·rate ≤ ink·spot (:163)` on checked double-entry arithmetic;
Liquity enforces `ICR ≥ 110%` with **no governance mint path** (`LUSDToken.mint :99`). But a stablecoin
needs more than conservation: it needs a **peg**, which the ledger alone can't guarantee because "$1"
is external. The two answers are the lean-in/delete dial applied to the *admin key itself*: **Maker
governs the peg** — adjustable risk params, surplus/debt auctions, DSR, and an **uncapped MKR-mint
backstop** (`flop.sol:165`), with `auth` holders able to rewrite every param and even swap any ilk's
price feed (ceiling = "MKR vote + OSM delay"); **Liquity deletes governance** — ownership renounced,
all params `constant`, and the peg pinned by a **permissionless redemption arbitrage** (anyone swaps 1
LUSD → $1 of ETH from the riskiest troves, `TroveManager:925-1023`) that needs no admin. Even their
oracle *failure* philosophy follows the dial: Maker fails **closed** (`spot → 0`, liquidatable —
acceptable because governance can intervene); Liquity fails **open** (runs on `lastGoodPrice` — because
there is no admin to pause).

**The cross-cut.** §5f shows the same dial — **own the residual vs engineer it away** — recurring at
*three different layers*: settlement (optimistic attestation vs atomic-no-residual), the admin key
(Maker govern-everything vs Liquity renounce-everything), and the oracle (swap-the-feed vs
fixed-with-heuristics). It is the same shape as NFT-lending's lean-in/refuse/replace (§5e) and the
prediction-market floor choices (§5d). The corpus-wide statement is now sharp: **every system reduces
to a conservation/solvency floor plus a residual; the residual comes in five classes (§5e); and for
each class a designer faces one recurring dial — *take the trust and bound it* (governance, oracles,
optimistic attestation, ADL) *or delete the trust and pay in flexibility* (immutability, atomicity,
redemption arbitrage, self-token mechanisms).** Auditing is naming the floor's mechanism, the dominant
residual class, and **which side of that dial the design chose** — then verifying the bound (if taken)
or the structural substitute (if deleted) actually holds.

---

## 5g. Opening the foundational boxes — the oracle, the staking rate, the AMM floor, the isolated market

Four more domains (price-oracle networks, liquid staking, AMM cores, isolated lending; see
`audits/protocols/AUDIT-ORACLE-NETWORKS-CHAINLINK-PYTH.md`, `AUDIT-LST-LIDO-ROCKETPOOL.md`,
`AUDIT-AMM-UNISWAP-V2-V3-V4.md`, `AUDIT-ISOLATED-LENDING-MORPHO-EULER.md`). Where §5f *dissected*
coordinates, §5g **opens the boxes that everything else in the corpus sits on top of** — and two of
them (the oracle, the AMM) are the load-bearing primitives the prior ~50 audits deferred to without
ever reading directly.

**(a) The price oracle — the universal residual bottoms out in a signer quorum + a consumer check.**
Every vertical telescoped its dominant residual onto "the oracle." Reading the two dominant networks
shows that residual is, mechanically, **a permissioned quorum attesting an off-chain number, with no
price discovery on-chain**. Chainlink `transmit()` verifies `f+1` owner-appointed signer ECDSA sigs over
a report, takes the **median**, and clamps to immutable `[minAnswer, maxAnswer]` (`OffchainAggregator
:625-681`) — the clamp that *freezes a feed at the boundary during a real depeg* (the LUNA mechanism).
Pyth verifies a **Wormhole guardian-set 13/19** VAA + Merkle proof (`ReceiverMessages:22-148`), meaning
**one global ~13-key quorum sits beneath every Pyth integration on every EVM chain at once** — the
"dominant residual" of dozens of protocols is *correlated through a single signer set*. Two
corpus-closing consequences: **(i) "the oracle" is a multisig** — so the independent-looking residuals
of lending, perps, stablecoins, and prediction markets are not independent; **(ii) half the oracle's
safety is not in the oracle** — both ship a no-staleness getter (`latestAnswer`/`getPriceUnsafe`) and
push freshness/bounds/confidence onto the *consumer*, so a complete audit must read the integrating
contract's oracle-read (`updatedAt`/`conf`/min-max), which is where the deferred trust actually lands.
This is why the corpus was right to name the oracle the residual *and* why naming it was never enough.

**(b) The staking rate — the same residual, layered and correlated.** LSTs (Lido/Rocket Pool) complete
the staking stack the corpus already touched from the top (validator → **LST** → restaking/LRT). The
floor conserves cleanly (Lido rebasing shares `balanceOf = shares·totalPooledEther/totalShares`; Rocket
Pool exchange-rate `ethValue = reth·totalETH/rethSupply`), but `totalPooledEther`/`totalETH` *include the
off-chain beacon balance reported by a permissioned committee* (Lido HashConsensus `support ≥ _quorum`;
Rocket Pool oDAO ≥ 51%), bounded by per-report sanity limits but not removed. This is *mechanically the
same residual* as the LRT rate above it and the Chainlink/Pyth feeds beside it — **the
committee-attests-an-off-chain-number residual recurs at every rung of the staking stack**, so an
integrator stacking LRT-on-LST-on-validator inherits *all* of them, correlated. The two protocols also
split on the §5e *destructible-principal* axis (Lido socializes slashing into holder balances; Rocket
Pool insulates rETH behind node ETH-bond + RPL first-loss). And the headline LST risk — the
**secondary-market depeg** — lives *outside* these contracts entirely: both define only the primary
oracle-rate mint/redeem; the AMM price is a market fact the contracts neither cause nor prevent. The
cleanest example in the corpus of a risk that is real, severe, and *entirely non-contractual*.

**(c) The AMM floor — the conservation floor with the residual subtracted, and a fourth enforcement
mechanism.** Uniswap is the conservation floor in its purest form: v2 is a *single inequality*
(`x·y ≥ k` on fee-adjusted balances, `UniswapV2Pair:182`), v3 *derives* outputs per-tick from sqrt-price
math so the invariant holds by construction, and v4 adds **conservation-by-deferred-settlement** — no
tokens move on swap; every movement is a signed delta in EIP-1153 transient storage, and `unlock`
**reverts unless every delta nets to zero** (`PoolManager:112`). This is a **fourth floor-enforcement
mechanism** (joining conservation-by-identity, reserve-locking solvency, and bounded-loss-by-caps): *let
the books be imbalanced mid-transaction, force them to balance exactly once, globally, at the boundary.*
v2/v3 have **no residual at all** (immutable math, no oracle, no admin over the floor — the limiting
case proving a floor can be one line); v4 **deliberately re-introduces one — the hook** — arbitrary pool
logic that can reshape swap amounts/fees and skim a delta the *caller* pays for, bounded only by net-zero
accounting (which protects the manager's books, *not* the user's value). The v2→v4 arc is the corpus's
central dial in a single version bump: delete the trust (v2/v3) → re-add it by choice as the price of
programmability (v4).

**(d) The isolated market — the oracle as a per-market choice, and deferred-settlement again.** Morpho
Blue and Euler v2 take the *same* conservative-rounding ERC4626 floor but relocate the oracle residual:
Morpho makes it **caller-chosen and never-validated** at market creation (`IOracle.price()` is a bare
`uint256`; the whole risk is the creator's/supplier's oracle choice, *contained per-`Id`*); Euler freezes
it **per-vault immutable** but conventionally points at a *governed router* (trust moves down a level).
Both **socialize bad debt to suppliers automatically and permissionlessly** — so the oracle residual and
the supplier-loss bucket are the *same* risk from two ends. And Euler's **EVC defers solvency checks to
the end of a batch** (`restoreExecutionContext:916-925`) — *structurally the same mechanism as Uniswap
v4's net-zero-delta*. Seeing "let it be imbalanced mid-flight, validate once at the boundary" appear in
a *second, unrelated* domain promotes it from an AMM quirk to a **general primitive**.

**The §5g cross-cut — two findings that close the corpus's two biggest deferrals.** First, **the oracle
residual is a signer quorum**, often a *shared* one (Pyth's 13/19 under everything), which means the
per-protocol "dominant residual" verdicts across the whole corpus are **correlated, not independent** —
a systemic observation no single-protocol audit could surface, and the strongest argument for the
consumer-side oracle-read being a first-class audit object. Second, **"conservation enforced once at a
transaction boundary"** (v4 net-zero-delta ≈ EVC deferred checks) is a *recurring* floor-enforcement
mechanism, the on-chain expression of atomicity (cf. §5f UniswapX), and belongs in the §5e mechanism
list as a fourth member. Net: §5g grounds the two most-cited abstractions in the corpus — "the oracle"
and "the conservation floor" — in concrete, mechanized, and in one case *correlated* form, and confirms
the own-vs-delete dial (§5f) one more time at the most foundational layer: the AMM and Morpho **delete**
the residual to its irreducible minimum; the oracle networks and LSTs **own** it as a bounded quorum;
v4's hook and Euler's router **re-add** it by deliberate design choice.

---

## 5h. Three more — the off-chain-actor residual, the attestor dial, and continuous liquidation

Three further domains (account abstraction, cross-chain messaging, crvUSD LLAMMA; see
`audits/protocols/AUDIT-ACCOUNT-ABSTRACTION-ERC4337.md`,
`AUDIT-CROSSCHAIN-MESSAGING-LAYERZERO-WORMHOLE.md`, `AUDIT-CRVUSD-LLAMMA-SOFT-LIQUIDATION.md`). Each
sharpens a residual class already in the taxonomy and one adds a *new liquidation mechanism*.

**(a) ERC-4337 — the residual is an off-chain actor whose *behavior* the contract cannot bound, only
whose *payment* it can.** Account abstraction has no conservation floor and no oracle; its "floor" is a
**payment invariant** (the bundler always gets paid), secured by the **validate-then-execute** design —
the EntryPoint validates all ops first, *prepays the gas from on-chain deposit before any code runs*
(`AA21`/`AA31`), so a failed execution is contained while a failed validation kills the bundle. The new
residual: a load-bearing part of the trust — the **ERC-7562 mempool rules** (validation must not read
`block.timestamp`, touch others' storage, or use banned opcodes) — is **enforced off-chain by the
bundler and cannot be enforced on-chain**; the contracts even document in their interfaces which rules
they can't guarantee. The stake is the bond that gives those off-chain rules teeth. And the EntryPoint is
the **anti-ceiling**: immutable, ungoverned, no owner/upgrade/pause — the strongest "delete the trust"
instance in the corpus, alongside Uniswap v2 and Liquity. This generalizes a shape seen in Across
(off-chain dataworker) and MEV/PBS (proposer ordering): **whenever a system needs honest off-chain work,
the contract bounds the payment but not the behavior; the residual is that actor's honesty + a bond.**

**(b) Cross-chain messaging — the attestor dial, and a *correlated* residual confirmed.** A generic
cross-chain message has the same irreducible residual as any bridge — *something off-chain must attest
what happened on the source chain* — and LayerZero vs Wormhole span the axis of *who chooses the
attestor*. Wormhole centralizes it in **one global 13/19 guardian set** that attests messages, rotates
itself, **and upgrades its own core** (`Governance.sol`); LayerZero **delegates the choice to each app**
via a per-app `UlnConfig` (`requiredDVNs[]` + optional threshold), with the only protocol floor being
"≥1 DVN." This both adds a third point to the prediction-market oracle spectrum (optimistic [Across] ↔
fixed-quorum [Wormhole] ↔ configurable-quorum [LayerZero]) **and confirms the §5g correlated-residual
finding**: Wormhole is *the same quorum that sits under Pyth*, so a protocol using Pyth prices **and**
Wormhole-bridged assets has a **single** 13/19 point, not two independent ones. The own-vs-delete dial
again: Wormhole owns the attestor (uniform, correlated, self-governing); LayerZero delegates it (flexible,
only as safe as each app's config).

**(c) crvUSD LLAMMA — a new liquidation-mechanism class: continuous soft-liquidation.** Every prior
liquidation in the corpus was **discrete** (auction / keeper seizure / SP-offset / ADL — a threshold
crosses and something happens *at that instant*). LLAMMA is the first **continuous** one: collateral is
spread across narrow price **bands**, and as the oracle falls through them the LLAMMA AMM
**automatically converts collateral→crvUSD band-by-band** — *any* arbitrageur calling `exchange()` does
the work, no `liquidate()`, no trigger, no auction, and it **reverses** on recovery. Health uses
`get_x_down` (the post-soft-liq value), so devaluation alone doesn't liquidate; discrete `liquidate()`
(`health < 0`) is only a *fallback* when a fast oracle crash outruns the soft slide. This **dissolves**
the perps "was the keeper fast enough" timeliness cliff and **migrates** the residual to (i) oracle
honesty/speed (`limit_p_o`'s per-block clamp + dynamic fee do the load-bearing work) and (ii) the
borrower's *continuous spread-bleed to arbitrageurs* (replacing the discrete liquidation penalty). It is
also the corpus's clearest **AMM-as-mechanism**: where Uniswap v4 (§5g) is an AMM as a pure conservation
floor, LLAMMA is an AMM *repurposed as a liquidation engine*, the band grid encoding a continuous
collateral→debt conversion schedule.

**The §5h cross-cut — the liquidation taxonomy is now complete, and the residual's "off-chain"
sub-type is named.** Two consolidations: first, the **liquidation/solvency-enforcement** residual (§5e
class 4) now has its full member list — *discrete auction, keeper seizure, SP-offset, ADL,* and
*continuous soft-liquidation* — spanning the spectrum from "a privileged keeper acts at a threshold" to
"arbitrage continuously and reversibly deleverages with no keeper at all," with the residual sliding from
*keeper-timeliness* to *oracle-honesty + spread-bleed*. Second, several domains (AA bundler, Across
dataworker, MEV proposer, messaging attestor) reveal that the **oracle/attestation residual (§5e class
3) has an *off-chain-actor* sub-type**: an actor whose *payment* the contract bounds but whose *behavior*
it cannot, backstopped only by a bond and a competitive market. Net: §5h fills the last gaps in the
mechanism lists rather than adding new classes — the five residual classes (§5e) and the own-vs-delete
dial (§5f) continue to hold across account abstraction, cross-chain messaging, and a novel continuous
liquidation, which is the strongest evidence yet that the taxonomy is closed under new paradigms.

---

## 5i. Three inverted trust models — issuer-is-god, off-chain backing, and the anonymity-set floor

Three domains chosen because each **inverts** an assumption the prior ~17 verticals took for granted
(permissioned/RWA tokens, Ethena USDe, Semaphore; see
`audits/protocols/AUDIT-PERMISSIONED-TOKENS-USDC-ERC3643.md`, `AUDIT-ETHENA-USDE-OFFCHAIN-CUSTODY.md`,
`AUDIT-SEMAPHORE-ZK-ANONYMITY-SET.md`). Together they expose three things the corpus's "conservation
floor + residual" lens had been *implicitly trusting*.

**(a) Permissioned tokens — the freeze key under all of DeFi (the meta-residual).** Every "sound,
conserve-by-construction floor" verdict in this corpus quietly assumed the collateral token is a **neutral
ERC20**. USDC violates that *by design*: a single `pauser` halts **all** transfers; a single `blacklister`
freezes **any** holder bidirectionally (`notBlacklisted` is checked on sender *and* receiver, so a frozen
address can neither send nor receive — `Blacklistable.sol:50-56` applied at `FiatTokenV1.sol:292-293`); the
`FiatTokenProxy` admin can **replace the entire implementation** over live balances
(`AdminUpgradeabilityProxy:107-132`); and the 1:1 backing is **off-chain with off-chain attestation**.
ERC-3643/T-REX goes further — **identity-gated transfers** (you can't even receive without on-chain KYC,
`Token.sol:417-426`) plus agent **`forcedTransfer`/`burn` as first-class base-layer clawback**. The
corpus-shaking consequence: **every protocol holding USDC inherits Circle's freeze/seize/upgrade power as a
hidden dependency** — blacklisting a pool/router address bricks that contract's USDC leg, a proxy upgrade
could re-author balance semantics underneath all integrators. This is the **anti-pole of the own-vs-delete
dial** (maximal issuer control, by regulatory necessity) and a residual the §5e taxonomy implied but never
isolated: a **token-layer control residual** (destructible principal + governance ceiling, fused and pushed
*beneath* every protocol that holds the token). The honest restatement of dozens of prior verdicts: *sound,
conditional on the collateral token being neutral — which, for the dominant collateral, it is not.*

**(b) Ethena USDe — a floor whose backing is off-chain by design.** Every prior stablecoin kept its backing
on-chain and verifiable (Maker's `vat`, Liquity's troves). USDe is the first whose economic floor is
*deliberately off-chain*: there is **no oracle, no collateralization check, no peg code** — `EthenaMinting`
is a routed swap+mint where the collateral is **`safeTransferFrom`'d straight to allowlisted CeFi
custodians** (`:413-433`) and the dollar peg is held by an **off-chain delta-neutral hedge** on CeFi
exchanges. So the peg residual — **(a) custodian solvency, (b) perp-exchange counterparty risk, (c)
funding-rate sign** — is *structurally invisible to on-chain analysis*. The on-chain code is a *sound
operator interface* (EIP-712 signed orders, per-block rate limits, a halt-only `GATEKEEPER_ROLE`), but it
makes **no solvency claim**; even the yield (sUSDe) is an off-chain-attested number streamed by a privileged
rewarder. This is the dual of (a): USDC's *issuer* can freeze an on-chain balance; USDe's *backing* is
off-chain and unverifiable. Both are the same lesson at the asset layer — **the on-chain conservation floor
is only as real as the off-chain facts it imports** (a reserve, a custodian, a hedge, a funding rate).

**(c) Semaphore — the anonymity-set floor, same zk residual as the rollups.** Semaphore conserves
**eligibility/identity instead of value**, with the *same machinery* a zk-rollup uses for state. The floor
is an **anonymity set** — a Poseidon Merkle tree of identity commitments whose *size is the privacy
guarantee*. A Groth16 proof binds `(merkleTreeRoot, nullifier, message, scope)` so a member proves "I'm
*some* leaf and haven't signaled before in this scope" *without revealing which*; the **nullifier is
anonymous double-spend prevention**. The connecting point: **the on-chain verifier proves almost nothing
itself** — it never re-derives membership, it trusts the *circuit*, and only checks a pairing + a recent
root + nullifier-not-reused. So soundness rests on **exactly the §5c zk-rollup residual** — the trusted-setup
ceremony (toxic-waste `tau` ⇒ forged non-member proofs, silently), circuit correctness, and Poseidon
collision-resistance — **plus one privacy-only term: the anonymity set can be cryptographically sound and
still hide nothing** (a 1-member group gives zero privacy; the contract only rejects *empty* groups). The
analog, for a privacy primitive, of "the conservation floor holds but the oracle lies."

**(a-deep) USDC vs USDT — the two settlement assets are different gods.** A deep comparative
(`AUDIT-LARGECAP-STABLES-USDC-USDT.md`) shows the issuer-is-god model is *not uniform* across the two tokens
that settle most of crypto. The decisive divergence is **seizure**: USDT's owner can `destroyBlackFunds`
(zero a blacklisted balance and **burn it from supply** — irreversible confiscation), where USDC's
blacklister can only **freeze**. USDT also has a **live owner-settable transfer-fee lever** (`setParams`,
capped <0.2%, currently 0) and an **upgrade-by-forwarding** model (`deprecate` → every call delegates to an
arbitrary new contract), all on a single `^0.4.17` owner key with single-step ownership; USDC **splits**
authority across five logic roles + a *separate* proxy-admin key (policy vs code, two Circle multisigs),
freezes-not-destroys, uses a transparent proxy, and adds a modern gasless surface (EIP-2612/3009/1271) whose
own subtlety is the `transferWithAuthorization` front-run/nonce-grief that `receiveWithAuthorization`'s
`to == msg.sender` gate exists to close. And USDT **breaks the ERC20 ABI** (no `bool` return + fee-on-transfer
lever — the footgun that forced DeFi onto `SafeERC20`), a property every "conservation floor" holding USDT
silently depends on handling. Both share the dominant residual — **off-chain bank reserves + partner-gated
redemption**, proven live by USDC's ~\$0.87 SVB depeg (Mar 2023). The lesson sharpens the meta-residual:
*the freeze key under DeFi is not one key — it's two different issuers with different powers, and the more
unilateral one (USDT: seize + tax + forward-upgrade, single owner) is also the larger and the one on the
oldest code.*

**The §5i cross-cut — the floor's three hidden dependencies, named.** These three inversions reveal that the
corpus's "the floor conserves" verdict always rested on three things it had been *trusting without saying
so*: **(1) the token layer is neutral** (false for USDC — the issuer can freeze the floor); **(2) the
backing is on-chain and real** (false for USDe — it's an off-chain CeFi hedge); and **(3) the proof/identity
machinery is sound** (for Semaphore/zk, a trusted-setup-and-circuit assumption, plus the set must be large
enough to mean anything). None of these is visible at the protocol level — each only appears when you *read
one layer down* (the token, the custodian, the ceremony). This is the strongest vindication of the corpus's
core method — **recompute, don't trust the summary** — extended from "recompute the protocol's math" to
"recompute the *assumptions under* the protocol": the asset it holds, the backing behind that asset, and the
cryptography under the proof. The five residual classes (§5e) and the own-vs-delete dial (§5f) still hold —
permissioned tokens are the dial's maximal-own pole, AA/Uniswap/Liquity its maximal-delete pole — but §5i
adds the meta-lesson that **a floor verdict is only as sound as the layer beneath the one you audited.**

---

## 6. Posture & disclosure summary

Defensive throughout: no exploit, no PoC, no weaponization; "no bare safe." The single
exploitable-class finding (MemeCore B/C) was **routed privately** to the project, fix-first.
Live-system requests (a third party's website/forum) were **declined** for active testing and
redirected to passive analysis + owner-run checks + auditing the relevant open-source software
(phpBB) — the boundary held even under repeated pushing. Public audits used `git clone` / public
artifacts only; nothing catastrophic was ever posted.

> **Bottom line:** one reusable lens, ~40 systems, every major paradigm (Move/Rust L1s, parallel
> EVMs, BFT consensus, eUTXO/multi-asset UTXO, account L1s, ZK and optimistic rollups, async-actor
> chains, Substrate, closed-core perps DEXs) — and a consistent two-part answer each time: *a
> conservation floor (named, graded by substrate) and a residual that is a governance ceiling or an
> irreducible 6b equivalence/oracle.* The framework found the one real bug, named every trust boundary
> in proportion, and never overclaimed. The expansion added no findings — it added *resolution*: a
> filled-in conservation ladder, a settlement-seam trust spectrum (validity → fraud → multisig), and a
> cross-language determinism spine (OCC) whose negation is precisely the one bug. The prediction-market
> vertical (§5d, four poles) then *corrected* a law rather than confirming it: the floor is not "always
> conserve" but "winners always paid," met by conservation / reserve-locking solvency / bounded-loss-by-caps
> — with LP capital as a risk bucket present in exactly the non-conservation floors.

Companion index: `AUDIT-METHODOLOGY.md`, `AUDIT-METHODOLOGY-CHECKLIST.md`,
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` (§1–11), `AUDIT-GOVERNANCE-CEILING.md`,
`AUDIT-WEBAPP-GENERALIZATION.md`, and the per-target reports referenced in the table above.
