# DESIGN-PRINCIPLES.md — What ~60 Audits Say a Chain Should Do

*The constructive mirror of `AUDIT-CAPSTONE.md`. The capstone catalogs what was found across ~60
systems + 7 large-cap consensus deltas + 15 fresh-code reads (EVM and non-EVM, 5 non-EVM teams). This
file inverts it: the **design rules** those audits imply — what a chain/protocol should actually do so
its bugs fail safe and its trust is honest. Every rule is grounded in a corpus observation, with the
anti-pattern named. Nothing here is novel cryptography; it's the boring discipline that separated the
~59 clean systems from the one finding.*

> **The one-sentence thesis.** Across the whole corpus, *every* real defect in a well-engineered chain
> failed **safe** — a transaction aborts, a node hangs, stake gets stuck, a constant is wrong — with
> conservation and consensus intact, **because the substrate forced it**. The single exception
> (MemeCore) is the only place a defect could fail **unsafe** (silent value/consensus divergence), and
> it's the only finding. **Design so your worst bug is a liveness bug.**

---

## 0. The Prime Directive — choose a fail-safe substrate

The most important decision is made before any business logic: the substrate that arithmetic, ordering,
and balances live on. Pick ones where a mistake **aborts or halts** instead of **wrapping or
diverging**.

- **Checked arithmetic, always.** Underflow/overflow must error or panic, never wrap. *Evidence:*
  Cosmos `math.Int` panics on overflow; Substrate `Imbalance` / `saturating` (defensive); Tezos `+?`/`-?`;
  ICP `checked_add`/`checked_sub`; Sui's address-balance underflow (R8) **aborted the settlement** —
  a liveness hiccup — precisely because the arithmetic was checked. A wrapping `u64` would have minted
  value instead.
- **Type-enforced value when you can.** Make a unit of value impossible to duplicate or vanish *in the
  type system*. *Evidence:* Move linear types (Sui/Aptos `Balance`/`Coin`: `store` without
  `copy`/`drop`); Substrate's `#[must_use] Imbalance` whose `Drop` books the delta to `TotalIssuance`.
- **Determinism by construction.** Same inputs → same result on every node, or the block is rejected.
  *Evidence:* this is the spine of §1; its violation is the entire MemeCore finding.

**Anti-pattern:** raw imperative balance mutation on unchecked integers in a path that can't simply
abort (MemeCore's geth-fork consensus). When the substrate doesn't force fail-safe, *you* must — and
that's where things slip.

---

## 1. Determinism — the quiet prerequisite for everything

A chain that can't agree on *order* can't agree on *balances*. Most consensus bugs are determinism
bugs.

1. **Never let map-iteration order reach a consensus-critical computation.** Build from a map if you
   must, but **canonicalize (sort) before** it becomes calldata, a hash input, or a state write.
   *Evidence — the corpus's #1 recurring guard:* BSC sorts the map-derived validator list
   (`sort.Sort(validatorsAscending)`) before the reward system-call; Polygon
   `sort.Sort(ValidatorsByAddress)`; Sonic canonicalizes inside `Build()` (sorted by weight+ID); geth's
   EIP-7928 BAL sorts every field before RLP; Kaspa GHOSTDAG re-sorts the mergeset by `(blue_work, hash)`;
   Sui Mysticeti sorts the sub-DAG by `(round, author)`. **MemeCore is the lone chain that fed an
   unsorted Go map straight into a state-changing system call** — the finding.
2. **Use a strict total order with a unique tiebreak.** `(primary, unique-key)` — e.g. (round, author),
   (blue_work, hash), (weight, id). No ambiguous ties.
3. **No floating point in consensus** *unless* the runtime guarantees deterministic IEEE-754. *Evidence:*
   EOS computes its Bancor curve in `double`/`std::pow` — safe **only** because the Antelope WASM VM
   mandates SoftFloat in both interpreter and JIT. If you can't guarantee that, use exact rationals
   (Solana Alpenglow compares stake as `Fraction::new(num, total)`, never `f64`).
4. **Two implementations of one rule must agree — centralize the canonical form.** *Evidence:* geth and
   reth both lean on the shared `alloy-eip7928` encoder rather than two hand-rolled ones; Aptos's
   const-folder bug (R9) was exactly a *compile-time ≠ runtime* divergence. Cross-client/compile≡runtime
   equivalence is a real bug class — minimize independent re-encoders, and pin them with shared test
   vectors.

---

## 2. Conservation — conserve by construction, then recompute and check it anyway

"No value created from nothing" should be true *structurally*, and then *verified* by a computation
that doesn't trust the structure.

1. **Make conservation structural.** A transfer should debit and credit the **same amount** in one
   atomic step; supply should change **only** through explicitly-typed mint/burn. *Evidence:* Cardano
   `consumed == produced`; Avalanche `produced ≤ consumed` per asset; Hedera's tx adjustment list must
   `isNetZeroAdjustment` (sum to zero, per asset); Tezos moves supply only via typed
   `infinite_source`/`infinite_sink`; ICP's complement-pool (`supply = max − token_pool`, derived).
2. **Then recompute total supply and reject on drift — don't trust your own bookkeeping.** The strongest
   floors re-derive the invariant. *Evidence:* Algorand recomputes `totals.All()` every block and rejects
   the block if `!= prevTotals`; Solana recomputes capitalization (storage index Σ **+ cached updates**,
   `checked_add`, R6); Berachain reverts if `balance < totalSupply()`; XRPL/Stellar invariant-check
   finalizers; Aptos Move-Prover `supply` specs. **A stored counter can drift; a recomputed-and-compared
   one cannot.**
3. **Round against the user, never toward value extraction.** Every rounding choice should favor the
   pool/protocol. *Evidence:* Pendle mint *and* redeem both round down; Curve's `dy` rounds toward the
   pool, fees grow `D` monotonically; Meteora pool-favorable on all legs; EOS truncates to the reserve's
   favor.
4. **Mind dual representations — they're a top bug frontier.** When the same value can exist in two forms
   (account-balance ↔ object-coin, Coin ↔ FungibleAsset), make movement between them **atomic 1:1
   burn-mint**, and make sure balance/supply queries sum **disjoint** stores with no double-count.
   *Evidence:* Aptos Coin↔FA conserves (atomic burn-mint, disjoint summing, R10) — *clean*; Sui's
   address-balance↔coins slipped at a non-atomic **settlement edge** (gas-smashing on a drained balance,
   R8) — *the real recent bug*. Same class, opposite outcomes, decided by atomicity.

**Anti-pattern:** a separately-stored `totalSupply` that's only ever incremented/decremented and never
re-checked; non-atomic conversion between two representations of the same asset.

---

## 3. Error handling — propagate, and halt over divergence

1. **Never swallow an error in a consensus-critical path.** A failed system call / state transition must
   **invalidate the block**, not silently produce a "valid" one. *Evidence:* BSC, Polygon, Celo, bor all
   `return err` from their system-call/fee paths; MonadBFT `assert!`s and halts on a safety violation.
   **MemeCore's `settleRewardsAndUpdateValidators` returns `nil` unconditionally** (the `vmenv.Call`
   error is only logged) — half of the finding.
