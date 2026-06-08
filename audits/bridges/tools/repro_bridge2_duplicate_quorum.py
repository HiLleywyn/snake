#!/usr/bin/env python3
"""
repro_bridge2_duplicate_quorum.py
LOCAL, NON-WEAPONIZED mechanism proof for the Hyperliquid Bridge2 duplicate-
validator-set quorum-inflation finding (see ../AUDIT-HYPERLIQUID-BRIDGE.md).

This is a DISCLOSURE ARTIFACT, not an exploit:
  - It targets NOTHING on-chain. No transaction is sent. No funds exist.
  - Keys are SYNTHETIC (generated here). Addresses are throwaway.
  - It proves the *mechanism* by running the EXACT contract logic --
    checkValidatorSignatures (Bridge2.sol:436-456) and recoverSigner +
    makeMessage + makeDomainSeparator (Signature.sol) -- ported VERBATIM,
    driven with REAL secp256k1 signatures.

Conclusion proven: if a validator set ever contains a DUPLICATE address (the
contract does NOT enforce uniqueness on-chain; Bridge2.sol:147 delegates it to
the off-chain L1), a SINGLE physical key reaches the >2/3 power threshold by
having its power counted at each duplicated position -- using even ONE signature
copied into two array slots, because the loop accounts power per ARRAY POSITION,
not per unique signer identity.

The on-chain history shows this never occurred (the finding is LATENT). This
script demonstrates *why the on-chain check should enforce uniqueness anyway*.
    pip install eth-abi eth-utils eth-account
"""
from eth_abi import encode as abi_encode
from eth_utils import keccak, to_checksum_address
from eth_keys import keys

