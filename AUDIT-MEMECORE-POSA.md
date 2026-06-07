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
