# Large-cap bug-hunt — hunting the *delta*, not the base

The one real finding in this corpus (MemeCore) was in the **custom consensus delta a geth-fork added on
top of audited geth**, not in inherited code. So the highest-EV large-cap hunt is: take large-cap chains
that are **forks-with-custom-consensus** (or that ship **recent** consensus/feature code), and hunt the
*delta* for the failure classes that actually bite — the **MemeCore set**:
- **(B) swallowed errors** in consensus-critical paths (a reverting system call silently produces a
  "valid" block);
- **(C) non-deterministic iteration** (Go map ranged without sort) feeding a state-changing /
  consensus-critical call → divergent state roots;
- missing checks / unverified system-call replay in new code.

Cores (EVM, Move VM, …) are the most-audited code on earth — skipped. **Anything live + exploitable is
stopped-and-notified privately; only redacted placeholders appear here.** Defensive, no PoC.

---

## L1. BSC (BNB) — parlia consensus delta + fast-finality (clean; canonically-correct counterpart to MemeCore)
**Target:** `bnb-chain/bsc` HEAD `3cf9043`, `consensus/parlia/parlia.go`. BSC is the **largest
parlia-derived geth fork** — i.e. the real, top-5-cap sibling of MemeCore's lineage. I hunted the exact
MemeCore failure classes, focusing on the **newer fast-finality code** (`distributeFinalityReward`,
BEP-126/319), which is the least-audited consensus surface.

**Result: clean — and it is the canonically-correct version of the MemeCore bug.** Same code pattern
(map → validator list → consensus-critical system call), opposite handling:
- **Class C (non-determinism) — FIXED here.** `distributeFinalityReward` builds the validator list from a
  Go **map** (`for val := range accumulatedWeights`, non-deterministic — *exactly* like MemeCore), but
  then **`sort.Sort(validatorsAscending(validators))`** before packing the system call, and builds the
  parallel `weights` array in the sorted order. So the calldata is canonical across all nodes. *(This is
  the precise line MemeCore is missing.)*
- **Class B (swallowed error) — FIXED here.** Every system-call path **propagates errors** (`return
  err` throughout `distributeFinalityReward`, `slash`, `distributeIncoming`), and `Finalize` asserts
  **`len(*systemTxs) == 0`** at the end (`:1491-1492`, "the length of systemTxs do not match") — no
  extra/curtailed system txs.
- **System-call replay is verified, not trusted.** `applyTransaction` reconstructs the `expectedTx` from
  the system message, and in verification mode **requires the block's actual system tx to be present and
  its hash to byte-equal the expected** (`:22-32`, error on mismatch) — a verifier cannot be fed a
  different system tx than the producer deterministically computed. Errors propagate.

**Significance.** Hunting the highest-value MemeCore classes in the *largest* parlia chain's *newest*
consensus code returned clean — and BSC implements the exact pattern MemeCore got wrong, **correctly**
(sort + verify + propagate). This (a) clears BSC on this surface, and (b) **independently confirms the
MemeCore finding is a genuine deviation from canonical parlia practice** — the parent chain sorts the
map-derived validator list and verifies/propagates, MemeCore does neither. The contrast is the proof.
**Residual:** the rest of parlia (vote/BLS aggregation in `votepool`, snapshot/validator-set transition
at epoch, the stakehub/feynman staking delta) — large surfaces, partially read; the fast-finality reward
+ system-call path is the MemeCore-class core and it's clean. **No finding.**

---

## L2. Polygon (POL/MATIC) — bor consensus delta: state-sync + producer selection (clean)
**Target:** `maticnetwork/bor` HEAD `706b800`, `consensus/bor/bor.go`. Bor's custom delta over geth is
the **heimdall→bor state-sync** (a consensus-critical system call importing off-chain events) and the
span/producer selection — both prime MemeCore-class surfaces. Hunted classes B + C.
- **Class C (determinism) — clean.** Validator sets and selected producers are consistently
  **`sort.Sort(valset.ValidatorsByAddress(...))`** before use (`:650,677,842,1062`), so the producer
  ordering is canonical. The **state-sync** is applied in **strict sequential ID order**:
  `CommitStates` (`:1758`) sets `from = lastStateID+1` (read from on-chain state), and
  `validateEventRecord` (`:1892`) requires **`lastStateID+1 == eventRecord.ID`** (+ chainID + time
  bound); on any invalid/out-of-order event the loop **`break`s** (`:1860`), so only a strictly
  contiguous, validated prefix of events is ever applied — deterministic across nodes, no gaps, no
  reordering.
