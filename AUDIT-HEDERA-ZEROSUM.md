# Hedera (HBAR) — zero-sum transfer-list conservation + council governance audit (clean)

**Target:** `hashgraph/hedera-services`, sparse clone `/tmp/hedera`
(`hedera-node/hedera-token-service-impl`). Audited the **crypto-transfer conservation validator**
(`validators/CryptoTransferValidator.java`) and the overflow-safe adjustment primitive
(`handlers/transfer/customfees/AdjustmentUtils.java`). **Posture:** defensive; no exploit, no PoC.
**Result: clean — no finding, nothing to disclose.**

Chosen for two distinct contributions: (1) a **conservation primitive new to the corpus** — the
*explicit zero-sum transfer list*: a transaction carries the complete list of balance adjustments and
the protocol rejects it unless they net to exactly zero; and (2) a distinct **governance-ceiling
point** — a permissioned, identity-bound *enterprise council* (neither anonymous multisig nor token
stake-vote).

## Conservation floor — the transaction *is* a balanced double-entry journal (Bucket 1 + 5)
A Hedera `CryptoTransfer` carries a list of `AccountAmount` adjustments (debits negative, credits
positive). The validator enforces conservation **on the transaction structure itself**, before any
state change:
- **HBAR:** `validateTruePreCheck(isNetZeroAdjustment(acctAmounts), INVALID_ACCOUNT_AMOUNTS)`
  (`CryptoTransferValidator.java:77`).
- **Each fungible token:** `validateTruePreCheck(isNetZeroAdjustment(fungibleTransfers),
  TRANSFERS_NOT_ZERO_SUM_FOR_TOKEN)` (`:295`) — per-token, so no cross-token netting.
- `isNetZeroAdjustment` (`:342-347`): sums every amount with **`BigInteger`** (so the summation itself
  can never overflow) and requires `net.equals(ZERO)`.
So **a transfer's credits must exactly offset its debits** — the transaction can neither create nor
destroy value, by construction, checked before application. Supporting guards: every entry must have a
valid `AccountID` (`INVALID_ACCOUNT_ID`/`INVALID_TRANSFER_ACCOUNT_ID`) and **no account may repeat**
(`ACCOUNT_REPEATED_IN_ACCOUNT_AMOUNTS`, `:73`,`:~305`) — so adjustments can't be split to evade a
per-account check. The actual *application* (`AdjustHbarChangesStep`/`AdjustFungibleTokenChangesStep`)
uses **`Math.addExact`** (`AdjustmentUtils.java:254`, "throws an exception if the result overflows")
when mutating balances, and checks sufficiency — so applying the (already-balanced) list still can't
silently wrap. **enforced.**

## Where this sits among conservation models
| Model | Who supplies the balance changes | Conservation check |
|---|---|---|
| **Hedera** | the **sender**, as an explicit adjustment list in the tx | protocol: list must **net to zero** (per asset) |
| Cardano | the tx's inputs/outputs | `consumed == produced` |
| Tezos | produced by execution (receipts) | typed source/sink; `transfer_n` Σin=Σout |
| Stacks | sender declares *bounds*; VM records actuals | actual movements within declared bounds |
| UTXO (BTC/LTC/Avalanche) | inputs/outputs | `out ≤ in` |
Hedera is the **explicit-balanced-journal** variant: closest to Cardano's `consumed == produced`, but
in an *account* model where the sender writes the full double-entry into the signed transaction and the
node validates it sums to zero. New supply enters only through *separate* `TokenMint`/`TokenBurn`
handlers (gated by the token's supply key) — crypto-transfer is strictly conservative. Distinct from
Stacks (which checks *bounds* on what a contract did) and from Tezos (which *produces* the receipts):
here the balanced journal **is the transaction**, supplied and signed by the sender, validated zero-sum.

## Governance ceiling — the enterprise council (a distinct point)
Hedera is governed by the **Hedera Governing Council** — a term-limited body of ~30+ named
enterprises that controls node admission, treasury, and fee schedules, and authorizes software
upgrades. This is a **third kind** of governance ceiling, between the corpus's existing poles:
- not an *anonymous multisig* (WLFI's 3-of-5 Safe) — the signers are identity-bound, legally
  accountable entities;
- not *token-stake self-amendment* (Tezos) or *proposal-by-vote with no admin key* (DeXe) — it is
  *permissioned/federated*, not open-stake.
So on the §4c spectrum Hedera is a **federated-council** ceiling: more accountable than an anonymous
key, less permissionless than stake governance. I place it from public documentation + the
permissioned node/admin structure in the codebase; I did **not** line-audit the upgrade/admin
authorization path (named, not opened).

## Consensus (named, not opened)
Hedera's conservation-of-agreement layer is **hashgraph aBFT** (gossip-about-gossip + virtual voting)
— an *asynchronous* BFT family distinct from the HotStuff/Jolteon (MonadBFT) and Tendermint
(IBC/Cosmos) consensuses audited elsewhere. The safety analog (no conflicting finalization) lives
there, not in the token service; orthogonal to this validity floor and not opened.

## What this audit did NOT cover (coverage honesty)
- **`TokenMint`/`TokenBurn`** — the only supply-changing handlers (gated by the supply key); the
  crypto-transfer path I audited is strictly zero-sum, but the mint/burn authorization is a separate
  surface, not opened.
- **NFT transfers & custom fees** — the `AdjustmentUtils` custom-fee assessment (royalty/fractional
  fees) generates *additional* balanced adjustments; I verified the zero-sum invariant and the
  overflow-safe add, not the full custom-fee assessment logic.
- **The application steps** (`AdjustHbarChangesStep` et al.) — read the overflow primitive and the
  validation; did not exhaustively trace every balance-mutation path.
- **Hashgraph aBFT consensus** and the **council upgrade/admin authorization** — named above, not
  opened.

## Self-check (epistemic hygiene)
- **Recompute, not trust the name.** I read `isNetZeroAdjustment` and confirmed it sums with
  `BigInteger` (overflow-proof) and gates on `== ZERO` (exact), that the zero-sum check is applied
  **per token** (not cross-asset), and that the no-repeated-account guard prevents adjustment-splitting.
  I confirmed application uses `Math.addExact` rather than raw `+`.
- **Exposure to reversal.** The verdict covers the *crypto-transfer* path; it would not catch a supply
  bug in `TokenMint`/`TokenBurn` (separate, not opened). It assumes the validated list is exactly what
  gets applied (the application steps consume the same `AccountAmount` list — I read the primitive, not
  every step). The governance/consensus placements are documentation-grounded, not full audits.

## Verdict
**Clean.** Hedera enforces value conservation at the transaction structure: a crypto-transfer's
`AccountAmount` adjustments must net to exactly zero (per asset, `BigInteger`-exact, with no repeated
accounts), and balance application uses overflow-throwing `Math.addExact` — so a transfer can neither
create nor destroy value, and new supply enters only via separate supply-key-gated mint/burn. It adds
the **explicit-balanced-journal** conservation variant (the sender signs the full double-entry; the
node checks it sums to zero) and a **federated enterprise-council** governance ceiling (between
anonymous-multisig and open-stake). No untrusted-input→value path in the audited surface; nothing to
disclose. Residuals: `TokenMint`/`TokenBurn` authorization, custom-fee assessment, and the hashgraph
aBFT layer.
