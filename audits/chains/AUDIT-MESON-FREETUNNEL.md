# Meson / Free Tunnel — cross-chain settlement-seam note (trust-model characterization; NOT a source audit)

**Targets:** Meson (the cross-chain stablecoin protocol behind `free-app.meson.fi`, retail/"Express")
and **Free Tunnel** (the `free-tunnel.meson.fi` product, "for large transfers"). Cross-chain bridges are
the corpus's **highest-risk category** — the §4f settlement seam, where most real hacks happen
(Wormhole, Ronin, Harmony, Nomad). **Posture:** defensive; no exploit. **This is a deliberate honesty
case: I characterized the *trust model* from public sources; I did NOT read the enforcing code.**

## ⚠️ Auditability floor (read this first)
I **could not obtain the enforcing contracts** from this environment:
- `MesonFi/meson-contracts-solidity` (the core swap) and every Free Tunnel contract repo I tried
  **prompt for auth** (private/renamed/gone) — not publicly cloneable here. Only `MesonFi/meson-to` (a
  UI **widget SDK**, no protocol logic) is public.
- I have no explorer API key to pull the verified on-chain source.
So everything below is the **design/trust model from public docs + the known HTLC/lock-mint
architecture**, not a line-level audit. **I am not vouching for the code — I haven't seen it.** What can
be said is *where the trust sits* and *what to verify if you get source or addresses.* (External
assurance does exist: Meson reports **Trail of Bits (3 rounds)** + **SSLabs/Georgia Tech** audits — that
is third-party trust, not my verification.)

## Two products, two very different trust models

### 1. Meson core / "Express" — HTLC atomic swap (a *5th* settlement-seam model; most trust-minimized)
Meson's core is **Hashed-Timelock-Contract atomic swaps** with LP liquidity and out-of-order processing.
This is a **new settlement-seam model for the corpus**, and the *strongest* of the bridge-ish designs:
- **Conserve-by-construction.** A swap is a hash-lock: the LP locks funds on the destination, the user
  locks on the source, and **the same secret preimage releases both legs** — or, after the timelock
  expires, **both refund**. There is **no party that can mint or release value unilaterally**; either the
  swap completes atomically or it unwinds. Value can't be created — the hash-lock *is* the conservation.
- **Trust assumption:** essentially cryptographic (the hash-lock + timelock) + LP liquidity. No
  validator set, no multisig that can sign value into existence. This is the **0-of-N-ish** end of the
  spectrum, closer to a validity proof than to a custodial bridge.
- **Residual / what to verify (if you get source):** the **timelock bounds** (too short → griefing the
  counterparty; too long → capital lockup), the **LP bond/lock/release** accounting (does release ==
  lock, 1:1, with no leak?), **secret-reveal front-running / ordering** (can a relayer steal the secret
  to grief?), and the swap **encoding** (`encodedSwap` integrity — amount/fee/recipient can't be
  malleated). These are the classic HTLC-swap residuals; ToB's 3 rounds presumably covered them.

### 2. Free Tunnel — "atomic lock-mint" (collapses toward the *multisig/proof* model; **higher risk**)
"Free Tunnel," used **for large transfers**, is a **lock-mint** bridge (Meson's atomic-lock-mint
framework): tokens are **locked on the source** and an **authorizer (proposer/executor) mints a
representation on the destination**. This is the **classic high-risk bridge category** — *every* large
bridge hack (Ronin $625M, Wormhole $325M, Harmony, Nomad) was a lock-mint bridge whose **mint authority
or proof check** was broken.
- **Trust assumption:** whoever can **authorize the destination mint** + the integrity of the
  **proof/attestation that the source lock happened**. If that's a multisig, it's the
  **multisig+dispute** model (>some honest threshold of an appointed signer set — like Hyperliquid
  Bridge2). If it's a light-client/proof, it's stronger. **This is the irreducible trust, and it's where
  the money is.**
- **Residual / what to verify (decisive — get these before trusting large transfers):**
  1. **Who/what authorizes a mint?** The proposer/executor **signer set + threshold** (a 2-of-3 EOA
     multisig is very different from a 5-of-8 institutional one or an on-chain proof).
  2. **The source-lock proof** the mint checks — is it a real inclusion proof, or just a signed message
     from the authorizer? (Signed-message-only = the authorizer is fully trusted.)
  3. **mint == lock, 1:1**, with replay protection (a lock can be minted exactly once).
  4. **Pause / upgrade / mint-cap keys** — who can upgrade the bridge or change the authorizer, and is
     minting rate-capped? (The upgrade key is the *real* ceiling, per the governance-ceiling spectrum.)

## Verdict & placement in the corpus
- **Meson core / Express (HTLC swap):** a genuinely **trust-minimized** design — conserve-by-construction
  via hash-lock, no free-mint authority. Adds the **atomic-swap** model as the **5th settlement-seam
  type** (after validity / fraud / light-client / multisig), sitting at the *most* trust-minimized end.
  *Design* is strong; ToB-audited; **I did not verify the code.**
- **Free Tunnel (lock-mint):** **higher-risk by category** — the trust concentrates on the **mint
  authority + the source-lock proof**, the exact surface of every large bridge hack. *Not* implying it's
  broken (it's ToB/SSLabs-audited), but **for "large transfers" the decisive questions are the four
  above**, and they should be answered from the actual contracts before moving real size.
- **Auditability:** the enforcing contracts aren't publicly cloneable from here, so this is a
  trust-model map, not a verification. **To actually audit:** get the deployed contract addresses (from
  the apps), read the verified source on each chain's explorer, and check the four Free-Tunnel residuals
  + the HTLC residuals above. **No finding — and no clearance; I couldn't see the code.**

*Companion to `AUDIT-BRIDGES-SIX-BUCKET.md` (the 6b reference case), `AUDIT-HYPERLIQUID-BRIDGE.md`
(multisig+dispute seam), `AUDIT-IBC-TRANSFER.md` (light-client seam), and the §4f settlement-seam
spectrum in `../methodology/AUDIT-CAPSTONE.md` — Meson's HTLC swap extends that spectrum to a 5th,
most-trust-minimized model; Free Tunnel sits at the high-risk multisig end.*
