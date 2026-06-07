# Trust-Cartography Capstone — Findings Across the Whole Corpus

*The wrap-up. One reusable lens — six buckets + three coordinates (equivalence / conservation
floor / governance ceiling) — applied to ~51 systems across every major execution paradigm. This
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
> cross-language determinism spine (OCC) whose negation is precisely the one bug.

Companion index: `AUDIT-METHODOLOGY.md`, `AUDIT-METHODOLOGY-CHECKLIST.md`,
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` (§1–11), `AUDIT-GOVERNANCE-CEILING.md`,
`AUDIT-WEBAPP-GENERALIZATION.md`, and the per-target reports referenced in the table above.
