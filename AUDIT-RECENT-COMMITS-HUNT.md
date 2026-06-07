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
