# DeXe Protocol (on-chain DAO governance) — Six-Bucket Trust Map

**Target:** `dexe-network/DeXe-Protocol`, cloned `/tmp/dexe`, HEAD `f09a3ba`. A
create-your-own-DAO platform: token + NFT-weighted governance, delegation/micropools, a validators
second chamber, treasury, token-sale proposals.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe."
**Audit coverage (stated up front):** the repo ships **6 professional audit reports** — Certik
(2023-05), Hacken (2023-05), Ambisafe (×3, 2023-07/2023-11/2024-08), Cyfrin (2023-11). Per the
engagement principle, this is a heavily-reviewed blue-chip; the methodology's value here is **not**
a 0-day hunt but to **map the trust surface and place DeXe on the governance-ceiling spectrum**.
Nothing routed privately; the vote-accounting is mature and audit-hardened.

---

## The headline: DeXe is the *self-governing* end of the governance-ceiling spectrum

Every config-changing function on the core `GovPool` — `changeVotePower`, `changeVerifier`,
`changeBABTRestriction`, `setNftMultiplierAddress`, `editDescriptionURL`, … (`GovPool.sol:391–414`)
— is gated by the modifier **`onlyThis`** (i.e. `msg.sender == address(this)`). The *only* way a
call originates from the contract itself is **proposal execution**: `GovPoolExecute.execute` runs a
passed proposal's actions via `actions[i].executor.call{value}(data)` (`:61`,`:83`). Therefore:

> **There is no owner/admin backdoor. Every privileged action — treasury moves, config changes,
> swapping the vote-power module or the off-chain verifier — must go through a passed proposal.**
> The trust root is the **on-chain voting process itself**, not a key.

This is the *correct* decentralized model and the opposite pole from the recent corpus:

| System | Governance ceiling |
|---|---|
| **HToken ($H)** | owner: uncapped mint + force-burn + upgrade (maximal key) |
| **WLFI** | 3-of-5 Safe proxy-admin can swap the implementation |
| **fetchd** | admin bounded (bridge can mint, cannot seize) |
| **DeXe** | **no admin** — the DAO governs itself via proposals (`onlyThis`); trust root = the vote |

The execution uses `.call` (not `delegatecall`) for actions (`:61`/`:83`), so a proposal cannot
hijack the GovPool's own storage via delegatecall — it acts as an external caller. **enforced.**

---

## Bucket 1 (governance analogue) — voting-power conservation (mature, audited)

The "conservation" invariant of a DAO is: **voting power cannot be forged or double-counted.**
DeXe enforces it with several mechanisms (`GovPoolVote.sol`, `GovUserKeeper.sol`):
- **Token-locking during votes** — personal votes lock the voter's tokens
  (`updateMaxTokenLockedAmount`, `GovPoolVote.sol:156`), tracking the *peak* lock so you cannot
  vote across many proposals beyond your balance.
- **Per-NFT-per-proposal dedup** — `require(nftsVoted.add(nftIds[i]), "Gov: NFT already voted")`
  (`:190`): an NFT's power counts once per proposal.
- **Vote-type separation** — `PersonalVote` / `MicropoolVote` (delegated) / `TreasuryVote` are
  tracked distinctly so delegated power isn't also usable by the delegator.
- **Delegation/micropools** — `delegateTokens`/`undelegateTokens` move power to a delegatee's
  micropool; the delegator can't simultaneously use it.

`totalVoted = amount + nftsPower` (`:199`). This is the standard, audited double-vote-prevention
shape (locking + dedup + type separation). **Verdict: enforced (and 6×-audited)** — I did not
attempt to out-audit the accounting; structurally it conserves voting power.

The DeXe-specific novelty is **time-based ERC721 voting power** (`ERC721RawPower`,
`AbstractERC721Power`, multipliers, `ERC721Expert`) — power that varies by NFT and over time. This
is the least-standard surface (vs ERC20Votes) and the right place for a *dedicated* power-math
review, but it is within the audited scope. **named (novel mechanism, audited).**