- **Class B (swallowed error) — clean.** The state-sync system call propagates: `gasUsed, err =
  CommitState(...); if err != nil { return nil, err }` (`:1875-1878`); `LastStateId` errors propagate
  (`:34,44`). No swallow.
- Per-block state-sync gas is bounded (`totalGas`), and `eventRecord.ID <= lastStateID` is skipped
  (idempotent replay guard).
**Result: clean** on the MemeCore classes. The bor↔heimdall boundary is the **cross-layer seam**
(bor trusts heimdall to supply correct, ordered state-sync events and the validator spans) — the
irreducible residual, same shape as the other settlement seams; but bor's *application* of heimdall
data is deterministic, strictly-ordered, validated, gas-bounded, and error-propagating. **No finding.**

---

### Large-cap delta-hunt status (2 of the biggest geth forks, both clean)
Applied the proven MemeCore lens (custom-consensus delta + the B/C failure classes) to the two largest
geth-fork large caps — **BSC** (parlia + fast-finality) and **Polygon** (bor state-sync + producer
selection). Both **clean**, and both implement the exact patterns MemeCore got wrong **correctly**
(sort the map-derived list; validate/order; propagate errors; verify system-tx replay). The honest
pattern: **well-resourced large-cap teams get the consensus delta right** — MemeCore is the exception
(a smaller, less-reviewed parlia descendant), which is precisely why it's the corpus's one finding. The
remaining large-cap delta surfaces (opBNB/Mantle op-stack deposit/derivation, Cronos, Sonic/Lachesis,
Gnosis posdao) are the next candidates, but the EV is declining: the failure class is rare at this tier.

---

## L3. Sonic / Fantom (S/FTM) — Lachesis epoch-sealing + SFC system-call (clean; verified through the dependency)
**Target:** `0xsoniclabs/sonic` HEAD `dc8f989`, `gossip/blockproc/{sealmodule,drivermodule}` +
`Fantom-foundation/lachesis-base inter/pos/validators.go`. A genuinely *different, large* consensus
delta (Lachesis aBFT DAG + the SFC/driver "internal transactions" called during epoch sealing — a
system-call-during-finalize pattern). Newer code (recent Sonic rebrand). Hunted classes B + C.
- **A real MemeCore-smell — traced and cleared.** `OperaEpochsSealer.SealEpoch` (`sealer.go:72`) does
  **`for v, profile := range s.bs.NextValidatorProfiles`** over a **map** — the exact MemeCore pattern.
  But the loop only `builder.Set(v, weight)` into a *keyed* `pos.BigBuilder` (order-independent), and
  `builder.Build()` assigns validator indices via **`sortedArray()` — "sorted by weight and ID",
  `sort.Sort(array)`** (lachesis-base `validators.go:97,164-172`). So the resulting validator set is
  **canonical regardless of map-iteration order**; everything downstream iterates by validator *index*
  (`for newValIdx := 0; newValIdx < newValidators.Len()`). Class C **clean** — the canonicalization is
  in `Build()`, not an explicit sort, so it required reading through the dependency to confirm.
- **System-call calldata is canonical.** Driver internal-txs build the SFC epoch metrics by validator
  *index* (`driver_txs.go:116-137`) and seal with **`es.Validators.SortedIDs()`** (`:147`); cheaters
  come from an ordered slice; confirmed DAG events are `sort.Sort(confirmedEvents)` (`c_block_callbacks.go:193`).
- **Class B (errors).** The SFC/driver calls are **deterministic EVM internal txs** (canonical
  calldata) applied through the standard EVM path with receipts — so any revert is *uniform across all
  nodes* (same input → same result), which is precisely what prevents the MemeCore-style *silent
  divergence* (there the danger was nondeterministic input → different revert outcomes per node).
**Result: clean.** The one map-range that looked like the MemeCore bug is rendered deterministic by
`Build()`'s weight+ID sort; system-call inputs are canonical; internal-tx failures are uniform.
**Residual:** Lachesis event/consensus internals (BLS/quorum, the DAG finalization) — the deeper
consensus layer, not opened. **No finding.**

