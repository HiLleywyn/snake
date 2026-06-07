# Canton Network / Splice (Canton Coin "Amulet") — Six-Bucket Trust Audit

**Target:** `canton-network/splice`, cloned `/tmp/splice`, HEAD `b499b51`. The open-source
tokenomics of the Canton Network: **Daml** smart contracts (190 `.daml`) implementing **Canton
Coin** (the "Amulet"), governed by the **DSO** (Decentralized Synchronizer Operations — the
on-ledger party representing the Super-Validator collective), plus ~5,600 Scala files of node/app
infrastructure.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite the
exact constraint. Nothing routed privately — none found. Focused on the **Amulet conservation
core** (the token's whole risk surface); coverage gaps stated.

**Why this target ("a big unknown"):** a genuinely new substrate for the corpus — neither EVM,
Move, UTXO, nor Solana, but **Daml** on a consortium synchronizer. The test was whether the
six-bucket lens transfers. It does, cleanly — and Daml turns out to enforce conservation much like
Move's linear types, via its **atomic consume/create + signatory model**.

---

## How Daml enforces conservation (the substrate — Bucket 1/2 fused)

In Daml a token is a *contract* (`Amulet`) with **signatories**; a transaction **consumes**
(archives) input contracts and **creates** output contracts atomically, and the ledger rejects it
unless every consumed contract existed and the required parties authorized it. That is the same
"can't forge, can't vanish, authorization-checked" property the corpus found in Move's linear
types — here enforced by the **Daml ledger model** rather than a type system. So the *structural*
half of conservation (inputs were real, outputs are created in one authorized atomic tx) is given
by the platform; what the Splice code must add is the *arithmetic* half: outputs + fees ≤ inputs.

---

## Bucket 1 / 5 — Amulet transfer conservation (verified by recompute; enforced)

The transfer pipeline (`executeTransfer'`, `AmuletRules.daml:1108`): `summarizeAndConsumeInputs`
→ `preprocessOutputs` → `summarizeTransfer` → **`checkTransferConstraints`** → create outputs.
The conservation arithmetic is in `summarizeTransfer` (`:1474`):

```daml
leftOverAmount =
    inp.totalAmuletAmount + totalAppReward + totalValidatorReward + totalUnclaimedActivityRecord
  + totalValidatorFaucet + totalSvReward + totalDevelopmentFund      -- all inputs (incl. reward coupons)
  - totalOutputAmount - sum outputFees                                -- minus outputs and their fees
senderChangeAmount = leftOverAmount                                   -- remainder returned to sender
senderChangeFee    = min 0.0 leftOverAmount                           -- negative iff inputs insufficient
```

and the gate (`checkTransferConstraints`, `:1074`):

```daml
| summary.senderChangeFee < 0.0 = Left (mkInsufficientFundsFailure ...)   -- inputs < outputs + fees ⟹ abort
| length inputs  > maxNumInputs  = Left ...
| length outputs > maxNumOutputs = Left ...
| otherwise = Right ()
```

**Recompute:** `inputs = outputs + outputFees + senderChange` with `senderChange ≥ 0` enforced — a
textbook UTXO conservation identity. The sender's change is created as a new Amulet
(`createTransferOutputs`); the fees are the burn, converted to reward coupons by `issueRewards`
("issue rewards for burns", `:1118`). Reward coupons enter circulation **as transfer inputs** here
— and the code deliberately folds the validator faucet into the reward amount "so that clients …
do not get the impression that amulet is created out of thin air" (`:~1517`): the designers reason
about conservation explicitly. **Verdict: enforced invariant** (balance check + Daml atomicity).

**Arithmetic (Bucket 5):** all amounts are Daml **`Decimal`** — exact 38-digit fixed-point with
overflow-throwing semantics, **no floating point**. So the summations are exact within precision;
there is no rounding-direction game to get wrong (unlike the AMM/LST integer paths). `maxNumInputs`
/`maxNumOutputs` bound the transaction size. Holding fees are asserted `== 0` on transfer
(`require "totalHoldingFees == 0"`, `:1477`) — demurrage is charged only at `Amulet_Expire`, a
separate path. **enforced.**

---

## Bucket 4 — issuance (mint side): rate-limited rounds, DevNet-gated taps

Real Amulet creation is **not** an open mint. The generic `AmuletRules_Mint` (`:328`) and
`AmuletRules_DevNet_Tap` (`:352`) both `require "isDevNet flag is true"` — **test-net only**. On
mainnet, new Amulet enters only through **mining-round reward issuance**: the round lifecycle
(`AmuletRules_AdvanceOpenMiningRounds` → `MiningRound_StartIssuing` → `MiningRound_Close`/`Archive`)
issues reward coupons (app/validator/SV) per round under an issuance config, which are then redeemed
as transfer inputs (above). Issuance is therefore **rate-limited by the round cadence and the DSO-set
config**, not mintable on demand — the inflation control. (The full per-round issuance curve was not
recomputed — coverage gap.) **structurally bounded; the per-round math is the residual to verify.**

---

## Bucket 2 — authority / witnessed objects

- **The DSO is the signatory** on `AmuletRules` (`:154`) and on the mining rounds, so every
  rules-level action (config, round advancement, issuance, DevNet taps) is authorized by the DSO
  party. Reward coupons and validator rights are Daml contracts whose signatory/authorization the
  ledger checks on consumption.
- Inputs to a transfer are consumed `ContractId`s the ledger verifies exist and are authorized by
  the sender/owner — the Daml analogue of "witnessed objects." **enforced by the platform.**

---

## Bucket 4 / governance ceiling — the DSO is the trust root

The **DSO party** is the on-ledger embodiment of the Super-Validator consortium; via Canton's
multi-party authorization it is jointly controlled by the SVs' governance. It can `AmuletRules_SetConfig`
(`:837`), schedule future configs, advance/close rounds, and (off this package) drive Daml package
upgrades. So **the DSO controls Amulet economics and rules** — apex power per
`AUDIT-GOVERNANCE-CEILING.md`, by design for a consortium ledger. The `isDevNet` gate keeps the
free-mint taps off mainnet. The Scala layer + the Canton synchronizer/sequencer (separate from this
repo) are the operational trust substrate beneath it. **trust-boundary debt (by design)** — the
honest framing is *"Canton Coin is conserved by the Daml ledger and an explicit balance check; its
rules and issuance are governed by the SV consortium (DSO)."*

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 1 | Transfer conservation | **enforced invariant** — `inputs = outputs + fees + change`, `change ≥ 0` (recompute-verified) + Daml consume/create atomicity |
| 1/2 | Daml ledger model | **platform-enforced** — consumed inputs must exist & be authorized; outputs atomic (Move-linear-types analogue) |
| 5 | Daml `Decimal` exact fixed-point | **enforced** — no float; overflow-throwing; size-bounded inputs/outputs |
| 4 | Mint = rate-limited round issuance; `Mint`/`Tap` `require isDevNet` | **structurally bounded** — no on-demand mainnet mint; per-round curve = residual |
| 2/4 | DSO signatory / authority | **platform-enforced** authorization |
| ceiling | DSO (SV consortium) sets config/rounds/issuance/upgrades | **trust-boundary debt (by design)** — the economic & rules trust root |

## What this audit did NOT cover (coverage honesty)

- The **per-round issuance curve / reward computation** (`Issuance.daml`, `RewardAccountingV2`,
  `MiningRound_StartIssuing` math) — the mint-rate residual; structurally bounded but its exact
  economics weren't recomputed.
- **Holding-fee / expiry** demurrage (`Expiry.daml`, `Amulet_Expire`), locked Amulet, and the
  two-step / external-party transfer variants beyond confirming they reuse `executeTransfer'`.
- The **~5,600 Scala files** (validator/SV node automation, stores, the token-standard APIs) — the
  off-ledger orchestration; the on-ledger Daml is the conservation authority.
- The **Canton protocol itself** (synchronizer, sequencer, mediator) — a separate codebase; Splice
  runs *on* it and inherits its safety.
- DSO **governance voting** mechanics (how SVs jointly authorize DSO actions).

## Nothing routed privately

No untrusted-input→value path found. Canton Coin transfers conserve by an explicit
`inputs = outputs + fees + change, change ≥ 0` check over exact `Decimal` arithmetic, on top of
Daml's atomic consume/create + signatory model (a linear-resource-style floor the corpus has seen
in Move). Mainnet minting is gated to rate-limited round issuance (free taps are `isDevNet`-only),
and the rules/economics are governed by the DSO consortium (the by-design ceiling). The methodology
transferred cleanly to a Daml/consortium substrate — a new §11 rung: **conservation = explicit
balance check + ledger-model atomicity; trust root = the consortium authority party.** Companion to
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` §11 (conservation-location ladder) and
`AUDIT-GOVERNANCE-CEILING.md` (the DSO as apex authority).
