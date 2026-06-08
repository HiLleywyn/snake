#!/usr/bin/env python3
"""
check_bridge2_validator_uniqueness.py — PASSIVE, READ-ONLY verification tool.

Settles the one open question on the Hyperliquid Bridge2 duplicate-validator-set
finding (see ../AUDIT-HYPERLIQUID-BRIDGE.md, "Correction & severity calibration"):

    *Was a validator set with a DUPLICATE address (or address(0)) ever actually
     checkpointed on-chain?*

If NO  -> the finding is latent / defense-in-depth (the on-chain check should still
          enforce uniqueness; recommended remediation stands).
If YES -> it is a LIVE Critical: a single physical key could have inflated quorum.
          Per audit posture, a positive result should be routed PRIVATELY to
          Hyperliquid, NOT published. This script does NOT exploit anything; it only
          decodes public historical calldata and checks a set-uniqueness predicate.

What it does (entirely passive):
  - Computes the 4-byte selectors from the ABI VERIFIED AGAINST Bridge2.sol source
    (ValidatorSetUpdateRequest{epoch, hotAddresses[], coldAddresses[], powers[]},
     ValidatorSet{epoch, validators[], powers[]}, Signature{r,s,v}).
  - Pulls the contract's full tx history (Arbiscan-compatible `account/txlist`).
  - Decodes the hot/cold address arrays from every updateValidatorSet / emergencyUnlock
    call, plus the deployment tx's initial set if decodable.
  - Flags any array where len(arr) != len(set(arr)) (duplicate) or contains 0x0.

Target: Bridge2 @ 0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7 (Arbitrum One).

Run it yourself against an endpoint YOU control (do not commit your API key):
    pip install eth-abi eth-utils requests
    ARBISCAN_API_KEY=xxxx python3 check_bridge2_validator_uniqueness.py
  (Arbiscan V2 unified endpoint with chainid=42161; or set ETHERSCAN_BASE to a
   self-hosted/alternate explorer exposing the same `account&action=txlist` API.)

No private keys, no transactions sent, no state changed. Read-only HTTP GETs.
"""

import os
import sys
import time

try:
    import requests
    from eth_abi import decode as abi_decode
    from eth_utils import function_signature_to_4byte_selector, to_checksum_address
except ImportError:
    sys.exit("pip install eth-abi eth-utils requests")

CONTRACT = "0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7"
CHAIN_ID = 42161  # Arbitrum One
ZERO = "0x" + "00" * 20

# --- ABI verified against Bridge2.sol (NOT the report's reconstruction) ---
VSUR = "(uint64,address[],address[],uint64[])"      # ValidatorSetUpdateRequest
VSET = "(uint64,address[],uint64[])"                # ValidatorSet
SIG  = "(uint256,uint256,uint8)[]"                  # Signature[]
UPDATE_SIG = f"updateValidatorSet({VSUR},{VSET},{SIG})"
UNLOCK_SIG = f"emergencyUnlock({VSUR},{VSET},{SIG},uint64)"
# Solidity ABI types for eth_abi.decode (tuple components, lists):
UPDATE_TYPES = ["(uint64,address[],address[],uint64[])",
                "(uint64,address[],uint64[])",
                "(uint256,uint256,uint8)[]"]
UNLOCK_TYPES = UPDATE_TYPES + ["uint64"]


def sel(sig):  # 0x-prefixed 4-byte selector
    return "0x" + function_signature_to_4byte_selector(sig).hex()


UPDATE_SELECTOR = sel(UPDATE_SIG)
UNLOCK_SELECTOR = sel(UNLOCK_SIG)


def check_arrays(label, txhash, hot, cold):
    """Return list of problem strings for one (hot, cold) pair."""
    out = []
    for name, arr in (("hotAddresses", hot), ("coldAddresses", cold)):
        addrs = [to_checksum_address(a) for a in arr]
        if len(addrs) != len(set(addrs)):
            dupes = sorted({a for a in addrs if addrs.count(a) > 1})
            out.append(f"  !! DUPLICATE in {name}: {dupes}  (n={len(addrs)}, unique={len(set(addrs))})")
        zeros = [a for a in addrs if a.lower() == ZERO]
        if zeros:
            out.append(f"  !! ZERO ADDRESS in {name}")
    return out


