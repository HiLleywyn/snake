# Humanity Protocol ($H token + human-only airdrop) — Six-Bucket Trust Audit

**Target:** `humanity-org` — `hp-basic-token` (the **$H** token) and
`hp-human-only-airdrop-off-chain-contracts` (the proof-of-humanity airdrop). Cloned
`/tmp/hp-basic-token`, `/tmp/hp-human-only-airdrop-off-chain-contracts`.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts cite the
exact constraint. Nothing routed privately — none found (these are simple contracts whose risk is
*by-design centralization*, not a defect). Small target → proportionally short.

---

## HToken ($H) — a fully owner-controlled token (all ceiling, minimal floor)

The entire token (`hp-basic-token/contracts/HToken.sol`) is 35 lines: an upgradeable OZ ERC20 with
two privileged functions.

```solidity
function mint(address _account, uint256 _value) public onlyOwner { _mint(_account, _value); }   // :25
function burn(address _account, uint256 _value) public onlyOwner { _burn(_account, _value); }    // :32
```

- **Bucket 1 (conservation floor): minimal.** Conservation is only OZ-ERC20's internal balance/
  supply accounting. There is **no supply cap** and **no fixed issuance** — total supply is whatever
  the owner mints. `mint` is unbounded `onlyOwner`.
- **Unconditional force-burn (the notable item).** `burn(_account, _value)` burns from an
  **arbitrary `_account`**, not the caller, gated only by `onlyOwner` — no allowance, no consent.
  The owner can **destroy any holder's $H**. (The NatSpec is explicit: *"the address which will see
  some of its tokens burned."*) This is precisely the `BurnFrom`/`ForceTransfer`-class capability
  that **fetchd deliberately disabled** (`AUDIT-FETCHD-COSMOS.md`); here it is present and
  unrestricted.
- **Upgradeable via `TransparentUpgradeableProxy` + `ProxyAdmin`** (`Proxies.sol`) — the same
  pattern as WLFI (`AUDIT-GOVERNANCE-CEILING.md`). The ProxyAdmin owner can replace the
  implementation wholesale: **apex power, "verified ≠ running."**

**Verdict: trust-boundary debt (by design), maximal.** $H is a fully centralized token: the owner
can mint without limit, burn any holder's balance, and (via ProxyAdmin) rewrite the contract. There
is no on-chain economic constraint on the owner — the *only* trust question is **who the owner and
ProxyAdmin are** (a multisig? a timelock? a hot key?), which is deployment config not in the repo.
This may be intentional for an early-stage token, but it sits at the opposite end of the spectrum
from fetchd's deliberately-bounded admin — and the unconditional force-burn deserves an explicit
decision (most production tokens do *not* let the owner burn arbitrary balances).

---

## The "human-only" airdrop — enforcement is off-chain (6b), not in the repo

`hp-human-only-airdrop-off-chain-contracts` contains **only** a `DemoToken.sol` (a plain ERC20 with
owner mint + `INITIAL_SUPPLY`) and a deploy script. The repo name says it: the airdrop is
**off-chain**. So the two things that *matter* for a proof-of-humanity airdrop —

1. **the human-gating** (the palm-biometric / proof-of-humanity sybil check that decides who is
   eligible), and
2. **the claim conservation** (no double-claim; total claimed ≤ allocation; signature/authorization
   validation) —

are **not on-chain and not in this repo.** They live in a **trusted off-chain signer/server** that
authorizes claims. That is a clean **6b seam** (`RETROSPECTIVE §9`): the equivalence *"this claimant
is a unique human eligible for amount X"* is discharged entirely by an off-chain authority the chain
cannot verify, exactly analogous to the Solana SDK-mirrors and the Canton DSO — the enforcing logic
is closed/off-chain. **named, irreducible from on-chain; unverifiable here.**

---

## Summary

| Item | Verdict |
|---|---|
| $H supply policy | **no cap / unbounded `onlyOwner` mint** — supply = owner's discretion |
| $H force-burn | **unconditional** — owner burns any holder's balance (the capability fetchd disabled) |
| $H upgradeability | **TransparentUpgradeableProxy + ProxyAdmin** — apex power, verified≠running |
| Governance ceiling | **owner + ProxyAdmin = total control** — the only real trust question is *who they are* (multisig/timelock?) |
| Human-only airdrop gating & claim conservation | **off-chain / not in repo (6b)** — discharged by a trusted server; unverifiable here |

## What this audit did NOT cover (coverage honesty)

- The **off-chain airdrop signer/backend** (eligibility, signature scheme, double-claim
  prevention) — the actual proof-of-humanity enforcement; not public here.
- The **Humanity Protocol chain itself** (the L2/identity chain) and the **EAS attestation
  contracts** (`eas-contracts`, a fork of Ethereum Attestation Service) — the on-chain
  proof-of-humanity attestation layer, a separate and more substantial surface than these token
  contracts.
- The `hp-verification-node-plugin` and `chains` metadata repos — not conservation-bearing.

## Addendum — Pass 2: `eas-contracts` is vanilla upstream EAS (trust is in the attester, not the code)

Followed the lead that the on-chain proof-of-humanity lives in `eas-contracts`. It doesn't —
because `humanity-org/eas-contracts` is a **near-verbatim fork of the upstream Ethereum Attestation
Service**:
- README is upstream's verbatim; the standard EAS contract set (`EAS.sol`, `SchemaRegistry.sol`,
  `EIP712Proxy`, `EIP1271Verifier`, `SchemaResolver`, `Indexer`); the **only** change is a deploy
  script (`scripts/deploy.ts`) + deployment artifacts (base-goerli, polygon). No
  `humanity`/`human`/`palm`/`sybil` references; **no custom proof-of-humanity resolver.**

So there is nothing to audit in the contracts — it is unmodified, already-audited upstream
infrastructure. The methodology's correct move is to **not** re-audit it and instead name where the
proof-of-humanity trust *actually* sits, because EAS is **permissionless**: anyone can attest to
anything, and the *meaning* of a "this is a verified human" attestation comes entirely from **which
attester key issued it**. Therefore Humanity's proof-of-humanity reduces to:

1. **The attester authority** — the key(s) Humanity uses to issue "human" credential attestations.
   Whoever controls that key can mint humanity for any address; revoking/rotating it is the trust
   root. *Off-chain-controlled; not in these contracts.*
2. **The off-chain biometric verification** (palm scan → decision to issue the attestation) behind
   that key. *Off-chain; not auditable here.*

**Verdict:** vanilla EAS (no fork delta to review); the proof-of-humanity trust is an **attester-key
+ off-chain-verification** 6b seam, identical in shape to the airdrop's off-chain gating above. The
contracts give you a generic, sound attestation rail; the sybil-resistance guarantee is entirely a
function of the issuing authority, which lives off-chain.

## Nothing routed privately

No untrusted-input→value defect found. The $H token and the airdrop's on-chain part are simple,
maximally-owner-controlled contracts; their risk is **by-design centralization**, not a bug. The
honest output is the governance-ceiling reading: **$H is fully owner-controlled (uncapped mint,
unconditional force-burn, upgradeable), so its entire trust rests on the owner/ProxyAdmin identity**,
and the proof-of-humanity airdrop's real logic (sybil-gating, claim conservation) is **off-chain** —
a trusted-server 6b seam outside this repo. The single most useful follow-up for this ecosystem is
the **EAS attestation contracts**, where the on-chain proof-of-humanity actually lives. Companion to
`AUDIT-GOVERNANCE-CEILING.md` (owner+ProxyAdmin apex; contrast with fetchd's bounded admin) and
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9 (the off-chain-authority 6b).
