# State-sync sweep — verify-before-persist, audited across clients

The sync seam under the threat model in [`README.md`](README.md): a malicious peer serving snapshot/checkpoint/
range data tries to drive an honest node to **diverge (D)**, **accept invalid state (A)**, **corrupt storage
(C)**, or **stall (S)**. The two questions: *(Q1) what is the root of trust for synced state, and (Q2) is
network-supplied data verified before it can influence persistent local state?* This is the
proven-vs-attested / recompute-vs-trust-the-summary axis (`../bridges/AUDIT-BRIDGES-SWEEP.md` coda) at the node
bootstrap layer.

---

## S1. go-ethereum snap sync — the proven end: every untrusted byte recomputed against the trusted root before it persists
**Target:** `ethereum/go-ethereum`, `eth/protocols/snap/sync.go` + `trie/proof.go`. Snap sync downloads the
state as **account/storage ranges** from untrusted peers and reconstructs the trie. It is the canonical
"network data influencing local state" path, and it is built exactly the way the corpus says it should be:
**recompute, don't trust the summary.** **Result: failure modes D/A/C are structurally forced *safe*; only S
(stall) remains, and it is mitigated by peer rescheduling.**

**(Q1) Root of trust:** `s.root` — the **state root from the (consensus-verified) block header**. The synced
state is never trusted on a peer's word; it is verified against the chain's own canonical root. (As the chain
advances during sync the **pivot** root moves, and the **healing** phase re-downloads missing trie nodes and
re-verifies them against the current root.)

**(Q2) Verify-before-persist: yes, and it gates everything.** In `OnAccounts` (`sync.go:2524`) the peer's
`hashes/accounts/proof` are checked by **`trie.VerifyRangeProof(root, req.origin, keys, accounts, proof)`
(`:2593`) *before* the response is ever delivered to the processing pipeline**. On failure →
**`scheduleRevertAccountRequest(req)` + return err** (`:2596-2598`) — the request is reverted and **rescheduled
to another peer**; nothing touches the database. `OnStorage` (`:2735`) is identical (`VerifyRangeProof` at
`:2845/:2856`). Untrusted bytes reach disk **only after** a proof against the trusted root succeeds.

**Why the range proof closes the omission/splice/reorder attacks (`trie/proof.go VerifyRangeProof :478`):** a
peer cannot cheat the *set* of keys in a range, because the proof enforces, before persistence —
- **monotonically increasing keys** (`keys[i] < keys[i+1]`, `:488`) → no reorder, no duplicates;
- **no path-prefix expansion** (`!HasPrefix(keys[i+1], keys[i])`, `:491`) → no structural trie attack;
- **no deletions** (`len(values[i]) != 0`, `:495`);
- **left boundary** (`firstKey <= keys[0]`, `:525`) → no keys spliced in before the requested origin;
- **reconstructed root must equal `rootHash`** — both the no-edge-proof case (rebuild via `StackTrie`, hash
  must match, `:506`) and the two-edge-proof case (`proofToPath` ×2 then root compare); and
- **`hasRightElement`** (the `cont` return, `:518/:542`) → the boundary proof reveals whether more elements
  exist to the right, so a peer **cannot falsely claim a range is empty or omit a trailing leaf** — the empty-
  range case must *prove* `!hasRightElement` (`:513-521`).

**Failure-mode analysis:**
- **D (divergence): structurally impossible.** The state root is the **unique** Merkle preimage commitment;
  any set of ranges that verifies against it reconstructs the *identical* state on every honest node. There is
  no iteration-order or nondeterminism freedom — the root pins the state exactly. (This is the MemeCore lesson
  inverted: here the substrate *forces* determinism.)
- **A (invalid acceptance): forced safe.** Nothing is accepted that doesn't verify against the trusted root; a
  forged balance/slot fails `VerifyRangeProof` → revert.
- **C (corruption): forced safe.** Verify happens *before* the write; a bad/partial/tampered range is rejected
  before it can be committed, so the DB is never left holding unverified bytes.
