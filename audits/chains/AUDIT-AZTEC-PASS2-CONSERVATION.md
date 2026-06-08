# Aztec — Pass 2: Value Conservation

**Target:** `AztecProtocol/aztec-packages` @ `32207bf`. **Question:** trace all
balance equations, joins/splits, burns/mints, fees, bridge interactions, and
rollup settlement accounting; for each conservation invariant identify the exact
enforcing mechanism and the layer it lives in (application circuit / protocol
circuit / sequencer / L1 host). **Read-only.** No exploit construction.

---

## The Aztec conservation model (the key structural finding)

Aztec has **no single `sum(inputs) == sum(outputs)` circuit**. Value
conservation is a **composition across three layers**, and that composition —
not any one constraint — is what holds:

1. **Application circuit** (token contract): checked `u128` balance arithmetic +
   authorization, producing `change = consumed − amount`.
2. **Protocol circuits** (kernel + rollup): the consumed notes must *actually
   exist* (note-hash tree membership) and each nullifier is *globally unique*
   (indexed-tree non-membership) → no forging or double-spending the inputs.
3. **L1 host** (Solidity): bridge mint/burn is gated to consumed-once cross-domain
   messages, and settlement binds every effect to a verified proof's public
   inputs.

Conservation therefore lives at **layer boundaries**, which is exactly where the
five-bucket model predicts the residual risk for a recursive cross-layer
architecture — and where every open item below sits.

---

## Application layer — token mint / burn / transfer

| Invariant | Location | Mechanism | Layer | Verdict |
|---|---|---|---|---|
| mint ↑ supply only by minter | `token_contract/.../main.nr:149-155,447-453` | `assert(minters.at(sender).read())` + checked `u128` add to `total_supply` | app circuit | **enforced** |
| burn ↓ supply by exactly amount | `main.nr:170-175,317-320,496-500` | authwit + checked `u128` sub of balance & `total_supply` | app circuit + kernel authwit | **enforced** |
| private split/join conserves | `aztec-nr/balance-set/.../balance_set.nr:62-69` | `assert(subtracted >= amount)`; `change = subtracted − amount` (checked); consumed notes nullified | app circuit | **enforced** |
| consumed notes are real & spent once | (protocol) note-hash membership + nullifier uniqueness (Pass 1 T6/T7) | kernel + rollup | protocol circuit | **enforced** |
| balance arithmetic overflow | `main.nr` / `balance_set.nr` | Noir `u128` `+`/`-` are **checked** (constraint fails on over/underflow) | app circuit | **enforced** |

There is **no explicit `sum(in)==amount+change` assertion** in the app circuit;
it is implied by `subtracted ≥ amount`, `change = subtracted − amount`, and the
protocol guaranteeing the consumed notes exist and can't be re-spent. **Verdict:
enforced by composition** (app arithmetic × protocol note/nullifier integrity).

---

## Bridge — L1↔L2 (amount↔message binding)

| Invariant | Location | Mechanism | Layer | Verdict |
|---|---|---|---|---|
| L1→L2 claim mints exactly the deposited amount | `token_bridge_contract/.../main.nr:49-62,91-111`; `token_portal_content_hash_lib/.../lib.nr:5-48` | amount encoded big-endian into `content_hash`; `context.consume_l1_to_l2_message(content_hash,…)` (kernel nullifies the message) | app circuit + kernel | **enforced** |
| L2→L1 exit burns before withdraw | `main.nr:69-85,117-137`; `lib.nr:51-81` | amount in `content_hash`; `context.message_portal(content)`; `burn_*` reduces supply | app circuit + kernel | **enforced** |
| L1 recomputes the *same* content hash | `l1-contracts/.../Hash.sol:30-39`; `Outbox.sol:163-165` | L1 sha256 over the same fields; `verifyMembership` against the published root | L1 host | **enforced (deterministic both sides)** |
| L1→L2 message consumed once | `Inbox.sol:75-128,141-159` | unique global leaf index + L2-side message nullifier; `consume` is Rollup-only + LAG | L1 host + protocol | **enforced** |
| **L2→L1 message consumed once** | `Outbox.sol:130-170` | per-epoch nullifier **bitmap** keyed by `leafId=(1<<path.len)+leafIndex`; field checks (recipient/chainId/version) | L1 host | **enforced — with a cross-layer caveat (see X2)** |

---

## Rollup settlement — fees, trees, public-input binding

