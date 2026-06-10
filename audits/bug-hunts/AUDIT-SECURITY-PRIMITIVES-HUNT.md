# The security primitives — oracle authenticity, threshold-key unforgeability, slashable-stake conservation

**Why this hunt exists.** Three live systems that are each a **foundational security primitive an entire ecosystem
composes on**: the authenticated price (Pyth), the threshold-signed key (FROST), and the slashable restaked stake
(EigenLayer). A bug doesn't break one app — it breaks the *guarantee everything above assumes*: every DeFi protocol
trusts the price is real, every custody setup trusts the key is unforgeable, every AVS trusts the stake is
slashable. Each is the bottom turtle.

**Defensive, read-only, public/verified-source only. No PoC, no probing, no transaction.** Recompute the primitive's
core guarantee from source and ask "what makes this guarantee hold?" For the crypto, weight the highest-confidence
statements to the concretely-checkable equations. Anything real and live would be stopped and routed for private
disclosure (redacted here). **All three came back clean — no live finding.**

| Target | The primitive | The guarantee a bug would break | Verdict |
|---|---|---|---|
| **Pyth** (HEAD `29239b2`) | pull-oracle authenticated price | a forged or rolled-back price is accepted | **clean** (VAA+data-source+publishTime all bind) |
| **ZF FROST** (HEAD `2016e44`) | threshold-Schnorr signature (RFC 9591) | a malicious signer forges a sig / the Drijvers attack | **clean** (binding factor covers the full commitment set) |
| **EigenLayer** (HEAD `f84a515`) | slashable restaked stake | dodge-slash / over-slash / share-inflation | **clean** (Σ slashed ≤ allocated; the two delays are equal) |

---

## 1. Pyth — authenticated price (a bug accepts a forged or rolled-back price)

**Repo:** `pyth-network/pyth-crosschain`, HEAD `29239b2`. Live on 50+ chains. A forged price must fail at *one of
three* checked gates, and all three hold.

- **Attestation + data-source binding (highest) — clean.** `parseAndVerifyPythVM` verifies the VAA via Pyth's own
  Wormhole receiver — non-empty guardian set, current-or-unexpired, **strictly-ascending guardian index**,
  `ecrecover == guardianSetKey`, quorum `ceil(2n/3)+1` of *distinct* sigs — **and then requires**
  `isValidDataSource(emitterChainId, emitterAddress)` (only the real Pyth emitter). A forged price fails at guardian
  sig OR data-source.
- **Merkle accumulator — clean.** Each price leaf is proven against the VAA-attested root with prefix-separated
  hashing (`0x00` leaf / `0x01` node / distinct empty) — second-preimage resistant, no leaf/node confusion; a price
  not in the attested root can't produce a digest match, and a trailing-bytes check rejects garbage updates.
- **Staleness / publishTime monotonicity — clean.** `updateLatestPriceIfNecessary` writes **only if
  `publishTime > latestPublishTime`** (no rollback); the read-side `getPriceNoOlderThan` uses a *symmetric* diff so a
  far-future timestamp is also rejected as stale.
- **Governance / guardian-set — clean.** Pyth-governance VAAs are sequence-monotonic (`sequence <= lastExecuted`
  reverts), bind magic+module+targetChain; guardian-set rotation must be signed by the *current* set, index `+1`
  exactly, with old-set expiry + replay guard.
- **Fee / decode — clean.** Fee math is checked (overflow reverts); the `int64`/`int32` price/expo casts are
  exact-width two's-complement (intended for negative prices, no truncation).

**No live finding.** Honest by-design notes: `address(0)` guardian-key non-rejection matches upstream Wormhole
(needs a malicious *signed* set); a TWAP equal-slot division-by-zero is a transaction-local revert only on
self-supplied input (slots are guardian-signed, non-craftable).

---

## 2. ZF FROST — threshold-key unforgeability (a bug enables the Drijvers forgery)

**Repo:** `ZcashFoundation/frost`, HEAD `2016e44`. The reference production FROST (RFC 9591) used by wallets/custody
for threshold BTC/Zcash signing; in-repo NCC audit. The strongest crypto-protocol result of the arc — all six
classes implement the spec faithfully, and the highest-confidence statements are the checkable equations.

- **Binding factor / nonce (the ROS/Drijvers defense, highest) — safe.** The binding-factor preimage is
  `Serialize(PK) ‖ H4(msg) ‖ H5(encode_group_commitments(all_commitments))`, then per-signer
  `rho_i = H1(prefix ‖ identifier_i)`. The `H5` hashes **every** participant's identifier + hiding + binding
  commitment — so each nonce is bound to the message **and the full commitment set and the signer's id**, exactly
  the RFC §4.4 construction. No signer can adaptively pick a nonce after seeing others — the historical FROST
  vulnerability class, defended.
- **Commitment / nonce validation — safe.** Nonces from a CSPRNG hedged with the secret share; hiding/binding
  independently sampled; non-identity checks on both commitments; deserialization rejects identity + off-curve
  points; `SigningNonces` is `ZeroizeOnDrop` and round-2 enforces the signer's own commitment matches its nonces (no
  equivocation).
- **VSS / share validation — safe.** `SecretShare::verify` checks `g^share == prod_k phi_k^(i^k)` (the RFC VSS RHS),
  group key = `phi_0`; DKG verifies a round-1 Schnorr PoK before any share use and does round-3 share verification
  with culprit identification — an inconsistent share can't pass.
