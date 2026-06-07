# IBC ics20 (Cosmos cross-chain transfer) — light-client settlement-seam audit (clean)

**Target:** `cosmos/ibc-go`, sparse clone `/tmp/ibc`. Audited the **ics20 transfer conservation**
(`modules/apps/transfer/keeper/relay.go`) and the **light-client authentication gate** that makes a
received packet trustworthy (`04-channel` `RecvPacket` → `07-tendermint` `VerifyMembership` /
`verifyHeader`). **Posture:** defensive; no exploit, no PoC. **Result: clean — no finding, nothing to
disclose.**

Chosen to close the residual I flagged in `AUDIT-COSMOS-BANK.md` (the Cosmos cross-chain seam) **and**
because it adds a **fourth settlement-seam trust model** to the spectrum built in the capstone (§4f):
**light-client / native verification** — distinct from validity-proof (zkSync), fraud-proof
(Optimism), and multisig+dispute (Hyperliquid).

## Conservation across the seam — escrow-or-burn on send, unescrow-or-mint on receive (1:1)
`relay.go` implements the "lock on home, voucher abroad" model:
- **Send** (`sendTransfer`): if this chain is the token's **source**, `EscrowCoin` (`:99`,`:297`) —
  `BankKeeper.SendCoins(sender → escrowAddress)` and `TotalEscrowForDenom += coin` (`:304-306`). If
  this chain is **not** the source (the coin is a foreign voucher), `BurnCoins` it (`:88`).
- **Receive** (`OnRecvPacket`, `:113`): if this chain is the source (tokens coming home),
  `UnescrowCoin` (`:163`,`:313`) — `SendCoins(escrowAddress → receiver)` and `TotalEscrowForDenom −=`
  (`:323-325`). If not the source (a new foreign token), `MintCoins` the voucher (`:187`).
- **Refund** (timeout / ack-error, `:243`): reverses exactly — mint-back or unescrow-back to sender.
So the global invariant is **`escrowed[denom] on the home chain == Σ vouchers minted across all
counterparties`**: a native token is *locked* in escrow precisely while a matching voucher exists
elsewhere; vouchers coming home are burned abroad and unescrowed at home, 1:1. **enforced.**

## The conservation backstop — the bank-layer underflow guard (connection to AUDIT-COSMOS-BANK)
`UnescrowCoin` carries a strikingly honest comment (`:315-319`): an over-unescrow *"is only expected
given an unexpected bug or a malicious counterparty module… A malicious counterparty module could
drain the escrow address by allowing more tokens to be sent back than were escrowed."* The crucial
point: that drain attempt **fails at the bank layer** — `SendCoins(escrowAddress → receiver)` runs
`subUnlockedCoins`, whose `SafeSub`/`hasNeg` guard (`AUDIT-COSMOS-BANK.md`) returns
`ErrInsufficientFunds` once the escrow account is empty. So **a chain can never unescrow more native
tokens than it actually escrowed**, regardless of what a Byzantine counterparty claims. This is the
defense-in-depth that makes the seam's blast radius bounded — and it is *exactly* the by-construction
bank conservation I verified upstream, now load-bearing for the cross-chain case. **enforced.**

### Blast-radius isolation (why a compromised counterparty can't mint your native token)
`OnRecvPacket` only *mints* when this chain is **not** the source (foreign vouchers); it *unescrows*
(bounded by the escrow balance) when it **is** the source. So even a fully-Byzantine counterparty can
at most mint unlimited vouchers **of its own denom** on your chain (redeemable only back to it — its
problem), and **cannot** mint your native token or drain your escrow beyond what was locked. The
conservation damage from a bad counterparty is **isolated to that counterparty's own token.** This is
the key reason IBC's trust is per-channel/per-counterparty, not systemic.

## The authentication gate — light-client verification (the 4th settlement model)
A received packet triggers mint/unescrow, so its authenticity is the whole game.
`04-channel/keeper/packet.go:RecvPacket` (`:100`) calls `VerifyPacketCommitment` (`:152`), which
proves — via the client's `VerifyMembership` (`07-tendermint/light_client_module.go:103`) — a **Merkle
proof that the packet commitment exists in the counterparty's state** at a proven height. That height's
root (`ConsensusState`) was only trusted because `verifyHeader`/`UpdateClient`
(`07-tendermint/update.go:45,107-115`) accepted the header via Tendermint light-client rules: the new
block's own commit needs **>2/3 of its validators**, and the fast update needs a **`TrustLevel`
proportion (default 1/3) of the *previously-trusted* validator set** to overlap and sign
(`light.Verify(..., cs.TrustLevel, ...)`; `TrustLevel` validated at `client_state.go:125`).
**Misbehaviour** (two conflicting signed headers) **freezes the client** (`misbehaviour.go`,
`VerifyCommitLight`) — the fraud-response analog.

