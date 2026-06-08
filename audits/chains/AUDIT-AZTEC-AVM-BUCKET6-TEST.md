# Aztec AVM — The Bucket-6 Falsification Test

**Target:** `AztecProtocol/aztec-packages` @ `32207bf`, the AVM (`vm2`).
**The question (a falsification, not an audit):** *does proving the public VM
**eliminate** bucket-6 (cross-layer settlement seam) debt, or merely **move**
it?* **No exploit search.** Every finding is forced into one of three outcomes:
**(1) proven in-circuit · (2) trusted by implementation · (3) trusted by
architecture.**

Setup: in Pass 2, the private kernel/rollup **deferred** two invariants to the
AVM (X1: revertible note-hash uniquification; X3: public-data-write correctness),
graded "trusted by architecture." Aztec *proves* its public VM. Aleo
*re-executes* its public layer under consensus; Mina *recursively proves the
whole state*. All three landed in bucket 6. The AVM is the cleanest place to ask
whether proving closes the seam.

---

## Result in one line

**Proving the public VM closes the *inter-layer deferral* (X1/X3 become proven
in-circuit) but does not eliminate bucket 6 — it converts "trusted by
architecture" into "trusted by implementation."** The agreement requirement moves
from *two protocol layers agreeing* to *the circuit's relations + spec table
completely capturing the semantics, and three reference implementations agreeing*.

---

## Outcome 1 — Proven in-circuit (what proving closed)

The AVM's PIL relations (`barretenberg/cpp/pil/vm2/`) constrain the invariants the
kernel deferred, and the rollup **recursively verifies the AVM proof and binds its
public inputs to the private side**:

| Invariant (Pass-2 status) | Now proven by | 
|---|---|
| **X1 note-hash uniquification** (was "trusted by architecture") | `opcodes/emit_notehash.pil` + `trees/note_hash_tree_check.pil` — siloing + `nonce=H(first_nullifier, note_index)` + unique-hash + tree insert; written to public inputs gated by `(1-discard)` |
| **X3 public-data writes** (was "trusted by architecture") | `opcodes/sstore.pil` + `trees/public_data_check.pil` + `public_data_squash.pil` — indexed-tree low-leaf membership, slot/value ordering, last-write squashing |
| nullifier uniqueness (public) | `opcodes/emit_nullifier.pil` + `trees/indexed_tree_check.pil` — low-leaf non-membership; duplicate cannot insert |
| revert / side-effect discard | `execution/discard.pil` — discard propagation; every side-effect write gated by `(1-discard)` |
| gas metering | `execution/gas.pil` — per-opcode base+dynamic, out-of-gas via `gt` |
| bytecode→contract-class binding | `bytecode/bc_retrieval.pil`, `class_id_derivation.pil`, `bc_hashing.pil` — deployment nullifier + class-id derivation + bytecode-commitment hash |
| instruction decoding | `bytecode/instr_fetching.pil`, `bc_decomposition.pil` |
| **private ↔ AVM interface** | `rollup-lib/.../public_tx_base_inputs_validator.nr:80` recursively verifies the AVM proof; `:105-224` `assert_eq`s prover_id, gas/fees, fee_payer, call requests, and the note-hash/nullifier/L2→L1 accumulated-data arrays (revertible + non-revertible) between private tail and AVM |

→ The Pass-2 *inter-layer* bucket-6 deferral is genuinely **closed**: the rollup
no longer trusts an unverified public layer; it verifies a proof and binds the
interface in-circuit.

---

## Outcome 2 — Trusted by implementation (where bucket 6 moved)

The AVM proof attests **only what its relations + spec table encode**. Two
residual seams, both *intra-circuit / cross-implementation*:

- **2a — Relation & opcode-spec completeness.** The proof guarantees the trace is
  internally consistent and satisfies the PIL relations; it does **not** prove
  those relations + the precomputed instruction-spec table
  (`precomputed.pil`/`constants_gen.pil`) *completely and correctly capture the
  intended AVM semantics*. The agent's survey notes the opcode spec table is
  "statically generated and trusted… the circuit does not prove [it matches] any
  canonical specification," and that per-opcode *execution correctness* is
  constrained on side-effects/registers while the **simulation supplies the
  operands/memory values** whose consistency (not whose "intended-ness") is
  constrained. A missing or wrong relation = a *sound proof of a wrong
  execution*. **Trusted by implementation.**