- **Signature-share verification (identifiable abort) — safe.** `g^z_i == R_i + Y_i·c·lambda_i` with
  `R_i = hiding_i + rho_i·binding_i`; `aggregate` verifies the aggregate first, then `detect_cheater` pinpoints
  culprits on failure.
- **Challenge + aggregation + Lagrange — safe.** `c = H2(R ‖ PK ‖ m)`; `R = Σ hiding_i + Σ rho_i·binding_i` over
  all signers; `z = Σ z_i` then a full Schnorr verify of the result; Lagrange `lambda_i` evaluated at 0 over the
  **actual signer set**, with membership + invert-failure guards.

**No live finding.** Honest caveat: source reading verifies the protocol arithmetic vs the spec — **not**
constant-timeness, RNG quality at integration sites, or the external `k256`/`curve25519` primitives.

---

## 3. EigenLayer — slashable-stake conservation (a bug dodges or over-applies a slash)

**Repo:** `Layr-Labs/eigenlayer-contracts`, HEAD `f84a515` (the `v1.9.0` slashing+redistribution era);
three independent audits of the slashing release in-repo. Live, secures billions in restaked ETH. The conservation
invariants — **Σ slashed ≤ allocated; no slash-dodge; stakers lose ≤ allocated** — all hold.

- **Magnitude / allocation (highest) — safe.** `encumberedMagnitude` is a single per-`[operator][strategy]`
  accumulator shared across *all* operator sets, with every allocation enforcing `encumbered <= maxMagnitude` — so
  **double-allocating the same stake to two AVSs is impossible**. Allocation is slashable only after
  `operatorAllocationDelay`, and stacking on a pending modification is blocked.
- **Slashing correctness — safe (deliberately opposite rounding).** An AVS slashes only *its own* set's
  `currentMagnitude` (can't reach other sets' magnitude or an unregistered operator); magnitude slashed rounds **up**
  (`mulWadRoundUp`, can't dodge via precision loss) and with `wadToSlash <= WAD` can never exceed currentMagnitude;
  on the staker side retained shares round **up** → burned shares round **down**, so **honest stake is never
  over-slashed**. State updates before the `nonReentrant`/`onlyAllocationManager` external call (CEI).
- **Deallocation / withdrawal race — safe (the load-bearing config).** A deallocation does *not* free encumbered
  magnitude immediately — only after `DEALLOCATION_DELAY`; withdrawals apply the magnitude at `slashableUntil`, so a
  slash landing in the window reduces what the withdrawer receives. **The decisive fact: mainnet sets
  `DEALLOCATION_DELAY == MIN_WITHDRAWAL_DELAY_BLOCKS == 100800` blocks (~14d)** — wired in the deployer and asserted
  by a release invariant — and that equality is what stops deallocated/withdrawing stake from escaping an in-flight
  slash.
- **Delegation / shares — safe.** Withdrawable = `depositShares · DSF · slashingFactor`; the DSF "forgiveness" on
  redelegation (`prevDepositShares == 0`) only adjusts the *new* operator's accounting forward — it can't recover
  already-burned shares, so redelegation isn't a slash-escape; historical withdrawals read `maxMagnitude` at the past
  block with current beacon-slashing-factor (current ≤ historical = more slashing = staker-safe).
- **Access / registry — safe.** `slashOperator` is gated to the per-set `getSlasher` (with a config delay); a
  malicious AVS registrar can only block its own registrations, not slash or touch magnitude.

**No live finding.** Honest scope: Solidity logic at this HEAD only — not off-chain slasher governance, the
EigenPod/beacon-proof layer, or deployment/proxy-admin configuration.

---

## Synthesis — the bottom turtles

1. **A primitive's guarantee always reduces to one checkable fact (or equation).** Pyth: the price fails at
   VAA-sig OR data-source OR publishTime. FROST: the binding-factor preimage covers `{PK, msg, full commitment set,
   signer id}`. EigenLayer: `encumbered ≤ max` and `DEALLOCATION_DELAY == MIN_WITHDRAWAL_DELAY`. The hunt's job was
   locating that fact and confirming nothing routes around it.
2. **The decisive EigenLayer fact was a config equality, not contract logic.** "Stake can't escape a slash" holds
   only because two delays are *set equal* on mainnet — found in the deployer + a release invariant, not the
   AllocationManager logic. A primitive's safety can live in its parameters; reading only the logic would have
   missed it.
3. **Crypto-protocol confidence is the equations, honestly bounded.** FROST's clean verdict is precise about what it
   covers (the spec arithmetic + validation equations) and what it doesn't (constant-time, RNG, external field ops)
   — the same calibration as the Reth/Lighthouse "DoS-surface-exhaustive, full-equivalence-is-test-territory" split.
4. **Opposite-rounding-both-protocol-safe, recognized not flagged.** EigenLayer's magnitude-rounds-up /
   shares-round-down is a deliberate matched pair; like OP's `==` clock check and Babylon's bounded float, it *looks*
   asymmetric until you see both directions land safe — resolving it to *why* is the method, not flagging it.

*Read-only, public/verified-source. No transaction sent, no live system probed, no exploit/PoC written. Any live
finding would be private-first + redacted; none was found here.*
