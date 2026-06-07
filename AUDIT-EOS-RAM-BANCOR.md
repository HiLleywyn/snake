# EOS / Antelope (EOS) — RAM Bancor-market conservation + float-determinism audit (clean, with a stated runtime assumption)

**Target:** `eosnetworkfoundation/eos-system-contracts`, sparse clone `/tmp/eos`
(`contracts/eosio.system`). Audited the **RAM market** — the Bancor relay in `exchange_state.cpp`
(`convert`, `convert_to_exchange`, `convert_from_exchange`, `get_bancor_output`). **Posture:**
defensive; no exploit, no PoC. **Result: clean — no finding, nothing to disclose**, with one
load-bearing *stated assumption* (the runtime's deterministic-float guarantee).

Chosen for a genuinely distinct economic primitive — RAM is **bought and sold against a Bancor bonding
curve**, not transferred — and for a pointed connection to this corpus's lone finding: the RAM math is
computed in **floating point (`double` + `std::pow`)** inside consensus code, which is normally the
*exact* determinism hazard that is the MemeCore failure class. EOS makes it safe — but at a layer below
the contract. That contrast is the reason this was worth a full pass.

## The RAM market — Bancor bonding curve, reserves updated consistently (Bucket 1/5, curve-invariant)
`buyram`/`sellram` route through `convert` (`exchange_state.cpp:39-57`), a two-hop through the relay's
"exchange" token:
- **`convert_to_exchange(reserve, payment)`** (`:11-23`): mints relay supply
  `dS = S0·((1 + dR/R0)^F − 1)`, then `reserve.balance += payment; supply += dS`. EOS paid **enters the
  reserve** (held, not minted/destroyed).
- **`convert_from_exchange(reserve, tokens)`** (`:25-37`): burns the relay tokens and pays out
  `dR = R0·((1 + dS/S0)^(1/F) − 1)`, then `reserve.balance -= |dR|; supply -= tokens`.
- Round-trip, the relay supply is minted then burned back, and the output is drawn from a finite
  reserve. `get_bancor_output` (`:81-94`): `out = in·ob/(ib + in)` — structurally `out < ob` always
  (you can **never drain the full output reserve**) and `out ≥ 0`.
The "conservation" here isn't a simple sum (it's a price curve), but it is **leak-free**: every unit of
EOS paid is held in the ramcore connector, RAM bytes come from a bounded reserve, and reserves are
updated by exactly the curve amounts. **enforced (as a curve invariant).**

## Rounding is reserve-favorable (conservative direction)
Both hops truncate toward zero (`int64_t(dS)`, `int64_t(-dR)`) and floor sign-flipped rounding noise to
zero (`if (dS < 0) dS = 0; // rounding errors` `:19`; `if (dR > 0) dR = 0;` `:33`). Truncation means
the *user receives slightly less* and the *reserve keeps the dust* — rounding favors the pool/system,
the same conservative discipline verified in Meteora DAMM v2 (`AUDIT-METEORA-*`) and Sui's split
assert. A user can't extract value via rounding. **enforced.**

## The determinism point — float in consensus, contained only by the runtime (the MemeCore contrast)
`get_bancor_output`/`convert_*` use `double` and `std::pow`. **Floating-point in consensus-executed
code is normally a determinism hazard** — if two nodes computed even one ULP differently, they'd
disagree on RAM balances and the chain would fork. That is *structurally the MemeCore class*
(non-deterministic input to a state-changing computation, `AUDIT-MEMECORE-POSA.md`). EOS/Antelope is
safe here **not because the contract avoids float**, but because the **Antelope WASM runtime mandates
deterministic floating point** (Berkeley SoftFloat-based IEEE-754 with fixed rounding, transcendentals
via a pinned deterministic libc compiled to WASM) — so every node computes bit-identical results.

This is the instructive inverse of MemeCore: there, nondeterminism (Go map order) leaked into consensus
*uncontained*; here, nondeterminism's classic source (float) is **contained at the runtime layer**, so
the same hazard is neutralized. **Crucially, the guarantee lives below the contract** — in the node's
WASM VM, which I did **not** audit (it's not in this repo). So this is a **stated load-bearing
assumption**: the RAM market's cross-node determinism rests on the Antelope runtime's deterministic-float
property. If that guarantee failed, this float math would be a consensus-split risk. I record it as the
key residual, not as cleared.

## Connections to the corpus
- **Determinism spine (§4g), the cautionary entry.** OCC (Monad/Aptos/Sei) and GHOSTDAG (Kaspa) make
  parallelism deterministic *in the protocol*; EOS instead pushes a determinism hazard (float) *down to
  the runtime* and relies on it. Same goal (all nodes agree), but the guarantee is delegated a layer
  down — the most "trust-the-runtime" point in the corpus, and the closest non-defective neighbor of
  the MemeCore finding.
- **Reserve-favorable rounding** joins Meteora/Sui/Avalanche on the "round against the user, never
  toward value-extraction" discipline.
- **Bonding-curve vs sum-conservation.** Unlike every prior conservation floor (sum/equation/journal),
  RAM is a *price-curve* reserve system — value is conserved by holding the paid EOS in the connector,
  not by a balance equation. A distinct conservation *shape* (AMM-like, cf. the DAMM v2 AMM but for a
  system resource).

## What this audit did NOT cover (coverage honesty)
- **The Antelope WASM runtime's deterministic-float guarantee** — the load-bearing assumption above;
  it lives in `AntelopeIO/spring` (the node), not these contracts. **The single most important residual.**
- **`eosio.token` base conservation** — the standard `add_balance`/`sub_balance` (overflow/sufficiency
  checked) under ordinary transfers; the base token floor, separate from the RAM market, not opened.
- **Resource staking (CPU/NET via `delegatebw`)** and **`buyram`/`sellram` wrappers** (fees, the 0.5%
  RAM fee, the `ramcore`/`ram`/`ramfee` account routing) — read the curve, not the full fee/stake
  plumbing.
- **`get_bancor_input`** (the inverse, for exact-output trades) and producer/voting economics.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read the actual Bancor formulas and confirmed `out = in·ob/(ib+in)`
  cannot drain the reserve (`out < ob`) and is floored at 0; confirmed both hops truncate in the
  reserve-favorable direction; and confirmed EOS paid is added to the reserve (held, not destroyed). I
  specifically flagged the `double`/`std::pow` usage rather than glossing it.
- **Exposure to reversal.** The clean verdict is *conditional on* the runtime's deterministic-float
  guarantee — which I explicitly did not verify (it's in the node). If that fails, the float math
  becomes a consensus hazard. I also did not audit the `eosio.token` base floor or the fee routing; a
  conservation bug could in principle live in the buy/sell wrappers I didn't open. Both stated as
  bounded reads, and the runtime assumption stated as the key residual rather than cleared.

## Verdict
**Clean (conditional on a named runtime assumption).** EOS's RAM market is a leak-free Bancor bonding
curve: EOS paid is held in the connector reserve, output is bounded (`out < reserve`) and floored at
zero, relay supply mints/burns symmetrically per round-trip, and truncation rounds in the reserve's
favor so users can't extract value via rounding. The notable feature is **floating-point math inside
consensus** — structurally the MemeCore determinism hazard — rendered safe **only** by the Antelope
WASM runtime's deterministic-float guarantee, a layer below these contracts that I record as the key
irreducible assumption. No untrusted-input→value path in the audited curve; nothing to disclose. It is
the corpus's cautionary determinism-spine entry: a determinism hazard delegated to (and contained by)
the runtime rather than avoided in code. Next pulls: the `spring` runtime's softfloat enforcement and
the `eosio.token` base floor.
