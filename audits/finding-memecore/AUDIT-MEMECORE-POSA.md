# Go-MemeCore (PoSA consensus) — Six-Bucket Trust Audit

**Target:** `memecore-foundation/Go-MemeCore`, cloned `/tmp/gomeme`, HEAD `4ab3ee9`
(v1.15.3). A **go-ethereum fork** (EVM L1, Cancun/EIP-4844) whose delta from upstream is a
custom **PoSA (Proof of Staked Authority)** consensus engine (`consensus/posa/`) plus
MemeCore hardforks (GasTree / RewardTree / CanPraTree).
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite
the exact constraint. The high-value items below are **consensus-robustness / hardening**
observations visible in the public repo, written fix-first — **not** an exploit recipe. The
determinism item (§6, item B+C) touches consensus safety and is the kind of thing that should
be **routed privately to the MemeCore foundation** (security contact / bug bounty) for
confirmation against their closed system contracts, rather than treated as settled.

**Why this target:** for a chain fork the methodology's sharpest question is **Bucket 4 — fork
lineage: what was inherited vs. changed.** geth core is heavily audited; the risk concentrates
in the PoSA engine, which is MemeCore's own code.

---

## Bucket 1 / 5 — native-token reward conservation (the inherited part is clean)

`accumulateRewards` (`posa.go:938`) mints a **fixed, config-selected** per-block reward to the
coinbase:

```go
blockReward := Phase1BlockReward
if config.IsRewardTreeFork(header.Number) { blockReward = RewardTreeForkBlockReward }
// overflow-checked before adding:
_, overflow := new(uint256.Int).AddOverflow(balance, blockReward)
if overflow { return errors.New("validator contract balance overflow") }
stateDB.AddBalance(header.Coinbase, blockReward, ...)
```

Inflation is therefore **bounded and deterministic** (a constant per block, switched once at
the RewardTree hardfork height), and the add is **overflow-guarded**. `Finalize`
(`posa.go:657`) propagates errors from `verifyValidators`, `accumulateRewards`, and `snapshot`.
**Verdict: enforced** for the in-Go issuance. The *redistribution* of that reward to validators
happens inside the **system contract** `timedTask` (below), whose conservation is on-chain
Solidity not in this repo — a Move↔Rust-style closed seam (`§6`).

---

## Bucket 6 — the PoSA system-contract seam (where the findings are)

Per block, `Finalize` → `settleRewardsAndUpdateValidators` (`contract.go:85`) makes a
system-originated EVM call to the reward contract:

```go
data := rewardABI.Pack("timedTask", signer, validatorList)   // 0x1234…0001
msg := &core.Message{ From: sysCallAddr /*0xfff…ffe*/, GasLimit: 50_000_000, GasPrice: 0, To: rewardAddr, Data: data }
ret, leftOverGas, err := vmenv.Call(msg.From, *msg.To, msg.Data, msg.GasLimit, common.U2560)
if p.enableEventLogging { /* …err only used for logging… */ }
state.Finalise(true)
return nil
```

### A. Reward distribution lives in a closed system contract (named seam)
The validator set is **read** from `getValidators()` at `0x1234…0002`; reward settlement is
**delegated** to `timedTask` at `0x1234…0001`. Both are on-chain contracts not in this repo, so
their conservation/authorization is unverifiable here — and **whoever can upgrade those two
contracts controls validator membership and reward distribution** (the governance ceiling,
below). This is the standard PoSA trust relocation (as in BSC parlia). **named, irreducible
from the client side.**

### B. The system-call result is not enforced (hardening debt → robustness risk)
`settleRewardsAndUpdateValidators` **returns `nil` unconditionally**: the `err` from
`vmenv.Call` is referenced only inside the `if p.enableEventLogging` block (and logging is
typically off in production). So if `timedTask` **reverts**, the revert is **swallowed** — the
EVM rolls back the call's own state changes, `state.Finalise(true)` commits the rest, and the
block is still treated as valid with reward settlement silently skipped. Robust PoSA
implementations (BSC parlia) treat an unexpected system-call failure as **block-invalidating**.
**Recommendation:** propagate the call error (return it from `Finalize`) so a reverting
`timedTask` cannot produce a "valid" block that skips settlement. **hardening debt.**