# ---- constants from Signature.sol (verbatim) ----
AGENT_TYPEHASH = keccak(text="Agent(string source,bytes32 connectionId)")
EIP712_DOMAIN  = keccak(text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
VERIFYING_CONTRACT = "0x" + "00" * 20  # address(0) in Signature.sol
CHAIN_ID = 42161                       # Arbitrum One (any value works; bug is chain-independent)
BRIDGE   = "0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7"  # used only as the EIP-712 'connectionId' input


def make_domain_separator():  # Signature.sol:27
    return keccak(abi_encode(["bytes32", "bytes32", "bytes32", "uint256", "address"],
                             [EIP712_DOMAIN, keccak(text="Exchange"), keccak(text="1"),
                              CHAIN_ID, VERIFYING_CONTRACT]))


def make_message(contract_addr, data):  # Bridge2.sol:590 makeMessage -> Signature.sol:23 hash(Agent)
    connection_id = keccak(abi_encode(["address", "bytes32"], [contract_addr, data]))
    return keccak(abi_encode(["bytes32", "bytes32", "bytes32"],
                             [AGENT_TYPEHASH, keccak(text="a"), connection_id]))


def eip712_digest(data_hash, domain_sep):  # Signature.sol:45  keccak(0x1901 ++ ds ++ dataHash)
    return keccak(b"\x19\x01" + domain_sep + data_hash)


def recover_signer(data_hash, sig, domain_sep):  # Signature.sol:40 recoverSigner (ecrecover)
    r, s, v = sig
    sg = keys.Signature(vrs=(v - 27, r, s))
    return sg.recover_public_key_from_msg_hash(eip712_digest(data_hash, domain_sep)).to_checksum_address()


def sign(priv, data_hash, domain_sep):  # produce a contract Signature{r,s,v} over the message
    sg = priv.sign_msg_hash(eip712_digest(data_hash, domain_sep))
    return (sg.r, sg.s, sg.v + 27)


def check_validator_signatures(message, validators, powers, signatures, total_power, domain_sep):
    """VERBATIM port of Bridge2.sol checkValidatorSignatures (:436-456)."""
    cumulative = 0
    sig_idx = 0
    n = len(signatures)
    for i in range(len(validators)):                                   # for activeValidatorSetIdx
        signer = recover_signer(message, signatures[sig_idx], domain_sep)
        if signer == validators[i]:                                    # if signer == validators[idx]
            cumulative += powers[i]                                     # cumulativePower += power
            if 3 * cumulative > 2 * total_power:                        # quorum reached -> break
                break
            sig_idx += 1                                               # signatureIdx += 1
            if sig_idx >= n:
                break
    ok = 3 * cumulative > 2 * total_power                               # final require
    return ok, cumulative


def main():
    ds = make_domain_separator()
    # two real keys: A (the single attacker key) and B (an honest minority)
    A = keys.PrivateKey(keccak(text="validator-A-synthetic"))
    B = keys.PrivateKey(keccak(text="validator-B-synthetic"))
    addrA = A.public_key.to_checksum_address()
    addrB = B.public_key.to_checksum_address()
    print(f"synthetic key A -> {addrA}")
    print(f"synthetic key B -> {addrB}")

    # the message that gets signed (content is irrelevant to the bug; any privileged op)
    data = keccak(text="any privileged Bridge2 operation, e.g. a validator-set update")
    msg = make_message(BRIDGE, data)

    # self-check: the ported recovery is faithful (sign then recover == signer)
    sigA = sign(A, msg, ds)
    assert recover_signer(msg, sigA, ds) == addrA, "recovery round-trip failed"
    print("recovery round-trip OK (real secp256k1, contract's exact EIP-712 scheme)\n")

    print("INTENDED set was [A, C, B] with powers [40, 40, 20] (A=40%, needs another to reach 2/3).")
    print("A duplication BUG produced [A, A, B] instead (the slot meant for C went to A).\n")

    # === case 1: DUPLICATE set [A, A, B], A signs ONCE, signature copied into two slots ===
    validators = [addrA, addrA, addrB]
    powers      = [40, 40, 20]
    total       = sum(powers)  # 100
    signatures  = [sigA, sigA]  # the SAME single signature, in two positions
    ok, power = check_validator_signatures(msg, validators, powers, signatures, total, ds)
    print(f"[CASE 1] duplicate set [A,A,B], signatures=[sigA, sigA] (one key, one sig copied):")
    print(f"         cumulativePower = {power}  ->  3*{power} > 2*{total}  ==  {3*power} > {2*total}  ==  {ok}")
    print(f"         => quorum {'PASSED' if ok else 'failed'} from a SINGLE physical key. "
          f"{'<<< DOUBLE-COUNT CONFIRMED' if ok else ''}\n")

    # === control: the CORRECT unique set [A, C, B], A signs once -> should FAIL ===
    C = keys.PrivateKey(keccak(text="validator-C-synthetic"))
    addrC = C.public_key.to_checksum_address()
    validators_u = [addrA, addrC, addrB]
    powers_u      = [40, 40, 20]
    signatures_u  = [sigA]  # only A signs
    ok_u, power_u = check_validator_signatures(msg, validators_u, powers_u, signatures_u, sum(powers_u), ds)
    print(f"[CONTROL] correct unique set [A,C,B], signatures=[sigA] (A alone, its real 40%):")
    print(f"          cumulativePower = {power_u}  ->  3*{power_u} > 2*{sum(powers_u)}  ==  {ok_u}")
    print(f"          => quorum {'PASSED' if ok_u else 'CORRECTLY REJECTED'} "
          f"(A alone has 40% < 66.7%, as intended).\n")

    print("=" * 72)
    print("PROVEN: the same key A is rejected at its real 40% weight (control) but PASSES")
    print("at 80% when duplicated (case 1) -- the loop counts power per array POSITION, not")
    print("per unique identity, and does not even require distinct signatures. The on-chain")
    print("check MUST enforce set-uniqueness (+ non-zero) regardless of off-chain promises.")
    print("Remediation: requireUniqueAddresses(hotAddresses) & (coldAddresses) in")
    print("updateValidatorSetInner + the constructor, before hashing/committing.")
    print("(Local mechanism proof only. No live target, no funds, no transaction.)")


if __name__ == "__main__":
    main()
