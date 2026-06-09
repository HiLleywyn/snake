# Cross-VM live bug-hunt — beyond Solidity forks/contests: Vyper, Solana, zk, Move, Cosmos, and ERC-4337

**Why this hunt exists.** The rest of the bug-hunt corpus is EVM/Solidity app-layer code — forks, contest repos,
and (most recently) live Solidity protocols. The taxonomy was always "the same five EVM classes on a different
protocol." This hunt deliberately changes the **target type**, not just the protocol: six live, mainnet-deployed,
bounty-eligible systems on **six different VMs / languages / paradigms**, each hunted on *its own* bug taxonomy —
the classes that exist on that platform and nowhere else.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute-don't-trust
applies in each platform's native semantics. Anything real and live would be stopped and routed for private
disclosure (redacted here). **All six came back clean — no live finding.**

| # | Target | Platform / language | Why the taxonomy is different | Verdict |
|---|---|---|---|---|
| 1 | **crvUSD / LLAMMA** (Curve) | **Vyper** (EVM, non-Solidity) | the 2023 Curve hack was a *Vyper-compiler* reentrancy-lock bug, not a contract-logic bug; `@nonreentrant` semantics, `unsafe_*` arithmetic, pragma-version range, and decimal handling are Vyper-specific | **clean** |
| 2 | **Kamino Lend** (`klend`) | **Solana** / Rust + Anchor | no `msg.sender`; security is "did the program validate every account?" — signer/owner/type-confusion/PDA/fake-oracle/truncating-cast/CPI, a taxonomy with almost zero EVM overlap | **clean** |
| 3 | **Privacy Pools** (0xbow) | **zk** / circom + Groth16 verifier | the dominant class is an *under-constrained circuit* (a missing constraint → soundness break → proof forgery), not a logic error; plus verifier public-input binding | **clean** |
| 4 | **Cetus CLMM** (Sui) | **Move** / resource-oriented | abilities (`copy`/`drop`/`store`/`key`) on value/authority structs, hot-potato flash receipts, witness/OTW forgery, generic-type confusion, Sui shared-object ownership — none of these classes exist elsewhere | **clean** (May-2025 CVE patch confirmed) |
| 5 | **Osmosis** (`osmosis-1`) | **Cosmos SDK** / Go module | the dominant class is *non-determinism in a consensus path* (map-iteration / wall-clock / float → chain fork/halt), plus the EndBlock panic surface — a consensus-layer taxonomy, not a value-leak one | **clean** |
| 6 | **EntryPoint v0.9 + Kernel v3.3** | **ERC-4337 / 7579** account abstraction | the UserOp validation/execution split: validation-vs-execution mismatch, userOpHash field binding, paymaster postOp griefing, 2D-nonce reuse, module install/hook bypass | **clean** (deployed=v0.7/v0.8; HEAD is ahead) |

---

## 1. crvUSD / LLAMMA — the Vyper-language surface first, then the mechanism

**Repo:** `curvefi/curve-stablecoin` @ `61f1a61`. **Per-contract pragma audited explicitly** (this is the
differentiator, not a footnote): `AMM.vy`/`controller.vy`/`MintController.vy`/`lending/*` are **Vyper 0.4.3**;
`ControllerFactory.vy`/`Stablecoin.vy`/`stabilizer/PegKeeper*.vy`/`price_oracles/AggregateStablePrice3.vy` are
**0.3.10**. **All pragmas are outside the known-buggy `0.2.15–0.3.0` reentrancy-lock range** that drained Curve in
2023.

**Honest scoping caveat surfaced by the hunt (deployed ≠ this HEAD).** The repo HEAD is the *next-generation*
crvUSD rewrite in **Vyper 0.4.3**; the code currently securing live mainnet TVL is the **0.3.7 / 0.3.9**
controllers (`0x100daa78…`, `0x1c91da02…`, Etherscan-verified). This is named, not buried: a bounty submission on
"live deployed code" must be re-derived against the exact Etherscan-verified 0.3.x source for the target market.
The 0.3.10 PegKeeper/factory/aggregator in this repo are close to live and were verified clean.

