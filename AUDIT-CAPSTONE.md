# Trust-Cartography Capstone — Findings Across the Whole Corpus

*The wrap-up. One reusable lens — six buckets + three coordinates (equivalence / conservation
floor / governance ceiling) — applied to ~25 systems across every major execution paradigm. This
records what was found, the comparative spectrums that emerged, and the laws that held.*

---

## 1. Headline

> **One genuinely actionable finding, responsibly disclosed (MemeCore PoSA, §3). Everything else
> resolved to: a sound/strong conservation floor + a residual that is either by-design governance
> centralization or an irreducible off-chain/cross-chain equivalence (6b).** No bare "safe" was
> ever used; every verdict points at the exact constraint or the exact unverifiable seam.

The corpus is itself the result: the lens produced *proportional signal* on every paradigm —
finding the real bug where one existed, and naming the trust precisely where none did.

---

## 2. Evidence table (every target, dominant locus, verdict)

| Target | Paradigm | Conservation floor | Residual / ceiling | Outcome |
|---|---|---|---|---|
| Namada MASP | ZK shielded | circuit value-balance | assets↔generator (governance) | constraint debt, no untrusted path |
| Penumbra | ZK shielded DEX | circuit + VCB | enable `overflow-checks` | hardening debt |
| Aztec | ZK rollup | proven AVM | spec↔circuit (6b) | 6a retired by proving |
| Aleo / Mina | ZK | replication / recursion | native↔circuit (6b) | enforced, 6b residue |
| Bridges (Wormhole/LZ/Hyperlane) | cross-chain | — | pure 6b | the 6b reference case |
| **Sui** (5 passes) | Move/Rust L1 | **linear types** (Σ=Supply by construction) | epoch delta in Rust/consensus; tautological local check | strongest floor in series |
| TRON (java-tron) | Java L1 | actuator↔processor equivalence | governance feature-gates | recompute-verified equivalent |
| WLFI | EVM token | OZ ERC20 | 3-of-5 Safe = proxy admin (verified≠running) | governance ceiling |
| Litecoin + MWEB | UTXO + MimbleWimble | tri-layer (scalar⇄pegs⇄commitments) | Bulletproofs soundness (6b) | enforced; inductive residual |
| **Base** | OP Stack rollup | ETHLockbox + fault proof | "DEFENDER_WINS ≠ valid" + Guardian | team-documented 6b |
| Civic | Token-2022 hook | validate-before-use gate | wallet↔token-account binding (off-chain) | enforced; 6b |
| Meteora DAMM v2 | AMM | pool-favorable rounding (all legs) | governance + Token-2022 hooks | strong floor |
| Marinade | LST | ledger-priced exchange rate | delegation (stake⇄validators) | strong floor |
| **Drift** | perp | **triple-capped PnL settlement** | the oracle | strong floor; oracle 6b |
| marginfi | lending | self-consistent rate decomposition | oracle + cross-protocol value-reporting | floor verified; verify-the-effect template |
| **MemeCore** | PoSA geth-fork | fixed/overflow-guarded reward | **§3 — see below** | **real finding, disclosed** |
| Canton / Splice | Daml consortium | balance check + ledger atomicity | DSO consortium | enforced |
| fetchd | Cosmos SDK | (forked modules) | bridge-mintable native (bounded) | by-design, capability-restricted |
| DeXe | DAO governance | voting-power integrity | proposal vote (no admin key) | self-governing pole |
| Humanity / World ID | proof-of-personhood | EAS (none) / ZK tree-integrity | off-chain orb/attester | see §5 comparison |
| LaunchLab / Alpha-Vault / Vault-SDK / Defi App | closed/mirror | — | unverifiable | auditability floor |

---

## 3. The one finding (MemeCore PoSA — disclosed to the team)

Two consensus-robustness items in `consensus/posa/contract.go::settleRewardsAndUpdateValidators`,
**routed privately** to the MemeCore foundation, written fix-first (no exploit):
- **B —** the `vmenv.Call` error is **swallowed** (`return nil` unconditionally); a reverting
  reward system-call (`timedTask`) silently produces a "valid" block. *Fix: propagate the error.*
- **C —** the validator list is built from a **Go map without sorting** and passed into the
  state-changing system call; map order is non-deterministic. With B and the fixed gas budget,
  order→gas→OOG-revert could cause a **silent consensus split**. *Fix: sort the list.*