- **S (stall): the only residual.** A malicious peer can *refuse* or feed bad proofs — but each failure
  **reschedules to another peer** (`scheduleRevert*`), and bad peers are dropped. Liveness rests on ≥1 honest
  serving peer (a 1-of-N honest-availability assumption), not on safety.

**Verdict: the proven end of the sync taxonomy.** Snap sync is, in effect, a **light client for your own
state history** — it recomputes every peer-supplied byte against the consensus root before persistence, with
a range proof complete enough to defeat omission/splice/reorder, and a clean revert-and-reschedule on any
failure. **No finding.** **Residual:** the header's state root (i.e. consensus itself — the irreducible
anchor) and **≥1 honest peer for liveness**. This is what "verify-before-persist" looks like done right, and
it is the bar the rest of this sweep is measured against.

---

## S2. Solana (Agave) + Bitcoin Core (assumeutxo) — snapshot loading: recompute the hash, isolate the failure
**Targets:** `anza-xyz/agave` (`snapshots/src/hardened_unpack.rs`, `runtime/src/{bank,snapshot_bank_utils}.rs`,
`validator/src/bootstrap.rs`), `bitcoin/bitcoin` (`src/validation.cpp`, `src/kernel/chainparams.cpp`). A clean
**contrast pair**: same verify-before-trust discipline, two different trust anchors. **No finding in either.**

- **Agave — anchor = gossip + full recompute.** The archive's filename hash must match a hash advertised by
  operator-configured `--known-validators` in gossip (`bootstrap.rs:831` drops peer hashes that don't match a
  known one), *and* after loading, the accounts **lt-hash is recomputed from the actually-loaded accounts**
  (`bank.rs:5306 verify_accounts`) and checked, folded into the bank hash, and asserted equal to the expected
  slot hash (`snapshot_bank_utils.rs:469`). The hash is **recomputed, not read from the manifest** — a tampered
  archive fails. The **untar is hardened** (verified myself): non-`Normal`/`CurDir` path components → `"invalid
  path found"` (`hardened_unpack.rs:132`), `Prefix/RootDir/CurDir → continue`, only `Normal` pushed (`:253/261`)
  — zip-slip closed; decompression bounded (4 TiB actual / 64 TiB apparent / 5M entries via
  `checked_total_size_sum`). Failure → unpack to a `TempDir`, mismatch → `panic` before adoption: the live
  accounts DB is never touched (**C** isolated).
- **Bitcoin assumeutxo — anchor = hardcoded-in-binary.** `m_assumeutxo_data` (`chainparams.cpp:190`) bakes a
  per-height `{hash_serialized, tx_count}` into the compiled binary. After streaming all coins, the UTXO hash is
  **recomputed** (`ComputeUTXOStats`) and checked: **`if (AssumeutxoHash{stats.hashSerialized} !=
  au_data.hash_serialized) return Error("Bad snapshot content hash...")`** (`validation.cpp:5906`, verified
  myself). Coins load into a **separate snapshot chainstate** on a distinct datadir, so a mismatch →
  `cleanup_bad_snapshot` deletes the partial leveldb and the **active chainstate is untouched** (**C**
  isolated). Deserialization is bounds-checked (coin count, height, `MoneyRange`, anti-wraparound, truncation).
  And the strongest defense-in-depth in the whole sweep: a **background chainstate re-validates from genesis**
  (`MaybeValidateSnapshot`) and, on mismatch, marks the snapshot `INVALID` and reverts — so even a *wrong
  hardcoded hash* is eventually caught by full replay.

**Failure modes:** both force **D/A/C safe** (recompute-vs-anchor before adoption; failure isolated to a
temp/separate store). **S** bounded (interrupt checks, size caps, retry). The anchors differ in *what you
trust*: Agave trusts the operator's known-validator set (a social quorum), Bitcoin trusts the binary it's
running (the developers + the build) with genesis-replay as the cryptographic backstop. **Proven end.**

