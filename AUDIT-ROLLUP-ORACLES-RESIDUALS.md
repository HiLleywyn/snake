# Residuals pass — the two rollup oracles opened (Optimism Cannon FPVM + zkSync Verifier)

This closes the deepest residuals I explicitly *named but deferred* in
`AUDIT-OPTIMISM-FRAUD-PROOF.md` and `AUDIT-ZKSYNC-VALIDITY-PROOF.md` — the "irreducible oracles" each
rollup's conservation bottoms out on. The point of the pass: **distinguish the part of each oracle that
is on-chain and verifiable from the part that is genuinely irreducible.** Both turned out to have a
real, sound on-chain enforcement half, which *narrows* (does not eliminate) the residual. **Posture:**
defensive; no exploit, no PoC. **No finding.** This is Law 6 ("name the oracle") taken one level
deeper — auditing the oracle's on-chain machinery itself.

---

## 1. Optimism — Cannon FPVM on-chain `step()` is a Merkle-authenticated MIPS emulator

In `AUDIT-OPTIMISM-FRAUD-PROOF.md` the residual was: *"the FPVM (Cannon) single-step proof — if the
FPVM mis-models the client even once, the wrong side can win the dispute game."* I opened the on-chain
adjudicator (`packages/contracts-bedrock/src/cannon/MIPS64.sol` + `libraries/MIPS64Memory.sol`).

**What `step()` does** (`MIPS64.sol:126`, `doStep`): given the agreed pre-state and a proof, it
- fetches the instruction at `thread.pc` via `ins.getInstructionDetails(pc, state.memRoot,
  insnProofOffset)` (`:251`) — the instruction is **read from memory and verified against the committed
  `memRoot`**, not supplied freely;
- executes exactly one MIPS instruction (`execMipsCoreStepLogic`, full decode in
  `MIPS64Instructions.sol`);
- applies memory reads/writes through `MIPS64Memory.readMem`/`writeMem` (`:381,396`);
- returns `postState_`, the hash of the post-state witness (`outputState()`).

**The load-bearing part — memory is genuinely authenticated** (`MIPS64Memory.sol`):
- `readMem` **reverts `InvalidMemoryProof` unless the supplied proof reconstructs `_memRoot`** (`:17-22`):
  it walks the Merkle siblings combining with `keccak256` (`:59-63`) and verifies the recomputed root
  equals `_memRoot` (`:75`).
- `writeMem` does the same authentication and **recomputes the new root** with the modified leaf
  (`:117-121`), returning `newMemRoot_`.
So neither disputant can feed a fake instruction or a fake memory value: every memory access must prove
membership in the agreed `memRoot`, and writes deterministically produce the next root.

**Residual, now narrowed.** The dispute game bisects disagreement down to one instruction and then
calls `step()`; whoever's claimed post-state matches the on-chain `step()` output wins. Since memory is
Merkle-authenticated and the step is deterministic, the adjudication is sound **provided
`MIPS64Instructions.sol` implements MIPS semantics identically to the off-chain Cannon VM (and to real
MIPS).** The residual is therefore no longer "trust the FPVM" but the much tighter **emulator-equivalence**
property: on-chain MIPS decode == off-chain MIPS decode. That is checkable by differential testing (the
Optimism team's `cannon` fuzzing/diff-tests against the Go VM) — an *equivalence* residual (6a-ish,
reducible by testing), not an opaque trust. **The memory-authentication half is verified clean.**

---

## 2. zkSync — the on-chain Verifier performs a real BN254 pairing check

In `AUDIT-ZKSYNC-VALIDITY-PROOF.md` the residual was: *"Verifier.sol — read only at the
`verifier.verify(...)` interface."* I opened it
(`l1-contracts/contracts/state-transition/verifiers/`).

**Routing** — `DualVerifier.verify(publicInputs, proof)` (`DualVerifier.sol:43`) reads `_proof[0]` as a
type selector and routes to the **FFLONK** (`type 0`) or **PLONK** (`type 1`) verifier — a transition
shim, not a bypass (empty proof → `EmptyProofLength`).

