# Ethereum (ETH) — go-ethereum state-transition conservation audit (clean)

**Target:** `ethereum/go-ethereum`, sparse clone `/tmp/geth` (`core`). Audited the **gas/fee
conservation lifecycle** in `core/state_transition.go` — `buyGas`, the fee split, `calcRefund`,
`returnGas` — the per-transaction ETH-movement core. **Posture:** defensive; no exploit, no PoC.
**Result: clean — no finding, nothing to disclose.**

Chosen because it's a real gap: I've audited many EVM *derivatives* — Base (`AUDIT-BASE-SIX-BUCKET.md`),
MemeCore (the PoSA fork, the one finding), Berachain, Monad — but never the **reference EVM** they all
inherit. And Ethereum's conservation has a distinctive feature worth a primary data point: the
**EIP-1559 basefee burn**, a first-class protocol-level deflationary sink (most chains pay all fees to
validators; Ethereum destroys the basefee).

## The per-transaction ETH conservation lifecycle (Bucket 1 + 5)
1. **`buyGas`** (`state_transition.go:367-432`): debit the sender the maximum gas cost upfront.
   - Sufficiency gate: `have, want := GetBalance(From), balanceCheck; if have.Cmp(want) < 0 →
     ErrInsufficientFunds` (`:416-418`) — you can't transact without covering `gasLimit·gasPrice`
     (+ blob fee + value).
   - `gp.SubGas(GasLimit)` (`:419`) — debits the **block gas pool** (block-level gas conservation: the
     sum of all txs' gas can't exceed the block limit).
   - `SubBalance(From, mgval)` (`:431`) where `mgval = gasLimit · gasPrice`. All intermediate math is
     `uint256` with explicit `AddOverflow`/`MulOverflow` checks (`:406-413`) → "required balance
     exceeds 256 bits" rather than wrapping.
2. **Execution**: value transfers run through the EVM's `SubBalance(caller)/AddBalance(recipient)`
   (conserved 1:1; the base floor, read at interface).
3. **Fee split — the basefee is burned** (`:679-695`):
   - `effectiveTip = gasPrice − baseFee` (`:685`).
   - Validator (`Coinbase`) is credited **only** `fee = gasUsed · effectiveTip` (`:693-695`).
   - The remaining `gasUsed · baseFee` was debited from the sender in `buyGas` and is **never credited
     to anyone** → **burned**. Net ETH supply decreases by `gasUsed · baseFee` each transaction. This
     is the EIP-1559 deflationary sink.
4. **`calcRefund` + `returnGas`** (`:773-807`): refund the sender unused gas, but **capped**:
   `refund = min(state.GetRefund(), gasUsed / RefundQuotientEIP3529)` (gasUsed/5 post-London, `:781`),
   then `returnGas` credits `gasRemaining · gasPrice` back (`:798-800`). The EIP-3529 cap is
   load-bearing: it's the bound that **killed the gas-token refund abuse** (pre-EIP-3529, refunds of
   gasUsed/2 let "gas tokens" mint/burn storage to game refunds — a real historical conservation/economic
   exploit class). **enforced.**

The conservation identity: `sender_pays = validator_tip + burned_basefee`, with `sender_pays =
(gasUsed − refund)·gasPrice`, `validator_tip = gasUsed·(gasPrice − baseFee)`, `burned =
gasUsed·baseFee`. Fees are neither created nor lost — they are split between the validator and the burn
sink, with unused/refunded gas returned. **enforced.**

## Where total supply actually lives (honest scoping)
Post-Merge, **ETH issuance is on the consensus layer** (the beacon chain pays validator rewards), not
in this execution-layer state transition. So the EL conserves value **modulo the EIP-1559 burn sink**:
`Δ total_supply = CL_issuance − Σ EL_burned_basefees`. This audit covers the **EL burn + fee/gas
conservation** (where ETH is destroyed and where fees go); the **issuance** side (CL rewards) is a
separate codebase (`prysm`/`lighthouse`/the beacon spec), not opened. I state this rather than implying
the EL is the whole supply story.