## S3. Beacon checkpoint sync (Lighthouse, Prysm) — weak subjectivity, and a real verification-strength gap
**Targets:** `sigp/lighthouse` (`beacon_node/beacon_chain/src/builder.rs`), `OffchainLabs/prysm`
(`beacon-chain/sync/checkpoint/{api,file}.go`, `db/kv/wss.go`). Checkpoint sync bootstraps a node from a recent
finalized state fetched from an **operator-chosen URL/file** — *weak subjectivity*: the source is, by design,
the trust anchor. The audit question is whether the client at least enforces internal consistency
(`hash_tree_root(state) ≡ block.state_root`) so a *tampered/inconsistent* checkpoint is caught.

- **Lighthouse — full bidirectional binding (robust).** `weak_subjectivity_state` (`builder.rs:424`) computes
  `hash_tree_root(state)`, injects it into the block's header and requires the reconstructed
  **`state.get_latest_block_root(state_root) == weak_subj_block.canonical_root()`** (verified myself, `:332`+):
  the block commits to the state root *and* the state commits to the block header → a genuine **two-way**
  binding, enforced **before any DB write**. A forged or inconsistent checkpoint is rejected.
- **Prysm — weaker, and the file path skips it entirely (INTERESTING, low severity).** The API path checks
  only the **body root**: `sbr := state.LatestBlockHeader().BodyRoot; if sbr != bodyRoot { return
  errCheckpointBlockMismatch }` (`api.go:140-142`, verified) — it computes `sr := state.HashTreeRoot()`
  (`:144`) but **never asserts `block.StateRoot == sr`** (the block→state direction Lighthouse covers). And the
  **file initializer** (`file.go:62`) calls `SaveOrigin(serState, serBlock)` with **no binding check at all**
  (verified). Neither client enforces an automatic **weak-subjectivity staleness window** at bootstrap.

