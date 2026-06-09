# Intent settlement — same-chain atomic vs cross-chain optimistic (UniswapX & Across)

**Scope.** Two intent/solver settlement designs chosen to isolate the one variable that defines the
domain: **does settlement need a cross-chain attestation, or not?** UniswapX (`Uniswap/UniswapX` @
`52299e9`, same-chain atomic Dutch-auction intents) and Across (`across-protocol/contracts` @
`334d063`, cross-chain optimistic relayer settlement). Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**;
factual trust-concentration notes flagged for context.

**Sources read (verbatim, line refs against those checkouts):** UniswapX `BaseReactor.sol`,
`DutchOrderReactor.sol`, `DutchDecayLib.sol`, `ExclusivityLib.sol`, `ResolvedOrderLib.sol`,
`Permit2Lib.sol`, `ProtocolFees.sol`, `ReactorStructs.sol`; Across `SpokePool.sol`, `HubPool.sol`,
`Ovm_SpokePool.sol`, `Ethereum_SpokePool.sol`.

---

## 0. The one-paragraph result

This is the **settlement-seam** coordinate (B17 in the corpus) made first-class, and the two
protocols sit at the extremes of it. UniswapX settles **same-chain and atomically**: the filler is
the counterparty, the swapper's input is pulled via Permit2 and the resolved (Dutch-decayed) output
is *forced* to the swapper in the **same transaction** — so there is **no oracle, no attestation, no
residual**; a fill that can't deliver simply reverts, and the swapper's worst case is "my intent
didn't execute." Conservation is by atomicity. Across settles **cross-chain and optimistically**: a
relayer fronts the output to the user on the destination chain *immediately and out of pocket*, but
**nothing on-chain proves that fill happened** — the relayer's right to reimbursement is asserted
*off-chain* by a "dataworker" who builds a Merkle `relayerRefundRoot`, which the HubPool proposes
under a UMA optimistic dispute window and pushes to the SpokePool through the canonical bridge. So
the entire cross-chain trust collapses onto two backstops: **(1) the optimistic-oracle dispute
catching a bad root, and (2) the canonical L1↔L2 messenger** that delivers it. The intent law:
*atomicity is the strongest possible settlement floor (no residual at all); the moment settlement
spans chains, an attestation residual appears, and every cross-chain intent system is ultimately a
bet on who attests the destination fill.*

---

## 1. UniswapX — conservation by atomicity. **No residual.**

