# Civic Token-2022 Transfer Hook — Six-Bucket Trust Audit

**Target:** `civicteam/token-extensions-transfer-hook`, cloned `/tmp/civic`, HEAD `b6cc715`.
Native (non-Anchor) Solana program, ID `cto22FHACEgis1zXbY4QJo5Rj6soAQguh1686nZJfNY`.
A Token-2022 **transfer hook** that gates every transfer on the recipient holding a valid
**Civic gateway token** (an on-chain identity/KYC credential) from a configured gatekeeper
network.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts
cite the exact constraint. The security-relevant "value" for a transfer hook is the
**transfer-permission decision** — a bypass = the KYC gate is evaded. Any
untrusted-input→unvalidated→bypass path would route privately to Civic; none was found.

The whole program is ~230 lines in `processor.rs`; this is a line-level read, not a survey.

---

## What the program actually guarantees (precise statement first)

> **On every Token-2022 transfer of a gated mint, the hook aborts unless the *destination
> token account* has, at PDA `[ "gateway", destination_token_account, 0u64,
> gatekeeper_network ]`, a gateway token that `solana_gateway::Gateway::verify_*` accepts
> as owned-by-that-account, issued-by-the-configured-gatekeeper-network, and active.**

Note the subject is the **token account**, not the wallet/human. That is the load-bearing
design choice and the source of the one substantive finding (§ Bucket 3).

---

## Bucket 2 — Witnessed objects & the validation chain (the core; enforced)

The Execute path (`process_execute`, `processor.rs:57`) is gated by a correctly-ordered
chain — every check runs **before** any account is indexed or trusted:

1. **Genuine-transfer gate.** `check_token_account_is_transferring` on *both* source and
   destination (`:71`–`:72`) reads the Token-2022 `TransferHookAccount.transferring` flag
   and errors with `ProgramCalledOutsideOfTransfer` if false (`:49`–`:53`). Because the
   `transferring` flag lives in a token account *owned by spl-token-2022* and is set true
   only by spl-token-2022 mid-transfer, this constraint genuinely establishes "we are
   inside a real Token-2022 transfer CPI." It is the defense against the hook being
   invoked standalone or by a spoofing program. **enforced by constraint** (flag is
   token-2022-write-only).
2. **Validation-PDA binding.** `get_extra_account_metas_address(mint, program_id)` must
   equal the passed validation account (`:75`–`:78`). **enforced.**
3. **Extra-account-meta validation (the anti-substitution core).**
   `ExtraAccountMetaList::check_account_infos::<ExecuteInstruction>(…)` (`:84`) recomputes
   every configured meta against the supplied account list and errors on mismatch or
   shortfall. Only after this succeeds does the code index `extra_account_infos[0]` / `[2]`
   (`:95`/`:97`) — so the **validate-before-index ordering removes any out-of-bounds or
   substitution risk**. The configured metas are: a *fixed-pubkey* gatekeeper network
   (`:154`), a *fixed-pubkey* gateway program (`:155`), and the gateway-token *PDA*
   (`:157`–`:171`). A caller therefore cannot substitute a different gatekeeper network
   (it is a literal configured key) nor a different gateway token (it must be the PDA
   derived from the real destination + configured gkn). **enforced by constraint.**
4. **Credential verification.** `Gateway::verify_gateway_token_account_info(gateway_token,
   destination, gatekeeper_network, None)` (`:104`) performs the real ownership/issuer/
   active-state check; the hook returns its result with no early-Ok and no bypass arm.
   **fails closed.**

Because accounts `0..3` of an Execute instruction are fixed by spl-token-2022 to the real
`source/mint/destination/authority`, the destination the hook checks **is** the real
transfer destination — the hook trusts token-2022 to pass real participants, and (1)
confirms that trust is warranted. **No substitution / bypass / reentrancy path found in the
reviewed code:** Execute performs no CPI (so no reentrancy), does no arithmetic, and gates
on a recomputed PDA + a fixed issuer key + an active-credential check.

---

## Bucket 3 — Dual representation: **the wallet ⇄ token-account KYC seam** (the finding)

This is the one substantive observation, and the program **documents it itself** (`:98`–
`:100`, `:159`–`:163`):

- Civic identity verifies **wallets/humans**. The hook can only see the transfer's
  **token accounts** (the owner wallet is not in the Execute account list). So the gateway
  token is PDA-bound to, and verified against, the **destination token account address**,
  not the recipient wallet.
- The equivalence *"this token account has a gateway token" ⟺ "the human behind it is
  KYC'd"* is therefore maintained by an **external (on/off-chain) association service** that
  the hook cannot see or enforce. This is a textbook **6b residue**: an equivalence between
  two representations of truth that the verifying program cannot close on its own.

Two concrete consequences worth raising with Civic as **design-intent questions** (not
asserted exploits, and the code already half-acknowledges them):

- **Token-account ownership transfer carries KYC status.** A token account's owner can be
  changed via `SetAuthority(AccountOwner)`. Since the gateway token is bound to the *token
  account address*, not the owner, a KYC'd user who hands off (or sells) ownership of a
  gated token account transfers its "verified" status to the new, unverified owner — the
  hook would still pass. Whether this matters depends entirely on Civic's association
  service re-binding on ownership change, which is **outside this program**.
- **Revocation propagation.** Revoking a human's identity must propagate to *every token
  account* associated with them, again via the external service; the hook checks only the
  single index-`0` gateway token PDA (`:168`) for the destination account.