2. **Verify replayed/synthetic transactions; don't trust the producer.** If a block carries
   system/internal txs, the verifier must reconstruct and **hash-check** them. *Evidence:* BSC
   `applyTransaction` byte-compares the actual system tx to the expected; reth recompute-and-hash-compares
   the BAL; Algorand/ICP/Cosmos recompute rather than trust.
3. **Crash/abort beats corrupt.** On an "impossible" invariant violation, halt the message/validator
   rather than continue. *Evidence:* ICP panics → the IC traps and rolls back the whole message; Move
   aborts; Monero rejects malformed points via catch-and-return-false.

---

## 4. The settlement seam — name your one oracle, and make it the only trust

Every cross-layer/cross-chain value movement bottoms out on *one* thing you must trust. Pick it
deliberately and make it the *only* one. The corpus has four models, ranked by who you must trust:

| Model | Trust assumption | Examples |
|---|---|---|
| **Validity proof** | 0-of-N (cryptographic) | zkSync — a SNARK gates withdrawals |
| **Fraud proof** | 1-of-N honest watcher + L1 liveness | Optimism — `DEFENDER_WINS` + challenge window |
| **Light client** | >2/3 of the *counterparty's* validators | IBC — Merkle-proof vs a verified header |
| **Multisig + dispute** | >2/3 of an *appointed* committee | Hyperliquid Bridge2 |

Rules that held across all of them:
1. **Release value only against a verified source**, with the heavy check *somewhere* explicit — on-chain
   or in a named off-chain validator. *Evidence:* Optimism `validateMessage` is a cheap warmth hook, but
   the op-supervisor enforces "executing message ⟺ real, in-dependency-set, non-reorged source" (R3→R4);
   IBC's `verifyChainedMembershipProof` ties the packet to the trusted root.
2. **Honor causality.** Never execute a message from the future (`executing.ts ≥ source.ts`), and ensure
   a reorged-out source **cascades to invalidate** its dependents. *Evidence:* op-supervisor's
   `breaks timestamp invariant: ErrConflict` (R4) and the cross-safe frontier's `ErrConflict` +
   `InvalidateLocalSafe` on a different-ID source (R5).
3. **Keep a backstop and a kill-switch.** A bank-layer underflow guard bounds blast radius even if the
   seam's trust fails (IBC: a chain can't unescrow more than it locked); a `failsafe`/pause halts the
   seam on anomaly (Optimism interop, THORChain solvency auto-halt).
4. **Isolate blast radius per counterparty.** A Byzantine counterparty should only be able to inflate
   *its own* voucher denom, never your native asset (IBC mint-only-when-not-source).

**Anti-pattern:** a settlement contract that *looks* like the whole check but silently relies on an
unstated off-chain validator you never named or audited.

---

## 5. Governance ceiling — be explicit about "trustless until whom?"

"Trustless" names a mechanism; the honest question is *trustless until whom*. Every system bottoms out
at a named authority — make it the *narrowest, most accountable, most visible* one you can.