**Per-class, in Vyper semantics:**
- **Language surface — clean.** Every state-mutating external *and every `@view`* in `AMM.vy` is `@nonreentrant`;
  under 0.4.x's **single global reentrancy key** a named-lock gap (the 2023 class) is structurally impossible, and
  locking the views **closes read-only reentrancy by construction**. Controller/Mint/Lend use
  `pragma nonreentrancy on` (auto-lock-all). `unsafe_*` arithmetic is pervasive but each site is provably bounded
  (band counts ≤ `MAX_TICKS`, values capped by `2**128` asserts, `frac ≤ 1e18`). `raw_call` sites handle
  `revert_on_failure=False` or use `max_outsize=0`.
- **LLAMMA band/tick — clean, rounds toward protocol.** `deposit_range` floors shares with a `DEAD_SHARES`
  inflation guard; `calc_swap_out` rounds **in_amount up / out_amount down** and caps the last tick via
  `min(…, y)`; band write-back matches the transferred amounts (Σ bands conserved).
- **Health / liquidation — clean, oracle-bound.** `get_x_down` prices collateral **adiabatically at the oracle
  price** (not manipulable AMM spot) and deliberately under-estimates, defeating spot-manipulation to dodge/force
  liquidation; debt rounds up against the liquidator; `limit_p_o` caps per-block oracle movement with a dynamic
  fee that makes the AMM loss-neutral to oracle jumps.
- **PegKeeper / monetary policy — clean, profit-gated.** `update()` acts only toward peg, capped to
  `imbalance/5`, and **must increase virtual-price-denominated profit or revert** (`assert new_profit > initial_profit`),
  so sandwich-extraction reverts. The rate uses the EMA-aggregated multi-pool oracle, not a single manipulable pool.

All findings are by-design and already-audited (ChainSecurity). **No live finding.**

---

## 2. Kamino Lend — the Solana taxonomy (account validation, not reentrancy)

**Repo:** `Kamino-Finance/klend` @ `23b9f2b`. **Deployed program id** `KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`
(declared `lib.rs:22`). The bug classes here barely overlap with EVM — there is no `msg.sender`; the program must
explicitly validate every account passed in, and a Solana hack is almost always one missing check.

**Per-class, in Solana/Anchor semantics:**
- **Account validation (highest) — clean.** Every value-moving handler (borrow/withdraw/repay/liquidate) pins
  `owner: Signer`, `has_one = lending_market` + `has_one = owner` on the obligation, and binds the supply/fee
  vaults and mint with `address = reserve.…` constraints. Remaining-account reserves go through a
  `FatAccountLoader` that enforces **both program-owner and the 8-byte Anchor discriminator** (no
  look-alike/type-confusion substitution), and each is additionally bound to the obligation's *recorded* reserve
  pubkey plus a staleness gate — an attacker cannot swap in a higher-value reserve.
- **Oracle account — clean (the classic "pass your own oracle" vector is closed).** Oracle accounts are typed
  `Option<AccountInfo>` (unchecked shape) but `validate_token_info_config` requires each supplied oracle key to
  **equal the address stored in the reserve's admin-configured config** (`check_pyth_acc_matches`,
  `check_scope_acc_matches`, …). The one nuance — `scope.rs:get_price_account` validates the discriminator but not
  the account owner — is rendered safe by that upstream address-pin, and the hunt **declined to inflate it** into a
  finding.
- **Arithmetic — clean.** Core value math is a fixed-point `Fraction`/`U256` with `checked_mul`/`saturating_*`; the
  only `as` casts in the value paths are benign widening or bool→u8, **no truncating u128→u64 or `wrapping_*`** in
  deposit/borrow/withdraw/liquidate.
- **CPI / token transfer — clean.** Transfers use the market-authority PDA with `gen_signer_seeds!`, amounts are
  post-checked against actual vault balance deltas (`LendingAction::Subtractive`), destinations are
  constraint-pinned, no attacker-supplied program-id CPI.
- **State machine — clean.** Liquidation amount/bonus are collared with a bad-debt cap (no over-seize);
  `socialize_loss` is admin-gated; the composite `deposit_and_withdraw` re-refreshes between legs and blocks
  `new_ltv > initial_ltv` (`WorseLtvBlocked`); the flash-loan pair enforces matching borrow↔repay at a pinned
  account index and forbids CPI via `get_stack_height() > TRANSACTION_LEVEL_STACK_HEIGHT`.

**No live finding.**

---

## 3. Privacy Pools — the zk taxonomy (under-constrained = soundness = forgery)

