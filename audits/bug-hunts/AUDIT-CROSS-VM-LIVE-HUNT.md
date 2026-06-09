# Cross-VM live bug-hunt — beyond Solidity forks/contests: Vyper, Solana/Rust, and a zk circuit

**Why this hunt exists.** The rest of the bug-hunt corpus is EVM/Solidity app-layer code — forks, contest repos,
and (most recently) live Solidity protocols. The taxonomy was always "the same five EVM classes on a different
protocol." This hunt deliberately changes the **target type**, not just the protocol: three live, mainnet-deployed,
bounty-eligible systems on **three different VMs / languages / paradigms**, each hunted on *its own* bug taxonomy —
the classes that exist on that platform and nowhere else.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute-don't-trust
applies in each platform's native semantics. Anything real and live would be stopped and routed for private
disclosure (redacted here). **All three came back clean — no live finding.**

| # | Target | Platform / language | Why the taxonomy is different | Verdict |
|---|---|---|---|---|
| 1 | **crvUSD / LLAMMA** (Curve) | **Vyper** (EVM, non-Solidity) | the 2023 Curve hack was a *Vyper-compiler* reentrancy-lock bug, not a contract-logic bug; `@nonreentrant` semantics, `unsafe_*` arithmetic, pragma-version range, and decimal handling are Vyper-specific | **clean** |
| 2 | **Kamino Lend** (`klend`) | **Solana** / Rust + Anchor | no `msg.sender`; security is "did the program validate every account?" — signer/owner/type-confusion/PDA/fake-oracle/truncating-cast/CPI, a taxonomy with almost zero EVM overlap | **clean** |
| 3 | **Privacy Pools** (0xbow) | **zk** / circom + Groth16 verifier | the dominant class is an *under-constrained circuit* (a missing constraint → soundness break → proof forgery), not a logic error; plus verifier public-input binding | **clean** |

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

## Synthesis — what changing the platform proved

1. **The method ports across VMs.** The same discipline — recompute every value-moving path from source, in the
   platform's *native* semantics, and ask "what stops an attacker from forging this?" — found the right guards on
   three platforms whose bug taxonomies barely overlap. On Vyper it was the lock model + `unsafe_*` bounds; on
   Solana it was account ownership/type/PDA validation and truncating casts; on zk it was the constraint system and
   verifier field-reduction. None of these classes exist on the others.
2. **Recompute-don't-trust scales to the hardest class.** The zk hunt re-derived an audit's soundness findings from
   the constraint system rather than trusting the audit — the circuit analogue of the alt_bn128 lesson — and
   resolved them via Poseidon-arity domain separation that the prose alone wouldn't settle.
3. **Deployed ≠ repo-HEAD is a first-class check on every platform.** The crvUSD hunt caught that the repo HEAD is
   the next-gen Vyper 0.4.3 line while live TVL runs 0.3.x; the Solana hunt pinned the on-chain program id; the zk
   hunt confirmed the live deployment + disclosure policy. A clean read of the wrong artifact is worthless
   regardless of language.
4. **Severity calibrated honestly, again.** The Solana `get_price_account` missing-owner-check and the zk advisory
   depth signals were each traced to *why they're safe* and explicitly **not** promoted to findings — the same
   discipline that calibrates EVM "dropped checks" down when value can't actually leave.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