| Invariant | Location | Mechanism | Layer | Verdict |
|---|---|---|---|---|
| **fee-payer balance can't underflow** | `private_tx_base_inputs_validator.nr:47-59` then `private_tx_effect_builder.nr:59` | `assert(!balance.lt(transaction_fee))` **before** `new_balance = old_balance − fee` (Field sub would otherwise wrap) | protocol circuit | **enforced** (the assertion is the guard) |
| fee = gas_used × effective_gas_fees | `fees.nr:43-50`; `gas.nr:27-30` | in-circuit arithmetic; `u32 × u128 ≈ 161 bits < 254` → no Field wrap | protocol circuit | **deterministic (range-safe by size)** |
| effective gas fees consistent (private tail ↔ AVM) | `public_tx_base_inputs_validator.nr:142-148` | `assert(compute_effective_gas_fees(...) == avm.effective_gas_fees)` | protocol circuit | **enforced** |
| all value effects bound to public inputs | `tx_base_public_inputs_composer.nr:119-146` | note/nullifier roots, `out_hash`, `accumulated_fees`, `mana`, **sponge-blob** absorb of every TxEffect field | protocol circuit | **enforced** |
| effects threaded to L1 | `merge_tx_rollups.nr` → `block_root` → `checkpoint_root` → `root_rollup.nr:121` | each level binds child public inputs; final `out_hash`/roots verified on L1 | protocol circuit → L1 | **enforced** |
| L2→L1 out_hash accumulation | `tx_base_public_inputs_composer.nr:138-146`; `merge_tx_rollups.nr:6-20` | unbalanced SHA256 message tree → epoch root | protocol circuit | **enforced** |
| **fee/mana Field accumulation across txs** | `merge_tx_rollups.nr:48` | Field `+`, **not range-constrained**; relies on `num_txs(u16) × fee(≤161b) < 254b` argument | protocol circuit | **deterministic — relies on bound, not constrained** |

### L1 settlement (Solidity)
- Archive-root / inHash / outHash / header / fee bindings to the verified epoch
  proof: `EpochProofLib.sol:165-180,206-208,293-303`, `ProposeLib.sol:286-289` —
  all `require`-gated against proof public inputs. **enforced.**
- Fee split `fee = burn + prover + sequencer`: `RewardLib.sol:213-250`, Solidity
  ≥0.8.27 checked arithmetic, **no `unchecked{}` on value**. **enforced.**
- FeeJuicePortal custody + Rollup-only distribution: `FeeJuicePortal.sol:52,73`.
  **enforced.**

---

## Cross-layer seams (where the residual risk concentrates)

### X1 — revertible note-hash uniquification deferred to the AVM *(from Pass 1 T8)*
`reset_output_validator.nr:52-63`. Private kernel siloes but does **not** make
revertible note hashes unique when public execution follows; the **AVM** must.
**Layer boundary: private kernel → AVM. Verdict: unclear needs human review.**

### X2 — Outbox leaf-id stability across partial/extending epoch proofs
`Outbox.sol:39-47` (verified directly). The L2→L1 double-consume bitmap is keyed
by `leafId`, and the contract **documents** that it *cannot* verify leaf-id
stability across two roots of the same epoch: *"a buggy or malicious rollup that
submitted two proofs for the same epoch where the same message lived at different
positions would … allow that message to be consumed twice."* It is an
**accepted, documented trust boundary** (the proving system must preserve subtree
positions; "the same trust boundary the Outbox has always had with the rollup").
**Layer boundary: L1 host → rollup proving system. Verdict: relies-on-proof
(documented protocol assumption) — the highest-interest conservation seam.**

### X3 — public-data-write correctness deferred to the AVM
`public_tx_base_inputs_validator.nr:273-280`. The tx-base rollup validates that
public-tx effects are **consistent** with the private tail/AVM accumulated data,
but the **AVM** is responsible for the correctness of the public data writes
themselves. **Layer boundary: AVM → rollup. Verdict: relies-on-protocol
(AVM-authoritative).**

### X4 — fee/mana Field accumulation is unconstrained
`merge_tx_rollups.nr:48`. Conservation of accumulated fees relies on a size
argument, not a circuit range check — the same class as Penumbra's
`overflow-checks` hardening item. **Verdict: deterministic, relies-on-bound.**

---

## Bottom line

Value conservation in Aztec is **enforced**, but by *composition*: checked app
arithmetic, protocol note-existence + nullifier-uniqueness, deterministic
amount↔message-hash binding on both bridge sides, and `require`/public-input
binding at L1 settlement. No reviewed path leaves a value effect unbound from the
proof, and bridge mint/burn is consumed-once on both sides.

**The residual risk is entirely at cross-layer boundaries (X1–X4)** — the private
kernel and L1 each *defer* a specific correctness obligation to another layer
(AVM uniquification, AVM public-data writes, the proving system's leaf-id
stability). These are **documented/accepted trust boundaries, not demonstrated
breaks.** That is a distinct finding class from Namada (governance constraint
debt) and Penumbra (arithmetic hardening): Aztec's risk concentrates at the
**recursion/settlement seams**, exactly as the five-bucket model predicts for a
multi-layer rollup.

## Disclosure posture
Defensive, constraint- and require-level reading of public code at a named
commit; no exploit, no PoC. X1–X4 are "confirm the other layer upholds its
obligation," not demonstrated vulnerabilities. Anything concrete would go to
Aztec's security channel under coordinated disclosure, not a public PR.

## Method
Three scoped read-only sweeps (token/bridge app circuits; L1 Solidity
Inbox/Outbox/Rollup/Reward/Portal; Noir rollup fee/settlement circuits) plus
direct verification of `Outbox.sol` and the fee-payer underflow guard.
