# Trust-Cartography → Web Apps (methodology generalization)

*Does the six-bucket / three-coordinate lens transfer from blockchains to ordinary web
applications? Yes — and the mapping is unusually clean, because a web app is the
Compression/Expansion axis (`RETROSPECTIVE §10`) in its starkest form. This note records the
transfer abstractly. It contains **no findings about any specific site** — it is the
generalized lens only.*

---

## The core fit: the client is the untrusted export boundary

Every blockchain audit in this corpus bottomed out at one discipline: **recompute, don't
trust the summary** — and at one structural fact: the load-bearing guarantee lives one layer
*out* from the code that looks in charge. A web app is the same shape, sharpened:

> **The client (browser JS) is pure *expansion*: it turns user intent into API calls. It is
> fully attacker-controlled and proves nothing. The server is the only place truth can live.
> Every web-security question reduces to: *does the server independently re-derive what the
> client claims, or does it trust the client's word?***

This is exactly the `§10` import/export framing: the browser is the export side (intent →
effects), so the server must treat every request as an unverified claim. Client-side
validation, client-set flags, base64 "obfuscation," multi-step UI gating — all of it is
*advisory*, identical to how reward formulas were advisory in the AMM/perp audits while the
type system / settlement cap did the real enforcing.

---

## The six buckets, mapped

| Bucket (chain) | Web-app analogue | The question |
|---|---|---|
| **1 — Conservation** | money/credits/quota integrity (balances, payments, points) | can a client mint value or pay less than charged by manipulating a request? |
| **2 — Witnessed objects** | auth tokens, sessions, reset tokens, API keys | are credentials unforgeable, server-issued, single-use where needed — and *not shipped to the client*? |
| **3 — Dual representation** | client validation vs server validation | is every client-side check **re-enforced server-side**? (the canonical web bug is "no") |
| **4 — Dependency lineage** | third-party scripts, CDNs, framework/library versions | are dependencies current and integrity-pinned? (outdated components are the #1 real breach vector) |
| **5 — Arithmetic/bounds** | input validation, type/length/range, injection | is untrusted input bounded and parameterized before it reaches a query/command/render? |
| **6 — Cross-layer seam** | the client↔server (and server↔3rd-party-API) boundary | does the server **verify the realized effect** of downstream calls rather than trust reported state? |

Two carry over almost verbatim:
- **The "verify-the-effect" template** (from the marginfi cross-protocol pass): when the server
  calls a downstream service, it should *check the actual result* (amount received, status,
  ownership) rather than trust the downstream's reported state. Same pattern, server↔3rd-party.
- **Bucket 3 = the recurring web bug.** "The client already checks X" is never a control. The
  audit instinct "recompute, don't trust the summary" becomes "re-validate server-side, don't
  trust the form."

---

## The three coordinates, mapped

- **Equivalence / 6b** — *"the client request faithfully represents an authorized intent."*
  Discharged only by server-side authentication + authorization on every state-changing
  endpoint. The irreducible residual is anything the server cannot independently know (e.g.,
  "is the human who holds this session the legitimate owner") — bounded by token secrecy and
  session integrity, never proven.
- **Conservation floor** — *where is "you can only act on your own data / spend what you have"
  enforced?* In a well-built app: server-side, per-request, keyed to the authenticated
  identity (the analogue of Sui's type system or marginfi's rate algebra). In a weak app:
  partly in the client (the analogue of an unguarded `proportional` foot-gun). **Object-level
  authorization (IDOR) is the lending/AMM-equivalent conservation question:** can identity A
  read/modify object owned by B by changing an id?
- **Governance ceiling** — *who can change/replace the whole app?* The hosting panel, the
  domain registrar, the deploy pipeline, the DB admin, the server's `.env`. Per
  `AUDIT-GOVERNANCE-CEILING.md`, this is the apex: whoever holds the hosting/credentials holds
  everything, and it is invisible to any code-level review.

---

## The auditability boundary (client-open, server-closed)

This is the web mirror of the corpus's "SDK-open, program-closed" finding
(`AUDIT-METEORA-VAULT-SDK.md`):

> **You can read the entire client (it is served to every visitor); you cannot read the
> server (the actual trust boundary). So *passive* web review can map the attack surface and
> form hypotheses — "the client shows no reset token, so the server had better enforce one" —
> but it can never *confirm* server-side behavior.**

Confirmation requires either (a) the owner inspecting their own server code/logs, or (b)
**authorized, written-scope active testing** against **accounts/data the tester controls**.
Two consequences this corpus holds to:
1. A relayed/verbal "go ahead" is **not** scope to attack a live production system, especially
   when it would touch third-party users' accounts or data. Reading public client code and
   response headers is passive and fine; sending crafted requests to exploit a hypothesis is
   not — and "fingerprint the version to find a CVE" is already on the offensive side of that
   line.
2. The safe way to settle an authorization hypothesis (e.g., a suspected object-level-authz or
   reset bug) is a **two-controlled-accounts test run by the owner**: create A and B you both
   own, attempt the cross-account action, observe. Real answer, zero real users touched, no
   exploit shipped.

---

## What this is and isn't

A defensive methodology note. It demonstrates the trust-cartography lens transfers to web
applications and records the mapping, the auditability boundary (client-open/server-closed),
and the ethical line (passive analysis and owner-run controlled tests vs. unauthorized active
probing of live third-party systems). It contains no assessment of, or finding about, any
particular website. Companion to `AUDIT-METHODOLOGY-RETROSPECTIVE.md` (§9 equivalence, §10
compression/expansion, §11 conservation floor), `AUDIT-GOVERNANCE-CEILING.md` (the ceiling =
hosting/credentials), and `AUDIT-MARGINFI-LENDING.md` (the verify-the-effect template).
