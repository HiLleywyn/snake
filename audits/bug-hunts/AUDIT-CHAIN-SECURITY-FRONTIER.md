# Chain-security frontier — the execution client, the fraud proof, and Bitcoin staking

**Why this hunt exists.** This is the highest-altitude round of the bug-hunt arc. After app contracts (EVM), the
cross-VM round, and the off-chain engine layer (CometBFT/mev-boost), this hunt targets the three places where a
single bug doesn't leak one protocol's funds — it **splits the chain, forges a rollup withdrawal, or unlocks
Bitcoin that should be slashable**. Three live, mainnet-critical systems, each securing a major network, each with
one of the largest bounties in its ecosystem.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute-don't-trust in
each system's native invariant model. Anything real and live would be stopped and routed for private disclosure
(redacted here). **All three came back clean — no live finding** — and each had its historically-sensitive seam or
prior CVE confirmed handled at the analyzed version.

| Target | Layer / language | Worst case if buggy | Verdict |
|---|---|---|---|
| **Reth** (post-`v2.2.0` HEAD) | ETH execution client (Rust) — significant-minority mainnet + L2s | **chain split** (state-root divergence) or **remote client DoS** | **clean** (DoS/panic surface exhaustively traced; state-root CVE fixed upstream) |
| **OP Stack FaultDisputeGame** (FDG `2.4.2`) | interactive fraud proof (Solidity) — Optimism/Base/OP-Stack withdrawals | **a false claim resolves as valid** → forged withdrawal / wrong state root finalized | **clean** (the core invariant holds across all six classes) |
| **Babylon** (`v4.3.0` line, `bbn-1`) | Bitcoin staking + finality (Go + BTC script) — largest BTC-staking protocol | **unslashable/stealable stake** or **fake BTC SPV proof** | **clean** (script-template-rebuild closes the unslashable vector; EOTS slashing always extractable) |

---

## 1. Reth — consensus-equivalence + client-DoS (a bug here splits the chain or crashes the node)

**Repo:** `paradigmxyz/reth`, post-**`v2.2.0`** HEAD (`9f2837e`). Live: significant-minority Ethereum mainnet client
+ many L2s; disclosure to `security@tempo.xyz`. The taxonomy is consensus-divergence (disagree with geth → fork) and
DoS, **not value leak** — and the honest confidence-weighting matters: full consensus-equivalence can't be proven by
reading, so the strongest claims are on the exhaustively-checkable DoS/panic surface.

**Per-class:**
- **Consensus divergence — clean (matches spec).** The high-risk seams each recompute-and-compare against the spec
  rule: 4844 `blob_gas_used` multiple-check + `excess_blob_gas` recomputation (`validation.rs:241,417`), EIP-1559
  base fee with the `INITIAL_BASE_FEE` London-transition special case (`:321`), withdrawals/blob-gas roots
  recomputed vs header. **Prior-art anchor:** the Sept-2025 v1.6.0 state-root stall confirms the state-root seam is
  *the* historically sensitive spot — and it's fixed well upstream of this version.
- **Engine API — clean.** `new_payload_v*` runs version-specific validation then delegates; the blob versioned-hash
  cross-check verifies **both count and element-wise order** of sidecar hashes vs the block's blob-tx hashes
  (`cancun.rs:93`); `ensure_well_formed_payload` recomputes the block hash and rejects any mismatch (binds all header
  fields).
- **Block/payload validation — clean.** gas-used ≤ gas-limit ≤ `MAXIMUM_GAS_LIMIT_BLOCK`, the EIP-7934 RLP
  block-size cap on Osaka, withdrawals-root + blob-gas-sum recomputed.
- **P2P / txpool DoS — clean (the highest-confidence section).** Request handlers are bounded by dual count
  (`MAX_*_SERVE`) **and** byte (`SOFT_RESPONSE_LIMIT`) caps; the wire decoder rejects length-inconsistent tx
  announcements (`hashes.len() != types.len()`) and dedups inside `if let (Some, Some)` so no index-panic; the
  txpool bounds memory **three ways** (count, bytes, per-sender slots).