**The cryptographic heart — `L1VerifierPlonk.sol`** ends in `finalPairing()` (`:1626`):
- it aggregates the two required pairings into one (gas optimization, `:1620`), loads the proof points
  and the fixed `G2` elements (`:1657-1666`), and calls
  `staticcall(gas(), 8, 0, 0x180, 0x00, 0x20)` (`:1673`) — **precompile `0x08`, the BN254/alt_bn128
  `ecPairing`**;
- **reverts "finalPairing: precompile failure"** if the call fails (`:1675`) and **"finalPairing:
  pairing failure"** if the pairing returns 0 (`:1678`).
So the verifier genuinely evaluates the Plonk/KZG verification equation as an elliptic-curve pairing and
**rejects the proof unless the pairing holds**. Upstream it also uses the `modexp` precompile (`:384`)
and computes the Fiat-Shamir challenges from the transcript. This is a real SNARK verifier, not a
rubber stamp.

**Residual, now narrowed.** The on-chain verifier soundly checks "this proof satisfies the verification
equation for verification-key `VK`." What it *cannot* check, and what remains irreducible, is that **`VK`
(and the circuit it was derived from) correctly encodes the intended L2 state-transition relation** —
i.e. circuit soundness + the trusted setup behind the KZG commitment. So the residual narrows from
"trust the verifier" to the genuinely irreducible **circuit/VK-encodes-the-right-relation + trusted-setup**
trust. **The on-chain pairing-verification half is verified clean.**

---

## Synthesis — what "name the oracle" looks like when you open the oracle
Both rollup oracles decompose into **a verifiable on-chain half + an irreducible off-chain half**:

| Rollup | On-chain half (verified clean here) | Irreducible residual (narrowed) |
|---|---|---|
| **Optimism** | `step()` is a **Merkle-authenticated** MIPS emulator (memory can't be faked) | MIPS-emulator **equivalence** (on-chain == Cannon-Go == real MIPS) — *reducible by diff-testing* |
| **zkSync** | Verifier does a **real BN254 pairing** check, reverts on failure | **circuit/VK** encodes the right relation + **trusted setup** — *irreducible cryptographic trust* |

The shape generalizes the §9 equivalence coordinate: an oracle's *enforcement* (does the chain reject a
bad input?) is almost always auditable and was clean in both cases; its *semantics binding* (does the
accepted input mean what we think?) is where the irreducible trust lives. The two rollups differ in the
*kind* of residual: Optimism's is an **equivalence** residual (two emulators must match — testable),
zkSync's is a **cryptographic-soundness** residual (a circuit + setup must be sound — provable only
under hardness assumptions). This is exactly the **fraud-proof (1-of-N, equivalence) vs validity-proof
(0-of-N, cryptographic)** distinction from the settlement-seam spectrum (capstone §4f), now confirmed
*at the oracle's own internals*: the fraud-proof oracle's residual is checkable by replication, the
validity-proof oracle's by cryptography.

## What this pass did NOT cover (coverage honesty)
- **The full MIPS instruction decode** (`MIPS64Instructions.sol`, ~all opcodes) — I verified the
  *memory-authentication* and step *structure*, not every opcode's semantics; opcode-equivalence is the
  residual (by design, the team's diff-tests own it).
- **The Plonk transcript/challenge derivation and the FFLONK verifier** — I confirmed the final pairing
  is a real `ecPairing` that gates acceptance; I did not re-derive every Fiat-Shamir challenge or audit
  the FFLONK path line-by-line.
- **The verification-key provenance** (who sets `VK`, the upgrade authority over it) — the governance
  ceiling over the verifier, noted in the original zkSync audit, not re-opened.

## Verdict
**No finding; two named residuals substantially narrowed.** Optimism's on-chain `step()` is a genuine
Merkle-authenticated MIPS single-step (memory cannot be forged), reducing its fraud-proof residual to
on-chain/off-chain **emulator equivalence** (testable). zkSync's on-chain verifier performs a real
BN254 pairing check that rejects invalid proofs, reducing its validity-proof residual to **circuit/VK
soundness + trusted setup** (irreducible cryptographic trust). In both, the *enforcement* half is
auditable and clean; only the *semantics-binding* half remains — and the kind of remaining trust
(equivalence vs cryptographic) tracks the fraud-vs-validity distinction precisely. The honest deliverable
holds: the gate is correctly wired, and now I've also confirmed the gate's *internal machinery* is real
— the residual is specifically the off-chain meaning, not the on-chain check.
