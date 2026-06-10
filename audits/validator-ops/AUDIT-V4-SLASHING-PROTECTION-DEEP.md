# V4 (deep) — slashing protection: the surround SQL, raise-only interchange import, GVR binding, doppelganger, and the advisory lock

**Scope.** A deep, individualized expansion of sweep item **V4** (`AUDIT-VALIDATOR-OPS-SWEEP.md` §V4), going past
the record-before-sign ordering + the basic EIP-3076 surround checks the rapid pass covered into the **full
implementation**: the verbatim attestation/block surround SQL + watermarks, the raise-only interchange import +
monotonic rollback, the genesis-validators-root (GVR) binding, Lighthouse's doppelganger detection, and
web3signer's per-validator advisory lock. Targets: `sigp/lighthouse` @ `176cce5`
(`validator_client/slashing_protection/`, `doppelganger_service/`), `Consensys/web3signer` @ `4c24e4d`
(`slashing-protection/`). Read-only, public-source, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No finding;** the single-DB-authority requirement, the GVR-not-persisted difference,
and doppelganger's best-effort nature are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established the two pillars (record-before-sign ordering; raise-only EIP-3076). The deeper reading
shows the **exact queries and the import safety**: the surround pair is **literal SQL** with strict watermark
operators (`<` source, `<=` target); interchange import is **collapse-to-single-high-water-row + monotonic
rollback + all-or-nothing batch**; the **GVR is bound at the import boundary but *not persisted* in Lighthouse's
DB** (cross-chain safety rests on the BLS signing domain) whereas **web3signer persists+pins it (TOFU)**;
doppelganger is a **non-cryptographic 2-epoch liveness heuristic** that escalates to `u64::MAX` + shutdown on a
violator; and web3signer's concurrency rests on a **per-validator-per-message-type `pg_advisory_xact_lock`**.

---

## 1. The attestation surround SQL — the canonical EIP-3076 pair + strict watermarks.

`slashing_database.rs check_attestation (:389-513)`, verbatim queries:
- **Double-vote** (same target, different signing root → `DoubleVote`, else `SameData`):
  `SELECT ... FROM signed_attestations WHERE validator_id=?1 AND target_epoch=?2` (`:409-419`).
- **Surrounding** (a prior att surrounds the new → `PrevSurroundsNew`):
  `... WHERE source_epoch < ?2 AND target_epoch > ?3 ORDER BY target_epoch DESC LIMIT 1` (`:436-448`).
- **Surrounded** (new surrounds a prior → `NewSurroundsPrev`):
  `... WHERE source_epoch > ?2 AND target_epoch < ?3 ...` (`:458-470`).
- **Watermarks**: `MIN(source_epoch)`/`MIN(target_epoch)` reject `source < min_source` and **`target <= min_target`**
  (`:481-509`) — note **target uses `<=` (strict)**, source uses `<`; and `source > target` is rejected up front.

**Characterization:** the canonical surround pair plus a watermark floor. The `MIN()` watermarks are what let
**pruned/imported history (collapsed to a single synthetic row) still bound future signing** — an attacker can't
replay an old low-epoch attestation after pruning. Insert happens only inside the same exclusive transaction.

---

## 2. The block-proposal SQL — same-slot-different-root + min-slot watermark.

`check_block_proposal (:340-386)`: `SELECT slot, signing_root FROM signed_blocks WHERE validator_id=?1 AND
slot=?2` → matching root = `SameData`, different = `DoubleBlockProposal`; `MIN(slot)` watermark rejects
`slot <= min_slot` (`SlotViolatesLowerBound`); `signed_blocks` has `UNIQUE(validator_id, slot)`.
**Characterization:** the block side of EIP-3076 — one signed block per slot, watermark-floored — with a DB
uniqueness constraint as a second line of defense.

---

## 3. Interchange import — raise-only, collapse-to-high-water, monotonic rollback, all-or-nothing.

`import_interchange_record (:853-923)`: each record is **collapsed to a single synthetic row with a null signing
root at the raised max** (after clearing existing rows): `new_max_slot = max_or(prev.max_block_slot,
max_block.slot)`; `source/target = max_or(prev, imported)`. A **monotonic rollback** (`:909-922`) re-reads the
summary and verifies `check_*_consistency` — which require **`monotonic(new, prev)` (new ≥ prev) AND `min == max`**
(post-collapse) — returning `ConsistencyError` on failure. The whole import is **one transaction; any single
record failure sets `commit = false` → `AtomicBatchAborted`** and the txn is dropped uncommitted.

**Characterization:** import is **strictly "raise the floor, never lower it"** — Lighthouse never trusts the
imported file to *reduce* a watermark; it max-merges against existing DB state, collapses to a single high-water
row, and **aborts the entire batch if the result isn't monotonically non-decreasing**. This is the defensive
core that makes importing an *attacker-supplied* interchange safe.

