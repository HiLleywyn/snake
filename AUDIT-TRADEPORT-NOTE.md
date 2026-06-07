# TradePort (NFT marketplace, Aptos) — auditability note + ABI-derived trust-surface map

**Target:** TradePort (`tradeport.xyz`), multichain NFT marketplace (Sui/Aptos/Movement/Supra/NEAR/
Stacks). Aptos contract `0xe11c12ec495f3989c35e1c6a0af414451223305b579291fc8f3d9d0575a23c26`
(V1 modules `listings`,`biddings`; V2 `listings_v2`,`biddings_v2` — "same account, operate
independently"). **Posture:** defensive, passive (public on-chain ABI only). No exploit.

## Auditability: closed-source — on-chain bytecode only
No public source repo found; TradePort/indexer.xyz ship SDKs/APIs but not the Move contracts. So this
is an **auditability-floor** case (like `AUDIT-LETSBONK-LAUNCHLAB.md`, `AUDIT-DEFIAPP-NOTE.md`): the
escrow/authorization/fee logic lives in unviewable bytecode. **A clean source-level audit is not
possible from public artifacts**, and I do not reverse-engineer bytecode to hunt exploits. What *is*
public and passive is the **ABI** (entry-function surface), pulled from the Aptos node API — richer
than an IDL because it carries typed signatures.

## Trust-surface map (from the live ABI)
**`listings_v2`:** `list_token(Object<Token>, price)`, `list_tokens`, `relist_token`,
`buy_token(Object<Listing>)`, `buy_tokens`, `unlist_token`. **`biddings_v2`:**
`token_bid(Object<Token>, price)`, `collection_bid(Object<Collection>, price)`,
`accept_token_bid`, `accept_collection_bid`, `cancel_token_bid`, `cancel_collection_bid`, and the
**compound** `unlist_and_accept_token_bid` / `unlist_and_accept_collection_bid` (touch a `Listing`
*and* a `Bid` in one tx). V1 mirrors these on the legacy token-v1 (string-id) model. Listings/bids
are first-class Aptos **objects** (`Object<Listing>`, `Object<TokenBid>`), so escrow is object-held.

## Invariants a source/bytecode audit MUST check (the EV targets)
None verifiable from the ABI; recorded so a deeper review (verified source or devnet) can drive them:
1. **Escrow conservation (NFT side):** a listed token is held by the marketplace and goes to exactly
   one party — buyer (`buy_token`), bidder (`accept_*`), or back to seller (`unlist_token`); never
   double-released. The Aptos-object model helps (the token object has one owner), but the transfer
   authorization is in bytecode.
2. **Escrow conservation (funds side):** bid funds escrowed on `*_bid`, returned on `cancel_*`,
   paid out on `accept_*` — each exactly once, no residual.
3. **Payment split = price:** on a sale, `seller_proceeds + royalty + marketplace_fee == buyer_paid`
   (no rounding leak, royalty read from the token's on-chain royalty, fee bounded).
4. **Authorization:** `unlist_token`/`cancel_*` only by the lister/bidder; `accept_*` only by the
   current token owner; `buy_token` by anyone with payment. (NFT-marketplace bugs are usually here.)
5. **Compound-op safety (highest value):** `unlist_and_accept_*` atomically unlist a listing and
   accept a bid — verify it can't be used to release the NFT *and* keep/double-spend escrow, that
   both objects belong to the caller's right role, and that it can't accept a stale/cancelled bid.
6. **V1/V2 isolation:** "same account, operate independently" — confirm V1 and V2 escrows can't be
   cross-drained (a V2 op acting on a V1-held token or vice versa).

## Verdict
**No finding — and none derivable from public artifacts** (closed-source; ABI only). Mapped the real
on-chain trust surface and the invariant checklist for a deeper review. The compound
`unlist_and_accept_*` ops and the payment-split/authorization paths are where an NFT-marketplace bug
would live and are the right targets *if* TradePort publishes source or a verified contract. Nothing
routed (nothing found). Same class as the other closed-source targets in the corpus.
