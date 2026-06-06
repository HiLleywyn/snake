# Namada — `UncheckedAllowedConversion` Call-Site Resolution

**Target:** `github.com/anoma/namada` @ `6714f3a` (HEAD 2026-01-14), against
`masp` @ `b2b0f61`. **Question (only):** can any untrusted / on-chain /
governance input insert a conversion generator that is **not** re-derived from
the asset ID before it enters the conversion Merkle tree or the value-balance
path? **Read-only.** No conversions, tests, PoCs, or exploit witnesses
constructed.

**Verdict vocabulary (strict):** `safe by checked constructor` ·
`trusted genesis/governance input, validated before tree insertion` ·
`trusted input, not validated` · `untrusted input, validated` ·
`untrusted input, not validated` · `unclear`.

---

## Top-line

The `AllowedConversion.generator` field is **private** (`masp` `convert.rs:28`),
so Namada can only obtain a conversion either (a) by deriving it from an asset
sum via `AllowedConversion::from(I128Sum)` (`convert.rs:87-118`, recomputes the
generator) or (b) by deserializing it — checked (`convert.rs:146-159`,
re-derives + rejects mismatch) or unchecked (`UncheckedAllowedConversion`,
`convert.rs:219-232`, takes generator bytes as-is).

**There is exactly one `UncheckedAllowedConversion` consumer in the entire
Namada tree, and exactly one storage-fed insertion into the on-chain conversion
tree that is not re-derived. Its writer is governance/migration only; no
transaction or WASM path can reach it.** → **No `untrusted input, not validated`
found. Stop-and-route condition NOT triggered.** Residual is governance-level
constraint debt (one site).

---

## Call sites

### CS1 — `crates/shielded_token/src/conversion.rs:628-656` (`apply_stored_conversion_updates`) → tree
- **Call site:** reads `masp_conversion_key(ep, asset_type)` from storage and
  deserializes each value as `UncheckedAllowedConversion` (`:629`, `:638`), then
  `leaf.conversion = conv.0` (`:656`). That leaf's `conversion.cmu()` becomes a
  Merkle leaf in `update_allowed_conversions` (`:858`, tree built `:879-885`,
  anchor written `:887`). This is the value-balance-bearing path.
- **Trust boundary:** the key lives under the **MASP internal address**;
  protocol VP rules forbid transaction/WASM writes. Writers observed: the
  governance **DB-migration** tooling (`examples/make-db-migration.rs:310`,
  writing `masp_conversion_key`) and tests only. → **trusted governance/migration
  input**, not on-chain/untrusted.
- **Validation performed:** *None at the consuming boundary* — the read is
  `Unchecked`, so the stored generator is taken as-is (no re-derivation, no
  `generator == from(assets)` check) before entering the tree. Validation exists
  only *upstream*, at migration load, and only conditionally (see CS4).
- **Verdict:** **trusted input, not validated** (at the insertion boundary) →
  governance-level constraint debt.

### CS2 — `conversion.rs:433-436` & `:539-545` (`update_{native,non_native}_conversions`)
- **Call site:** per-epoch reward conversions inserted into `current_convs` via
  `…checked!(…)?.into()` — i.e. `AllowedConversion::from(I128Sum)`.
- **Trust boundary:** values are protocol-computed from on-chain reward
  parameters; the generator is derived, never read from bytes.
- **Validation performed:** generator deterministically derived at
  `convert.rs:87-118`.
- **Verdict:** **safe by checked constructor.**

### CS3 — `conversion.rs:847-858` (leaf update + tree leaf)
- **Call site:** `leaf.conversion += current_conv` then `Node::new(leaf.conversion.cmu()…)`.
- **Trust boundary:** `current_conv` is from CS2 (derived); `leaf.conversion`
  is from CS2-derived or CS1-stored; `+=` is the homomorphic add
  (`convert.rs:162-178`, adds both `assets` and `generator` consistently).
- **Validation performed:** generator equivalence preserved by homomorphism
  **iff** the `leaf.conversion` operand was itself well-formed (true for CS2;
  inherited from CS1 for the stored case).
- **Verdict:** **safe by checked constructor** for the CS2-derived operands;
  inherits CS1's verdict for the stored-update operand.