### C. Non-deterministic validator ordering into a consensus-critical call (determinism risk)
`validatorList` is built by ranging a **Go map** with no sort (`contract.go:93–96`):

```go
for validator := range validators { validatorList = append(validatorList, validator) }
```

Go randomizes map iteration order, so `validatorList`’s order **differs across nodes and runs**,
and it is then passed as input to a state-changing system call that is part of the block's
state transition. If `timedTask`'s **gas usage or resulting state** depends on the array order,
nodes can diverge. Combined with **B** and the fixed 50M gas budget, the sharp edge is:
order-dependent gas could push `timedTask` to out-of-gas-revert on some nodes' ordering but not
others' → divergent state roots → a **silent consensus split** (silent precisely because the
revert is swallowed and the block is still "valid" on both sides). In practice a running chain
implies `timedTask` is currently order-insensitive and well under the gas limit — so this is
**latent fragility, not a demonstrated live split** — but it depends on an unseen contract and
would re-arm on any change to either side. **Recommendation:** **sort `validatorList`
deterministically** before the call (parlia sorts its validator set), independent of fixing B.
This is the highest-value item and the one to confirm privately with the team. **robustness /
constraint debt (consensus-adjacent).**

---

## Bucket 2 — witnessed objects / signing

Block authorship is `ecrecover`-verified (`contract.go:87`) with a fallback to the local
`p.signer` during production (`:90`) — consistent because the producer *is* the signer. The
validator authority set is the witnessed object, sourced from the `0x…0002` contract. Inherited
geth secp256k1/state machinery. **inherited; the PoSA-specific signer handling is consistent.**

---

## Bucket 4 / governance ceiling

- **The two system contracts** (`0x1234…0001` reward, `0x1234…0002` validatorSet) are the trust
  root: they define who validates and how rewards flow, and they are read/called every block.
  Whoever holds their **upgrade authority** controls the chain's validator membership and native
  emission — apex power (`AUDIT-GOVERNANCE-CEILING.md`), and not visible in this repo.
- **Hardfork switches** (RewardTree changes the block reward; GasTree / CanPraTree) are
  config-gated lineage transitions — verify their activation heights and the new constants match
  the intended economics.
- Inherited geth = high evidence depth; the audit weight is the PoSA delta above.

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1/5 | Per-block reward issuance | **enforced** — fixed, deterministic, overflow-guarded mint to coinbase |
| 1/6 | Reward *redistribution* (`timedTask`) | **named seam** — in closed system contract; conservation unverifiable here |
| 6-B | System-call error swallowed (`return nil`) | **hardening debt** — propagate the error; a reverting `timedTask` should invalidate the block |
| 6-C | Unsorted (map-order) validator list into the system call | **robustness / consensus-adjacent** — sort it; latent split risk via order→gas→OOG with B; confirm privately |
| 2 | Signer recovery / authority | **inherited; consistent** |
| 4 / ceiling | `0x…0001`/`0x…0002` system contracts + upgrade authority + hardfork constants | **trust-boundary debt (by design)** — the validator/emission trust root |

## What this audit did NOT cover (coverage honesty)

- The two **system contracts** (`timedTask`, `getValidators`) — closed/on-chain; their reward
  conservation, authorization, and order-sensitivity are the decisive unknowns (and exactly what
  determines whether §6-C is benign or live).
- The PoSA **snapshot / signer-cadence / in-turn** logic (`snapshot.go`, `posa.go` sealing) and
  fork-choice beyond the finalize path.
- The custom hardfork **constants and activation heights** (RewardTree block reward value, etc.).
- Everything inherited from upstream geth (EVM, txpool, p2p, trie) — treated as high-evidence
  inherited code.

## Addendum — Pass 2: sealing cadence & epoch validator transition (largely standard / sound)

Read after the disclosure of §6-B/C, to characterize the rest of the engine. Conclusion: it is
conventional clique/parlia and sound at the import gate — which keeps §6-B/C as the standouts.