## Connections to the corpus
- **The fee-burn family.** Ethereum's basefee burn is the largest-scale member of the
  intentional-destruction sink seen in XRPL (`Δdrops == −fee`, `AUDIT-XRPL-INVARIANTS.md`), Tezos
  (`infinite_sink` `Burned`/`Storage_fees`, `AUDIT-TEZOS-TOKEN.md`), and Filecoin (penalty burns). A
  recurring corpus pattern: **conservation includes typed *sinks*, not just transfers** — "value
  conserved" must account for protocol burns.
- **The reference for the EVM-derivative audits.** Base/Monad/Berachain/MemeCore all inherit this
  state-transition shape. Notably, the MemeCore finding was a *consensus-layer reward* bug in a PoSA
  fork — **not** in this core EL fee path, which is clean; the contrast localizes that finding to the
  fork's added consensus code, not inherited geth.
- **Overflow = halt, not wrap.** The `uint256` `AddOverflow`/`MulOverflow` → error discipline matches
  Cosmos `math.Int` panic, Tezos `+?`, ICP checked ops — the halt-over-corruption philosophy absent in
  MemeCore.
- **Imperative-substrate floor.** Per §4b, Ethereum is the canonical *account-balance mutation* rung —
  conservation is maintained by disciplined `Sub`/`Add` with sufficiency+overflow checks, the weakest
  substrate (no type-system/crypto enforcement), which is exactly why the per-op checks and the refund
  cap matter so much.

## What this audit did NOT cover (coverage honesty)
- **CL issuance / the beacon chain** — where ETH is *created* (validator rewards, withdrawals); a
  separate codebase. The supply story is only complete with it.
- **The EVM opcode-level balance ops** (`core/vm`, `CALL` value transfer, `SELFDESTRUCT`,
  `SubBalance`/`AddBalance` in `state`) — read at interface; the per-opcode gas accounting and the
  `AddBalance` overflow "cannot-happen" path not exhaustively opened.
- **Withdrawals (EIP-4895)** and **blob gas (EIP-4844)** beyond the buyGas overflow checks — the blob
  fee is also burned; not fully traced.
- **Block-level invariants** (gas-limit adjustment, basefee update rule) and consensus (the Merge /
  fork-choice) — orthogonal.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I confirmed the validator is credited `gasUsed · effectiveTip`
  with `effectiveTip = gasPrice − baseFee`, so the basefee portion is genuinely *not* credited
  anywhere (burned), and that the refund is `min(counter, gasUsed/5)` capped (EIP-3529), not unbounded.
  I confirmed the sufficiency check precedes `SubBalance` so the upfront debit can't underflow.
- **Exposure to reversal.** The clean verdict is about the *EL fee/gas conservation*; it explicitly
  does **not** clear the CL issuance side (not in scope) — so "ETH supply is conserved" is *not* a
  claim I'm making; I'm claiming the EL destroys exactly `gasUsed·baseFee` and splits the rest
  correctly. The exact refund/fee ordering (whether refund is folded into `gasUsed` before the tip
  calc) I read structurally; a subtle ordering bug there would change the split arithmetic, and I did
  not derive the identity line-by-line through `execute()` — stated as a bounded read.

## Verdict
**Clean.** go-ethereum's state transition conserves value across the gas/fee lifecycle: the sender is
debited upfront under a sufficiency gate, value transfers are 1:1, the validator receives only the tip
(`gasPrice − baseFee`), the **basefee is burned** (debited but never credited — the EIP-1559
deflationary sink), and refunds are capped (EIP-3529, the fix for gas-token abuse), all in
overflow-checked `uint256`. It is the reference EVM that the corpus's EVM-derivative audits inherit, and
the largest-scale member of the fee-burn/typed-sink family. No untrusted-input→value path in the
audited EL surface; nothing to disclose. Honest scope: ETH *issuance* is consensus-layer (not here), so
this clears the EL burn/fee conservation, not the full supply equation. Next pulls: the CL issuance
side and the EVM opcode-level balance/gas accounting.
