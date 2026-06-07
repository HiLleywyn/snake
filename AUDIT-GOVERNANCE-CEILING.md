# The Governance Ceiling — a cross-target pattern note

*A companion to the six-bucket methodology. Not a seventh bucket and not the
Compression/Expansion axis — it is a different kind of observation: about the **privileged
role that sits above the verified mechanism and can change, pause, or replace it.** It
surfaced independently in nearly every target and is frequently the true answer to "what
could actually go wrong," yet it is the part a purely code-and-crypto audit is structurally
blind to.*

---

## The thesis

> **A system's assurance is capped by its most powerful privileged role. The cryptography
> and conservation logic are a *floor* under normal operation; the governance authority is
> the *ceiling*. No proof, type system, or commitment sum can raise a system above the
> trust you place in whoever can upgrade or override it.**

Restated as the one-liner the rest of the methodology can absorb:

> **Buckets 1–6 audit the mechanism. This note audits the authority that can replace the
> mechanism.** `assurance(system) ≤ assurance(governance_root)`.

Every target reviewed had a strong mechanism *and* a role that outranks it. The mechanism
was usually the interesting code; the role was usually one `onlyOwner` modifier — small,
correct, well-tested, and decisive. The risk is almost never a *bug* in the override. The
risk is the override's **existence, blast radius, and key custody.**

---

## The corpus evidence (it is everywhere)

| Target | The mechanism (floor) | The override (ceiling) | Apex power |
|--------|----------------------|------------------------|-----------|
| **WLFI** (EVM) | ERC20Votes, allowlist transfer-gating, vote caps | 3-of-5 Gnosis Safe owns the token **and** the ProxyAdmin | **upgrade** — and it was used: live impl `0x59a3…` (V3) ≠ verified impl `0x3722…` |
| **Base / OP Stack** | fault-proof withdrawal seam, ETHLockbox conservation | Guardian: `blacklistDisputeGame` (:174), `updateRetirementTimestamp` (:163), `setRespectedGameType` (:153), `pause`; ProxyAdmin owner upgrades + lockbox migration | **upgrade + retire-all** (invalidate every game in one call) |
| **Sui** (Move) | linear-type coin conservation (strongest floor in the series) | regulated coins: `DenyCapV2` freeze + `deny_list_v2_enable_global_pause`; framework upgrade via epoch-change system tx | **framework upgrade** (system package replace) |
| **TRON** (Java) | actuator/processor accounting, Stake 2.0 | witness **committee** flips feature gates (`allowChangeDelegation`, `allowTvmVote`, `supportUnfreezeDelay`) | **consensus-rule flip** (changes which code path is live) |
| **Litecoin** (UTXO) | MWEB tri-layer conservation, PoW | `frozen_mweb_output_ids` consensus blocklist; grandfather magic values; dev+miner social layer | **consensus param / hard-fork** (out-of-band, slow) |
| **Namada** (zk) | MASP circuit conservation | `UncheckedAllowedConversion` fed by **governance migrations** | **conversion-tree governance** (constraint debt) |

