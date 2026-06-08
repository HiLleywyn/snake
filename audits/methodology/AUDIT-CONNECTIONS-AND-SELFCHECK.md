# Connections across the corpus + self-audit (epistemic-hygiene pass)

*Two jobs in one: (1) apply the exposure-to-reversal discipline to my own prior claims and record
corrections; (2) surface the connections between the ~45 audits — which references reinforce or
contradict each other. Recompute, don't trust the summaries.*

---

## Part 1 — Self-audit (mistakes found & corrected)

Ran the exposure-to-reversal test on the highest-stakes claims (the ones that, if wrong, flip a
verdict). Recomputed from code, not from my own write-ups.

- **CORRECTED — Aptos linear-type floor (method error, conclusion held).** `AUDIT-APTOS-COIN.md`
  originally said the floor was "verified … in Sui Pass 7 — Aptos runs its own Move fork of the same
  ability design." That **extrapolated** Sui's verifier to Aptos. On re-check I read **Aptos's own**
  verifier (`third_party/move/move-bytecode-verifier/src/type_safety.rs`) and independently confirmed:
  `Pop→POP_WITHOUT_DROP` (`:620`), `CopyLoc→COPYLOC_WITHOUT_COPY` (`:838`),
  `ReadRef→READREF_WITHOUT_COPY` (`:991`), `WriteRef`-needs-`drop` (`:1011`). Conclusion stands; the
  *extrapolation was the mistake*, now grounded. (This is the exact failure mode the methodology warns
  about: trusting a cross-target summary instead of recomputing on the actual codebase.)
- **CONFIRMED — MemeCore §6-B/C (the one disclosed finding).** Re-read `consensus/posa/contract.go`:
  the `vmenv.Call` `err` is referenced only inside `if p.enableEventLogging`, then
  `state.Finalise(true); return nil` — genuinely swallowed; and the validator list is still built by
  `for validator := range <map>` with no sort. Finding holds. **Hedge re-affirmed:** §6-C is *latent*
  ("a running chain implies it's currently order-insensitive"), not a demonstrated live split — I did
  not overclaim it as a live exploit.
- **Hedges re-affirmed (not overclaimed):** Sui native-SUI supply = *"consensus-agreement property,
  not type-enforced"* (the local check is tautological for the epoch tx) — still correctly stated as a
  weaker class than user-coin conservation. Closed-source verdicts (LaunchLab/Alpha-Vault/Vault-SDK/
  Defi-App/TradePort) = *"not establishable from public artifacts,"* never "safe." Drift/marginfi
  residual = the oracle, named irreducible. No bare "safe" anywhere on re-scan.
- **Bias check (am I under-digging the blue-chips?).** Honest answer: the find-distribution is *bug in
  the newer custom-glue chain (MemeCore), clean in the formally-specified blue-chips (Aptos has Move
  Prover specs; Sui/Drift/marginfi/DeXe are multi-audited)* — and every "clean" verdict cites the
  exact enforcing constraint **and** lists coverage gaps. That pattern is consistent with reality, not
  with under-digging — but the coverage gaps (e.g., Sui's `move-abstract-interpreter` engine, Aptos
  Block-STM, MonadBFT crypto) are real and stated, not hidden.

---

## Part 2 — Connections (cross-references between audits)

### A. The determinism-&-failure-handling spine (the corpus's central thread)
The one real bug and the correctness of every well-built chain are **the same property** at different
layers: *deterministic state transition + halt-not-swallow.*
- **MemeCore** `AUDIT-MEMECORE-POSA.md` — VIOLATES it: non-deterministic Go-map validator order +
  swallowed system-call error → latent silent split. The negative example.
- **Sui Pass 6** `AUDIT-SUI-SIX-BUCKET.md` — IMMUNE: BTreeMap-only (42/0 HashMap), deterministic
  safe-mode on epoch-PT failure (drop_writes, not swallow).
- **Monad** `AUDIT-MONAD-PARALLEL.md` — SOUND: OCC + strictly-ordered commit + `MONAD_ASSERT` halt.
- **MonadBFT** `AUDIT-MONADBFT-CONSENSUS.md` — SOUND: monotonic one-vote-per-round + `assert!`-halt
  ("crash rather than sign an unsafe vote").