- **Panic surface — clean on attacker input.** The strongest single piece of evidence: the snappy-decompression
  ingestion path **reads the claimed decompressed length and rejects `> MAX_PAYLOAD_SIZE` *before* allocating**
  (`p2pstream.rs:439-449`) — defeats a decompression-bomb OOM. The reachable `.expect()`/`debug_unreachable!` sites
  are all on locally-established invariants, not network input (`debug_unreachable!` is a release no-op).

**No live finding.**

---

## 2. OP Stack FaultDisputeGame — the fraud-proof invariant (a false claim must never resolve valid)

**Repo:** `ethereum-optimism/optimism`, develop HEAD (`dfea9e0`), FDG `@custom:semver 2.4.2` (at/ahead of the deployed
line). Live: secures Optimism/Base/OP-Stack withdrawals; one of the largest Immunefi bounties in crypto. The Cannon
MIPS VM internals were scoped out (covered elsewhere in the corpus); the `vm().step` boundary is confirmed bound to
the bisected position. The single invariant: **a false claim cannot resolve as `DefenderWins` regardless of move
order, clock, or resolution sequence.**

**Per-class:**
- **Resolution correctness (highest) — safe.** Two-phase (per-subgame `resolveClaim` bottom-up, then global
  `resolve`). No subgame can be left unresolved to sneak a false root through: the per-subgame loop reverts
  `OutOfOrderResolution` if any child is unresolved, and global `resolve` reverts unless index 0 is resolved. A
  subgame is countered iff it has an *uncountered* child; the **leftmost-position preference** is the known
  invalid-defense-position griefing mitigation, not a miscount.
- **Clock / chess-timer — safe.** Each move inherits the grandparent's accumulated duration (the chess clock).
  Subtlety verified: the move gate uses `nextDuration == MAX_CLOCK_DURATION` (`==`, not `>=`) and **that is safe
  because `getChallengerDuration` already saturates at MAX** — no off-by-one window. The freeloader/clock-extension
  defense (min-time guarantee at `MAX_GAME_DEPTH-1` / `SPLIT_DEPTH-1`) is bounded to fit uint64.
- **Move / position — safe.** Positions are *derived* from the parent's stored position (never attacker-supplied);
  `_disputed` must equal the parent claim (no claim-substitution); the duplicate check keys on
  `(claim, position, challengeIndex)`; depth bounded by `MAX_POSITION_BITLEN`/`maxGameDepth ≤ 125`.
- **Step / VM binding — safe.** The leaf-level prestate is selected via `_findTraceAncestor` against the **actual
  bisected position**, the prestate preimage is hash-bound (ignoring the VMStatus byte), and the poststate parity
  check (`(parentPos.depth - postState.position.depth) % 2`) correctly handles both attack and defense — a counter
  succeeds exactly when the on-chain VM transition contradicts the disputed claim.
- **Bonds + init — safe.** Bonds credit a single recipient per resolved subgame (no double-credit), with a REFUND
  mode safety valve for improper/blacklisted games and credit zeroed before transfer (no reentrancy). `initialize`
  blocks re-init and enforces a **calldata-length check** that prevents extraData padding from colliding the factory
  UUID; the anchor root must be non-zero and strictly before the disputed L2 block.

