# Seaport — marketplace settlement & the conduit approval-delegation residual

**Scope.** Seaport (OpenSea's NFT/token marketplace settlement protocol, v1.6) — the offer/consideration
settlement engine, the **conduit** approval-delegation system, the **zone** order-gating hook, and the
counter-based cancellation (`ProjectOpenSea/seaport` + the `seaport-core`/`seaport-types` submodules).
This adds a **new residual** to the corpus: *approval delegation* — users grant token approvals to a
long-lived shared **conduit**, not to the protocol, so *channel control = approval control*. Public
source, read-only, recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect
found**; the conduit-owner concentration and zone trust are characterized factually (both are documented
in-source).

**Sources (verbatim, line refs):** seaport-core `lib/{Consideration, OrderFulfiller, OrderCombiner,
Executor, ZoneInteraction, Verifiers, SignatureVerification, CounterManager, ConsiderationBase}.sol`,
`conduit/{Conduit, ConduitController}.sol`; seaport-types `lib/Consideration{Structs,Enums}.sol`;
seaport `Seaport.sol`.

---

## 0. The one-paragraph result

Seaport's settlement is clean and *conserve-by-matching*: every fill transfers each **offer** item from
the offerer and requires **every consideration** item to be fully met or the whole batch reverts
(`unmetAmount != 0 → revert`). Seaport itself is **immutable** — a repo-wide search finds no owner, no
upgrade path, no pause, no admin on the settlement engine; the only constructor arg is the conduit
controller. So the protocol is a maximal "delete the trust" instance like Uniswap v2. But the trust didn't
vanish — it **moved one layer out, to the conduit**, and that is the dominant and genuinely novel residual.
Users don't approve Seaport; they approve a long-lived, shared **`Conduit`**, and Seaport is merely an
*open channel* on it. A conduit has an **owner** (held in the `ConduitController`) who can **arbitrarily
open or close channels** — and **any open channel can call `execute` to move *any* tokens the conduit has
approval over, from any holder, immediately, with no per-order signature or fill.** The source says so in
as many words: *"a malicious or negligent owner can add a channel that allows for any approved tokens to be
taken immediately — be extremely cautious what conduits you give token approvals to."* The systemic concern
is concentration: most users have approved OpenSea's *one* canonical conduit, so its owner key is a
single point under a huge approval base — a risk *independent of Seaport's own immutability*. Two smaller
trusted surfaces complete the picture: the **zone** (a per-order external hook that can veto a restricted
order both before and after transfer — censor/DoS), and the **counter** (a cheap mass-cancel that
invalidates all of an offerer's signed orders at once via a large quasi-random jump). So the Seaport law:
*the settlement engine is immutable and conserves by matching, but the residual is approval delegation —
the user's standing token approvals live on a shared conduit whose owner can mint a channel that spends
them, so "trustless marketplace" means trustless in the *matching*, and trust-the-conduit-owner in the
*custody*.*

---

## 1. Settlement — conserve-by-matching. **Immutable, sound.**

An order is `OfferItem[]` + `ConsiderationItem[]` with an `orderType` (FULL/PARTIAL × OPEN/RESTRICTED, or
CONTRACT). `_validateAndFulfillAdvancedOrder (OrderFulfiller.sol:87-179)` orders the steps: reentrancy
guard → `_validateOrder` (signature/status) → criteria → **zone pre-auth** → `_updateStatus` →
**`_transferEach`** → **zone post-validation**. `_transferEach (:371-500)` moves **offer items FROM the
offerer** (via the offerer's `conduitKey`) and **consideration items FROM `msg.sender`** (the fulfiller, via
`fulfillerConduitKey`) to each item's recipient, refunding leftover native balance. The conservation
invariant is in `OrderCombiner._performFinalChecksAndExecuteOrders (:950-961)`: after execution **every
consideration item's remaining amount must be zero**, else `_revertConsiderationNotMet`. **Each fill either
fully satisfies every required consideration or reverts** — conserve-by-matching, the same shape as a CLOB
settlement.

**Seaport is immutable.** A repo-wide grep over the core settlement for
`onlyOwner/Ownable/upgradeTo/delegatecall/selfdestruct/pause/proxy/admin` returns **nothing**;
`ConsiderationBase`'s constructor sets the domain separator, chain id, conduit controller, and conduit
creation-code-hash all `immutable` (`:89-111`). **No owner, no upgrade, no pause, no admin on order flow.**

---

## 2. The conduit — the dominant approval-delegation residual. **The novel finding.**

Users approve a long-lived **`Conduit`**, and Seaport is an *open channel* on it. The source's own warning
(`Conduit.sol:32-39`): *"each conduit has an owner that can arbitrarily add or remove channels, and a
malicious or negligent owner can add a channel that allows for any approved ERC20/721/1155 tokens to be
taken immediately."* Mechanically:
- `Conduit.execute(ConduitTransfer[]) (:108-127)` is gated by `onlyOpenChannel` and moves `item.from →
  item.to` for each transfer (ERC20/721/1155). **Any open channel can move any token the conduit is
  approved for, from any holder.**
- `Conduit.updateChannel (:203-219)` flips a channel open/closed — **only callable by the conduit's
  `_controller`** (the `ConduitController`).
- `ConduitController.updateChannel (:126-193)` requires `_assertCallerIsConduitOwner (:483-492)` then calls
  the conduit — so **the conduit *owner* decides which channels exist.** Ownership is two-step transferable.
- Seaport reaches the conduit via `Executor._callConduitUsingOffsets (:447-491)`, deriving the conduit from
  `conduitKey` and requiring the `execute.selector` magic return (when `conduitKey == 0`, Seaport transfers
  directly, no conduit).

**Characterization (factual, defensive):** this is the dominant residual. The user's *standing approvals*
live on the conduit; **whoever owns the conduit can open an arbitrary new channel and drain every token
approved to it, immediately, with no order or signature.** Seaport's immutability does **not** cover this —
it's a separate, owner-mutable surface. The systemic risk is concentration: most users approve OpenSea's
*one* canonical conduit, so its owner key sits under a vast approval base. (ERC20 identifier-malleability in
`_transfer` is explicitly delegated to the calling channel to guard, `:231-234`.)

---

## 3. The zone — trusted per-order gating hook. **Censor/DoS surface.**

For **restricted** orders (`1 < orderType < 4`, caller ≠ zone), Seaport invokes the named `zone` twice:
**pre-execution** `authorizeOrder` (`ZoneInteraction.sol:250-282`) and **post-execution** `validateOrder`
(`:296-370`), each requiring the call's own selector as the magic return (`_callAndCheckStatus :410-462`,
`InvalidRestrictedOrder` on failure). **Characterization:** the zone is a trusted external hook that can
**veto a fill before and after transfer** — a malicious/buggy zone can censor or DoS fills, and since
`validateOrder` runs *after* `_transferEach`, it observes post-transfer state (the reentrancy guard is set).
*Trust in a restricted order = trust in its zone.* The shipped `PausableZone` is one such trusted zone with
a controller that can pause/cancel.

---

## 4. Signature & counter — EIP-712/1271/2098, and a cheap mass-cancel

`_verifySignature (Verifiers.sol:90-137)` skips if `offerer == caller`, else derives the EIP-712 digest,
supports **bulk-order Merkle proofs**, and `_assertValidSignature (SignatureVerification.sol)` tries ECDSA
(incl. EIP-2098 compact) then falls back to **EIP-1271** smart-wallet sigs (0x1626ba7e magic). Cancellation:
`_incrementCounter (CounterManager.sol:37-68)` jumps the offerer's counter by a **large quasi-random** value
(upper bits of `blockhash`), and since the order hash bakes in the current counter, one increment
**invalidates all of that offerer's outstanding signed orders at once** — the large jump deliberately
prevents "re-activating" old orders by guessing back to a prior counter. Per-order `_cancel` is restricted to
the offerer or zone. **Characterization:** mass-cancel is cheap and replay-safe; the EIP-1271 path adds the
same time-varying-validity nuance flagged in the USDC audit (a contract signer's answer can change across
blocks).

---

## 5. Governance — none on Seaport; conduit owners + zones are the standing trust

Seaport has **no owner/upgrade/pause** — a fixed settlement engine with no kill switch or admin override on
order flow. The entire mutable trust surface is pushed outward to **(a) each conduit owner** (controls which
channels can spend user-approved tokens — the high-concentration risk) and **(b) each restricted order's
zone** (can veto fills). The conduit's `_controller` is immutable, but channel *membership* is owner-mutable.

---

## 6. Where this sits in the corpus

Seaport is a **maximal "delete the trust" settlement engine** (immutable, conserve-by-matching — alongside
Uniswap v2, Liquity, the ERC-4337 EntryPoint) that nonetheless carries a **new residual class instance:
approval delegation.** It sharpens a distinction the corpus had blurred: an *immutable protocol* is not the
same as a *trustless user experience* — Seaport can't be upgraded or paused, yet a user's funds are exposed
through the **standing token approval** they granted a *separate, owner-governed* conduit. This is the
custody-side mirror of the §5i "read one layer down" lesson: auditing Seaport's (flawless) settlement says
nothing about the conduit your approvals actually sit on. On the §5e taxonomy it's a **governance-ceiling
sub-type pushed *below* the protocol** — like the USDC freeze key under DeFi (§5i), the conduit owner is a
key *outside* the audited contract that can move funds *inside* the user's wallet, here via the approval
primitive rather than the token's blacklist. The honest user statement: *Seaport's matching is immutable and
conserves perfectly, but you're not trusting Seaport — you're trusting whoever owns the conduit you approved
(who can open a channel that spends your tokens) and, for restricted orders, the zone (which can block your
fill). "Trustless marketplace" is true of the trade and false of the custody.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
