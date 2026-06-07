# Recent-commits hunt — the freshest, least-reviewed code

The other high-EV vein: code that *postdates the last audit*. New EIPs, new precompiles, new
consensus features — least battle-tested, where un-found bugs live. Method: clone a major repo *with
history*, `git log` recent security-relevant commits, and read the **changed** code (biased to new
*features*, not bug-fixes — fixed bugs are already fixed). Same failure classes (determinism, swallowed
errors, conservation, missing checks). **Live+exploitable → stopped-and-notified privately; redacted
placeholder only.** Defensive, no PoC.

---

## R1. go-ethereum — EIP-7928 Block Access List (BAL) construction/encoding (clean)
**Target:** `ethereum/go-ethereum` (history clone), `core/types/bal/{bal,bal_encoding}.go` +
`core/state/reader_eip_7928.go`. Picked because recent commits (`#34803` "track the block-level
accessList", `#34957` "construct block accessList") add a **brand-new consensus-relevant feature**: the
block access list (a canonical, hashable summary of all addresses/slots/balance/nonce/code touched in a
block). It's the *freshest* consensus-surface code, and the precise MemeCore-class risk applies: the BAL
is **built from Go maps** (`ConstructionBlockAccessList.Accounts map[common.Address]*...`, storage/
balance/nonce/code all maps, `bal.go:30-76`) and then must produce a **canonical** encoding — if it
encoded in map-iteration order, different nodes would compute different BALs → different block hash →
consensus split.
- **It canonicalizes correctly before encoding — clean.** `EncodeRLP` sorts *everything*:
  addresses by `common.Address.Cmp` (`bal_encoding.go:465`), storage write/read slots by
  `common.Hash.Cmp` (`:394,416`), and every per-tx index list by `cmp.Compare`
  (`:403,423,433,443` — write/balance/nonce/code indices); the canonical `BlockAccessList.EncodeRLP`
  form sorts accounts by `bytes.Compare(a.Address[:], b.Address[:])` (`:84`) and entries by
  `BlockAccessIndex` (`:187,290,301,313`). So the encoded/hashed BAL is **canonical regardless of map
  iteration order** — the build-from-map-then-sort-before-consensus pattern, done right (same as Sonic
  L3 / BSC L1).
**Result: clean.** The newest consensus-relevant feature in geth handles the exact MemeCore-class
determinism concern correctly (comprehensive canonical sort at encode time). **Residual:** BAL
*validation/enforcement* (matching the constructed BAL to actual execution, once the fork activates) and
the per-field completeness (every touched slot recorded) are the surfaces to re-check when the fork
goes live — currently construction is canonical. **No finding.** *(Also noted: recent blob-hash fixes
`#35065`/`#35109` are already-merged fixes — the area is active but the bugs are patched.)*

---

## R2. reth — EIP-7928 BAL *validation* (the geth-BAL counterpart, in a newer client) (clean structure; pre-fork)
**Target:** `paradigmxyz/reth` (history clone), `crates/ethereum/consensus/src/validation.rs` +
`crates/engine/tree/src/tree/payload_processor/bal/execute.rs`. The deliberate complement to R1: reth is
a *newer* client, and the recent commit `03d9691 feat(consensus): add experimental BAL validation`
implements the **validation** side of the same EIP-7928 BAL whose *construction* I checked in geth. The
high-EV risk is **client-diversity consensus divergence**: if reth's canonical BAL encoding differs from
geth's by even one byte, a geth-produced block's BAL hash would be recomputed differently by reth →
reth rejects a valid block → chain split.
- **Validation is recompute-and-hash-compare — structurally sound.** reth re-executes, builds the BAL,
  and `if block_access_list_hash != block_bal_hash { return Err(BlockAccessListHashMismatch) }`
  (`validation.rs:118`). Correct shape (recompute, don't trust the header's claim).
- **Encoding is delegated to a *shared canonical crate*, not reimplemented.** reth uses
  `alloy_eip7928::{Bal, BlockAccessList}` and `compute_block_access_list_hash` (`bal/execute.rs:20,303`)
  — so the sort/RLP canonicalization lives in the shared `alloy-eip7928` library, the Rust-ecosystem
  counterpart to geth's `core/types/bal`. The divergence risk therefore reduces to **"alloy-eip7928's
  canonical encoding == geth's `bal` encoding == the EIP-7928 spec,"** which is exactly what the
  EIP-7928 **cross-client execution-spec test vectors** exist to enforce — centralized agreement, not
  N independent encoders.
- **Pre-fork / experimental.** It's an *experimental toggle* for the future Amsterdam/Glamsterdam fork
  (`6a5f371 validate Amsterdam header fields`), **not yet mainnet-consensus-enforced** — so even a
  latent encoding discrepancy could not currently split mainnet.
**Result: clean structure.** reth validates correctly (recompute + hash-compare) and delegates encoding
to the shared canonical crate, so it can't trivially diverge from geth by a private sort choice.
**Residual (named, not closed):** the byte-for-byte agreement of `alloy-eip7928` ↔ geth's `bal` encoder
— I did not read alloy's source here (separate crate), so the cross-client canonical-encoding match is
asserted to be covered by EIP-7928 test vectors, not verified by me. Re-check at fork activation. **No
finding.**

### Recent-commits hunt status
Two complementary fresh-feature reads on the *same* newest consensus feature (EIP-7928 BAL): geth's
**construction** (R1) canonically sorts before encoding; reth's **validation** (R2) recompute-and-hash-
compares with encoding delegated to the shared `alloy-eip7928` crate. Both clean; both pre-fork. The
freshest consensus code in the two major EL clients handles the MemeCore-class determinism concern
correctly, and the cross-client divergence risk is centralized into a shared canonical encoder + spec
test vectors. The honest residual is the shared-encoder byte-agreement (test-vector territory) — to
re-verify when the fork activates. **No finding.**