**Repo:** `0xbow-io/privacy-pools-core` @ `a80836a4`. Live 0xbow mainnet privacy protocol (Tornado-style deposit/
withdraw with an ASP association-set gate); `SECURITY.md` directs private disclosure. The dominant bug class is a
**missing constraint** that lets a malicious prover prove a false statement — a soundness break that mints/withdraws
forged value. For each signal the question is "what stops a prover from setting this to an arbitrary value?"

**The headline discipline: recompute-don't-trust applied to a circuit.** An in-repo Oxorio audit flagged two
soundness-relevant items; rather than take the audit's word, the hunt **re-derived both from source at HEAD**:
- the previously-flagged unused `actualDepth` signal is now bound by a real constraint
  `LessEqThan(6): actualDepth <= maxDepth` with `depthCheck.out === 1` (`merkleTree.circom:44-47`) — no longer free;
- the "multiple valid proofs / fake-leaf" forgery the auditor sketched is **non-applicable by Poseidon-arity domain
  separation** — leaves are `Poseidon(3)` `[value,label,precommitment]` and internal nodes are `Poseidon(2)`
  (confirmed on-chain `PoseidonT4.hash(...)`), so the leaf=Poseidon(2) forgery cannot type-check.

**Per-class:**
- **Under-constrained — clean.** Every output signal is wired from a Poseidon hasher and forced equal to the
  Merkle root (`stateRoot === stateRootChecker.out`); the LeanIMT node recurrence is fully determined; selectors
  are boolean-constrained via `Num2Bits`.
- **Range checks — clean, and they *are* the conservation guard.** `withdrawnValue` and
  `remainingValue = existingValue − withdrawnValue` both pass `Num2Bits(128)`; an over-withdrawal makes
  `remainingValue ≈ p` (negative mod the field), which **fails the 128-bit decomposition** — so value conservation
  is enforced by the range check itself. `existingValue` isn't directly range-checked but is bounded by induction
  from the on-chain `uint128` deposit cap.
- **Public-input / verifier binding — clean.** `WithdrawalVerifier` binds all 8 public signals and runs
  `checkField` (`< r`, the BN254 scalar field) on **every** one; the 8-signal order matches the circuit and the
  `ProofLib` accessors exactly; A-negation uses the base field `q`. `context` is bound in-circuit (the
  `contextSquared` dummy) and on-chain equals `keccak256(abi.encode(_withdrawal, SCOPE)) % r`, binding the proof to
  recipient/fee/scope (no target malleability).
- **Nullifier / state binding — clean.** `_spend` reverts on reuse and the circuit forces
  `existingNullifier ≠ newNullifier`; state roots are accepted only from a 64-deep history ring; the ASP root must
  equal `ENTRYPOINT.latestRoot()`.

**No live finding.** By-design note (not a bug): the `stateTreeDepth`/`ASPTreeDepth` public signals are advisory —
soundness rests entirely on root-equality + arity domain separation, both of which hold.

---

## 4. Cetus CLMM — the Move resource/ability taxonomy

**Package:** `CetusProtocol/cetus-contracts`, `cetus_clmm` @ `ddfbdeb` (`Move.toml` `mainnet-v1.3.0`), **deployed
mainnet `0x1eabed72c53feb3805120a081dc15963c204dc8d091542592abaf7a35689b2fb`**. The bug classes here exist nowhere
else: a struct's *abilities* are its security boundary, and authority is carried by no-ability / no-copy types.

**The headline: the May-2025 $220M exploit root cause is confirmed patched at the pinned revision.** That hack was
an overflow in `integer-mate`'s `checked_shlw` (a bogus bound mask). The pinned dep here
(`integer-mate` @ `09a12d9`, `math_u256.move:18`) reads `let bound = 1 << 192; if (n >= bound) (0,true) else ((n<<64),false)`
— the correct overflow guard — and `get_delta_a` aborts on its `true` flag. Re-derived from source, not taken on
faith.

**Per-class, in Move semantics:**
- **Abilities (highest) — clean.** `Pool<A,B> has key, store` holds `Balance<A>/Balance<B>` with **no `copy`/`drop`**
  (can't be duplicated or silently dropped); `AdminCap`/`ProtocolFeeCollectCap has key, store` (capabilities, no
  `copy`/`drop`, unforgeable-by-copy); the `POOL`/`POSITION`/`CETUS` one-time-witnesses are `has drop {}` only
  (correct OTW shape). No value/authority struct carries an ability that breaks its invariant.