Reading the *apex power* column is the headline: in five of six, the top authority can
**change the rules or the code itself**, not merely halt. The strength of the floor (Sui's
compile-time linear types, Litecoin's commitment algebra) does **not** lower the ceiling —
Sui's unforgeable coins still sit under a framework-upgrade authority.

---

## The blast-radius ladder (rank every privileged power)

Not all overrides are equal. Rank each privileged function by what it can do, smallest to
largest blast radius:

1. **Halt** — `pause` / freeze withdrawals. Reversible, denies-service, moves no value.
   (Base `SuperchainConfig.pause`; WLFI `pause`; Sui global pause.)
2. **Parameter / feature flip** — change a rate, threshold, or feature gate. Bounded by the
   parameter's domain. (TRON committee gates; WLFI `setMaxVotingPower`.)
3. **Targeted invalidation** — blacklist/freeze one object or account. (Base
   `blacklistDisputeGame`; Sui `DenyCap`; Litecoin frozen outputs; WLFI `adminBurn`.)
4. **Mass invalidation** — retire/invalidate an entire class at once. (Base
   `updateRetirementTimestamp` retires every game; `setRespectedGameType` orphans a game
   implementation.)
5. **Upgrade / replace implementation** — the apex. Can retroactively change *everything*,
   including the verified code. (WLFI ProxyAdmin; Base ProxyAdmin owner; Sui framework
   upgrade.)

The audit deliverable is this ladder, populated: for **every** state-mutating privileged
function, record `(who, blast radius, timelock?, exit window?)`. The ranking matters
because the mitigations that make rung 1 acceptable are useless at rung 5.

---

## The apex corollary: "verified ≠ running" (the assumption-breaker)

Rung 5 (upgrade) breaks the foundational premise of *all* code auditing — that the code you
read is the code that runs. **WLFI is the proof:** the verified, published implementation
(`0x3722…`) was not the live one (`0x59a3…`, V3) at the time of review. An upgradeable proxy
makes every other finding conditional:

> **Every Bucket 1–6 verdict on an upgradeable system carries a silent suffix:
> *"…as of the current implementation, until the upgrade key says otherwise."***

This is why locating the governance ceiling must come **first**, before the mechanism
audit: it sets the expiry date on everything else you conclude. Always resolve the live
implementation (EIP-1967 impl slot, system-package version, respected-game-type) before
reading code, or you may be auditing a ghost.

---

## The dual valence (why this is not a "finding")

These powers are **simultaneously** the largest single point of failure **and** the
primary safety backstop. The same key that could rug is the key that:
- stops a live fault-proof exploit (Base Guardian blacklists the malicious game),
- claws back stolen funds (WLFI `adminBurn` on a hacker; Sui `DenyCap` freeze),
- halts a draining bug before it spreads (any `pause`).

Base's entire stage-1 model is *deliberately* "the fault proof is sound **OR** the Guardian
is honest." So the audit verdict must name **both** valences and refuse to collapse them:

> Not "the owner can drain" (alarmist) and not "the owner is trusted" (negligent), but:
> **"value X is reachable by role R via power P; R is an N-of-M multisig with/without a
> T-second timelock and with/without a user exit window."** State the fact; let the reader
> price the trust.

---

## What actually makes a ceiling safe (the mitigations ladder)

The governance ceiling is not removable in most live systems, but it is *conditionable*.
Ranked by how much they constrain the apex:

1. **Raw EOA owner** — worst; one key, instant, unbounded. (Audit: flag loudly.)
2. **Multisig** — raises the bar to N-of-M key compromise. (WLFI 3-of-5; Base Security
   Council.) Necessary, not sufficient.
3. **Multisig + timelock** — delays the override so it is *observable* before it lands.
4. **+ user exit window** — users can withdraw *before* a malicious upgrade takes effect.
   This is the single most important property: it converts "trust the key" into "trust your
   own ability to leave." (The OP Stack air-gaps — `PROOF_MATURITY_DELAY`,
   `DISPUTE_GAME_FINALITY_DELAY` — partially serve this for in-flight withdrawals.)
5. **Removal / immutability** — the ceiling is raised to the protocol itself (true stage-2;
   Litecoin's "governance" is a slow social hard-fork, the closest to ceiling-removal in
   the corpus, at the cost of upgrade agility).

The presence or absence of **timelock + exit window** is the highest-signal,
*mechanically checkable* governance fact. It is the difference between a backstop and a
backdoor, and it does not require understanding the domain to verify.

---

## How to locate it (a front-door procedure, like §10's three questions)

Before — or in parallel with — the bucket sweep:

1. **Enumerate authority.** Grep for `onlyOwner`, `onlyGuardian`, `_assertOnly*`,
   `proxyAdmin`, `upgradeTo`, `pause`, `DenyCap`, committee/governance gates. List every
   privileged entry point.
2. **Resolve the live code & roots.** EIP-1967 impl slot, ProxyAdmin owner, Guardian
   address, system-state version, respected game type. *Confirm verified == running.*
3. **Build the blast-radius ladder.** For each privileged function: who, blast radius
   (1–5), timelock?, exit window?
4. **Trace key custody.** Is the apex role an EOA, a multisig (threshold?), a timelocked
   multisig, a DAO, or the protocol itself?
5. **State both valences.** Backstop power *and* failure-mode, as a fact, per the dual-
   valence rule above.

The output is one paragraph that frequently dominates the risk picture more than any
single mechanism finding — and it is the part the project's own threat model usually states
least clearly.

---

## Where this sits relative to the rest of the methodology

Three orthogonal coordinates now locate a system's trust; each moves *down/outward*, away
from the code that looks in charge:

| Coordinate | Question | Source |
|-----------|----------|--------|
| **Equivalence (6b)** | What must be believed equal, and who discharges it? | Retrospective §9 |
| **Conservation floor** | Where is "no value created" enforced, and how strong? | Retrospective §11 |
| **Governance ceiling** | Who can change/replace the whole mechanism, and how reversibly? | *this note* |

§9 and §11 audit the mechanism. This note audits the authority over the mechanism. A
system can ace both lower coordinates — Sui's coins are *unforgeable by the type checker* —
and still be capped by a framework-upgrade key. **The ceiling is independent of the floor,
and usually lower than the cryptography suggests.**

> **"Trustless" names the mechanism. The honest question is: trustless *until whom*?**

---

## What this is and isn't

A defensive, public-information synthesis across open-source targets at named commits. It
demonstrates **no** vulnerability: every governance power cited is a documented, intended
administrative capability, and several are essential safety backstops. The contribution is
methodological — a repeatable procedure for finding and stating the privileged-authority
ceiling that bounds every other assurance claim, and the corpus evidence that this ceiling
is nearly universal and frequently the dominant risk. Companion to
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` (§9, §11), `AUDIT-WLFI` (the verified≠running
instance), and `AUDIT-BASE-SIX-BUCKET.md` (the Guardian-backstopped stage-1 instance).