### Status (3 large-cap consensus deltas, all clean)
BSC, Polygon, Sonic — three structurally different large-cap consensus deltas (parlia+fast-finality;
bor state-sync; Lachesis epoch-seal+SFC), all **clean** on the MemeCore classes. Sonic is the most
instructive: it *contains* the MemeCore smell (a map-range in epoch sealing) but canonicalizes it in
`Build()` — caught and cleared only by tracing into the dependency. The pattern holds firmly: large-cap
teams canonicalize before consensus-critical use; MemeCore's raw unsorted map → system call is the
genuine outlier.

---

## L4. Celo (CELO) — custom fee-currency state-transition delta: ERC-20 gas, debit==credit (clean)
**Target:** `celo-org/op-geth` HEAD `6d8cea0`, `core/state_transition.go` + `contracts/celo`. Celo's
delta is a **modification of the conservation-critical fee path**: gas can be paid in allowlisted ERC-20
"fee currencies," so `buyGas`/refund/fee-distribution are custom. This is exactly the kind of edit to
the EIP-1559 burn/fee path (audited clean in vanilla geth, `AUDIT-ETHEREUM-EIP1559.md`) where bugs hide.
- **Conservation holds exactly (debit == credit).** Debit: `buyGas` → `subFees(mgval)` where
  `mgval = gasLimit·gasPrice` (`:330-392`). Credit (fee-currency path, `CreditFees`, `:804-833`):
  `refund = gasRemaining·gasPrice`, `tipTxFee = gasUsed·gasPrice − gasUsed·baseFee`,
  `baseTxFee = gasUsed·baseFee` → distributed to payer / coinbase / FeeHandler. Sum =
  `gasRemaining·price + gasUsed·price = gasLimit·price = mgval`. **Exact** — no leak in the custom path.
- **Class B (errors) — clean.** `if err := contracts.CreditFees(...); err != nil { return nil, err }`
  (`:835-839`) — a failed fee-currency credit **aborts** the tx (no silent strand/divergence). The
  upfront `canPayFee` balance gate precedes the debit (`:378`).
- **Malicious-fee-currency risk is bounded.** Fee currencies must be **allowlisted** (the
  `FeeCurrencyDirectory` registry, governance-vetted), and the fee-currency call carries a bounded
  **intrinsic gas** (`CurrencyIntrinsicGasCost`, `:129`, capped) — mitigating the "arbitrary ERC-20
  code in the gas path" reentrancy/gas-grief concern.
- **Difference from vanilla geth (noted, not a bug):** baseFee routes to the **FeeHandler** (buyback/
  burn/community), *not* the in-protocol burn — conserved (distributed), just a different sink.
**Result: clean** — the custom fee path conserves exactly, propagates credit errors, and bounds the
fee-currency contract call. **Residual:** the **fee-currency allowlist governance** (a malicious/buggy
*allowlisted* ERC-20 is the trust surface, vetted by governance) and the **exchange-rate oracle**
(`ConvertCeloToCurrency`, `:821` — the CELO↔fee-currency rate is a trusted input). **No finding.**

### Status (4 large-cap deltas, all clean)
BSC (parlia+fast-finality), Polygon (bor state-sync), Sonic (Lachesis epoch-seal), Celo (ERC-20
fee-currency). Four structurally-different large-cap deltas — consensus reward/validator, cross-layer
state-sync, DAG epoch-seal, and a custom fee/conservation path — **all clean** on the MemeCore classes
and on conservation. The custom fee path (Celo) is the most conservation-relevant edit and it balances
to the wei. Consistent result: large-cap deltas are carefully engineered; the trust sits at governance
(allowlists, upgrade authority) and oracle inputs, not at exploitable code bugs.

---

## L5. Cronos (CRO) — EVM `bank` precompile: caller-namespaced mint/burn (clean)
**Target:** `crypto-org-chain/cronos` HEAD `6385c1c`, `x/cronos/keeper/precompiles/bank.go`. Cronos's
custom delta (the `x/evm` core is an Ethermint dependency) includes a **bank precompile** exposing
cosmos `MintCoins`/`BurnCoins`/`SendCoins` to EVM contracts — a high-risk conservation surface (EVM code
that can mint/burn native coins). Hunted authorization + conservation.
- **The authorization model is caller-namespacing — clean.** The mint/burn denom is
  `denom := EVMDenom(contract.Caller())` (`:130`), and `EVMDenom(token) = EVMDenomPrefix + token.Hex()`
  (`:56-58`). So a contract can mint/burn **only the denom keyed to its own address** — it cannot touch
  another contract's denom. Each EVM contract controls exactly its own native-coin supply (the correct,
  token-contract-like authorization). **No cross-contract mint.**