---

## 4. GVR binding — and the Lighthouse-vs-web3signer difference.

Lighthouse checks the GVR **only at import/export** (`:817-822`, mismatch → `GenesisValidatorsMismatch`); it is
**not persisted in the slashing DB** (no `genesis_validators_root` column — the DB is chain-agnostic, and
running-signer cross-chain safety rests on the **BLS signing domain** producing different roots). **Web3signer
differs**: `GenesisValidatorRootValidator.checkGenesisValidatorsRootAndInsertIfEmpty` **persists the GVR in
`metadata` on first use and pins it (TOFU)** — any later block/attestation/import with a different GVR is
rejected **at the DB layer** (`MetadataDao`, `InterchangeV5Importer:94-101`).

**Characterization:** both bind the slashing record to a chain, but **web3signer is stricter** — a TOFU-pinned
GVR row means even a *signing-time* cross-chain mismatch is caught, whereas Lighthouse relies on the signing
domain at sign time and the GVR check only at the interchange boundary. A precise, real difference worth naming.

---

## 5. Doppelganger detection — a non-cryptographic 2-epoch liveness heuristic.

`doppelganger_service/lib.rs`: default `remaining_epochs = 1` (yielding the ~2-epoch real wait via the
"satisfied at the last slot of e+1" rule, `:510-513`); `requires_further_checks()` → `SigningDisabled`. Validators
**registered at/before genesis get `remaining_epochs = 0` (no protection at genesis — explicit trade-off)**.
Liveness uses two BN calls (current + previous epoch); **BN failures return empty vecs to avoid stalling**
(`:137-146`). **On any `is_live` violator: every validator's `remaining_epochs` is set to `u64::MAX`** (permanent
signing halt even if shutdown fails) then `shutdown_func()` is invoked (`:560-592`).

**Characterization:** doppelganger is a **best-effort, non-cryptographic** safeguard — it watches the network for
the validator's own attestations for ~2 epochs before enabling signing, to catch a duplicate instance of the same
key. It is **disabled at genesis**, **tolerant of BN liveness-query failures** (slows progress, doesn't fail
closed), and **independent of (not a replacement for) the DB-level slashing protection** — it reduces but does
not eliminate the duplicate-instance window.

---

## 6. Web3signer concurrency — the per-validator advisory lock.

`DbLocker.lockForValidator` runs `SELECT pg_advisory_xact_lock(?, ?)` keyed by `LockType` (BLOCK=0/ATTESTATION=1)
and validator id — a **transaction-scoped Postgres lock, auto-released at commit/rollback**. `maySignAttestation`/
`maySignBlock` (a) check the GVR **before** the txn, (b) open `jdbi.inTransaction(READ_COMMITTED)` and
**immediately take the advisory lock** so check-and-insert is serialized per validator, (c) run the watermark +
surround checks, then `persist()` only if not already existing. The surround SQL (`SignedAttestationsDao`) is
**identical to Lighthouse's predicates**.

**Characterization:** because web3signer is a **networked multi-client signer** (vs Lighthouse's single-process
SQLite `locking_mode=EXCLUSIVE` + pool size 1), it serializes concurrent check-and-insert via a
**per-validator-per-message-type advisory lock** taken as the first statement inside the txn. Correctness assumes
all signing paths consistently take that lock before checking — which the two `maySign*` methods do.

---

## 7. Verdict & residual

the double-sign mode is closed by **ordering** (record commits before signature, sweep) **plus** the deep
machinery: literal surround SQL with strict watermarks, raise-only collapse-to-high-water interchange import with
monotonic rollback and all-or-nothing batching, GVR binding (TOFU-pinned in web3signer), per-validator advisory
locking, and the doppelganger 2-epoch backstop. **No finding.** **Residuals**, named: (a) **single-DB-authority**
is the load-bearing operational assumption — Lighthouse forces it via `EXCLUSIVE` + `POOL_SIZE=1` and explicitly
marks its `preliminary_check_*` reads "DO NOT USE TO DECIDE IF SAFE TO SIGN"; running two VCs against DB copies,
or sharing a key without shared HRS/slashing state, **defeats protection** (the doppelganger/duplicate-instance
risk the code can't enforce); (b) **Lighthouse does not persist the GVR** (cross-chain rejection only at the
interchange boundary + the signing domain) — web3signer is stricter (TOFU-pinned GVR row); (c) **doppelganger is
best-effort and non-cryptographic** (disabled at genesis, BN-failure-tolerant) — a window-reducer, not a
guarantee; (d) **import/prune collapses detail to a watermark** (correct for raise-only safety, but imported
detail is intentionally discarded). The catastrophic mode is closed by ordering + raise-only monotonic state;
the residual is operational single-authority + the GVR-binding-strength difference.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-VALIDATOR-OPS-SWEEP.md` §V4.*
