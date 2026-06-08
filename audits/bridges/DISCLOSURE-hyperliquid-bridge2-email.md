# Bug-bounty disclosure email — ready to send

**To:** Hyperliquid bug bounty / security contact
**Attachments (2):**
- `repro_bridge2_duplicate_quorum.py` — local, non-weaponized mechanism reproduction
- `check_bridge2_validator_uniqueness.py` — read-only on-chain history verifier

---

## Subject

`Bridge2 (0x2Df1…3dF7): validator-set uniqueness is not enforced on-chain — latent quorum double-count (defense-in-depth) + full on-chain history scan + local reproduction`

---

## Body

Hi Hyperliquid security team,

This is a **defensive, responsibly-scoped** report on the Arbitrum Bridge2 contract
(`0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7`). I want to be upfront about severity: I assess this as a
**latent / defense-in-depth** issue, **not** a live exploitable vulnerability — I verified on-chain that it has
**never been triggered** (details below). I'm reporting it because the missing invariant is security-critical
and cheap to enforce, and because the verification work may be useful to you regardless of the bounty decision.

Everything below was done **read-only**: no transaction was ever sent, no exploit was run against the live
contract, and the reproduction uses synthetic keys on a local-only basis.

### 1. Summary

`checkValidatorSignatures` accumulates validator power **per array position** and does **not** enforce that
the active validator set contains **unique** addresses. The contract delegates uniqueness to the off-chain L1
generation (acknowledged in code: `Bridge2.sol:147` — *"The uniqueness of the validators is enforced on the L1
side."*). **If** a validator set with a duplicate address were ever checkpointed, a **single physical key**
could reach the `>2/3` power threshold by having its power counted at each duplicated position — and it would
not even need distinct signatures (see §4). This would let one key unilaterally authorize any
`checkValidatorSignatures`-gated operation (withdrawals, validator-set updates, config changes,
`emergencyUnlock`).

### 2. The mechanism (`Bridge2.sol:419–457`)

```solidity
for (uint64 activeValidatorSetIdx; activeValidatorSetIdx < end; activeValidatorSetIdx++) {
  address signer = recoverSigner(message, signatures[signatureIdx], domainSeparator);
  if (signer == activeValidatorSet.validators[activeValidatorSetIdx]) {
    uint64 power = activeValidatorSet.powers[activeValidatorSetIdx];
    cumulativePower += power;
    if (3 * cumulativePower > 2 * totalValidatorPower) { break; }
    signatureIdx += 1;
    if (signatureIdx >= nSignatures) { break; }
  }
}
require(3 * cumulativePower > 2 * totalValidatorPower, "...not enough power");
```

`signatureIdx` advances only on a match, so a *single signature blob* can't be replayed within one call and a
*single index* is counted once. But that is **not** the same as "each key's power is counted once." For a set
`[A, A, B]` with powers `[40, 40, 20]` (total 100), key A is matched at index 0 (+40) and index 1 (+40) →
`cumulativePower = 80` → `3·80 > 2·100` → quorum passes from one key.

### 3. Preconditions — why this is **latent**, not live

A duplicate set can only become active in three ways, all of which I checked:
- **`updateValidatorSet` / `finalizeValidatorSetUpdate`** — the update is **itself `>2/3`-quorum-gated**
  (`Bridge2.sol:521` calls `checkValidatorSignatures` against the *current* set). A duplicate set therefore
  requires either (a) the current honest validators to sign it — i.e. an **off-chain generator bug** that emits
  a duplicate with `>2/3` of power concentrated on one bridge key, or (b) a `>2/3` validator compromise (in
  which case funds are already at risk independently).
- **`emergencyUnlock`** — cold-quorum gated (`>2/3` cold).
- **Genesis** — the constructor (which does *not* enforce uniqueness either).

So exploitability hinges on the **off-chain validator-set generation**, which is closed-source and which I
cannot audit — I can neither prove nor disprove it can emit a concentrated-power duplicate. I am **not**
claiming it can.

### 4. On-chain verification — it has **never** happened (attachment 2)

Using a public Arbitrum RPC (read-only), I enumerated **every** validator-set transaction in the contract's
history via the `RequestedValidatorSetUpdate` / `FinalizedValidatorSetUpdate` logs, then decoded the
`hot`/`cold` address arrays from each `updateValidatorSet` / `emergencyUnlock` calldata **and** the genesis
constructor args:

- **11 distinct validator-set transactions = the entire history.** Genesis: 1 validator (unique). Every
  subsequent set: 4 hot / 4 cold, **all unique**. **Zero duplicate addresses, zero `address(0)`, ever
  checkpointed.**

This is the basis for my "latent, not live" assessment, and it confirms your off-chain invariant has held in
practice. The script (`check_bridge2_validator_uniqueness.py`) reproduces this; it's read-only and needs no
private key.

### 5. Reproduction — the double-count, proven locally (attachment 1)

`repro_bridge2_duplicate_quorum.py` ports `checkValidatorSignatures` (`:436-456`) and
`recoverSigner`/`makeMessage`/`makeDomainSeparator` (your EIP-712 scheme in `Signature.sol`) **verbatim** and
drives them with **real secp256k1** signatures (recovery round-trip asserted). Output:

```
[CASE 1] duplicate set [A,A,B], signatures=[sigA, sigA]:  cumulativePower=80 -> 3*80 > 2*100 == True   (PASSED, one key)
[CONTROL] unique  set [A,C,B], signatures=[sigA]      :  cumulativePower=40 -> 3*40 > 2*100 == False  (correctly rejected)
```

The same key A is rejected at its real 40% weight (control) but passes at 80% when duplicated. **Refinement:**
the attack does **not** require two *distinct* signatures — the loop dedupes by array **position**
(`signatureIdx`), not by signature content, so a single signature copied into two slots is counted twice. The
sole precondition is therefore "a duplicate address in the active set."

This is a **local mechanism proof only** — synthetic keys, no live target, no funds, no transaction.

### 6. Impact

- **As-is (current and historical state): none realized** — no duplicate set has ever been active.
- **If the off-chain pipeline ever emits a concentrated-power duplicate set** (bug, mis-mapping of L1 validators
  to bridge ECDSA signer addresses, or a malicious code change to the closed generator), the active set would
  carry a quorum-breaking duplicate, and a single key could authorize withdrawals / set-updates / `emergencyUnlock`.
- Classification: **defense-in-depth / latent quorum-accounting**. The on-chain check should not depend on an
  off-chain promise for a fund-custody-critical invariant.

### 7. Remediation

Enforce uniqueness (and non-zero) on-chain before any set is hashed/committed — `O(n²)` over a small set, cheap:

```solidity
function requireUniqueNonZero(address[] memory a) internal pure {
    for (uint256 i = 0; i < a.length; i++) {
        require(a[i] != address(0), "Bridge2: zero validator address");
        for (uint256 j = i + 1; j < a.length; j++) {
            require(a[i] != a[j], "Bridge2: duplicate validator address");
        }
    }
}
```

Call it on `hotAddresses` and `coldAddresses` in **`updateValidatorSetInner`** and the **constructor**, before
`makeValidatorSetHash`. This closes the entire class regardless of off-chain behavior.

### 8. Posture / scope

All analysis was read-only. The history scan made only `eth_call`/`eth_getLogs`/`eth_getTransactionByHash`
requests to a public RPC. The reproduction is local with synthetic keys. No exploit was attempted against the
live contract, no transaction was sent, and no funds were touched. If you'd prefer, I'm happy to walk through
the verification or the reproduction live.

Thanks for running an open bridge contract and a security program — happy to provide anything else useful.

Best regards,
[your name / handle]

---

*Sender note (not part of the email): the two attachments are in this folder —*
`tools/repro_bridge2_duplicate_quorum.py` *and* `tools/check_bridge2_validator_uniqueness.py`*. Both run with*
`pip install eth-abi eth-utils eth-account`*. Lead with §4 (history scan) and §5 (repro) — they're what make this
more than a comment-flag. Consider redacting/adjusting the subject's "defense-in-depth" framing only if their
program explicitly rewards latent findings; otherwise the honest framing tends to build credibility.*