- **Anti-domination & in-turn (inherited clique, correct).** `verifySeal` (`posa.go:551`) and
  `apply` (`snapshot.go:138`) enforce `errRecentlySigned` with the classic bound `limit =
  len(Signers)/2 + 1` — a validator cannot re-sign within half-the-set blocks, so single-
  validator domination requires >½ collusion. In-turn vs no-turn difficulty
  (`diffInTurn=2`/`diffNoTurn=1`) is checked against `snap.inturn` (`:575`). The checkpoint
  signer auth check precedes `inturn`, so an empty/forged set fails authorization
  (`errUnauthorizedSigner`) rather than reaching the `% len(signers)` division. **enforced.**
- **Epoch transition is contract-gated at import (sound, parlia-style).** At a checkpoint the
  snapshot **replaces** `Signers` wholesale from `header.Extra` (`snapshot.go:147–152`); the
  authenticity of that list is enforced in `Finalize → verifyValidators` (`posa.go:436`), which
  requires `header.Extra == sort(getValidators(@0x…0002, parent))`. The producer side
  (`prepareValidators`, `:639`) builds `header.Extra` from the same sorted contract output —
  **symmetric**, and **both** the validators list and the reward-call validators are sorted on
  this path (note: the *reward-call* list in §6-C is the one that is **not** sorted —
  `contract.go` builds it from a map without sorting, unlike here). **enforced at import.**
- **Deferred-verification seam (6a, hedged).** The *snapshot / header-verification* path trusts
  `header.Extra`'s validator set **before** the `Finalize` contract check — i.e. `verifySeal`
  authorizes signers from a snapshot whose checkpoint set is not yet contract-verified. This
  matches parlia (verification deferred to full block import, which is the canonical gate, so a
  forged-checkpoint branch cannot finalize state). It is called out only so the team can confirm
  no sync mode makes an **irreversible** trust decision on the pre-`Finalize` snapshot. **named,
  matches known-good pattern.**
- **Reinforces the ceiling.** Unlike clique's vote-evolved signer set, MemeCore **replaces** the
  set from the `0x…0002` contract each epoch with no on-chain-history self-consistency — so that
  contract (and its upgrade authority) is the *absolute* authority over validator membership.
  Strengthens the governance-ceiling note above.

**Pass-2 verdict:** the sealing/epoch machinery is standard and sound at the import gate; the
two consensus-robustness items worth fixing remain **§6-B (swallowed system-call error)** and
**§6-C (unsorted reward-call validator list)**, both already routed privately.

## Addendum — Pass 3: custom hardforks (GasTree / RewardTree / CanPraTree) — clean

- **RewardTree** (`RewardTreeForkBlock`) — block-reward reduction (to `300·10^17` wei). Covered
  in Bucket 1/5: fixed, deterministic, overflow-guarded switch. **enforced.**
