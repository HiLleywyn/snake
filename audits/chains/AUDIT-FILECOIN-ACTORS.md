# Filecoin (FIL) — storage-collateral conservation audit (clean)

**Target:** `filecoin-project/builtin-actors`, sparse clone `/tmp/fil` (`actors`, `runtime`). Audited
the two Filecoin-distinctive conservation surfaces: the **miner collateral-backing invariant**
(`actors/miner/src/testing.rs`) and the **reward actor** as the sole, bounded FIL mint
(`actors/reward/src/{lib,testing}.rs`). **Posture:** defensive; no exploit, no PoC. **Result: clean —
no finding, nothing to disclose.**

Chosen because Filecoin ties token value to **physical storage**: miners lock FIL as collateral
(initial pledge + precommit deposit), earn newly-minted FIL by continuously proving storage
(PoRep/PoSt), and are **penalized by burning** locked collateral if they fail. The conservation
question is therefore unusual — not just "transfers balance," but "is the committed collateral really
held, and is issuance bounded?" Both have clean, legible answers.

## Floor 1 — collateral is really backed (the miner balance invariant)
`check_miner_balances` (`miner/src/testing.rs:247-310`) states the core invariant
(`:275`):
```
balance − locked_funds − pre_commit_deposits − initial_pledge  ≥  0
```
**a miner's on-chain actor balance must always cover the sum of every locked obligation** — vesting
locked funds, precommit deposits, and initial pledge. A miner cannot pledge collateral it does not
actually hold. Reinforced by:
- all four components individually non-negative (`:254-273`, incl. `fee_debt ≥ 0`);
- **`locked_funds == Σ vesting-table entries`** (`:304-310`) — the locked-funds scalar isn't a
  free-floating number; it must equal the actual sum of the (quantized, positive) vesting schedule
  entries. So locked value is reconciled against the real schedule, not asserted.
This is the "balance covers liabilities" floor — the same shape as Stellar's `LiabilitiesMatchOffers`
(`AUDIT-STELLAR-INVARIANTS.md`) and the collateral checks in Drift/marginfi, here applied to storage
collateral. **enforced.**