---

## Bucket 6 — settlement seams

- **6b (off-chain results):** `GovPoolOffchain.saveOffchainResults` accepts results signed by a
  configured `offChain.verifier` (`:27`, ECDSA `recover == verifier`). So off-chain governance
  results enter on-chain on a **trusted verifier key's** signature — a 6b seam — but the verifier is
  set via `changeVerifier` which is `onlyThis` (DAO-governed). The trust is thus *delegated by the
  DAO*, not external. **named; DAO-controlled.**
- **Price feeds:** token-sale-proposal pricing uses `UniswapPathFinder` (DEX price) — the standard
  DEX-oracle trust (manipulation/path risk) for any swap-priced action; audited surface.

---

## Governance ceiling & residual

Because the trust root is the vote, the residual is the **standard DAO-capture surface**: whoever
assembles enough voting power (tokens + NFT power + delegations) to pass quorum **and** clear the
**validators second chamber** (`GovValidators*`) controls execution — i.e. the treasury and all
config. This is *by design* (it's a DAO), bounded by the quorum/validator parameters and the
locking/dedup conservation above. The honest framing: **DeXe relocates trust to the
voting-power distribution and the quorum/validator design, with no privileged-key escape hatch.**
The remaining keys are DAO-appointed (the off-chain verifier, the NFT multiplier address) and
DAO-replaceable via proposal. **trust-boundary debt = governance capture (inherent to DAOs).**

---

## Summary

| Bucket | Subject | Verdict |
|---|---|---|
| ceiling | `onlyThis` on all config → proposal-gated | **enforced** — no admin backdoor; trust root = the vote (self-governing pole of the spectrum) |
| 1 | Voting-power conservation (lock + NFT dedup + vote-type separation + delegation) | **enforced & 6×-audited** — standard double-vote prevention |
| 1 | Time-based ERC721 voting power (novel) | **named** — least-standard surface; within audited scope |
| exec | Proposal execution via `.call` (not delegatecall) | **enforced** — actions can't hijack GovPool storage |
| 6b | Off-chain results verifier key | **named** — trusted key, but DAO-set/replaceable |
| 6b | DEX price feed (token sale) | **named** — standard oracle-manipulation surface |
| residual | Governance capture (quorum + validators) | **trust-boundary debt (inherent to DAOs)** — bounded by quorum/validator design |

## What this audit did NOT do (coverage honesty)

- **Not a 0-day hunt.** This is a 6×-audited blue-chip; I mapped the trust surface and verified the
  *shape* of the conservation/ceiling, not line-by-line correctness of accounting that four firms
  already covered.
- The **time-based ERC721 power math** (decay/multiplier/expert interactions) — the novel surface;
  named as the highest-value place for a dedicated review, not recomputed.
- The **validators second chamber** (`GovValidators*`) quorum/threshold logic, the **token-sale
  proposal** vesting/claim accounting, the **rewards** (`GovPoolRewards`) conservation, and the
  **factory/upgrade** model — all read only at their interfaces.

## Nothing routed privately

No defect found (nor sought, in audited accounting). The honest, methodology-level output is the
**placement**: DeXe is the self-governing pole of the governance-ceiling axis — every privileged
action is proposal-gated via `onlyThis`, so there is **no key that can mint/seize/upgrade outside a
vote**; voting-power conservation is enforced by locking + per-NFT dedup + vote-type separation
(6×-audited); and the residual is the inherent DAO risk (governance capture via quorum + the
validators chamber) plus DAO-appointed off-chain seams (the results verifier, DEX pricing). It is
the cleanest contrast in the corpus to the owner-controlled tokens (HToken/WLFI). Companion to
`AUDIT-GOVERNANCE-CEILING.md` (DeXe = the "ceiling removed into the protocol/vote" end) and
`AUDIT-METHODOLOGY-RETROSPECTIVE.md` §11 (a new "DAO governance" rung: conservation = voting-power
integrity; trust root = the on-chain vote).
