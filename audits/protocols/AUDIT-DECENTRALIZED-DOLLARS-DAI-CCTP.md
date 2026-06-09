# Decentralized dollars, centralized residual — DAI (a USDC wrapper via the PSM) and CCTP (Circle's cross-chain quorum)

**Scope.** Two systems marketed as decentralized/permissionless that, on close reading, **inherit Circle's
centralization through the back door**: MakerDAO's **DAI** via the Peg Stability Module + the sDAI/DSR layer
(`makerdao/dss-psm`, `makerdao/sdai`, `makerdao/dss`), and Circle's **CCTP** cross-chain native-USDC
burn-and-mint (`circlefin/evm-cctp-contracts`). This continues the large-cap stablecoin deep-dive (USDC vs
USDT) into the *second-order* dollars built on or around USDC. (FRAX — the fractional-algorithmic + AMO
model — is characterized separately in `AUDIT-FRAX-FRACTIONAL-ALGO-AMO.md`.) Public source, read-only,
recompute-don't-trust. **Defensive, characterize-don't-exploit. No exploitable defect found**; the
inherited-centralization residuals are characterized factually. (All "freeze/seize" capabilities referenced
are Circle's *own* native functions, external to the protocols audited — not bugs in Maker or CCTP.)

**Sources (verbatim, line refs):** Maker `dss-psm/src/{psm,join-auth}.sol`, `sdai/src/SavingsDai.sol`,
`dss/src/{vat,pot,join}.sol`; CCTP `evm-cctp-contracts/src/{TokenMessenger,MessageTransmitter,TokenMinter,
TokenController}.sol`, `src/roles/{Attestable,Pausable,Rescuable}.sol`.

---

## 0. The one-paragraph result

The prior audit established that USDC and USDT are centrally-administered, off-chain-backed claims with
issuer freeze/seize keys. This one shows that **two of the most prominent "decentralized" pieces of
infrastructure built around USDC inherit that centralization** — in two different shapes. **DAI** is, to a
large and direct degree, *a USDC wrapper*: the Peg Stability Module (`DssPsm`) pegs DAI to \$1 by minting
fresh DAI **1:1 against USDC deposited into a single `AuthGemJoin` address**, so a meaningful fraction of
DAI's collateral is USDC physically custodied at one contract — and **if Circle blacklists that address, the
`buyGem` redemptions revert permanently and that backing freezes while the minted DAI debt stays outstanding
in the `vat`.** The "decentralized stablecoin" is censorship-resistant only as far as Circle permits; sDAI
sits cleanly on top as an ERC4626 over the DSR rate `chi`, but the "risk-free" DSR yield is Maker
*seigniorage* substantially underwritten by returns on that same centralized USDC. **CCTP** — the protocol
that makes USDC "native" across chains — bottoms out, exactly like every cross-chain system in this corpus,
in an **off-chain attestation quorum**: the destination mint is gated *solely* by a threshold of **Circle
attester signatures** (shipping **1-of-1** by default), with **no on-chain proof of the source burn**, no
staking, no fraud window. So the finding is one statement told twice: *"decentralized" describes the
issuance mechanism, not the residual underneath it — DAI inherits Circle's freeze via USDC custody in the
PSM, and native cross-chain USDC inherits Circle's authority via the attester signature on every mint; in
both, a supposedly trustless dollar rests on a single corporate operator's forbearance.*

---

## 1. DAI — a USDC wrapper via the PSM, with sDAI/DSR on top. **Inherited freeze risk.**

**The 1:1 peg mechanism (`DssPsm`).** `sellGem (psm.sol:109-119)` does *not* trade DAI from a pool — it
deposits the user's USDC into the vault and **mints fresh DAI against it**:
```solidity
gemJoin.join(address(this), gemAmt, msg.sender);                                    // :113  USDC in
vat.frob(ilk, address(this), address(this), address(this), int256(gemAmt18), int256(gemAmt18)); // :114  draw DAI 1:1
daiJoin.exit(usr, daiAmt);                                                          // :116  DAI out
```
with `to18ConversionFactor = 1e12` for 6-decimal USDC (`:72`), so **1 USDC ⇒ exactly 1.0 DAI** minus `tin`
(historically 0). `buyGem (:121-132)` is the exact inverse (burn DAI, return the custodied USDC). This is
the hard arbitrage anchor that pins DAI to USDC at \$1 — and the reason DAI's market price tracks USDC's so
tightly: it is *redeemable for USDC at par* through the PSM.

**The USDC dependency (the central finding).** Every PSM-minted DAI is backed 1:1 by USDC held as a plain
ERC20 balance at the `AuthGemJoin` address (`join-auth.sol:71` — `gem.transferFrom(... address(this) ...)`
on deposit; redemption at `:77` — `gem.transfer(guy, wad)`). **That USDC is subject to Circle's `blacklist`.**
If Circle blacklists the gemJoin address, `gem.transfer` on `:77` reverts permanently — `buyGem` redemptions
become impossible and the PSM-backed slice of DAI loses access to its collateral while the corresponding
`urn.art` DAI debt remains outstanding in the `vat`. **"Decentralized" DAI inherits USDC's centralized
freeze/seize power as a residual: the peg's hard floor is only as censorship-resistant as Circle permits.**
This is a custody/freeze characterization — the blacklist is Circle's own function, not a Maker
vulnerability — but it is the dominant centralization residual under DAI, and it is *invisible* if you only
read Maker's (genuinely decentralized) `vat`/governance code.

**sDAI = ERC4626 over the DSR `chi`.** `SavingsDai (sdai)` is non-rebasing; its only price input is the DSR
rate accumulator from `pot.sol`: `convertToAssets(shares) = shares · chi / RAY (:284-288)`, with state
changes calling `pot.drip()` first to realize the up-to-date `chi`. It holds no USDC and has no peg logic —
a clean, monotonically-appreciating yield claim on DAI sitting in the pot.

**The DSR is seigniorage, backed substantially by the USDC.** `pot.drip (:144-151)` mints fresh internal DAI
to the pot and books an equal `sin` (unbacked debt) against the `vow` via `vat.suck(vow, pot, ...)
(:230-235)`. So DSR yield is paid from Maker's surplus — funded by vault stability fees **plus yield earned
on PSM-deployed collateral (the very USDC parked via the PSM, routed to RWA/T-bill vaults).** The loop
closes: *the "risk-free" sDAI yield is substantially underwritten by returns on the centralized USDC that
also carries the freeze risk.*

**Governance:** the PSM is `wards`/`auth`-controlled by MakerDAO governance (`MCD_PAUSE_PROXY`); `file` sets
`tin`/`tout`; the PSM ilk's `line` (debt ceiling on the `vat`) caps how much DAI the PSM can mint against
USDC; `AuthGemJoin.cage()` can halt deposits. So Maker governance controls the *size* of the USDC dependency
(and can, and has, debated reducing it) but not the *freeze* risk itself, which is wholly Circle's.

---

## 2. CCTP — native cross-chain USDC, gated by Circle's attester quorum. **The same residual, cross-chain.**

**Burn side.** `TokenMessenger.depositForBurn → _depositForBurn (:427-481)` pulls the user's USDC to the
local minter and **irrevocably burns it** (`_localMinter.burn`, via `TokenMinter.burn :111-120`, gated by a
per-message burn limit), then formats a 132-byte `BurnMessage` emitted **only as a `MessageSent` event**
(`MessageTransmitter._sendMessage :362`). **Nothing is sent on-chain — the burn just emits a log for
Circle's off-chain attesters to observe and sign.** The burn is final the instant it lands.

**Mint side — gated solely by Circle's signature.** `MessageTransmitter.receiveMessage (:250-306)` *first*
verifies the attestation, then dispatches to `TokenMessenger.handleReceiveMessage (:313-346)` which mints via
`TokenMinter.mint (:85-103)`:
```solidity
_verifyAttestationSignatures(message, attestation);        // :265  Circle quorum signature — the sole gate
require(usedNonces[_sourceAndNonce] == 0, "Nonce already used"); usedNonces[_sourceAndNonce] = 1;  // :284-285
...
require(_token.mint(to, amount), "Mint operation failed");  // TokenMinter:101  unconditional 1:1 mint
```
**There is no on-chain proof of the source burn** — the destination mints native USDC *iff* a threshold of
valid Circle attester ECDSA signatures over `keccak256(message)` is presented. The mint is otherwise
unconditional (no escrow, no liquidity pool).

**The attester quorum (`Attestable.sol`).** `_verifyAttestationSignatures (:227-263)` is an m-of-n
ascending-address ECDSA multisig; the set and threshold are controlled entirely by Circle's `attesterManager`
(`enableAttester`/`disableAttester`/`setSignatureThreshold`), and **the constructor ships it as 1-of-1**
(`:88-92`). No staking, no slashing, no fraud window, no permissionless verification. **Every native
cross-chain USDC mint trusts this small, Circle-operated quorum's honesty and liveness** — compromise the
keys and you mint native USDC from nothing; quorum downtime means already-burned USDC cannot be redeemed.

**Replay:** a per-`(sourceDomain, nonce)` `usedNonces` bitmap (`:281-286`), checked-and-set before the
handler — each burn mints exactly once. **Governance:** an `Ownable2Step` `owner` appoints `pauser` (can
**halt all mints/burns chain-wide** instantly), `attesterManager` (rotate the quorum), `tokenController`
(throttle/zero burns per token/message), and `rescuer` — all single-key, no timelock in these contracts.

**Native-vs-bridged fragmentation:** CCTP mints/burns the *canonical* native USDC keyed by `linkTokenPair`
mappings the `tokenController` controls. USDC moved over third-party lock-and-mint bridges (historical
"USDC.e") is a *different* ERC20 not in this registry and **not redeemable through CCTP** — non-fungible
on-chain despite identical branding, a persistent UX/liquidity hazard.

**Characterization:** CCTP is the canonical instance of the corpus's cross-chain law — *cross-chain value
always bottoms out in an off-chain attestation quorum* (cf. Wormhole 13/19, LayerZero DVNs, Across
optimistic, §5h) — where here the quorum is **a single corporate operator** (Circle), shipping 1-of-1. It is
the cross-chain twin of the §1 finding: DAI inherits Circle's freeze via USDC *custody*; native cross-chain
USDC inherits Circle's authority via the *attester signature on every mint*.

---

## 3. The synthesis — one residual, two routes

| | DAI (PSM) | CCTP |
|---|---|---|
| **Marketed as** | decentralized stablecoin | trustless native cross-chain USDC |
| **Actual residual** | USDC custody at one `AuthGemJoin` address | Circle attester quorum signature on every mint |
| **Circle's lever** | blacklist the gemJoin ⇒ freeze backing, break `buyGem` | pause / rotate attesters / 1-of-1 sign ⇒ halt or forge mints |
| **On-chain proof** | none of USDC's redeemability (off-chain reserve) | none of the source burn (off-chain signature) |
| **Visible in the protocol's own code?** | no — Maker's `vat`/governance is genuinely decentralized | no — CCTP's solidity is clean; the trust is the off-chain attester |
| **Severity** | a large fraction of DAI's backing | *all* native cross-chain USDC |

**The unifying statement:** in both, the *issuance mechanism* is decentralized or trustless-looking (Maker's
governance and vault accounting are real; CCTP's burn/mint/replay logic is clean), but the **residual** — the
thing the whole construction's safety actually rests on — is **Circle, off-chain, invisible at the protocol's
own layer.** This is the §5i meta-residual ("the floor is only as neutral as the token beneath it") in two
fresh forms, and it is the §5h cross-chain law specialized to the dominant stablecoin: *every supposedly
decentralized dollar that touches USDC imports Circle's freeze key (via custody, DAI) or Circle's signature
(via attestation, CCTP), and no amount of reading the decentralized layer reveals it — you have to read one
layer down, to the token and the attester.*

---

## 4. Posture & conclusion

- **No exploitable contract defect found** in Maker's PSM/sDAI or in CCTP — both are well-built and doing
  exactly what they are designed to. The findings are *inherited-centralization* facts: DAI's peg floor and a
  large slice of its collateral depend on USDC custodied at one blacklist-able address; native cross-chain
  USDC depends entirely on Circle's off-chain attester signature (default 1-of-1) with no on-chain burn
  proof.
- **Method note:** this is "recompute, don't trust the summary" applied to the *decentralization claim
  itself*. The summary — "DAI is a decentralized stablecoin," "CCTP is trustless cross-chain USDC" — is true
  of the *mechanism* and false of the *residual*. Reading Maker's governance or CCTP's burn/mint logic in
  isolation confirms the summary; reading one layer down (the USDC at the gemJoin, the attester behind the
  mint) reveals the centralization the summary hides. The honest user statement: *DAI is censorship-resistant
  and CCTP is trustless only above the USDC layer — and at that layer both rest on Circle's forbearance,
  which no on-chain guarantee in either protocol can replace.*

*Read-only, public-source. No transaction sent, no live system probed, no funds touched.*
