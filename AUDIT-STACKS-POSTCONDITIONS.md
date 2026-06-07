# Stacks (STX) — Clarity post-conditions audit (clean; a novel conservation primitive)

**Target:** `stacks-network/stacks-core`, sparse clone `/tmp/stacks`
(`stackslib/src/chainstate/stacks`). Audited the **post-condition checker**
(`db/transactions.rs:check_transaction_postconditions`) — Clarity's built-in, caller-declared,
VM-enforced per-transaction asset-movement guard. **Posture:** defensive; no exploit, no PoC.
**Result: clean — no finding, nothing to disclose.**

Chosen because Stacks adds a **conservation-enforcement primitive not seen elsewhere in the corpus**:
most chains enforce conservation at the *protocol/ledger* level (the global books balance). Clarity
additionally lets the *sender declare* exactly which asset movements their transaction is allowed to
cause, and the VM **aborts and reverts the whole transaction if reality doesn't match** — conservation
from the *user's* perspective, as a defense against the contract they're calling. This is "verify the
effect, don't trust the reported state" (capstone Law 2 / the marginfi template) built into the
transaction format itself.

## The mechanism — declared expectation vs. actual asset movements, abort on mismatch
During Clarity execution every `stx-transfer`/`ft-transfer`/`nft-transfer` is recorded into an
`AssetMap`. After execution, `check_transaction_postconditions` (`transactions.rs:697-...`) runs two
checks:

**1. Each declared post-condition must hold** (`:717-...`). E.g. for an STX condition: the actual
`amount_sent = amount_transferred + amount_burned` (overflow-checked, `:729-731`) is compared to the
declared bound via `condition_code.check(declared, actual)` (sent-eq / sent-le / sent-ge, etc.); on
violation it returns a failure reason → **the transaction is rolled back** (`:733-739`). Same for
fungible and non-fungible tokens.

**2. The catch-all — no *unchecked* asset may move** (`:845-899`), gated by mode
(`:710-715`):
```
Allow      => false   // only explicit conditions checked
Deny       => true    // EVERY moved asset must be covered, for every principal
Originator => principal == origin   // every moved asset of the tx origin must be covered
```
In **Deny** mode (the wallet-default), it iterates over *every* asset actually moved (`all_assets_sent
= asset_map.to_table()`) and, for each principal, **fails the transaction if any moved asset was not
explicitly covered by a post-condition** — "Fungible asset … was moved by … but not checked"
(`:892-897`), and the NFT equivalent down to the individual token value (`:862-869`). So a Deny-mode
transaction **aborts unless the complete set of asset movements it caused was declared in advance.**
**enforced.**

## Why this is a distinct contribution
The threat model is the inverse of the usual one. Protocol-level conservation (every other chain in
the corpus) answers *"can the system create value?"* — no. Clarity post-conditions answer *"can the
contract I'm calling move more of my assets than I authorized?"* — also no, because the VM reverts the
whole call if it tries. It is **caller-scoped conservation**: the user bounds the blast radius of an
untrusted contract at the transaction layer. Compared to EVM's "approve(unlimited) and hope," Stacks
makes the asset-movement bound a **first-class, mandatory-to-check (in Deny mode) part of the signed
transaction**, verified against actual execution with atomic abort. The closest corpus relatives are
Civic's validate-before-use Token-2022 hook (`AUDIT-CIVIC-TRANSFER-HOOK.md`) and the marginfi
"verify-what-was-received" template — but post-conditions generalize it to *any* asset and bake it into
the transaction format.

## Honest scoping (what post-conditions do and don't guarantee)
- **Mode matters.** `Deny` is the safe, complete guard (default in modern wallets). `Allow` disables
  the catch-all (only explicit conditions checked — unchecked movements pass). `Originator` (a legacy
  default) enforces the catch-all **only for the transaction origin's assets**, not for other
  principals touched mid-contract. So the strength of the guarantee is *mode-dependent*; I verified the
  enforcement logic is correct for each mode, and that Deny is the strict one.
- **Post-conditions are an *additional* guard, not the base ledger conservation.** The actual STX/FT/NFT
  balance arithmetic (the transfer primitives that can't overspend) is the Clarity VM's own ledger
  accounting — the protocol floor. Post-conditions sit *on top* as a caller-declared invariant. I
  audited the guard layer here, not the VM's base transfer accounting (separate surface).
- **Abort = revert.** A failed post-condition rolls back all state from the transaction (the
  halt-over-divergence philosophy verified positively across the corpus and absent in MemeCore).

## Connections to the corpus
- **Law 2 made native:** "verify the effect, don't trust the reported state" is usually a *pattern an
  auditor looks for* (marginfi). Stacks **encodes it in the transaction format** — the chain checks the
  effect against the declaration for you.
- **Caller-scoped vs system-scoped conservation:** every other audit verified *system* conservation
  (supply can't inflate). Stacks adds the orthogonal *caller* conservation (a contract can't exceed the
  movements the caller signed for). New axis: conservation has a *who-is-protected* dimension.
- **Defense-in-depth shape** mirrors the IBC bank-underflow backstop and Optimism's air-gap: an extra
  enforced gate over the base mechanism.

## What this audit did NOT cover (coverage honesty)
- **The Clarity VM's base ledger accounting** (the `stx-transfer?`/`ft-transfer?`/`nft-transfer?`
  implementations and balance arithmetic) — the protocol conservation floor under the post-condition
  guard; not opened here.
- **`AssetMap` construction during execution** — that it faithfully records *every* asset movement
  (the post-condition guarantee is only as complete as the asset_map; an unrecorded movement would
  escape the catch-all). I read the *checker*; I did not exhaustively verify the *recorder* captures
  all paths (the load-bearing assumption — stated as the key residual).
- **PoX (Proof-of-Transfer) consensus** and the Bitcoin-anchoring/peg — separate surfaces.
- **Clarity's decidability / no-reentrancy language design** — a related safety property, noted not
  opened.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read the actual Deny-mode catch-all loop and confirmed it fails
  on *any* moved-but-unchecked asset (not just declared-and-violated), and that `amount_sent` includes
  both transferred and burned STX (so burning can't evade a transfer condition). I confirmed the three
  modes' semantics from `enforce_unchecked_assets_for_principal`.
- **Exposure to reversal.** The guarantee rests entirely on the `AssetMap` recording *every* asset
  movement during execution — if a transfer path failed to register in the asset_map, it would bypass
  even Deny mode. I verified the checker is correct and complete *given* a complete asset_map; I did
  **not** prove the recorder is complete (named as the key residual). Also, the protection is
  mode-scoped (Allow/Originator are weaker) — a guarantee about Deny, not about all txs.

## Verdict
**Clean.** Clarity post-conditions are a correctly-implemented, novel conservation primitive:
caller-declared, VM-enforced, per-transaction asset-movement bounds with atomic abort-on-mismatch, and
a Deny mode that rejects *any* unchecked asset movement — encoding "verify the effect" into the
transaction format and giving users system-enforced protection against the contracts they call. No
defect found in the checker; nothing to disclose. The key residual is the completeness of the
`AssetMap` recorder (the checker is only as strong as what execution registers), and the
mode-dependence of the guarantee (Deny is strict; Allow/Originator are weaker). A new corpus axis:
conservation has a *who-is-protected* dimension (system vs caller). Next pulls: the Clarity base
transfer accounting and `AssetMap` construction completeness.