def decode_update(data_hex, types):
    raw = bytes.fromhex(data_hex[10:])  # strip 0x + 4-byte selector
    decoded = abi_decode(types, raw)
    vsur = decoded[0]               # (epoch, hotAddresses, coldAddresses, powers)
    hot, cold = vsur[1], vsur[2]
    return hot, cold


def fetch_txlist(base, key):
    """Arbiscan-compatible account/txlist, paginated."""
    txs, page = [], 1
    while True:
        params = dict(module="account", action="txlist", address=CONTRACT,
                      startblock=0, endblock=99999999, page=page, offset=1000,
                      sort="asc", apikey=key)
        if "v2" in base or "chainid" in base:
            params["chainid"] = CHAIN_ID
        r = requests.get(base, params=params, timeout=30).json()
        if r.get("status") != "1" or not r.get("result"):
            break
        batch = r["result"]
        txs.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
        time.sleep(0.25)  # be polite to the API
    return txs


def main():
    key = os.environ.get("ARBISCAN_API_KEY") or os.environ.get("ETHERSCAN_API_KEY")
    base = os.environ.get("ETHERSCAN_BASE", "https://api.etherscan.io/v2/api")
    print(f"Bridge2:           {CONTRACT}  (Arbitrum One, chainid {CHAIN_ID})")
    print(f"updateValidatorSet selector: {UPDATE_SELECTOR}")
    print(f"emergencyUnlock    selector: {UNLOCK_SELECTOR}")
    if not key:
        print("\nSet ARBISCAN_API_KEY (or ETHERSCAN_API_KEY) and re-run. "
              "Selectors above can also be matched manually against any tx dump.")
        return

    print("\nFetching full tx history (paginated)...")
    txs = fetch_txlist(base, key)
    print(f"  {len(txs)} transactions to the contract.\n")

    findings, n_update, n_unlock = [], 0, 0
    for tx in txs:
        data = tx.get("input", "")
        if not isinstance(data, str) or len(data) < 10:
            continue
        selector = data[:10].lower()
        try:
            if selector == UPDATE_SELECTOR:
                n_update += 1
                hot, cold = decode_update(data, UPDATE_TYPES)
            elif selector == UNLOCK_SELECTOR:
                n_unlock += 1
                hot, cold = decode_update(data, UNLOCK_TYPES)
            else:
                continue
        except Exception as e:
            findings.append(f"  ?? could not decode {tx.get('hash')}: {e}")
            continue
        problems = check_arrays(selector, tx.get("hash"), hot, cold)
        if problems:
            findings.append(f"TX {tx.get('hash')} (block {tx.get('blockNumber')}):")
            findings.extend(problems)

    print(f"Decoded {n_update} updateValidatorSet + {n_unlock} emergencyUnlock calls.")
    print("NOTE: also check the DEPLOYMENT tx's constructor args for the genesis set "
          "(Bridge2.sol constructor takes hotAddresses/coldAddresses/powers).\n")

    if findings:
        print("=" * 70)
        print("DUPLICATE / ZERO VALIDATOR ADDRESS FOUND IN CHECKPOINTED HISTORY:")
        print("=" * 70)
        print("\n".join(findings))
        print("\n>>> This would be a LIVE Critical. Per audit posture: route PRIVATELY")
        print(">>> to Hyperliquid (security contact / bug bounty), do NOT publish, do")
        print(">>> NOT write or run any exploit. This script only read public data.")
    else:
        print("RESULT: no duplicate or zero validator address found in any checkpointed")
        print("update/emergencyUnlock set. The finding remains LATENT / defense-in-depth:")
        print("the on-chain check still SHOULD enforce uniqueness (Bridge2.sol:147 delegates")
        print("it off-chain). Recommended remediation: requireUniqueAddresses + non-zero in")
        print("updateValidatorSetInner before hashing/committing.")


if __name__ == "__main__":
    main()
