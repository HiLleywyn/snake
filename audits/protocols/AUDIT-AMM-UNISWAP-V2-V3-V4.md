# AMM cores — the conservation floor in its purest form (Uniswap v2 → v3 → v4)

**Scope.** The canonical AMM/DEX cores: Uniswap v2 (`Uniswap/v2-core`), v3 (`Uniswap/v3-core`), v4
(`Uniswap/v4-core`). This is the foundational DeFi primitive the corpus had not yet read directly —
the conservation floor in its most distilled form, and (in v4) a genuinely **new floor-enforcement
mechanism**. Public source, read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit.
No exploitable defect found**; the v4 hook trust seam is characterized factually.

**Sources read (verbatim, line refs):** v2 `UniswapV2Pair.sol`, `UniswapV2Factory.sol`; v3
`UniswapV3Pool.sol`, `UniswapV3Factory.sol`; v4 `PoolManager.sol`, `ProtocolFees.sol`, and the
transient-storage libraries `Lock.sol`/`NonzeroDeltaCount.sol`/`CurrencyDelta.sol`, plus
`libraries/Hooks.sol` and `types/BalanceDelta.sol`.

---

## 0. The one-paragraph result

An AMM is the conservation floor with *nothing else attached* — no oracle, no liquidation, no
governance over the math, no admin who can move funds. It is the cleanest object in the entire corpus,
and the three versions are a masterclass in **how to express one invariant three ways**. v2 enforces
conservation with a **single inequality** — `x·y ≥ k` on fee-adjusted balances, one `require` (line
182) that is the whole trust model. v3 *deletes the explicit product check* and instead **derives**
every output from sqrt-price math over piecewise-constant in-range liquidity, so the invariant holds
*per tick by construction* — backstopped, like v2, by an optimistic-transfer-then-`balanceBefore +
amount ≤ balanceAfter` callback check. v4 makes the leap that matters for the taxonomy: it generalizes
the per-call balance check into a **transaction-wide net-zero-delta invariant** — every token movement
becomes a deferred signed delta in EIP-1153 transient storage, and the `unlock` callback **reverts
unless every currency's delta has netted to zero** (`NonzeroDeltaCount != 0 → CurrencyNotSettled`,
line 112). This is a *fourth* floor-enforcement mechanism for the corpus: not conservation-by-identity
(CTF), not reserve-locking (Azuro), not bounded-loss-by-caps (Thales) — but **conservation-by-deferred
-settlement**, where the books are allowed to be imbalanced *during* a transaction and are forced to
balance exactly *once*, globally, at the end. And v4 introduces the AMM's first real residual: the
**hook** — arbitrary externalized pool logic that can alter swap amounts and fees and skim a delta the
*caller* pays for, bounded only by the net-zero accounting (which protects the *manager's* books, not
the *user's* value). So the AMM law: *the conservation floor can be a single line, and the cleanest
DeFi primitive has no residual at all — until v4 deliberately re-introduces one (the hook) as the price
of programmability.*

---

## 1. v2 — the floor as a single inequality. **The purest conservation floor in the corpus.**

`swap()` sends tokens **optimistically** (with an attacker-controllable callback), then re-reads
balances and enforces the constant-product floor on *fee-adjusted* balances:
```solidity
uint balance0Adjusted = balance0.mul(1000).sub(amount0In.mul(3));   // :180  bakes in 0.3% fee
uint balance1Adjusted = balance1.mul(1000).sub(amount1In.mul(3));   // :181
require(balance0Adjusted.mul(balance1Adjusted) >= uint(_reserve0).mul(_reserve1).mul(1000**2), 'K'); // :182
```
**Line 182 is the entire conservation guarantee.** `balanceAdjusted = balance·1000 − amountIn·3`
encodes the fee; the post-swap adjusted product must be ≥ the pre-swap reserve product — `x·y ≥ k`.
LP shares are `sqrt(amount0·amount1) − MINIMUM_LIQUIDITY` on first mint (with 1000 units permanently
locked to `address(0)` as the inflation-attack mitigation, `:120-121`) and strictly proportional
`min(amount0·supply/reserve0, amount1·supply/reserve1)` thereafter (`:123`) — you cannot dilute by
under-depositing one side. **No external trust seam in the swap path** beyond the optional `feeTo`
protocol skim. This is the conservation floor stripped to its irreducible core: one line, immutable, no
oracle, no admin over the math.

---

## 2. v3 — the floor derived, not checked. **Per-tick by construction.**

v3 replaces the global product check with output amounts **derived** from sqrt-price math. `swap()`
walks initialized ticks (`:641-730`): `computeSwapStep` (`:663`) consumes input against the *in-range*
`liquidity` held constant within a tick range; crossing an initialized tick applies that tick's signed
`liquidityNet` (`ticks.cross :709`, `addDelta :722`); `feeGrowthGlobalX128` accrues fees *per unit of
in-range liquidity* (`:690`). Because each step's amounts come from the price-range math, **the
invariant holds per tick by construction** — there is no single `k` to check. Settlement still uses the
v2 pattern: optimistic transfer, callback, then `require(balanceBefore + amount ≤ balanceAfter) (:777)`.
`flash()` is the same `balance ≥ balanceBefore + fee` repayment check (`:813-814`), surplus distributed
to LPs. **Governance is `onlyFactoryOwner` protocol-fee toggles only (`setFeeProtocol :837`)** — core
math immutable.

---

## 3. v4 — conservation by deferred settlement. **A fourth floor-enforcement mechanism.**

This is the taxonomy contribution. v4 is a **singleton** holding all pools, and it generalizes the
per-call balance check into a **transaction-wide invariant**:
```solidity
function unlock(bytes calldata data) external returns (bytes memory result) {
    Lock.unlock();
    result = IUnlockCallback(msg.sender).unlockCallback(data);   // caller does everything here
    if (NonzeroDeltaCount.read() != 0) CurrencyNotSettled.selector.revertWith();  // :112  THE floor
    Lock.lock();
}
```
**No tokens move on `swap`.** `swap` returns a `BalanceDelta` (packed `int128` pair, `BalanceDelta.sol`)
applied as an *accounting entry*, not a transfer. Every credit/debit flows through `_accountDelta
(:368-384)`, which maintains a transient counter of currencies with nonzero outstanding delta. The
caller settles by `take` (creates a debt) and `settle`/`sync` (measures reserves paid in, zeroes the
debt). All three quantities — the lock flag, the nonzero-delta count, and the per-(target,currency)
delta — live in **EIP-1153 transient storage** (`Lock.sol`, `NonzeroDeltaCount.sol`,
`CurrencyDelta.sol`), so they cost no permanent storage and auto-reset each tx.

**Characterization (the new mechanism):** the books are *allowed to be imbalanced during* a
transaction and are forced to balance exactly **once, globally, at `unlock` end**. This is
**conservation-by-deferred-settlement** — distinct from CTF conservation-by-identity, Azuro
reserve-locking, and Thales bounded-loss-by-caps. It enables flash-accounting (swap, then borrow against
the output, then settle, all netted) without intermediate transfers, and the *only* thing standing
between a user and a drained pool is that `NonzeroDeltaCount != 0` revert. The math floor itself
(sqrt-price) is still v3-style inside `Pool.swap`; v4's innovation is purely in *when and how* the floor
is enforced.

---

## 4. The hook — the AMM's first real residual. **A deliberately re-introduced trust seam.**

v4 externalizes pool logic into an arbitrary **hook** contract whose permitted callbacks are declared
by **bits of its own address** (`Hooks.hasPermission :337-339` is a pure bit-test;
`BEFORE_SWAP_FLAG = 1<<7`, the `RETURNS_DELTA` variants at `:29-47`, `isValidHookAddress :109-127`
enforcing that a returns-delta flag requires its action flag). Call sites fire `beforeSwap`/`afterSwap`
etc. (`PoolManager.sol:202,221`). The trust is real:
- `beforeSwap` can **change the swap amount** (`amountToSwap += hookDeltaSpecified`, `Hooks:275`) and
  override the LP fee for dynamic-fee pools (`:263`).
- `afterSwap` can **extract its own delta, which the *caller* is forced to pay** (`swapDelta = swapDelta
  − hookDelta`, `:312`; accounted to the hook at `PoolManager:224`).

**Characterization (factual, defensive):** the hook is the dominant new trust seam in v4. The net-zero
accounting guarantees the *manager's* books balance — a hook **cannot** make conservation fail — but it
**does not protect the *user*** from an adversarial hook skimming value via swap-amount/fee/delta
manipulation. Worse, the address bits only gate *which* callbacks fire, not *what they do*: a hook can
have benign-looking flags and arbitrary logic. `callHook` only checks the returned selector matches
(`:152`) and `callHookWithReturnDelta` only checks length (`:166`) — the delta value is taken on faith
and applied to the caller. **Integrators must whitelist/audit hooks per pool.** This is the v4-specific
residual: conservation is bulletproof; *value-for-the-user* is now hook-dependent.

(Other factual notes: the v2/v3/v4 optimistic-transfer pattern is reentrancy-bearing by design but
guarded by the lock mutex + the floor check, which is the *sole* guarantee since the callback target is
attacker-controlled; `NonzeroDeltaCount.decrement` can underflow and relies on the global
increments-≥-decrements invariant.)

---

## 5. Governance — minimal in all three. **The math is immutable.**

| | Governance scope |
|---|---|
| **v2** | `feeToSetter` sets `feeTo` (protocol skim) and hands off the setter; **no upgrade, no pause, pools immutable** |
| **v3** | `owner` can `setOwner`, `enableFeeAmount`, toggle per-pool protocol fee (`onlyFactoryOwner`); core math immutable |
| **v4** | `Owned`; `setProtocolFeeController` (`onlyOwner`), controller sets bounded per-pool protocol fee + collects; **owner cannot touch LP funds, pause swaps, or alter pool math** |

In all three, **governance is confined to protocol-fee economics**; the swap/LP math is immutable. This
is the *lowest math-governance ceiling in the corpus* — the AMM is, with UniswapX, the clearest example
of the "delete the trust" pole: there is no admin who can change how conservation works.

---

## 6. Where this sits in the corpus

The AMM is the **conservation floor with the residual subtracted** — the limiting case that proves the
floor can be a single immutable inequality with no oracle, no liquidation, and no math-governance. It
adds a **fourth floor-enforcement mechanism** to the taxonomy (joining conservation-by-identity,
reserve-locking solvency, and bounded-loss-by-caps): **conservation-by-deferred-settlement** (v4's
transient net-zero-delta), which is the same idea as the EVM transaction-as-atomic-unit pushed to its
logical end — *let the books be imbalanced mid-flight, force them to zero exactly once.* And the v2→v4
arc is itself the corpus's central dial in miniature: v2/v3 are pure "delete the trust" (immutable,
no residual), while v4 **deliberately re-introduces a residual — the hook — as the price of
programmability**, and bounds it the only way it safely can (the hook can reshape value but cannot break
conservation). The honest user statement for v4: *the pool cannot be drained out of accounting, but the
hook can reshape your trade — so trusting a v4 pool means trusting its hook.* The universal law holds in
its cleanest form: floor + residual, where the AMM lets you watch the residual appear, by choice, in a
single version bump.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
