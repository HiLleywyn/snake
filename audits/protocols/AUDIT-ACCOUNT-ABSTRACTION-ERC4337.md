# Account abstraction (ERC-4337) — a new actor-trust topology: validate-then-execute + the off-chain bundler

**Scope.** The ERC-4337 EntryPoint and its surrounding actors (`eth-infinitism/account-abstraction` @
`1c6b669d`, EntryPoint self-identifying as **v0.9**). This is a trust *topology* the corpus had not
seen — not a conservation floor with an oracle, but a multi-actor pipeline (account, paymaster, bundler,
EntryPoint) whose safety rests on a **validation/execution separation** plus **off-chain mempool
rules**. Public source, read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No
exploitable defect found**; the AA-specific risk surfaces (paymaster postOp griefing, the off-chain
validation-rule dependency, the validate→execute state gap) are characterized factually.

**Sources read (verbatim, line refs):** `core/EntryPoint.sol`, `core/StakeManager.sol`,
`core/BasePaymaster.sol`, `core/Stakeable.sol`, `core/Helpers.sol`, `core/BaseAccount.sol`,
`interfaces/{IAccount, IPaymaster, IStakeManager}.sol`.

---

## 0. The one-paragraph result

Account abstraction has no conservation floor and no price oracle — its "floor" is a **payment
invariant** (the EntryPoint must always be able to pay the bundler for gas it spent), and its residual
is a **trust topology**: who validates, who pays, who orders, and who enforces the rules. The core
design is a strict **two-phase batch**: the EntryPoint validates *all* ops first (cheap, gas-bounded,
deterministic — any validation failure reverts the **whole** bundle), then executes *all* ops
independently (a failed execution is **contained** to that op, gas still charged). The security seam is
the **validation/execution separation**: validation decides *who pays* and **pre-pays the EntryPoint
from on-chain deposit before any execution runs** (`AA21`/`AA31`), so execution can fail harmlessly. The
genuinely new element for the corpus is that **a load-bearing part of the trust is enforced off-chain,
by the bundler, not by any contract**: the ERC-7562 validation rules (validation must not read
`block.timestamp`, touch other accounts' storage, or use banned opcodes) are what keep the alternative
mempool DoS-safe, and the EntryPoint *cannot* enforce them — it only imposes gas caps and a return-shape
check. The **stake** exists precisely to backstop this: a paymaster/factory that wants to touch external
state during validation must post a time-locked DoS bond, so off-chain reputation has on-chain teeth.
And the EntryPoint itself is the *opposite* of a governance ceiling — an **immutable, ungoverned,
canonical singleton** with no owner, no upgrade, no pause; the only trust is *using the genuine
address*. So the AA law: *the floor is "the bundler always gets paid" (secured by prepay-before-execute);
the residual is a four-actor topology where the most important rules live in the off-chain mempool, and
the EntryPoint deliberately holds zero discretionary power so that all trust sits at the edges — the
paymaster operator's key and the bundler's honesty.*

---

## 1. The two-phase flow — validate-all, then execute-all. **The core design.**

`handleOps (:78-96)` runs validation over the entire batch first (`_iterateValidationPhase :346-368`),
then a separate execution loop, then pays the bundler:
```solidity
_iterateValidationPhase(ops, opInfos, address(0), 0);   // phase 1: validate ALL — any revert kills the bundle
for (uint256 i = 0; i < opslen; i++) collected += _executeUserOp(i, ops[i], opInfos[i]);  // phase 2
_compensate(beneficiary, collected);                    // bundler (msg.sender) paid the collected fees
```
**Phase 1 failure reverts the whole bundle** (each op's `_validatePrepayment` +
`_validateAccountAndPaymasterValidationData` can `revert FailedOp`). **Phase 2 failure is contained:**
`_executeUserOp (:227-301)` runs each op via a self-`call` to `innerHandleOp` whose success is *captured,
not propagated* (`:256-259`); a reverting execution only emits `UserOperationRevertReason` and flips
`mode = opReverted (:443)` — gas is still charged via `_postExecution`. The sole exception that aborts
the batch is `AA95 out of gas (:271)` — the bundler under-funding the tx. The bundler is `msg.sender`,
names itself `beneficiary`, and monetizes the spread between the user's `maxFeePerGas` and actual
`tx.gasprice`.

---

## 2. The validation/execution separation — prepay before execute. **The security invariant.**

This is the load-bearing idea. `_validateAccountPrepayment (:566-596)` calls
`IAccount.validateUserOp` under a strict `verificationGasLimit` cap (`:621`, `AA26` if exceeded), rejects
any return whose size ≠ 32 bytes (`:624` — **no free-form revert reason can masquerade as success**), and
**pulls the full prefund from the account's on-chain deposit, reverting `AA21 didn't pay prefund` if it
isn't there** (`:591-593`). The packed `validationData` carries `sigFailed` + a `validUntil/validAfter`
time-range (`_getValidationData :770-789`), checked into `AA22`/`AA24`/`AA27` (`:737-744`). Nonce
uniqueness is enforced by the EntryPoint (`AA25`).

**Characterization:** validation is *gas-bounded, deterministic, must return a packed `uint256`, and must
pre-pay before any code executes*. Execution is sandboxed in a separate self-call whose failure is
caught. **The invariant: validation results decide who pays; the payment is secured up front; therefore
execution can fail without anyone being cheated.** This is the AA analog of "verify-before-persist" from
the L1 state-sync work — *secure the payment before running the untrusted action.*

---

## 3. Deposit vs stake — gas-prefund balance + a time-locked DoS bond. **Two distinct roles.**

`StakeManager` holds, per actor, a `DepositInfo{deposit, staked, stake, unstakeDelaySec, withdrawTime}`:
- **`deposit`** is the **gas-prefund pool** the EntryPoint debits during validation (`_tryDecrementDeposit`)
  and credits refunds back to. An account that funds its own deposit needs no stake.
- **`stake`** is a **time-locked DoS bond** (`addStake :86-104` — `unstakeDelaySec` can only *increase*
  (`:89`), preventing a quick exit; `withdrawStake` refuses until `withdrawTime` elapses, `:118-133`). It
  is *not* spent on gas — its purpose is purely to back the off-chain rule (§4): **a paymaster/factory may
  only touch external/associated state during validation if it is staked with sufficient delay**, so
  off-chain throttling of a misbehaving actor costs a real, withdrawal-delayed bond.

**Characterization:** deposit = prepaid gas; stake = reputation collateral that gives the off-chain
mempool rules economic teeth.

---

## 4. The off-chain bundler validation-rule trust — the genuinely new residual. **Factual.**

The corpus's residuals were all *on-chain* (a quorum, a key, a price). AA introduces one that is
**enforced off-chain and cannot be enforced on-chain**. The EntryPoint imposes only gas caps + the
32-byte return-shape check; the mempool's DoS-safety rests entirely on bundlers running **ERC-7562**
simulation. The contracts *admit* this in their own comments:
- `IAccount.sol:32`: "validation code cannot use `block.timestamp`/`block.number` directly" — a
  determinism rule **only an off-chain simulator can enforce**.
- `IPaymaster.sol:24`: "bundlers will reject this method if it changes the state, unless the paymaster is
  trusted (whitelisted)" — explicit statement that **storage/opcode banning is a bundler policy**.

**Factual risk surfaces (defensive, no exploit):**
1. **Banned-opcode / storage-isolation is off-chain only.** A bundler that skips ERC-7562 (or a
   private/whitelisted bundler) can include ops the public mempool would reject. The DoS-safety property
   ("an op that validates can't be cheaply invalidated by others' state") is a *mempool* guarantee, not a
   *contract* one.
2. **Validate→execute state gap.** All ops validate in phase 1; each op's `callData` runs later in phase
   2, *after earlier ops in the batch have executed*. Validation cannot rely on state later ops mutate —
   the prepay-first design makes this safe **for payment**, but app-level invariants checked in validation
   are **not** guaranteed to still hold at execution.
3. **Paymaster postOp griefing.** A user op whose execution reverts still forces the paymaster to pay
   (`opReverted`) and run `postOp`; a paymaster's own reverting `postOp` is caught and charged the full
   prefund, plus a ≤10% unused-gas penalty (`UNUSED_GAS_PENALTY_PERCENT`). This is the canonical
   paymaster-griefing surface — the paymaster bears cost for griefy ops it sponsored.
4. **Bundler censorship/ordering.** Inclusion, intra-batch ordering, and `beneficiary` are entirely the
   bundler's discretion; there is **no on-chain fairness guarantee** — censorship resistance depends on a
   competitive bundler market. (This is the AA version of the MEV/PBS proposer-trust seam.)

---

## 5. Governance — the EntryPoint is the *anti*-ceiling; trust sits at the edges

- **EntryPoint: immutable, ungoverned, canonical singleton.** Header (`:24-29`): "Only one instance
  required on each chain… Always verify the EntryPoint addresses." There is **no owner, no admin, no
  upgrade hook, no pause** anywhere in `EntryPoint.sol`/`StakeManager.sol` — confirmed. The *entire*
  governance model is "use the genuine canonical address." `handleOps` is even EOA-gated
  (`nonReentrant :68-75` requires `tx.origin == msg.sender && msg.sender.code.length == 0`).
- **Discretionary power lives only at the paymaster/factory layer.** `BasePaymaster` is `Ownable2Step`
  via `Stakeable`; the owner can `withdrawTo` (drain the paymaster's deposit) and manage stake — but has
  **no power over the EntryPoint or over user accounts**. So the key-compromise/rug surface is scoped to
  *each paymaster's own deposit*, not the protocol.

**Characterization:** AA is the **delete-the-ceiling** pole taken to its limit — an immutable core with
*zero* privileged actor, where all trust is pushed to the edges: the paymaster operator's key (bounded
to its own funds) and the bundler's honesty (bounded by the competitive mempool + the stake bond).

---

## 6. Where this sits in the corpus

ERC-4337 adds a **new residual class** that complements the §5e taxonomy: not destructible principal,
not a price oracle, but an **off-chain liveness/rule-enforcement trust** (the bundler + the ERC-7562
mempool rules). It is the same *shape* as two earlier findings — the Across "dataworker attests
off-chain" settlement seam (§5f) and the MEV/PBS proposer-trust — generalized: **whenever a system needs
an actor to do honest off-chain work (attest a fill, order a block, simulate a validation), the
contracts can bound the *payment* but not the *behavior*, and the residual is that actor's honesty,
backstopped by a bond.** AA's contribution is the cleanest separation of the two halves: the EntryPoint
*provably* secures the payment (prepay-before-execute, immutable, ungoverned), and *explicitly* delegates
the behavior to the off-chain bundler — even documenting in its interfaces which rules it cannot enforce.
It also re-confirms the own-vs-delete dial at the core: the EntryPoint **deletes** governance entirely
(no owner, immutable singleton — the strongest "delete the trust" instance in the corpus, alongside
Uniswap v2 and Liquity), pushing every remaining trust to a bounded edge. The honest user statement:
*your account can't be drained by the EntryPoint (it has no power and secures payment before running your
code), but you are trusting your paymaster's solvency, your bundler's honesty/inclusion, and the
off-chain mempool rules that the contract itself cannot guarantee.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