- **GasTree** (`GasTreeForkBlock`) — base-fee floor reduction (1500 → 15 gwei). Forks
  `CalcBaseFee` (`consensus/misc/eip1559/eip1559.go:55`). Reviewed the arithmetic:
  - transition block returns `GasTreeInitialBaseFee` directly (`:61`); London-init is correctly
    skipped when GasTree is already active (`:66`); the EIP-1559 up/down algorithm is the
    standard geth one (big.Int, no overflow; decrease `num ≤ parentBaseFee` so no underflow).
  - The bespoke part is a **minimum base-fee floor** (non-standard for Ethereum, which lets
    base fee decay to 0): enforced on the decrease path (`:101–108`) — `GasTreeInitialBaseFee`
    post-fork, `InitialBaseFee` pre-fork — and the floor selector (`IsGasTreeFork(parent.Number)`)
    is consistent with the transition selector. Floor is maintained across the unchanged/increase
    paths (those only hold or raise the fee). **Verdict: correct; an economic-policy floor, not a
    security issue.** (Base-fee *burning* vs. routing is in the inherited state-transition layer,
    out of this fork's scope.)
- **CanPraTree** — named in `README.md` as a supported hardfork but **has no implementation in
  this version** (no `CanPra*` references anywhere in the Go source). **documentation/code drift
  (Bucket 4):** the README advertises a fork the code doesn't yet contain — harmless but worth
  aligning (it's likely planned). **not present.**

**Pass-3 verdict:** the custom hardforks are clean — RewardTree and GasTree are correct,
bounded parameter-switch forks; CanPraTree is unimplemented (README drift only). Nothing here
changes the standing conclusion: the only items worth fixing remain **§6-B** and **§6-C**.

## Responsible-disclosure note

Items **§6-B and §6-C together describe a *latent* consensus-robustness concern** (swallowed
system-call error + non-deterministic validator ordering). It is visible to anyone reading the
public repo and is **not** presented here with any trigger or exploit. Because it touches
consensus safety, the right path is to **share it privately with the MemeCore foundation** (their
`SECURITY.md` / security contact) so they can confirm against their system contracts and, if
warranted, sort the validator list and enforce the call result. Nothing is posted as a weapon;
the recommendations (sort the list; propagate the error) are the fix. Companion to
`AUDIT-DRIFT-PERP.md` / `AUDIT-MARGINFI-LENDING.md` (closed system-contract seams) and
`AUDIT-GOVERNANCE-CEILING.md` (the upgrade-authority trust root).

## Addendum — Pass 4: independent corroboration + sharpened reachability analysis

Two independent static analyses (external) reproduced §6-B/§6-C **exactly** — same
`settleRewardsAndUpdateValidators`, same map-ranged `validatorList`, same swallowed `vmenv.Call`
error, same `state.Finalise(true)`/`return nil`. So the *code shape* is corroborated ("not
hallucinated"). The work below sharpens **reachability** (the load-bearing question), correcting the
analysis in **both** directions so the severity is neither over- nor under-stated.

### Consensus-path: confirmed (this is not a background task)
`Finalize → settleRewardsAndUpdateValidators(…, state, snap.Signers)`, and
`FinalizeAndAssemble → header.Root = state.IntermediateRoot(...)`. So whatever the reward call does
to `state` **directly determines the block's state root**, on both the producer and verifier paths.
Steps proven from the repo: (1) `snap.Signers` is map-derived → order is non-canonical per node/run;
(2) that order becomes the `timedTask` calldata; (3) it runs in finalization; (4) errors don't abort
finalization (§6-B). A repo search found **no sort/fix commit**.

### Correction toward *more* concern — the caller check likely passes for the real call
The repo reward bytecode dispatches selector **`0x992ffba7`** (`timedTask(address,address[])`) to a
function that begins with a caller check. The consensus engine calls **from the system address
`0xffff…fffe`**. If that leading check is the standard `require(msg.sender == 0xffff…fffe)`
(`onlySystem`), the consensus invocation **passes** it and proceeds to use the validator array — so
the hopeful "reverts on the caller check before touching the array" branch does **not** apply to the
real finalization call (it would only fire for some *other* caller). Confirm what the check compares
to; if it's the system address, the array-is-reached branch is the live one.

### Correction toward *less* concern (load-bearing) — the state root is write-order-invariant
The Ethereum state root (`IntermediateRoot`) is a pure function of the final `{address → account}`
MPT, **independent of write/iteration order**. So "honest nodes build different calldata → different
root" is **not automatic**: if `timedTask` succeeds and the rewards are a commutative set of balance
writes, every order yields the *same* final state → the *same* root → **no divergence**, despite the
non-canonical calldata. This is precisely why §6-C is *latent, not demonstrated*, and why a naive
`[A,B,C]` vs `[C,B,A]` root-compare at a comfortable gas budget can show equal roots and **falsely**
read "inert."

### Therefore the real split requires order to change the *final state* — two specific vectors
1. **Gas-edge (the genuine B×C split path).** The reward call's gas is a **finite, fixed
   `GasLimit: 50_000_000`** (`contract.go:50`) — so the gas-edge is **structurally open**, not closed
   by an unlimited-gas argument. If `timedTask`'s cost under some orderings approaches 50M, then for
   the *same block* one node's order completes (writes rewards) while another's **OOGs → reverts**
   (all writes rolled back); because the error is **swallowed (§6-B)**, the OOG node *finalizes a
   no-reward block anyway* while the other finalizes a with-reward block → **two "valid" blocks,
   divergent roots.** B and C are *both* required: without the swallow, the OOG node errors loudly
   instead of silently producing a divergent block. *(A full revert in **every** order is
   order-invariant → same no-op root → "silent reward-settlement failure," a real bug but not a
   split.)*
2. **Order-dependent committed computation.** Even with no OOG, divergence occurs if the *successful*
   path writes an order-sensitive value — a stored accumulator, integer-division remainder/dust
   handed to "the first" validator, or duplicate handling. Gas-independent; would survive even
   unlimited gas.

If each **verifier** rebuilds the calldata locally from its own `snap.Signers` map iteration (rather
than replaying the producer's calldata verbatim), the divergence is **producer-vs-verifier on the same
block** — real, not hypothetical — but still gated by the two vectors above (MPT invariance).

### The decisive test (corrected) — and an honest "can't run it here"
I also cannot execute it from this environment (no GitHub DNS to clone/build; and I will not build a
triggering PoC). The gas-accurate simulation the team can run:
- Same parent state / header / signer set, at the **actual mainnet gas budget**, against the **live**
  reward implementation (not privnet genesis).
- **Vector 1:** find whether any reordering flips success↔OOG at 50M. If yes → catastrophic.
- **Vector 2:** among orders that all succeed, compare roots. Differ → catastrophic; identical →
  this vector inert.
- All orders fully revert → "silent reward-settlement failure," not a split.

### Net severity (sharpened, unchanged in spirit)
**Credible possible consensus split** via the gas-edge × swallowed-error interaction (and/or an
order-dependent committed write); **not proven** without a gas-accurate, live-implementation
simulation; and specifically **not** provable by naive order→root comparison (MPT write-order
invariance). The repo proves the non-canonical calldata, the swallowed error, the consensus path, and
the finite 50M budget; it does **not** prove live divergent state roots. The fix is **unconditional
and cheap regardless of which branch is true — sort `validatorList`, propagate the call error** — which
is exactly why this was routed to the team to resolve reachability against the real gas constant and
reward contract. Posture unchanged: defensive, no PoC, fix-first.

## Addendum — Pass 5: deeper static dig (re-cloned v1.15.3) — divergence is in the verify path; latency proof strengthened

Re-cloned `memecore-foundation/Go-MemeCore` HEAD `4ab3ee9` (v1.15.3) and read the full path. New, all
**proven from the Go source**:

- **The validator update is contract-side; `ret` is unused.** `settleRewardsAndUpdateValidators`
  (`contract.go:85-162`) packs `timedTask(signer, validatorList)` and calls it; the return `ret` is
  referenced **only** inside `if p.enableEventLogging` (`:126-158`). The "update validators" effect is
  entirely the contract's own storage writes — the Go side reads nothing back. `signer` (the other
  calldata arg) is deterministic (`ecrecover`); **only `validatorList` order is non-canonical.**
- **Both produce and verify rebuild the calldata locally from a map — divergence is in the verify
  path, not hypothetical.** `Snapshot.Signers` is `map[common.Address]struct{}` (`snapshot.go:27`).
  Producer: `FinalizeAndAssemble → p.Finalize(...) → settleRewardsAndUpdateValidators(…, snap.Signers)`,
  then `header.Root = state.IntermediateRoot(...)` (`posa.go:714,720`). Verifier: block import calls
  `Finalize → settle(…, snap.Signers)` (`posa.go:673`) and compares its computed root to `header.Root`.
  The synthetic reward call is **not stored in the block** — every importing node **re-derives the
  calldata by ranging its own `snap.Signers`** (`contract.go:94`, no sort). Go randomizes map
  iteration, so producer and each verifier feed `timedTask` a **differently-ordered array for the same
  block.** (Contrast the *epoch* path, which **is** sorted — `verifyValidators` requires
  `header.Extra == sort(getValidators)` — so only the reward call lacks the sort.)

- **Latency proof, strengthened (and this is the key correction).** Because every importing node ranges
  its map independently, *if* `timedTask`'s committed state or gas depended on order, producer-vs-
  verifier roots would diverge on **essentially every block** (orders are independently randomized per
  node, per block) — and the chain could finalize **nothing**. MemeCore mainnet finalizes blocks.
  **Therefore the live `timedTask` is provably order-invariant *right now*** — not merely "probably,
  rare-edge-case," but "must be fully order-commutative or the chain would be wholly broken." So this
  is **latent fragility, conclusively not a live split.**

- **Which vector could re-arm it (and which can't).** Gas-edge is *unlikely*: under EIP-2929 the gas
  for a straight reward loop is order-invariant (the cold/warm cost is set by the *union* of slots
  touched — each distinct slot is cold exactly once regardless of order — and 50M is a large budget).
  The plausible re-arming vector is an **order-dependent committed write** in a future `timedTask`
  upgrade — e.g. integer-division **remainder/dust handed to a positional element** (`validatorList[0]`),
  or a **pool-exhaustion early-exit** ("pay until the pool runs dry"), both of which also make gas
  order-dependent. Either would make producer-vs-verifier roots mismatch on every block instantly.

### Reframed severity (sharper, and more useful)
This is best characterized **not** as "critical, exploitable now" but as a **removed determinism
invariant / latent consensus landmine**: the client provides **no** canonical ordering, so consensus
correctness rests *entirely* on the **closed, upgradeable** `timedTask` contract remaining
order-commutative — and that contract is the **mutable** side (the governance ceiling, §4). A routine,
innocuous-looking reward-logic change (adding remainder handling, a pool cap, per-validator weighting
with rounding) would **brick consensus** (every block forks producer-vs-verifier), with the failure
**silenced** by §6-B so nodes finalize divergent "valid" blocks rather than erroring. The fix restores
the missing client-side guarantee at zero cost: **sort `validatorList`** (parlia does) **and propagate
the call error.** Current status: **not live, conclusively latent**; the value of fixing it is removing
a landmine under any future reward-contract upgrade, not patching an active exploit.

## Addendum — Pass 6: the rest of the consensus delta (full pass for the team) — clean; the finding sharpened

After the disclosure, a full pass over MemeCore's remaining consensus surfaces (turning "one finding +
fix" into a complete review). Two honest corrections to the earlier residual list, and a sharpening of
the finding itself.

### Correction: surfaces I'd flagged that **don't exist** in MemeCore
- **No BLS fast-finality / `votepool` / vote-attestation.** MemeCore's PoSA has no `consensus/posa`
  vote pool or BLS aggregation (`grep`: none) — that's a **BSC parlia-v2** feature, not present here.
  MemeCore is a simpler **clique/parlia-v1-style** engine (block-sealing + snapshot + the system-call
  reward). So there is no >2/3-stake-QC surface to audit; the earlier "votepool/BLS" residual was
  mis-attributed from BSC. Removed.
- **No `feynman`/`stakehub` staking module.** No on-chain staking delta (`grep`: none); validators are
  sourced from the system contract (v1-style), not an in-protocol staking module. The earlier
  "stakehub/feynman" residual also doesn't apply. Removed.
  *(This is the recompute-don't-trust discipline applied to my own notes: the BSC-derived residual list
  didn't survive contact with MemeCore's actual, smaller surface.)*

### The epoch validator-set transition is canonical — and consensus-*enforces* the sort
This is the important part, because it sits **right next to the bug** and makes the finding precise:
- **`verifyValidators` (`posa.go:436-454`):** at each epoch boundary it fetches the validators from the
  contract, **`sort.Sort(validatorsAscending(validators))` (`:445`)**, serializes them, and requires
  **`header.Extra[vanity:suffix] == sorted-signers`** or `errMismatchingCheckpointSigners` (`:451`). So
  the checkpoint validator set carried in the header is **consensus-enforced to be the canonically
  sorted set** — every node rejects a header whose validator bytes aren't sorted.
- **`prepareValidators` (`:639-648`):** the producer builds `header.Extra` from the *same*
  `sort.Sort(validatorsAscending)` output — symmetric with verify.
- **`snapshot.apply` checkpoint (`snapshot.go:144-152`):** at the epoch boundary it **replaces
  `snap.Signers`** by parsing that just-verified, canonically-sorted `header.Extra`.

**Consequence:** `snap.Signers` (the validator-set map) has **identical contents on every node**, derived
from sorted, consensus-checked bytes. The validator *set* is fully deterministic.

### The finding, sharpened
MemeCore **already applies the exact canonicalization the fix needs** — twice
(`verifyValidators` + `prepareValidators`), and it's even **consensus-enforced** (`header.Extra` must be
sorted). The lone defect is that `settleRewardsAndUpdateValidators` (`contract.go`) consumes the
resulting `snap.Signers` **map** by ranging it **without re-applying that sort** before packing it as the
ordered `timedTask(signer, validatorList)` argument. So this is not "they don't sort" — they sort at the
epoch boundary and consensus-check it; they missed re-sorting at the *one* consumption site where the set
becomes an ordered call argument. The fix is literally the canonicalization they already do:
`sort.Sort(validatorsAscending(validatorList))` (or `bytes.Compare`) before `rewardABI.Pack(...)`, plus
propagating the call error. (Cf. §6-B/§6-C and Pass 5.)

### Remaining surface (clean / named)
- **Seal cadence / anti-domination** (`verifySeal`, in-turn difficulty, `errRecentlySigned` with
  `len(Signers)/2+1`) — standard clique, reviewed in Pass 2, **clean**.
- **The two system contracts** (`0x…0001` reward / `0x…0002` validatorSet) — closed/on-chain; the
  irreducible trust (and the upgrade authority is the governance ceiling). Unchanged.

**Pass-6 verdict:** MemeCore's consensus delta is **smaller than BSC's** (no BLS finality, no staking
module) and **canonical everywhere it matters except the one reward-call consumption site** — which it
sorts and consensus-enforces at the epoch boundary but skips at the call. The corpus's single finding
stands, now maximally precise: **one missed re-sort at one consumption site, in an engine that otherwise
sorts and verifies the same set correctly.** No further finding.

---

## Pass 7 — re-audit with skeptical fresh eyes (the "sometimes you're wrong, look again" pass)

After the alt_bn128 episode (where a one-line summary of *another* codebase turned out to invert the truth on a
deep re-read — `../crypto-primitives/`), the finding itself was re-opened from source with the assumption that
it might be **wrong**, and both load-bearing claims were re-traced in the actual current client
(`consensus/posa/contract.go`, `settleRewardsAndUpdateValidators`):

1. **Unsorted validator list — re-confirmed.** `validatorList := make([]common.Address, 0); for validator :=
   range validators { validatorList = append(validatorList, validator) }` (`:93-96`) builds the list by
   **iterating a Go `map[common.Address]struct{}`** (randomized iteration order), and it is passed **directly**
   to `rewardABI.Pack(rewardMethodSet, signer, validatorList)` (`:106`) — **no `sort.Slice` anywhere between
   the loop and the Pack.** The order in which validators are handed to the reward contract is therefore
   non-deterministic across nodes.
2. **Swallowed system-call error — re-confirmed, and this is the spot that most deserved a second look.** The
   reward call `ret, leftOverGas, err := vmenv.Call(..., msg.GasLimit /* 50_000_000 */, ...)` (`:124`) is
   followed by an `if err != nil` (`:127`) — but that check is **nested inside `if p.enableEventLogging`**
   (`:126`), and even when reached it only `log.Error`s; the `err` is **never returned**. The function then
   runs **`state.Finalise(true)` (`:160`) and `return nil` (`:161`) unconditionally.** So a reward call that
   reverts or hits the 50M-gas edge differently on different nodes (because the validator order differs) is
   **swallowed**, the block is finalized anyway, and the function reports success.

**Verdict of the re-audit: the finding stands, verified from the current source, not from prior passes.** The
two ingredients of a latent consensus split — *non-deterministic input to a metered system call* + *the error
of that call discarded with unconditional finalization* — are both present exactly as described. The single
most-scrutinized claim in the corpus was re-opened on the explicit premise that it might be wrong, and reading
the real code confirmed it. The fix is unchanged: **sort `validatorList` before the Pack, and propagate the
`vmenv.Call` error (return it) instead of swallowing it** — both small, both hardfork-gated.