- **Aptos Block-STM** (flagged, not yet opened) — same OCC family as Monad (see B).
> **Connection:** MemeCore failed *exactly* the discipline Sui (epoch), Monad (execution), and
> MonadBFT (consensus) each enforce. The "halt over silent divergence" philosophy recurs verbatim in
> all three; MemeCore's `return nil` is its precise negation.

### B. The OCC / relaxed-merge twins (Monad ≡ Aptos)
Monad's `try_fix_account_mismatch` (balance-only relaxed merge over optimistic parallel EVM,
`AUDIT-MONAD-PARALLEL.md`) and **Aptos Block-STM** are the *same* technique — optimistic concurrent
execution with read-set conflict detection + deterministic re-execution. **The Aptos surface I left as
the "next pull" is the Monad relaxed-merge class I already opened** — so the Monad analysis
(centralized constraint instrumentation; the load-bearing piece is the conflict-detector) is the
template for auditing Aptos Block-STM. Concrete cross-reference, not a coincidence.

### C. The Move linear-type floor (Sui ≡ Aptos), now both verifier-confirmed
`Balance<T>` (Sui) and `Coin<T>` (Aptos): identical `store`-no-`copy`-no-`drop` floor, and **both
verifiers are now independently read** (Sui Pass 7 + the self-check above). This is the strongest
conservation floor in the corpus, and it is the *only* one confirmed across two distinct
implementations. Divergence worth noting on the **governance-ceiling** axis (D): Sui's `TreasuryCap`
is unique/non-copyable; Aptos's `MintCapability` has `copy` — a per-coin authority the holder can
replicate.

### D. The governance-ceiling spectrum (extended)
From `AUDIT-GOVERNANCE-CEILING.md`, ordered most→least centralized, now with the new data points:
**HToken** (owner: mint+force-burn+upgrade) → **WLFI** (3-of-5 Safe swaps impl) → **World ID** (owner
can swap the ZK verifier) → **Aptos `MintCapability`** (copyable per-coin mint) → **fetchd** (admin
bounded — can mint via bridge, *cannot* seize) → **DeXe** (no key; proposal-gated `onlyThis`). Same
coordinate; the chains differ by *how much one key can do*.

### E. The auditability-floor family (open client, closed program)
`AUDIT-LETSBONK-LAUNCHLAB.md`, `…ALPHA-VAULT.md`, `…VAULT-SDK.md`, `AUDIT-DEFIAPP-NOTE.md`, and now
**`AUDIT-TRADEPORT-NOTE.md`** — all ship SDK/IDL/ABI/audit-PDFs but withhold the enforcing logic.
TradePort is the **NFT-marketplace** instance (its Aptos ABI is *richer* than an IDL — typed entry
points — but still no logic). **Connection:** the "verified ≠ running / open-mirror, closed-program"
gap spans launchpads, vaults, DeFi *and* NFT marketplaces — it is the dominant auditability limit of
the top 100, not a one-off.

### F. The off-chain-authority 6b family
The irreducible trust always relocates off-chain to a named authority:
**World ID** (orb + identity operator) · **Humanity** (EAS attester key) · **Civic** (wallet↔token-
account associator) · **Drift / marginfi** (price oracle) · **fetchd** (the bridge + ETH peg) ·
**TradePort** (the off-chain indexer/aggregator the UI trusts). Proof-of-personhood, oracles, bridges,
and marketplace-aggregators are the *same shape*: the chain proves bookkeeping; an off-chain party
provides the truth.

---

## The single sentence the connections collapse to
> Across the top-100-grade corpus, **the same two coordinates explain every system**: a *conservation
> floor* (graded type-system > crypto > ledger-atomicity > consensus-re-derivation > runtime-check >
> imperative) and a *residual* that is either a **governance ceiling** or an **off-chain/6b
> equivalence** — and the one real bug (MemeCore) is precisely a chain that broke the determinism
> discipline its better-built peers (Sui/Monad/Aptos/MonadBFT) enforce.

Companion to `AUDIT-CAPSTONE.md` (the evidence table) and `AUDIT-METHODOLOGY-RETROSPECTIVE.md`
(§9 equivalence / §10 compression / §11 conservation-floor).