Latent (a running chain implies it's currently order-insensitive), but consensus-adjacent — the one
target in the sweep that produced a real, fixable defect rather than a by-design trust boundary.

---

## 4. The comparative spectrums (the synthesis)

### (a) Three trust coordinates — every system reduces to these
1. **Equivalence / 6b (§9):** *what must be believed equal, and who discharges it* — proven (zk),
   re-executed (Aleo/Sui), agreed (Base fault proof), signed (bridges/World ID operator), or trusted
   (closed source).
2. **Conservation floor (§11):** *where "no value created" is enforced, and how strong* — see (b).
3. **Governance ceiling:** *who can replace the mechanism* — see (c).
All three move **down and outward**, away from the code that looks in charge.

### (b) Conservation-location ladder (strongest → weakest enforcement)
type system (Sui linear types) > cryptographic algebra (MWEB commitments, World ID ZK) >
ledger-model atomicity (Daml) > consensus re-derivation (Sui epoch, MemeCore) > runtime balance
check (UTXO, AMM rounding, lending rate-decomposition, perp settlement cap) > account-balance
mutation (EVM/Cosmos imperative). **Strength is inversely correlated with how much you must trust
the author** — and it determines the residual's *shape*: type/crypto-enforced systems push fragility
to **liveness** (abort/safe-mode); imperative systems push it to **value** (a missing check = mintable
supply).

### (c) Governance-ceiling spectrum (most → least centralized)
**$H/HToken** (owner: uncapped mint + force-burn + upgrade) → **WLFI** (3-of-5 Safe swaps the impl)
→ **World ID** (owner can swap the verifier/upgrade — ZK conditional on owner) → **fetchd** (admin
*bounded*: bridge can mint, cannot seize — `BurnFrom`/`ForceTransfer` deliberately disabled) →
**DeXe** (no admin key; every privileged action is proposal-gated via `onlyThis` — trust root is the
vote). *Same coordinate, opposite poles.*

### (d) Auditability floor — "open source" is not one thing
full-source-and-running (Sui, Drift, marginfi, Marinade, DAMM v2, Civic, MemeCore, Canton, fetchd,
DeXe, World ID) → **verified-but-swappable** (WLFI: verified ≠ running) → **SDK/IDL mirror, program
closed** (LaunchLab, Alpha-Vault, Vault-SDK) → **audit-PDFs only** (Defi App) → no source. The
**withheld layer is consistently the orchestration / enforcing logic** — exactly where conservation
is enforced or broken.

### (e) Proof-of-personhood, compared
**Humanity** keeps *all* sybil-resistance off-chain (vanilla EAS + an attester key). **World ID**
puts *tree integrity* under ZK on-chain (insertion proofs, fresh-root checks) but still rests on an
off-chain **orb + operator** for personhood and delegates **nullifier uniqueness to integrating
apps**. Both share the irreducible 6b of *any* PoP system: an off-chain biometric authority decides
who is a unique human; the chain can at best prove the bookkeeping is correct.

---

## 5. The laws that held across every paradigm

1. **The load-bearing guarantee is never where you first look.** It lived in Rust not Move (Sui),
   in `ApplyBlock` not `Block::Validate` (Litecoin), in the `split` assert not the reward formula
   (DAMM/Sui), in the system-snapshot not the rate math (Marinade/Sui staking), in the proxy admin
   not the token (WLFI/$H), in consensus not the entrypoint (MemeCore/Sui). **Locate the enforcement
   mechanism before reading the business logic.**
2. **"Verify the effect, don't trust the reported state."** The marginfi cross-protocol pass is the
   positive template: refresh → compute-conservatively → CPI → **verify what was actually
   received**. The detector for the *missing* version of this is the highest-EV bug hunt.
3. **Residual shape follows enforcement substrate** (§4b): liveness-shaped under type/crypto;
   value-shaped under imperative. The MemeCore finding is exactly an imperative-substrate
   value/liveness gap (swallowed error + nondeterminism) in otherwise-inherited code.
4. **"Trustless" names the mechanism; the honest question is *trustless until whom?*** Every system
   bottoms out at a named authority — a multisig, a Guardian, a DSO, an orb operator, a bridge key,
   or (best) the vote itself.
5. **Closed enforcing-logic is the modern default and the real frontier.** Across Solana
   launchpads/vaults and app-chains, the audited/published artifact is increasingly the *mirror*,
   not the *program* — so the discipline must include *naming what you cannot see* as a first-class
   output.

---

## 6. Posture & disclosure summary

Defensive throughout: no exploit, no PoC, no weaponization; "no bare safe." The single
exploitable-class finding (MemeCore B/C) was **routed privately** to the project, fix-first.
Live-system requests (a third party's website/forum) were **declined** for active testing and
redirected to passive analysis + owner-run checks + auditing the relevant open-source software
(phpBB) — the boundary held even under repeated pushing. Public audits used `git clone` / public
artifacts only; nothing catastrophic was ever posted.

> **Bottom line:** one reusable lens, ~25 systems, every major paradigm — and a consistent two-part
> answer each time: *a conservation floor (named, graded by substrate) and a residual that is a
> governance ceiling or an irreducible 6b equivalence.* The framework found the one real bug, named
> every trust boundary in proportion, and never overclaimed.

Companion index: `AUDIT-METHODOLOGY.md`, `AUDIT-METHODOLOGY-CHECKLIST.md`,
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` (§1–11), `AUDIT-GOVERNANCE-CEILING.md`,
`AUDIT-WEBAPP-GENERALIZATION.md`, and the per-target reports referenced in the table above.