**Verdict: trust-boundary debt (6b), partially documented by design.** The on-chain gate is
sound *for what it checks*; the gap between "token account is gated" and "recipient is
verified" is an external-service equivalence the hook structurally cannot discharge. This is
the right place for the residual to live — but it should be named, and the association
service's ownership-change / revocation handling is where the real review effort for this
*feature* belongs. (Mirrors the corpus pattern: the load-bearing guarantee lives one layer
out from the code that looks in charge — here, in the off-chain associator.)

---

## Bucket 4 — Dependency / lineage

- **Hardcoded gateway program ID** (`GATEWAY_PROGRAM_ID`, `:38`) and gateway-token seed
  literal (`:33`) are pinned to Civic's on-chain identity program. The hook's correctness
  is inherited from `solana_gateway::Gateway::verify_*` semantics (active/expiry/issuer
  checks) — a dependency boundary, not re-verified here. **named dependency.**
- **Discriminator reuse.** Civic's init instruction reuses the *standard* SPL discriminator
  `hash("spl-transfer-hook-interface:initialize-extra-account-metas")` (`instruction.rs:37`).
  The dispatcher (`processor.rs:207`) tries `TransferHookInstruction::unpack` first, lets
  non-Execute variants fall through (`_ => {}`, `:216`), then parses Civic's own init. I
  traced this: Execute has a distinct discriminator, and the init fall-through resolves
  correctly regardless of whether the standard unpack accepts the 32-byte payload. **no
  dispatch ambiguity found** (the fall-through is the constraint that makes it safe).

---

## Bucket 5 — Arithmetic / bounds

N/A by construction — the hook moves no value and does no arithmetic; `amount` is received
and used only to repack the Execute instruction for `check_account_infos` (`:86`), never to
compute anything. `#![allow(clippy::integer_arithmetic)]` (`lib.rs:6`) is inherited
boilerplate and harmless here (no arithmetic exists). **not applicable.**

---

## Bucket 6 — Settlement seam & permissioning

- **6a (reduced): the token-2022 ⇄ hook handshake.** Discharged by the `transferring`-flag
  protocol (token-2022 sets/clears it; the hook checks it) — a real, enforced cross-program
  invariant, not a deferral.
- **Init authorization (the permission gate).** `process_initialize_extra_account_metas`
  (`:117`) requires `authority_info.is_signer` **and** `authority_info.key ==
  mint.mint_authority` (`:138`–`:143`) — only the mint authority can configure the hook and
  choose the gatekeeper network. **enforced by constraint.**
- **Immutability (constraint debt).** There is **no update/revoke instruction** — the
  gatekeeper network is fixed at init and the `ExtraAccountMetaList` PDA cannot be
  re-initialized (the `system::allocate` on an already-allocated account fails). Rotating
  the gatekeeper network or disabling the gate is not possible on-chain. **constraint debt**
  (rigidity; not a vulnerability, but a notable operational limitation for an
  identity-gating system where networks may need to rotate).
- **PDA rent (robustness note).** Init uses raw `system::allocate` + `assign` (`:185`–
  `:194`) without transferring rent lamports; the validation PDA must be pre-funded to
  rent-exemption by the caller or the transaction fails at rent collection. Liveness/robustness,
  not security. **noted.**

---

## Governance ceiling (per `AUDIT-GOVERNANCE-CEILING.md`)

- **In-program:** the **mint authority** is the configuring role (init-gated). If it is a
  multisig, the gate's setup is multisig-gated; if a hot key, that key chooses the
  gatekeeper network.
- **Out-of-program (not in repo, must be checked on-chain before trusting a deployment):**
  the program's **BPF upgrade authority** (can replace the hook logic wholesale — apex
  power), and the **gatekeeper network operator** (Civic) who can issue/revoke the gateway
  tokens that are the actual credential. The strongest gate here is only as strong as the
  gatekeeper network's issuance integrity — the credential issuer is the real trust root.

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| 2 | Genuine-transfer (`transferring`) gate | **enforced** — flag is token-2022-write-only |
| 2 | Validation-PDA + `check_account_infos` (anti-substitution) | **enforced** — recomputed PDAs + fixed-key metas; validate-before-index |
| 2 | Gateway-token credential check | **enforced / fails closed** — no early-Ok, no bypass arm |
| 3 | Wallet ⇄ token-account KYC equivalence | **trust-boundary debt (6b)** — maintained by an external service the hook can't verify; ownership-transfer & revocation propagation are off-chain (design-documented) |
| 4 | Gateway program/seed pinning; discriminator reuse | **named dependency / no dispatch ambiguity** |
| 5 | Arithmetic | **N/A** — no value math |
| 6 | Init authorization | **enforced** — signer + `== mint_authority` |
| 6 | Config immutability (no rotate/revoke) | **constraint debt** — fixed gkn post-init |
| ceiling | Mint authority + BPF upgrade authority + gatekeeper network | **trust root = the credential issuer** |

## Nothing routed privately — and the honest result

No exploitable untrusted-input→bypass path was found in the reviewed code. The validation
ordering is correct, account substitution is closed by `ExtraAccountMetaList::check_account_infos`
plus fixed-pubkey metas, out-of-transfer invocation is blocked by the `transferring` flag,
and init is gated to the mint authority. The program is a tight, defensible gate **for what
it checks on-chain**.

The substantive output is architectural, not a CVE: **the hook gates token accounts, while
the product intent gates humans, and the bridge between them is an off-chain association
service the program cannot enforce.** Token-account ownership transfer and identity
revocation both live on the far side of that bridge. These are design-intent questions to
confirm with Civic (and the highest-value place to spend further review on this feature) —
raised here as named trust boundaries, not as exploits, and not posted anywhere but this
defensive write-up. Companion to `AUDIT-GOVERNANCE-CEILING.md` (credential-issuer as trust
root) and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9 (the 6b external equivalence).