1. **Bound the admin in code.** If there's an upgrade/mint authority, cap and rate-limit what it can do.
   *Evidence (the good end):* WLD — capped supply, 15-yr mint lock, ≤~1.5%/yr rate-limited, non-upgradeable;
   fetchd — bridge can mint but **cannot seize** (`ForceTransfer` deliberately disabled); Berachain
   `MAX_*_RATE` bounds. *(The bad end: an owner with uncapped mint + force-burn + upgrade.)*
2. **Gate consensus-affecting changes behind a hardfork/height** so all nodes flip together
   (bit-for-bit replay correctness) — never hot-patch un-gated.
3. **Prefer vote-gated or federated-accountable over an anonymous key.** Spectrum: anonymous multisig →
   token-stake vote (DeXe, Tezos self-amendment) → identity-bound council (Hedera). Pick consciously and
   document it.
4. **The mutable side is the trust.** If the enforcing logic is upgradeable (a swappable verifier, a
   reward contract), *that upgrade authority* is your real ceiling — say so. (MemeCore's missing
   client-side sort means consensus correctness rests entirely on the closed, upgradeable reward
   contract staying order-commutative — a single innocuous upgrade could detonate it.)

---

## 6. Auditability floor — ship the enforcing logic, open and verifiable

"Open source" is not one thing. The corpus repeatedly found the *withheld layer is the enforcing layer*.

1. **The code that enforces conservation/consensus must be open and match what's running.** *Evidence
   (worst→best):* PI — closed core, unauditable, trust = the team entirely; closed enforcing programs with
   only an SDK/IDL mirror (LaunchLab/vaults); WLFI — *verified ≠ running* (a Safe can swap the impl);
   full-source-and-running (Sui, Drift, etc.).
2. **A clean token contract ≠ a safe asset.** LAB's token is a fixed-supply ownerless ERC-20 (can't be
   inflated) — but the real risk lived **off the token**, in vesting contracts + holder concentration.
   Audit the *distribution*, not just the token.
3. **Closed-but-bounded can still be mapped.** Read on-chain ABIs/IDLs to map the trust surface even when
   source is closed (TradePort, Hyperliquid Bridge2) — but say plainly what you *cannot* verify.

---

## 7. The MemeCore checklist — the concrete don'ts (and the two-line fix)

The one finding, distilled into a pre-ship checklist for any chain with a "system call during block
finalization" (parlia/PoSA/epoch-seal patterns):

- [ ] **Is any consensus-critical input built by ranging a Go map (or any unordered set) without a
      subsequent sort?** → **Sort it** with a unique tiebreak before it becomes calldata/state.
- [ ] **Is any system-call / state-transition error swallowed (`return nil`, log-only)?** → **Propagate
      it** so a failure invalidates the block.
- [ ] **Are block-carried system txs verified by reconstruct-and-hash-compare on import?**
- [ ] **Is the gas budget for the system call finite, and could ordering flip success↔OOG?** → confirm
      order-invariance at the real budget against the live contract.
- [ ] **Is correctness resting on a closed, upgradeable contract staying order-commutative?** → restore
      the client-side invariant so a future upgrade can't detonate it.

The fix MemeCore needed (and BSC/Polygon/Sonic all already have): **sort the validator list + propagate
the call error**, gated behind a hardfork. Two small, independent changes. (See `MEMECORE-FIX.md` if
present.)

---

## The one-page checklist

**Substrate:** checked arithmetic · type-enforced value · deterministic by construction.
**Determinism:** canonicalize before any consensus-critical use · strict total order + unique tiebreak ·
no nondeterministic float · centralize cross-impl encoders + pin with test vectors.
**Conservation:** conserve-by-construction · **recompute total supply and reject on drift** ·
round against the user · atomic 1:1 between dual representations, disjoint-store summing.
**Errors:** never swallow in a consensus path · verify replayed system txs · halt over corrupt.
**Settlement seams:** name your one oracle · release only vs a verified source · honor causality +
cascade reorg invalidation · keep a backstop + kill-switch · isolate per-counterparty blast radius.
**Governance:** bound the admin in code · gate consensus changes behind a fork · prefer vote/federated
over anonymous key · name the mutable-side trust.
**Auditability:** open the *enforcing* logic, verified == running · audit distribution not just the
token · map closed surfaces via ABI and say what you can't verify.

> **Net:** the hard part of a chain isn't the token (a safe one is ~20 lines). It's a substrate that
> fails safe, a conservation invariant you recompute rather than trust, determinism before every
> consensus decision, and **one honestly-named trust** at each seam. Do those, and your worst bug is a
> liveness bug that gets caught and fixed before it costs anyone — which is exactly what ~59 of the ~60
> systems demonstrated, and the one that didn't is the only one with a finding.

*Companion to `AUDIT-CAPSTONE.md` (§4 spectrums, §5 laws, §5b the fail-safe-substrate boundary),
`AUDIT-LARGECAP-BUGHUNT.md`, and `AUDIT-RECENT-COMMITS-HUNT.md`.*