- **2b — Tri-implementation equivalence.** The same AVM semantics exist in three
  encodings that must agree: the C++ **simulation** (fast mode, used by block
  building), the C++ **constraining** relations (the prover), and the **TS
  simulator** (`yarn-project/simulator/src/public/avm`). The public inputs alone
  are *built* in `simulation/lib/public_inputs_builder.hpp` and *constrained* in
  `tracegen/public_inputs_trace.hpp` — two constructions that must match.
  Divergence ⇒ a result applied/built that can't be proven, or proven differently
  than intended. **Trusted by implementation.**

**2b is structurally identical to Mina's native↔circuit seam and Aleo's
finalize-execution↔intent seam.** It is the same bucket-6 shape, regardless of
whether the public layer is *proved* (Aztec), *re-executed* (Aleo), or
*recursively proved* (Mina).

---

## Outcome 3 — Trusted by architecture (the irreducible remainder)

- **Recursive-verifier / proof-system soundness** — the rollup's
  `verify_proof_with_columns` (Honk recursive verifier) is trusted as a primitive
  (same class as Mina's Pickles, Aleo's Varuna).
- **Revertibility phase classification** — *which* effects are revertible
  (setup/app/teardown) is decided by the public kernel / tx context; the AVM
  receives the `discard` phase as **input**, not derived. A small residual
  cross-layer input.

---

## Verdict & the model refinement

**Proving the public VM does not eliminate bucket 6 — it relocates and transforms
it.** This forces a split of bucket 6 into two sub-forms:

- **Bucket 6a — inter-layer deferral** ("layer A trusts layer B to enforce X").
  **Reducible by proving:** Aztec converted X1/X3 from 6a → *proven in-circuit* by
  giving the public layer a proof and recursively verifying it.
- **Bucket 6b — interpretation / equivalence** ("multiple encodings of the same
  semantics must agree"). **Not reducible by proving** — because proving *creates a
  new encoding* (the circuit/relations) that must now agree with (i) the intended
  spec and (ii) the executor(s) that build blocks. Proving **converts 6a into
  6b.**

That conversion is the whole answer:

> You cannot prove your way out of bucket 6. A proof is *of a circuit*, and the
> circuit is *one encoding* of the intended semantics. Something outside the proof
> must vouch that the encoding matches intent (relation/spec completeness) and
> that the block-builder's executor matches the encoding (implementation
> equivalence). The more you prove, the more 6a you retire — and the more 6b you
> create.

**So bucket 6 is an intrinsic property of complex zk systems, not a consequence
of under-proving.** The three architectures differ only in *which* form dominates:
- **Aleo** — public layer re-executed under consensus: bucket 6 lives as
  *consensus-replication + native/circuit intent agreement*.
- **Mina** — public layer recursively proved: bucket 6 lives as *native↔circuit
  equivalence (6b)* + the recursion handoff.
- **Aztec** — public layer proved as a VM: bucket 6a (deferral) is **retired**,
  replaced by bucket 6b (relation/spec completeness + sim↔constrain↔TS
  equivalence).

This is the sharper, arguably more important finding the falsification was set up
to produce: **proving relocates agreement debt; it does not abolish it.** Bucket 6
is load-bearing precisely because it is the one bucket that *survives* maximal
proving.

---

## Three-outcome summary

| Area | Outcome |
|---|---|
| public-input binding (private ↔ AVM) | **proven in-circuit** (`public_tx_base_inputs_validator.nr:80,105-224`) |
| deferred invariants X1 / X3 | **proven in-circuit** (`emit_notehash.pil`, `sstore.pil`, …) |
| nullifier semantics (public) | **proven in-circuit** (`indexed_tree_check.pil`) |
| rollup settlement semantics (AVM→rollup) | **proven in-circuit** (recursive verify + array `assert_eq`) |
| revert behavior | **proven in-circuit** (`discard.pil`) — *phase classification* input: trusted by architecture |
| state interpretation / VM↔circuit equivalence | **trusted by implementation** (sim ↔ constrain ↔ TS simulator) |
| relation & opcode-spec completeness | **trusted by implementation** (`precomputed.pil`) |
| cross-proof / recursive-verifier soundness | **trusted by architecture** (Honk recursive verifier) |

## Disclosure posture
Defensive, structural reading of public code at a named commit; no exploit, no
PoC. The "trusted by implementation" items are the documented, expected trust
base of a proven VM (relation completeness + reference-implementation agreement),
not demonstrated breaks.

## Method
One scoped read-only survey of the `pil/vm2` proven-relation surface, plus direct
reading of `public_tx_base_inputs_validator.nr` (the rollup↔AVM binding) and the
`vm2` architecture (`CLAUDE.md`: simulation → tracegen → constraining).