## Floor 2 — the sole mint is bounded (reward actor, baseline-capped)
New FIL enters circulation only via the reward actor's block rewards. `AwardBlockReward`
(`reward/src/lib.rs:111-130`): `block_reward = (this_epoch_reward * win_count) /
EXPECTED_LEADERS_PER_EPOCH`, and `total_storage_power_reward += block_reward` tracks cumulative
issuance. The reward state invariant (`reward/src/testing.rs:19-52`) bounds it:
- **`total_storage_power_reward + balance ≥ storage_mining_allocation`** (`:19-23`) — cumulative
  minted-out plus the reward actor's remaining balance must still cover the protocol's storage-mining
  allocation; the actor cannot mint beyond its allocated share (the FIL "minting reserve" drains, it
  doesn't conjure).
- **`cumsum_realized ≤ cumsum_baseline`** (`:43-44`) and `cumsum_realized ≥ 0` (`:51`) — issuance
  follows the **baseline minting** schedule; realized network progress can't outrun the baseline that
  governs the emission curve.
- `effective_network_time ≤ epoch` (`:35-36`).
So issuance is **capped and schedule-bounded**, the controlled-inflation floor (same family as
Bitcoin's coinbase schedule and Berachain's `MAX_*_RATE` bounds, `AUDIT-BERACHAIN-POL.md`). **enforced.**

## How these are enforced vs. specified (an honesty distinction)
The `check_state_invariants` functions live in `testing.rs` — they are the **legible specification** of
the floor, run by the conformance/validation/migration harness, **not a per-block consensus gate**
(unlike Algorand's `CalculateTotals`, which *is* a consensus gate, `AUDIT-ALGORAND-TOTALS.md`). The
*production* enforcement is **by construction in the actor methods**: locking pledge checks available
(unlocked) balance before locking; penalties burn from locked funds; vesting adds quantized entries
that keep `locked_funds == Σ entries`. So Filecoin sits in the **conserve-by-construction** camp (like
current Cosmos `x/bank`, `AUDIT-COSMOS-BANK.md`), with `testing.rs` serving as the auditable written
invariant the methods are built to preserve. I verified the *invariant statement* and that it is the
correct floor; I read the method-level maintenance at the structural level, not exhaustively.

## Connections to the corpus
- **Capped issuance** joins Bitcoin/Litecoin (coinbase schedule) and Berachain (rate-bounded) on the
  controlled-mint rung.
- **Balance-covers-obligations** joins Stellar (`LiabilitiesMatchOffers`), Drift, and marginfi — the
  collateral-backing pattern, here for *storage* collateral with **burning as the penalty** (locked
  FIL destroyed on proof failure — a deflationary sink like XRPL's fee burn / the IBC-style sink).
- **Conserve-by-construction + written invariant** mirrors Cosmos `x/bank` post-invariant-removal: the
  spec is documented, the methods maintain it; the difference is Filecoin still ships the invariant
  checker (in testing/migration), Cosmos removed its registered one.
- **Value type:** `TokenAmount` is a signed `BigInt`; the invariants explicitly assert non-negativity
  rather than relying on an unsigned type — so the checks *are* the non-negativity guarantee (a
  weaker substrate than Rust's `u128`/Move's linear types, compensated by explicit assertions).

## What this audit did NOT cover (coverage honesty)
- **FVM value-transfer atomicity** — the actual debit-sender/credit-receiver on `rt.send(value)` lives
  in **`ref-fvm`** (separate repo, not cloned); the per-message conservation primitive is assumed
  sound there (the analog of the Cosmos `SendCoins` 1:1 I verified directly elsewhere).
- **PoRep / PoSt proof soundness** — whether a miner's storage proof actually proves real, unique
  storage (in `rust-fil-proofs`, separate). This is Filecoin's **deep irreducible trust**: the entire
  "value tied to storage" model rests on the proof system being sound (the analog of zkSync's
  circuit / Monero's range proofs). Named, not opened.
- **Power actor / consensus (Expected Consensus)** — the storage-power→block-election weighting; the
  agreement layer, orthogonal.
- **Market actor deal collateral & cron settlement** — the storage-deal payment escrow (provider/client
  collateral, deal payment streaming), a further collateral-conservation surface, not opened.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read the actual inequality `balance − locked − precommit −
  pledge ≥ 0` and the `locked_funds == Σ vesting entries` reconciliation, and the reward bound
  `total_minted + balance ≥ allocation` with `cumsum_realized ≤ cumsum_baseline` — confirming both the
  collateral-backing and the capped-issuance floors are stated as real inequalities, not narration.
- **Exposure to reversal.** The verdict rests on (a) `ref-fvm` transferring value conservatively (not
  in scope — assumed), and (b) the actor methods actually maintaining the `testing.rs` invariants in
  production (I read the invariant + structural maintenance, did not prove every method preserves it).
  Most importantly, the *economic* conservation ("storage is real") rests entirely on PoRep/PoSt
  soundness, which I explicitly mark as the irreducible trust rather than clearing it.

## Verdict
**Clean.** Filecoin's storage-collateral economics rest on two legible floors: a miner's on-chain
balance must cover all locked collateral (`balance ≥ locked + precommit + pledge`, with
`locked == Σ vesting`), and the sole FIL mint is capped and baseline-bounded
(`total_minted + reward_balance ≥ allocation`, `cumsum_realized ≤ cumsum_baseline`). Both are
maintained by-construction in the actor methods and stated as auditable invariants in `testing.rs`.
No untrusted-input→value path found in the audited surfaces; nothing to disclose. The irreducible
trust is **PoRep/PoSt soundness** (is the storage backing the value actually real), with FVM transfer
atomicity assumed from `ref-fvm`. Next pulls: the market actor's deal-collateral escrow and the
`ref-fvm` send primitive.

---

# Addendum — the PoRep/PoSt "is storage real" residual, narrowed (actor-level enforcement opened)

The main audit named PoRep/PoSt soundness as Filecoin's deep irreducible trust. I opened the
**actor-level enforcement** (`actors/miner/src/lib.rs`) and it decomposes the same way the rollup
oracles did (`AUDIT-ROLLUP-ORACLES-RESIDUALS.md`): a verifiable on-chain half + an irreducible
cryptographic half.

**On-chain enforcement (verified clean) — `verify_windowed_post` (`:4531-4575`):**
- **Challenge randomness is beacon-derived, not prover-chosen.** It regenerates the challenge via
  `rt.get_randomness_from_beacon(WindowedPoStChallengeSeed, challenge_epoch, entropy)` (`:4549-4553`),
  with entropy bound to the miner address — so a prover **cannot grind a favorable challenge**; the
  challenge is fixed by on-chain drand beacon randomness at the challenge epoch. This is the
  load-bearing anti-grinding property and it is enforced in-actor.
- **The proof is bound to the right public inputs:** the `WindowPoStVerifyInfo` ties the proof to the
  **specific `sealed_cid`s** of the challenged sectors (`:4555-4562`) and the **prover's miner ID**
  (`:4569`) — so a proof for other data or another miner won't verify.
- **Fault-on-failure:** a sector that isn't proven in its deadline is marked faulty and **penalized
  (collateral burned)** — the economic enforcement that makes the storage commitment real. PoRep is
  the symmetric story: `prove_commit`/`batch_verify_seals` (`:1569`) and
  `verify_aggregate_seals` (`:4911`) bind the seal proof to chain-derived seal randomness
  (`SectorSealProofInput.randomness`/`interactive_randomness`, `:4577+`) before a sector gains power.

**Irreducible residual (narrowed):** the actual cryptographic check is `rt.verify_post(&pv_info)`
(`:4573`) — a **runtime syscall** implemented by the proofs subsystem (`filecoin-proofs` /
`rust-fil-proofs`, Groth16/`bellperson` SNARKs over the PoRep/PoSt circuits), not in these actors. So
the residual narrows from "trust PoRep/PoSt" to specifically: **the `verify_post`/`verify_seal` syscall
soundly verifies the SNARK, and the PoRep/PoSt construction genuinely implies unique replicated storage**
(SNARK soundness + the proof-of-replication security argument + trusted setup). That is a
**cryptographic-soundness** residual (like zkSync's circuit), irreducible under hardness assumptions —
*not* the equivalence-style residual of Optimism's emulator. The actor correctly *gates* on it with a
non-grindable, public-input-bound challenge; only the syscall's cryptographic soundness remains. **No
finding.**
