# Bridge sweep — the weak link, audited

Bridges are the corpus's **highest-risk category** (§4f settlement seam): every nine-figure hack lives
here — Ronin $625M, Poly $611M, Wormhole $325M, Nomad $190M, Harmony $100M. The MemeCore work and the
Meson note made the lens sharp, so this is a dedicated sweep. **The two questions that decide every
bridge's safety:**

> **(1) Who authorizes the mint/release?** (the trust model) · **(2) What does the mint check — a real
> proof, or a signed message?** (the verification). Plus: **mint == lock 1:1 + replay guard**, and **who
> can upgrade / pause / change the authorizer** (the governance ceiling).

**Posture:** defensive; no exploit; clone public source where available, characterize + name the trust
where not. Findings (if exploitable + live) → stopped-and-notified privately. The trust-model taxonomy
extends the §4f spectrum (`../methodology/AUDIT-CAPSTONE.md`).

### Bridge trust-model taxonomy (ranked by who you must trust, best → worst)
| Model | Trust | Examples (in this sweep) |
|---|---|---|
| **Light client / native proof** | cryptographic (verify the source chain's consensus/proof) | IBC, zkBridge, native rollup bridges |
| **HTLC atomic swap** | hash-lock + timelock (no free-mint authority) | Meson core / Express |
| **PoS validator set / separate chain** | >2/3 stake of a staked set | Axelar |
| **Oracle + relayer (separated)** | 2 independent parties must both be honest | LayerZero |
| **Optimistic / intent** | 1-of-N honest watcher + a fronting relayer's capital | Across, Hop |
| **External appointed committee (multisig)** | >threshold of an appointed signer set | **Wormhole (13/19)**, Hyperliquid Bridge2, Ronin |

The multisig committee is the most-hacked model (Ronin, Harmony, Hyperliquid-class). Light-client and
HTLC are the most trust-minimized. Most "bridges" are message-passing layers that *a token bridge sits
on top of* — the token bridge's mint trusts the messaging layer's authorizer.

---

## B1. Wormhole — Guardian multisig (13/19); robust, post-hack-hardened (clean contract; trust = the Guardians)
**Target:** `wormhole-foundation/wormhole`, `ethereum/contracts/{Messages,bridge/Bridge}.sol`. The
canonical **external-committee** bridge, and the one whose **$325M Feb-2022 hack was exactly a
signature-verification bypass** — so the guardian check is *the* thing to read. **Result: the on-chain
verification is robust and post-hack-hardened; the trust is cleanly the 19 Guardians.**

**Trust model:** a **VAA** (Verified Action Approval) signed by **≥13 of 19 Guardians** authorizes every
mint/release. The contract verifies the multisig; the irreducible trust is the Guardian set.

**Guardian signature verification (`Messages.sol verifyVMInternal`/`verifySignatures`) — every guard the
hack taught is present (with WARNING comments documenting why):**
1. **Hash binds body** (`:50-65`): `keccak(keccak(body)) == vm.hash` — a valid signed hash can't be
   paired with a different body (the body-swap class).
2. **Empty guardian-set rejected** (`:75-77`): `guardianSet.keys.length == 0 → "invalid guardian set"` —
   the exact "set falls to zero → quorum compromised" trap, explicitly guarded.
3. **>2/3 quorum** (`:90`, `quorum = (n*2/3)+1` `:216` → **13/19**): `signatures.length >= quorum`.
4. **ecrecover ≠ 0** (`:119`): `require(signatory != address(0))` — rejects the invalid-signature-returns-0
   trap (the heart of the original bypass class).
5. **Ascending guardian indices** (`:122`): `sig.guardianIndex > lastIndex` — no guardian double-counted.
6. **Bounds + per-guardian key match** (`:131,135`): `guardianIndex < guardianCount` and
   **`signatory == guardianSet.keys[sig.guardianIndex]`** — each signature must match the *specific real
   Guardian* at its index. So 13 distinct, real Guardians must have signed.

**Token bridge `_completeTransfer` (`Bridge.sol:588`) — mint/release is gated + replay-guarded:**
- **Replay guard:** `if (isTransferCompleted(vm.hash)) revert TransferAlreadyCompleted();
  setTransferCompleted(vm.hash)` (`:602-603`) — a VAA is redeemable **exactly once**.
- Mints the wrapped token (or releases the locked native) against the **guardian-verified VAA**, gated by
  the source **emitter registration** (`bridgeContracts[emitterChainId]` must equal the VAA emitter — so
  only the real source token-bridge can authorize a mint), and `notPaused`.

**Verdict: the contract is clean and well-hardened** — the verification has every guard, the post-hack
WARNING comments show the lessons were internalized, mint==release with a one-time replay guard and
emitter registration. **Residual (the irreducible trust): the 19 Guardians.** A **≥7-of-19 (>1/3)
Guardian compromise forges any VAA → mints anything → drains everything** — the canonical multisig-bridge
risk, identical class to Ronin/Hyperliquid, mitigated only by *who the Guardians are* (reputable
entities, distributed keys) and the guardian-set governance (itself guardian-signed). The code can't fix
that; it's the model. **No finding** in the contract; the trust is named and it's the Guardians.