The filler is `msg.sender` and the counterparty. `BaseReactor.execute` resolves → prepares → fills
in one atomic call. `_prepare (:92-102)` per order does `_injectFees` → `order.validate(msg.sender)`
→ `_transferInputTokens` (pulls the swapper's input **to the filler** via Permit2), then `_fill
(:106-129)` loops outputs and `output.token.transferFill(recipient, amount) (:116)` **from the
filler** to the swapper's recipient. Input in, output out, same tx.

**The swapper-protection invariant is structural, not a check.** The resolved (post-decay) output
*becomes* the exact `output.amount` that `_fill` is forced to transfer — there is no separate
"received ≥ expected" comparison because the reactor transfers *exactly* the decayed floor for that
timestamp. `DutchDecayLib.decay (:26-42)` returns `startAmount` before decay, `endAmount` after, a
linear interpolation between; outputs are constrained `startAmount ≥ endAmount (:97)` (decays
*downward*, favoring the swapper early). The signed `info.reactor` is checked in
`ResolvedOrderLib.validate (:14-15, InvalidReactor)`, so the swapper's signature only binds to the
one reactor it trusts.

**What the swapper trusts:** (a) the reactor's forced output transfer; (b) **Permit2** for
signature/nonce/deadline — replay protection is *delegated* to Permit2's unordered-nonce bitmap, not
re-implemented (`Permit2Lib.sol:10-18`); (c) an optional swapper-supplied `additionalValidation
Contract` hook (`:18-20`). **What the filler risks:** in callback mode, being unable to source
liquidity — but atomicity means a failed fill just reverts. Fill rights: open, or `exclusiveFiller`
until `exclusivityEnd`, with a non-exclusive override scaling outputs *up* as a price-improvement
penalty (`ExclusivityLib.sol:69-98`).

**Governance:** reactors are **immutable** (no proxy; `permit2` immutable). The only owner power is
swapping the fee controller (`ProtocolFees.sol`, `Owned`), and the fee is **hard-capped at
`MAX_FEE_BPS = 5` (0.05%, `:30,89-91`)** — the owner cannot exceed it or seize swapper funds. **The
conservation floor is hardcoded, not governable.** This is the *lowest* governance ceiling in the
entire corpus.

**Verdict:** the strongest settlement floor possible — atomicity makes the residual *empty*. The
only "oracle" is the EVM transaction itself.

---

## 2. Across — conservation by optimistic cross-chain attestation. **The residual is the destination-fill proof.**

**Origin:** `depositV3 (:583-611)` locks the user's input on the origin chain, assigns `depositId =
numberOfDeposits++`, and emits a deposit event specifying the desired `outputToken`/`outputAmount`/
`destinationChainId`/`fillDeadline`.

**Destination (relayer fronts funds):** `fillRelay (:958-982)` checks exclusivity, computes
`relayHash = keccak256(abi.encode(relayData, destinationChainId)) (:1296)`, and in
`_transferTokensToRecipient (:1648-1682)` moves the **relayer's own** funds:
`safeTransferFrom(msg.sender, recipient, amountToSend) (:1669)` — paid out of pocket, immediately.
Double-fill is blocked by `fillStatuses[relayHash] (:1598)`. **Crucially, the fill is recorded only
as local SpokePool state + a `FilledRelay` event (:1618-1639) — there is no cross-chain proof it
happened.**

**Reimbursement (optimistic, off-chain-attested):** the relayer is *not* reimbursed by the fill. A
**dataworker** observes `FilledRelay` events off-chain, builds a `relayerRefundRoot`, the HubPool
relays it to the SpokePool via `relayRootBundle (:347-353, onlyAdmin)`, and the relayer claims via
`executeRelayerRefundLeaf (:1197-1236)` — which checks **only a Merkle proof** against the stored
root (`:1210`) and a claimed-bitmap (`:1214`).

**The HubPool optimistic layer:** `proposeRootBundle (HubPool.sol:560-594)` pulls a `bondAmount` and
opens `challengePeriodEndTimestamp = now + liveness (7200s default)`. `executeRootBundle (:612)`
requires liveness elapsed, Merkle-verifies the `PoolRebalanceLeaf`, and **`adapter.delegatecall
(:678)`** pushes roots cross-chain. `disputeRootBundle (:715-796)` routes to UMA's
`SkinnyOptimisticOracle`, deletes the disputed proposal, and adjudication moves to UMA's DVM.

**THE RESIDUAL, named precisely:** *nothing on-chain proves the destination fill occurred.* The
relayer's refund right is asserted **off-chain by the dataworker** and admitted to the SpokePool
**only because the root arrived from the HubPool through the canonical bridge** (`onlyAdmin →
crossDomainAdmin`, verified per-chain in `_requireAdminSender`, e.g. `Ovm_SpokePool.sol:215-216`).
So cross-chain trust collapses onto exactly two backstops: **(1) the UMA optimistic dispute window
catching a fraudulent/incorrect refund root, and (2) the canonical L1↔L2 messenger** that delivers
it. This is the textbook B17 settlement seam — and it is *irreducible*: any system that pays a user
on chain B against funds locked on chain A must, somewhere, decide *who attests that chain B was
paid.* Across's answer is "optimistically, with a bonded proposer and a DVM backstop."

**Governance (broad — the trust-concentration note):** HubPool `onlyOwner` holds `setBond`,
`setLiveness`, adapter/route config, `setPaused`, and notably **`emergencyDeleteProposal (:229-233)`**
(kill any in-flight proposal + refund its bond); SpokePool has `emergencyDeleteRootBundle (:361,
onlyAdmin)` (delete an already-relayed root). And `executeRootBundle` relays via
**`adapter.delegatecall`** — so **adapter integrity is fully load-bearing.** Stated factually:
significant trust is concentrated in the HubPool owner and the admin-set adapters; the optimistic
window + canonical bridge are the structural safety nets, not the owner.

---

## 3. Where this sits in the corpus — the settlement-seam axis, fully resolved

The corpus already had a "settlement-seam trust spectrum" (validity-proof → fraud-proof → multisig).
These two protocols *anchor its endpoints* for the intent/solver model:

| | Settlement | What conserves & how | Attestation residual | Governance ceiling |
|---|---|---|---|---|
| **UniswapX** | same-chain **atomic** | output *forced* to swapper in-tx; input via Permit2 | **none** (the EVM tx is the proof) | minimal, immutable, 5bps fee cap |
| **Across** | cross-chain **optimistic** | relayer fronts dest funds; refunded via bonded Merkle root | **destination-fill proof** (off-chain dataworker + UMA dispute + canonical bridge) | broad HubPool owner + load-bearing adapter |

**The sharpened law:** the residual is conserved and only relocates — and **atomicity is the unique
case where it relocates to *nothing*.** UniswapX shows the floor at its theoretical best: when
settlement is atomic, the swapper-protection invariant is *structural* (forced transfer of the
resolved amount), governance is hardcoded out (5bps cap, immutable), and there is no oracle to trust.
The instant settlement spans chains (Across), the attestation residual reappears and dominates — and
it is the *same* optimistic-oracle seam (UMA) that the Polymarket and Azuro resolutions used, now in
service of "did the destination get paid" instead of "did the event happen." This unifies the
prediction-market oracle study with the cross-chain settlement study: **optimistic attestation is one
reusable answer to the universal residual, whether the question is a real-world outcome or a remote
fill.** No exploitable defect; the honest user statement for Across is *"your relayer was paid
optimistically — soundness rests on the dispute window and the canonical bridge, not on a proof."*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