- **Conserving + guarded.** Mint = `MintCoins(module)` → `SendCoinsFromModuleToAccount(addr)`; Burn =
  `SendCoinsFromAccountToModule(addr)` → `BurnCoins(module)` (`:137-148`) — the checked bank ops
  (`AUDIT-COSMOS-BANK.md`), conserving 1:1. Amount validated ("invalid amount", `:124`), recipient
  blocklist-checked (`checkBlockedAddr`, `:92-98`), and the whole action runs in
  `stateDB.ExecuteNativeAction` (`:132`) so it is **journaled and reverts atomically** with the EVM tx.
**Result: clean** — caller-namespaced denom is the load-bearing authorization (a contract can only mint
its own token), conservation rides the checked bank keeper, and the action is atomic with the EVM tx.
**Residual:** the native CRO↔EVM balance sync + 18-vs-native-decimal conversion lives in the **Ethermint
dependency** (not in-repo), and precompile registration / module permissions (`permissions.go`) is the
governance surface. **No finding.**

## L6. Mantle (MNT) — skipped (repo is deprecated l2geth)
The public `mantlenetworkio/mantle` is the **pre-bedrock l2geth** stack (v0.4.3); current Mantle runs an
op-geth fork (MNT as gas token, EigenDA), which is a separate repo not pulled here. Auditing the dead
l2geth has no live value. **Not audited** (would need the current op-geth fork to check the MNT
gas-token fee path, analogous to Celo L4). Noted for honesty, not a result.

---

## L7. Berachain (BERA) — BeaconKit deposit/staking state-transition (clean)
**Target:** `berachain/beacon-kit` HEAD `b0aa196`, `state-transition/core/validation_deposits.go`. Custom
consensus delta (CometBFT + EL via engine API); the conservation-critical seam is EL-deposit-contract →
beacon validator stake. Hunted the eth2-class deposit bugs (double-process / skip / reorder / count
mismatch). **Result: clean — carefully validated.**
- **Strict contiguous ordering.** Genesis (`:53-58`) and live (`:129-136`) both require
  `deposit.GetIndex() == depositIndex + i` → `ErrDepositIndexOutOfOrder` otherwise. No gaps, no
  reordering.
- **Count match.** `len(localDeposits) == depositIndex + len(blkDeposits)` or `ErrDepositsLengthMismatch`
  (`:119-125`) — a block can't add/omit deposits vs the local (EL-mirrored) view.
- **Content match against local store + root.** Each block deposit must `Equals` the local store's
  deposit at that index (`ErrDepositMismatch`, `:138-139`), and the local deposit Merkle root is
  cross-checked against `blkDepositRoot` — so a forged deposit can't be slipped in. The local store
  mirrors the EL `BeaconDeposit` contract.
- Per-block deposit cap (`maxDepositsPerBlock`) bounds processing; validator-set cap enforced at genesis.
**Result: clean** — deposits are credited to validator stake in strict order, count/content/root-validated
against the EL contract; no double-credit, skip, or reorder. **Residual:** the EL↔beacon engine-API
boundary and the BLS/withdrawal-credential crypto (deposit signature verification) — read at interface;
the deposit *accounting* is robust. **No finding.**

### Status (6 large-cap deltas hunted, all clean; 2 unavailable)
Hunted: **BSC, Polygon, Sonic, Celo, Cronos, Berachain** — parlia fast-finality, bor state-sync,
Lachesis epoch-seal, ERC-20 fee-currency, EVM↔bank precompile, and beacon deposit/staking. All **clean**
on the MemeCore classes and on conservation. **Unavailable:** Injective (private repo), Mantle (public
repo is the deprecated pre-bedrock l2geth). The verdict is now firm across 6 structurally-distinct
top-cap consensus/execution deltas: well-resourced teams sort/canonicalize before consensus-critical use,
validate ordering with strict indices, match against a local/EL view, and propagate errors. **MemeCore
remains the lone outlier** — the only delta in the entire corpus that fed an unsorted map into a
consensus-critical system call with a swallowed error. The trust in every clean case sits at governance
(allowlists/upgrade authority) and oracle/cross-layer inputs, not at exploitable code.