**No live finding.** The acknowledged residual ("a proper/finalized game does not by itself imply the root claim is
correct — the guardian blacklist is the backstop") is documented in-source as by-design, not a contract defect.

---

## 3. Babylon — the hybrid Bitcoin-script + Cosmos taxonomy (unslashable stake or fake BTC proof)

**Repo:** `babylonlabs-io/babylon` (`v4` module, `v4.3.0` line), HEAD `fe3dd3e`. Live: `bbn-1`, the largest
BTC-staking protocol; disclosure to `security@babylonlabs.io`. Value is locked by **Bitcoin scripts** and the
protocol is a **Cosmos chain** verifying BTC SPV proofs + BLS/EOTS finality — so the taxonomy is hybrid.

**Per-class:**
- **BTC staking script / tx validation (highest) — clean.** The chain **never trusts a user-supplied script**: it
  *rebuilds* the expected taproot pkScript from `BuildStakingInfo(...)` where **covenant keys and quorum come from
  chain params, not the user** (`validate_parsed_message.go:32-105`), then byte-matches the actual output. The
  slashing tx is forced to pay the governance `SlashingPkScript` at ≥ `value*rate` with change to the staker
  timelock; the unbonding output is byte-matched against `BuildUnbondingInfo`. **No script-template-mismatch /
  unslashable-stake path** — this is the highest-value vector and it's closed at the root.
- **SPV / BTC light client — clean.** Header validation delegates to btcd's vetted `CheckBlockHeaderContext` (PoW +
  2016-block retarget) and `CheckBlockHeaderSanity`; fork replacement requires **strictly greater** cumulative work;
  merkle inclusion carries the CVE-2012-2459 guards (rejects `proofLength==64` and the 1-element forgery, requires
  non-coinbase index, k-deep confirmation).
- **Finality / EOTS double-sign slashing — clean.** Equivocation detection is symmetric (both fork-after-canonical
  and canonical-after-fork slash). The decisive binding: a height maps to **exactly one** committed public-randomness
  leaf (`StartHeight + Proof.Index == BlockHeight` with Merkle inclusion), so an FP **cannot equivocate on the
  randomness to dodge key extraction** — two sigs at one height reuse R → `eots.Extract` recovers the key via
  `x = (s1-s2)/(e1-e2)`. An honest FP (never reusing R) can't be slashed.
- **Unbonding / timelock — clean (Bitcoin enforces it).** The unbonding output carries the same slashing path and
  the covenant pre-signs the unbonding-slashing tx, so unbonded stake stays slashable through its timelock;
  `BTCUndelegate` is intent-based detection of an already-broadcast BTC spend, not a chain-side early withdrawal.
- **Cosmos-SDK hygiene — clean.** Consensus-path map iteration is explicitly sorted; privileged msgs gate on
  `authority`. The one smell — `SlashingRate.Float64()` feeding `MulF64` (float-in-consensus) — is traced to a
  governance param bounded to (0,1) at ≤4 decimals with `LegacyDec.Float64()→ParseFloat` being IEEE-754-deterministic
  across Go platforms; **named, matched to a prior accepted audit observation, not inflated into a finding.**

**No live finding.**

---

## Synthesis — the method at the top of the stack

1. **The higher the altitude, the more the "invariant" is the whole game.** At this layer there is one sentence per
   target whose violation is catastrophic: "Reth computes the same state root as geth," "a false claim never resolves
   valid," "staked Bitcoin is always slashable." The hunt's job was to find the *specific code* that makes each
   sentence true and confirm no path around it — resolution-order guards + clock saturation (OP), the
   script-rebuild-from-params (Babylon), the recompute-and-compare seams (Reth).
2. **Honest confidence-weighting is itself a deliverable.** Reth's report led with the exhaustively-checkable DoS/panic
   surface and explicitly flagged that full consensus-equivalence can't be proven by reading — the opposite of
   overclaiming. That calibration is what makes the clean verdicts trustworthy.
3. **The subtle "looks wrong, is right" cases are where a shallow pass produces false positives.** OP's `==` vs `>=`
   clock check *looks* like an off-by-one until you see `getChallengerDuration` saturates at MAX; Babylon's
   float-in-consensus *looks* like a non-determinism bug until you see the bounded-precision governance param. The
   method's value is resolving these to *why* they're safe, not flagging them.
4. **CVE/prior-art anchoring on every live target.** Reth's state-root stall (Sept-2025), the merkle-malleability
   CVE-2012-2459 in Babylon's SPV, the documented FDG griefing mitigations — each hunt located the historically
   sensitive spot and confirmed it's handled at the analyzed version. Same "deployed == audited" discipline applied
   to known issues, now at the chain-security layer.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