- **Hot-potato / flash — clean.** `FlashSwapReceipt`/`AddLiquidityReceipt`/`FlashLoanReceipt` have **no abilities**
  — the textbook hot-potato, consumable only by destructuring in `repay_*`. `repay_flash_swap` asserts the
  `pool_id` match, asserts the repaid `balance::value == pay_amount` exactly, and asserts `ref_fee_amount == 0` so
  the partner-ref-fee path can't be skipped via the non-partner repay. No drop/store/sidestep.
- **Generics / witness — clean.** `Coin/Balance<A,B>` are `phantom` params tied to the specific `Pool<A,B>`; receipts
  carry the same phantoms, so a wrong-type repay won't type-check. No `public fun` takes an unconstrained witness.
- **Visibility / ownership — clean.** Liquidity mutators are `public(package)` (unreachable externally);
  `close_position` aborts unless `is_empty` (no orphaned reserves); admin paths are capability- or ACL-gated, and
  `collect_protocol_fee_with_cap` derives the member from `object::id_address(cap)` then checks the role (a random
  cap won't pass). The unguarded `pause_pool` is `#[test_only]`, not in deployed bytecode.
- **Arithmetic — clean.** Swap rounds toward the pool (in rounds up, out rounds down); all `as` downcasts are
  guarded by `<= u64::max` asserts.

**No live finding.**

---

## 5. Osmosis — the Cosmos SDK consensus-determinism taxonomy

**Repo:** `osmosis-labs/osmosis` @ `2df8d8e`, live as **`osmosis-1`** (active disclosure program +
Immunefi). This is a Cosmos **SDK-Go module chain**, so the dominant bug class is not a value leak — it's
**non-determinism in a consensus path**, where a single map-iteration-order difference forks or halts the chain.

**Per-class, in SDK-Go semantics:**
- **Non-determinism (the classic SDK fork bug) — clean, and actively defended.** No `time.Now()` in consensus
  paths (telemetry only); `math/rand` is simulation-only; floats appear only in telemetry/JSON-filter parsing,
  never mutating consensus state (the devs even comment "floats are non-deterministic"). Critically, **every map
  iteration that touches consensus state is sorted before the state write** — a disciplined, consistent pattern:
  `lockup/keeper/lock.go:662,726` (`sort.Slice(durations)` before store writes), `pool-incentives/keeper/distr.go:182`
  (`sort.SliceStable` by GaugeId), `gamm/keeper/migrate.go:294`, and `incentives/keeper/distribute.go:428` (writes to
  a **pre-assigned `v.index`** so output order is traversal-independent). The protorev epoch hook ranges nested maps
  but writes to **distinct KV keys** with a strict `.GT` tie-break, so final state is order-independent.
- **EndBlock / epoch-hook panic surface — clean.** `epochs/keeper/abci.go` uses a sorted KV iterator; hooks
  propagate `error` returns rather than panicking on the value-moving paths.
- **Funds / bank — clean.** ProtoRev profit distribution iterates `sdk.Coins` (already a sorted slice), computes the
  split deterministically, then sends.
- **Math / rounding — clean.** CL swap math rounds uniformly toward the pool: amountIn `.Ceil().TruncateInt()`,
  amountOut `.TruncateInt()`, spread factors `.Ceil()`; checked `osmomath` types throughout.

**No live finding.** The recurring "deterministically iterate" / "non-deterministic" comments show the maintainers
actively defend exactly this taxonomy — the consensus-layer analogue of protocol-favoring rounding.

---

## 6. EntryPoint v0.9 + Kernel v3.3 — the ERC-4337 UserOp-lifecycle taxonomy

**Repos:** `eth-infinitism/account-abstraction` @ `1c6b669` (v0.9 dev line) + `zerodevapp/kernel` @ `6a098bc`
(Kernel v3.3, ERC-7579). Both ship `audits/` dirs. The AA-specific classes center on the validation/execution split
and the UserOp hash.

**Honest deployed-≠-HEAD caveat (named up front):** this HEAD is the **v0.9 upcoming line**, not the deployed
mainnet bytecode — the canonical EntryPoints are v0.7 `0x0000000071727De22E5E9d8BAf0edAc6f37da032` and v0.8. Any
finding would have to be re-pinned to the actually-deployed verified source before disclosure.

**Per-class:**
- **Validation/execution consistency (highest for accounts) — clean.** SimpleAccount's `_validateSignature`
  recovers over a `userOpHash` that binds `callData`, and `execute` is gated by `_requireForExecute`
  (EntryPoint-or-owner). Kernel binds a `vId`→selector and, when a hook is required, **forces the outer selector to
  be `executeUserOp`** and runs that hook keyed by `executionHook[userOpHash]`; the non-hook branch checks
  `allowedSelectors[vId][callData[0:4]]`. Validation authorizes exactly what executes.
- **userOpHash / signature binding — clean.** `getUserOpHash` is EIP-712 `toTypedDataHash`, the domain binding
  chainId + verifyingContract (EntryPoint) + name/version, the struct binding sender/nonce/initCode/callData/gas
  limits/fees/paymasterAndData. No cross-chain/cross-account replay; OZ `ECDSA.recover` rejects high-s (no
  malleability). *Lower-confidence by-design note:* v0.9 adds a paymaster-signature suffix deliberately excluded
  from the hash — bounds-checked (rejects a sig extending into paymasterData) with the magic byte re-appended so the
  boundary can't shift — but it is the freshest, least-audited surface, worth re-review against deployed bytecode.
- **Paymaster griefing/theft — clean.** A reverting `postOp` still charges the paymaster the max penalty; the
  deposit is decremented before validate; `pmVerificationGasLimit` and returndata size are enforced. No
  drain/underpay path.
- **Nonce + EntryPoint accounting — clean.** The 2D nonce (`key<<64 | seq`) increments-and-compares (no reuse/skip);
  StakeManager uses checked decrements + CEI `withdrawTo`; `handleOps` is `nonReentrant`; refund credits
  `prefund − actualGasCost` only when `prefund ≥ actualGasCost` (no over-refund).
- **Module/factory (ERC-7579) — clean.** Install/uninstall/grantAccess/upgrade are `onlyEntryPointOrSelfOrRoot`;
  `executeFromExecutor` needs no modifier because the **storage lookup is the auth** (a non-installed executor has
  `hook == address(0)` → `InvalidExecutor()`); root-validator hook removal is guarded against locking the account.

**No live finding.**

---

## Synthesis — what changing the platform proved

1. **The method ports across six VMs.** The same discipline — recompute every value-moving (or consensus-critical)
   path from source, in the platform's *native* semantics, and ask "what stops an attacker from forging this?" —
   found the right guards on six platforms whose bug taxonomies barely overlap. Vyper: the lock model + `unsafe_*`
   bounds. Solana: account ownership/type/PDA validation + truncating casts. zk: the constraint system + verifier
   field-reduction. Move: struct abilities + hot-potato consumption. Cosmos-SDK: consensus-path determinism (sorted
   map iteration). ERC-4337: the validation/execution split + userOpHash field binding. **Almost none of these
   classes exist on the others** — the discriminator each time was learning what the platform's actual hacks look
   like and hunting *that*, not porting the EVM checklist.
2. **Recompute-don't-trust scales to the hardest classes.** The zk hunt re-derived an audit's soundness findings
   from the constraint system rather than trusting the audit (resolved via Poseidon-arity domain separation the
   prose alone wouldn't settle); the Move hunt re-derived the May-2025 $220M CVE fix from the pinned `integer-mate`
   bound mask rather than assuming "v1.3.0 = patched"; the Cosmos hunt confirmed determinism by reading the actual
   `sort.*` call before each state write, not the comment claiming it.
3. **Deployed ≠ repo-HEAD is a first-class check on every platform.** crvUSD: HEAD is the next-gen Vyper 0.4.3 line
   while live TVL runs 0.3.x. Solana: pinned the on-chain program id. zk: confirmed live deployment + disclosure
   policy. Move: pinned the published mainnet package address + the dependency tag. ERC-4337: caught that the v0.9
   HEAD is *ahead* of the deployed v0.7/v0.8 bytecode. A clean read of the wrong artifact is worthless regardless of
   language.
4. **Severity calibrated honestly, again.** The Solana `get_price_account` missing-owner-check, the zk advisory
   depth signals, and the ERC-4337 v0.9 paymaster-suffix exclusion were each traced to *why they're safe* (or
   flagged as fresh-surface-to-re-review) and explicitly **not** promoted to findings — the same discipline that
   calibrates EVM "dropped checks" down when value can't actually leave.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