**The honest framing (and why this is *not* a stop-and-notify exploit):** checkpoint sync *trusts the source by
design* — a fully-consistent malicious checkpoint (forged state + matching forged block) is accepted by **both
clients**, because that is the weak-subjectivity trust model. The gap is strictly **defense-in-depth**:
Lighthouse would *additionally* reject an **inconsistent** checkpoint (state that doesn't match its block) that
Prysm's file path would persist as the finalized origin. Exploiting it requires already controlling the
operator's checkpoint source (the existing trust anchor), so it is **operator-trust-bounded, not a remote
unauthenticated defect** — a verification-strength hardening gap, publicly-observable behavior, documented here
defensively. **Recommended hardening (the constructive mirror):** add the bidirectional
`block.StateRoot == hash_tree_root(state)` check to Prysm's file/API bootstrap (matching Lighthouse), and
enforce the WS-period window at init in both. Failure modes: **A/D** are bounded by the operator's source choice
(not remotely reachable); the residual is *verification strength relative to the same trust anchor*.

## S4. Cosmos (CometBFT + SDK) + Substrate warp — chunked sync, cryptographically rooted
**Targets:** `cometbft/cometbft` (`statesync/syncer.go`), `cosmos/cosmos-sdk` (`store/snapshots/manager.go`),
`paritytech/polkadot-sdk` (`.../strategy/state_sync.rs`). The **chunked-snapshot** model: state split into
chunks served by untrusted peers. **No finding; one hardening note.**

- **CometBFT + Cosmos SDK (sound, two-layer).** Trust anchor is a **light client** (`TrustOptions`, ≥2
  witnesses); the snapshot's apphash is obtained by light-verifying block `height+1` and stored as
  `trustedAppHash`. The **decisive gate** is *after* all chunks apply: **`if !bytes.Equal(snapshot.trustedAppHash,
  resp.LastBlockAppHash) return errVerifyFailed`** (`syncer.go:504`, verified myself). The SDK adds a **per-chunk
  `sha256` check before write** — `sha256(chunk) == Metadata.ChunkHashes[i]` else `ErrChunkHashMismatch`
  (`manager.go:430`), with a strict sequential index (reorder/dup/skip structurally impossible). *Subtlety:* the
  `ChunkHashes` come from the **untrusted** offered snapshot, so the per-chunk hash only proves "matches what the
  offerer committed to" — the binding to *real* state is the final apphash gate. Defense-in-depth depends on
  `syncer.go:504`, and it's present. **Hardening note:** the zlib stream caps each item at 64 MB
  (`snapshotMaxItemSize`) but has **no cap on total decompressed size** — a resource/**S**-stall consideration on
  untrusted chunks, not accept-invalid (the apphash gate still rejects).
- **Substrate warp (the strongest design in the sweep).** Trust anchor is a **GRANDPA finality proof** chaining
  from genesis → the target header (carrying the authoritative `state_root`). Then **every state chunk is
  range-proof-verified against that root *before apply***: `verify_range_proof(self.metadata.target_root(),
  proof, last_key)` (`state_sync.rs:276`, verified myself); failure → `BadResponse` → drop the peer. Nothing
  enters local state until its proof verifies against the finalized root — the geth-snap property (S1) in its
  cleanest form. (Caveat: a `skip_proof` light-sync mode bypasses verification, but it is **operator-gated and
  off the warp path** — warp always verifies.)

**Failure modes:** all three force **D/A/C safe** (final apphash gate / per-chunk range proof vs a
cryptographically-rooted value); **S** mitigated by chunk timeouts + peer rejection. The only residual is the
Cosmos total-decompress-size hardening note. **Proven end.**

## S5. Reth + Erigon — re-execution vs. snapshot-registry trust (the one anchor outlier)
**Targets:** `paradigmxyz/reth` (`crates/stages/stages/src/stages/merkle.rs`, `pipeline/mod.rs`),
`erigontech/erigon` (`execution/stagedsync/exec3.go`, `db/snapcfg`, `db/downloader/`). Two Go/Rust execution
clients, two *different* trust models for getting state. **Reth clean; Erigon's snapshot-import path is the
sweep's one genuine trust-anchor outlier (not a live exploit).**

- **Reth — re-execution, commit gated by the recomputed root.** Reth doesn't import a state snapshot; it
  **re-executes blocks** and Merkle-izes. `validate_state_root` recomputes the trie root from DB tables and
  returns `ConsensusError::BodyStateRootDiff` on mismatch vs `header.state_root()` (`merkle.rs:437-453`). The
  ordering is "write-then-verify" *but safe*: trie writes go to an **uncommitted** RW provider, and the pipeline
  calls `provider_rw.commit()` **only on the `Ok` branch** — on error it `drop`s the provider, discarding every
  write (`pipeline/mod.rs:497-545`). So nothing invalid persists; unwind recomputes-then-writes. **D/A/C
  blocked; S bounded** by download caps + unwind depth.
- **Erigon — block-execution path sound; snapshot path trusts a registry.** The post-pivot execution path
  recomputes and checks the commitment root (`if !bytes.Equal(computedRootHash, header.Root[:])`,
  `exec3.go:779`) with a documented **write-then-verify-then-unwind** model (state flushed, then corrected by a
  bounded binary-search unwind — consistent within the unwind horizon; `ErrTooDeepUnwind` = controlled halt, not
  corruption). **But the snapshotted state itself (accounts/storage/commitment domains) is *trusted as
  imported*** — integrity rests on the **preverified `filename → torrent-infohash` registry** (`db/snapcfg`),
  checked by the BitTorrent piece-hash layer, with **no on-node state-root re-derivation against a header on
  import** (`afterSnapshotDownload` only re-adds torrents + checks completeness). The registry is the trust
  anchor — analogous to a *trusted-checkpoint* / *committee* bridge rather than a recompute.
  - **Trust-pivot worth flagging (opt-in, mitigated, not a live exploit):** with `--snap.p2p-manifest`, the
    `filename→infohash` manifest can be sourced from **peers** (highest *self-reported* `KnownBlocks`, no
    signature/quorum). **Mitigations that defang it on standard chains:** `MergeChainToml` only **adds** new
    filenames and **never overrides** an embedded/anchored hash; the path is flag-gated; it falls back to the
    centralized registry. No way found to override an anchored entry, so residual exposure is limited to
    filenames absent from the shipped set (custom/empty-registry networks). Flagged as **the weakest trust edge
    in the sweep**, not a splittable bug.

**Failure modes:** Reth — D/A/C blocked by the commit-gated recompute. Erigon — execution path D/A/C safe via
recompute+unwind; **the snapshot-import path's safety is the *registry anchor*, not a node-local proof** (so a
wrong anchor, or an unanchored peer infohash on a custom-network P2P-manifest, is the A/D edge). The
constructive mirror: a snapshot bridge is strongest when the node **re-derives** the state root from the
imported data and checks it against a consensus-anchored header (geth/reth/substrate), rather than trusting
that the bytes behind a hash are the right *state*.

---

## Synthesis — state sync is the *proven* end, and it fails safe (the substrate again)
Across **10 sync implementations in 4 ecosystems** (EVM exec: geth/reth/erigon; beacon: lighthouse/prysm;
Cosmos: cometbft/sdk; Substrate; Solana; Bitcoin) — **every well-engineered client recomputes or proof-verifies
network-supplied data against a cryptographic root before it can become canonical, and every failure path fails
*safe*** (revert-and-reschedule, reject, isolate-to-temp, or unwind). This is the corpus's **fail-safe-substrate
law** (`../methodology/AUDIT-CAPSTONE.md §5b`) at the sync layer: the dangerous modes **D (divergence)** and
**A (accept-invalid)** and **C (corrupt-storage)** are *forced* off the table by verify-against-root +
gate-the-commit; what remains is **S (stall)** (mitigated everywhere by peer rescheduling/timeouts) and
**resource-exhaustion hardening** (the Cosmos total-decompress cap, Lighthouse's uncapped HTTP body). It is the
same result the chain audits found: *real defects in well-built clients fail safe because the substrate forces
it.*

And it is the **proven-vs-attested axis** (`../bridges/AUDIT-BRIDGES-SWEEP.md`) one more time — **a snapshot is
a summary of your own chain's state, and the taxonomy ranks how much each client recomputes it:**
- **Proven (recompute vs. a consensus-anchored root):** geth snap, reth re-execution, substrate warp, cosmos
  apphash gate, solana lt-hash, bitcoin UTXO-hash+genesis-replay, lighthouse bidirectional binding — *the
  destination eats its own tail.*
- **Attested (trust a curated/external anchor without a node-local state recompute):** **Erigon's snapshot
  import** (a shipped infohash registry) and, in verification *strength*, **Prysm's checkpoint binding** (body
  root only / none on the file path). These are the sync analogs of a committee bridge — sound under their
  anchor, weaker if the anchor is wrong, and the two places this sweep would point a hardening effort.

Two ordering patterns, both safe when done right: **verify-before-write** (geth/substrate/cosmos/solana/bitcoin)
and **write-then-verify-then-discard/unwind** (reth's commit-gating, erigon's bounded unwind) — the latter is
only as safe as the rollback is correct and bounded, which is why it carries the `ErrTooDeepUnwind` controlled
halt rather than risking a half-written DB. **No exploitable finding; two anchor/strength outliers named, with
the constructive fix for each.** The snake checks its tail at the sync seam too.

---

## S6. go-ethereum RLP + devp2p decoder — bound-before-allocate, and canonical-form as a divergence defense
**Target:** `ethereum/go-ethereum`, `p2p/rlpx/rlpx.go` + `rlp/decode.go`. The deserialization seam from the
threat model — *untrusted network bytes decoded before any verification* — and the classic resource-exhaustion
surface (decompression bombs, length-prefix allocation attacks). The adapted question: **is decoding bounded
before allocation, and is it canonical (deterministic)?** **Result: both — yes; failure modes S (resource) and
D (divergence) are defeated at the decoder, verified myself.**

**Two-layer defense, correctly ordered:**
- **devp2p frame (`rlpx.go`):** every message frame is capped at **`maxUint24` = 16 MB** (`:215, :236`). The
  **snappy decompression bomb is defeated *before* decoding**: `snappy.DecodedLen(data)` reads the *declared*
  decompressed size from the frame header **without decompressing**, and `if actualSize > maxUint24 → return
  errPlainMessageTooLarge` (`:149-155`) — only *then* is the output buffer grown and `snappy.Decode` called
  (`:156-157`). A tiny compressed payload claiming gigabytes of output is rejected before a single large byte
  is allocated. (Plus `baseProtocolMaxMsgSize` per-protocol caps in `transport.go`.)
- **RLP decoder (`decode.go`):** the stream is created with `NewStream(r, inputLimit)` so `s.remaining` is
  bounded by the actual message size, and **`Kind()` validates every length prefix against the remaining input
  *before* the reader allocates**: `else if s.limited && s.size > s.remaining → ErrValueTooLarge` (`:1031`,
  *"value size exceeds available input length"*) — and for list elements `inList && s.size > listLimit →
  ErrElemTooLarge` (`:1029`). So a string/list header claiming a 4 GB length inside a 100-byte message is
  rejected **before** the `make([]byte, size)` path (`:876`) ever runs. No attacker-controlled allocation.

**The subtle one — canonical form is a *divergence* defense.** `readKind` rejects non-minimal length
encodings (`size < 56 → ErrCanonSize`, `:1073/:1085`), the integer paths reject leading zeros / non-minimal
single-byte forms (`ErrCanonInt`, `ErrCanonSize`, `:871/:883`), and `uint` rejects overflow (`size >
maxbits/8 → errUintOverflow`, `:755`). This isn't just anti-malleability: it guarantees **two honest nodes
decode the same wire bytes into the same value or both reject** — closing a quiet **D (divergence)** vector
where a permissive decoder could let a non-canonical encoding mean different things on different clients (the
sync-layer cousin of the MemeCore determinism lesson).

**Failure modes:** **S (resource exhaustion): defeated** — 16 MB frame cap + pre-decode bomb check +
bound-before-allocate; an attacker cannot force a large allocation or a decompression blowup. **D
(divergence): defeated** — canonical-encoding enforcement. **A (accept-invalid): out of scope here by design**
— the decoder is *structural* (it produces a well-formed typed value); *semantic* validation (signatures,
state, gas) is downstream, which is the correct separation. **No finding.** This is "bound the claimed size
against the real input before you allocate, and insist on one canonical encoding" — the deserialization analog
of S1's verify-before-persist, and the bar for every other wire decoder in this sub-sweep (SSZ, the eth/68 and
snap/1 handlers, txpool ingress — landing next).

## Sweep status (running)
| # | Target | Layer | (Q2) verify-before-persist? | Worst reachable failure mode |
|---|---|---|---|---|
| S1 | go-ethereum snap sync | EVM state ranges | **yes** — `VerifyRangeProof` vs header root before write | only **S**; D/A/C forced safe |
| S2 | Agave (Solana) · Bitcoin assumeutxo | L1 snapshot load | **yes** — recompute hash vs gossip / hardcoded anchor; isolate failure | only **S**; D/A/C safe (Bitcoin adds genesis-replay) |
| S3 | Lighthouse · Prysm | beacon checkpoint sync | Lighthouse **bidirectional**; Prysm **body-root only / none on file path** | A/D operator-bounded; **Prysm = verification-strength gap** |
| S4 | CometBFT+SDK · Substrate warp | chunked state-sync | **yes** — final apphash gate (`syncer.go:504`) / per-chunk range proof (`state_sync.rs:276`) | only **S**; D/A/C safe (1 decompress-cap note) |
| S5 | Reth · Erigon | EVM exec sync | Reth **recompute, commit-gated**; Erigon exec recompute+unwind, **snapshot = registry trust** | Reth D/A/C blocked; **Erigon snapshot = anchor outlier** |
| S6 | go-ethereum RLP + devp2p | wire deserialization | **yes** — frame ≤16MB, snappy `DecodedLen` bomb check, RLP `size > remaining → ErrValueTooLarge` before alloc | **S** defeated (bounded alloc); **D** defeated (canonical form) |

**Result:** 10 implementations, 4 ecosystems — **state sync is the *proven* end and fails safe** (D/A/C forced
off the table; only S + resource-hardening remain). Two named outliers: **Erigon's snapshot-import registry
trust** (anchor) and **Prysm's checkpoint binding** (strength) — both characterized with a constructive fix,
neither a remote exploit.