### CS4 — `crates/sdk/src/migrations.rs:664` + `:225-267` (`validate`) — migration load
- **Call site:** `derive_borshdeserializer!(AllowedConversion)` registers the
  **checked** deserializer; `UpdateValue::validate` (`:236-245`) runs it on the
  bytes by `type_hash`.
- **Trust boundary:** migrations are governance/operator artifacts applied at a
  scheduled height (not a transaction).
- **Validation performed:** *If* the migration declares the value with
  `AllowedConversion`'s type hash → checked deserializer re-derives the generator
  and rejects mismatch (`convert.rs:149-158`). *But* `UpdateValue::raw`
  (`:58-95`) permits a `Vec<u8>` raw write whose deserializer accepts arbitrary
  bytes (`:254`), bypassing the `AllowedConversion` check; those bytes are later
  read unchecked at CS1.
- **Verdict:** **trusted genesis/governance input, validated before tree
  insertion** *only when the checked `AllowedConversion` type is used* —
  otherwise the raw path is **trusted input, not validated** (the same debt as
  CS1, originating one layer up).

### CS5 — `crates/shielded_token/src/masp/shielded_wallet.rs:1140,2763,2813` (+ `masp.rs:638`)
- **Call site:** `AllowedConversion::from(conv)` for client-side proof building.
- **Trust boundary:** client/wallet (prover) side; does not write the on-chain
  tree. The chain independently re-checks any spend via tree membership + binding
  signature.
- **Validation performed:** derived at `convert.rs:87-118`; irrelevant to
  consensus conservation.
- **Verdict:** **safe by checked constructor** (and out of the consensus trust
  path).

### CS6 — `crates/storage/src/conversion_state.rs:29` (`ConversionLeaf.conversion`) — state reload
- **Call site:** the persisted conversion-state leaf field, reloaded via derived
  Borsh.
- **Trust boundary:** node-local persisted state, reloaded on startup.
- **Validation performed:** `ConversionLeaf` uses the **checked**
  `AllowedConversion` deserializer on reload (re-derives generator).
- **Verdict:** **safe by checked constructor.**

---

## Canonical strict output (per reviewer)

```
conversion.rs:638      → masp_conversion_key storage read → MASP internal storage boundary
                         → unchecked deserialization
                         → trusted governance/migration input, not validated
conversion.rs:656/:858 → conversion-tree leaf insertion → consumes value from :638
                         → no re-derivation at insertion
                         → trusted input, not validated
conversion.rs:435/:539 → per-epoch reward conversion construction → checked .into() derivation
                         → safe by checked constructor
migrations.rs:664 +    → typed AllowedConversion migration validation → checked deserializer
  validate():245         → trusted genesis/governance input, validated before tree insertion
migrations.rs:58/:254  → raw Vec<u8> DB migration writes → bypasses typed validation
                         → trusted input, not validated
```

**Preferred remediation (reviewer):** force all `masp_conversion_key` writes
through typed `AllowedConversion` validation, **or** re-derive/check the
generator at the read site before tree insertion. The **read-side check is
preferred** because it protects against future migration mistakes (it fails
closed regardless of how the bytes were written).

## Conclusion & remediation

- **No `untrusted input, not validated` exists** — every path that admits a
  non-derived generator (CS1, and its CS4 raw-migration source) is gated by the
  MASP internal-address VP to **governance/migration** writers. The private
  `generator` field closes all transaction/WASM routes. **Private routing is not
  required.**
- **One item of governance-level constraint debt (CS1 / CS4-raw):** the
  conversion-tree insertion path reads `UncheckedAllowedConversion` and never
  re-derives `generator == from(assets)` at the point of insertion; correctness
  relies on the migration author/tooling having used the checked type. The
  framework permits a raw-bytes bypass.
- **Defensive remediation (suggestion only):** in
  `apply_stored_conversion_updates`, deserialize stored updates as **checked**
  `AllowedConversion` (or, equivalently, after assigning `leaf.conversion`,
  assert `leaf.conversion == AllowedConversion::from(leaf.conversion.assets)`),
  so a malformed governance/migration update fails closed at insertion rather
  than entering the tree. This converts the verdict from *trusted input, not
  validated* to *…validated before tree insertion* and removes the dependency on
  migration discipline.

**Disclosure posture:** governance-only trust boundary, no untrusted path, no
exploit constructed — safe to record publicly. Proceeding to **Penumbra** next,
same template.