So IBC's settlement trust is: **the counterparty chain's own consensus is honest (>2/3 of *their*
validators non-Byzantine), verified cryptographically on-chain** (signatures + Merkle membership). No
extra trusted committee is introduced — unlike a multisig bridge, the trusted set *is* the
counterparty's validator set.

## Connections to the corpus — settlement-seam spectrum, now 4-wide
| Model | Output trusted because… | Safety assumption | Example |
|---|---|---|---|
| Validity proof | a SNARK proves it | 0-of-N (cryptographic) | zkSync |
| Fraud proof | nobody disproved it in window | 1-of-N honest watcher + L1 liveness | Optimism |
| **Light client (IBC)** | **counterparty consensus signed it, verified on-chain** | **>2/3 of the *counterparty's* validators honest** | ibc-go |
| Multisig + dispute | a trusted committee signed it | >2/3 of a *separate* committee | Hyperliquid Bridge2 |
IBC sits between fraud-proof and multisig: it needs an honest *counterparty validator supermajority*
(like a multisig, but the "committee" is the counterparty's real validator set, not an appointed one)
and verifies them with native cryptography (like a proof, but verifying *consensus signatures* rather
than *execution validity*). It is the most "trust-minimized among equals" model — no privileged bridge
operator — at the cost of trusting each counterparty's consensus. The recurring optimistic-settlement
skeleton (request→verify→act, with a freeze path) holds here too (packet→proof→mint, misbehaviour
freeze).

## What this audit did NOT cover (coverage honesty)
- **`VerifyMembership` Merkle internals** (ICS-23 proof spec) and the connection/channel handshake
  state machine — read at the call/trust level, not the proof-bytes level.
- **The full `light.Verify` / `VerifyCommitLightTrusting`** signature math (in CometBFT, not ibc-go) —
  the deepest cryptographic residual (the analog of zkSync's circuit / Optimism's FPVM: here it's the
  Tendermint commit-verification, which is well-studied but not re-derived here).
- **ics20 v2 / multidenom, PFM (packet-forward), and async acks** — newer transfer features.
- **The `TotalEscrow` vs escrow-balance reconciliation** (historically an x/bank invariant; with that
  framework removed per `AUDIT-COSMOS-BANK.md`, the bank underflow guard is now the live backstop —
  noted as the same conserve-by-construction shift).

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I traced the actual dependency mint/unescrow ⟸ `OnRecvPacket`
  ⟸ `RecvPacket` ⟸ `VerifyPacketCommitment` ⟸ light-client `VerifyMembership` ⟸ a `ConsensusState`
  established only via `verifyHeader` with `TrustLevel`. I confirmed the escrow drain is bounded by the
  bank `subUnlockedCoins` underflow guard rather than assuming the comment's claim.
- **Exposure to reversal.** The verdict rests on the counterparty-consensus assumption being the
  *intended* trust (it is — that's IBC's design), and on no mint path existing that runs without the
  channel proof (I read the single `RecvPacket` gate; I did not enumerate every app that could call the
  transfer keeper directly). The deepest residual — soundness of the Tendermint commit verification —
  is named, not cleared.

## Verdict
**Clean.** IBC ics20 conserves value across chains by escrow-or-burn on send and unescrow-or-mint on
receive (1:1, with `TotalEscrowForDenom` tracked), backstopped by the bank-layer underflow guard so a
chain can never unescrow more than it locked, and isolated so a Byzantine counterparty can only inflate
*its own* voucher denom — never your native token or escrow. Authenticity rests on **light-client
verification** — the counterparty's own validator supermajority, checked cryptographically on-chain —
which I record as the corpus's **fourth settlement-seam trust model**, distinct from validity-proof,
fraud-proof, and multisig. No untrusted-input→value path found; nothing to disclose. The named
irreducible trust is each counterparty chain's consensus honesty (and the CometBFT commit-verification
soundness underneath it). Next pull: ICS-23 membership-proof internals and ics20-v2/PFM.
