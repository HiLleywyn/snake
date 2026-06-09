# V3 (deep) — consensus randomness & leader election: the swap-or-not shuffle, the balance-weighted proposer loop, and Algorand's binomial sortition

**Scope.** A deep, individualized expansion of sweep item **V3** (`AUDIT-VALIDATOR-OPS-SWEEP.md` §V3), going past
the RANDAO `bls.Verify`-before-mix + Algorand VRF-verify-before-sortition the rapid pass covered into the **full
selection machinery**: Ethereum's 90-round swap-or-not shuffle, the effective-balance-weighted proposer
rejection-sampling loop, the domain-separated `get_seed` + committee slice; and Algorand's binomial-CDF
sortition, the lowest-VRF proposer credential, and the two-phase (seed/balance) anti-grinding lookback. Targets:
`ethereum/consensus-specs` @ `1f41e6b` (`specs/phase0/beacon-chain.md`), `algorand/go-algorand` @ `ea67b3f` +
`algorand/sortition` v1.0.0. Read-only, public-source, recompute-don't-trust. **Defensive,
characterize-don't-exploit. No finding;** the load-bearing assumptions (loop termination, float determinism,
counter domain-separation) are characterized factually.

---

## 0. What the deep pass adds over the sweep

The sweep established "proven, not asserted" (entropy is BLS/VRF-verified before it influences selection; the
contribution is deterministic → only 1-bit withholding bias). The deeper reading shows the **mapping from
entropy to assignment** — and *why an adversary who can't predict the seed can't bias the outcome*: the
swap-or-not shuffle is a **near-uniform seed-keyed bijection** (90 rounds), so biasing a validator's
slot/committee **reduces to controlling the RANDAO seed**; the proposer loop is **stake-proportional rejection
sampling**; `get_seed` is **domain-separated** so the proposer and attester roles can't be cross-ground; and
Algorand decouples **"which randomness" (seedRound) from "whose stake" (balanceRound)** by hundreds of rounds —
the anti-grinding core.

---

## 1. Ethereum — the swap-or-not shuffle. **A seed-keyed near-uniform bijection.**

`compute_shuffled_permutation (beacon-chain.md:819-842)`, `SHUFFLE_ROUND_COUNT = 90`: each of 90 rounds picks a
seed-derived `pivot`, pairs index `x` with its mirror `flip = (pivot − x) mod n`, and **swaps the pair iff a
single seed-derived bit at the pair's max position is set**:
```python
pivot = int.from_bytes(hash(seed + round_bytes)[0:8]) % index_count       # :828
flip = (pivot + index_count - indices[i]) % index_count                   # :831
position = max(indices[i], flip)
bit = (hash(seed + round_bytes + position_bucket)[(position%256)//8] >> (position%8)) % 2   # :838-839
indices[i] = flip if bit else indices[i]                                  # :840
```
**Characterization:** because the swap decision per pair comes from `hash(seed‖round‖bucket)`, the permutation is
a **deterministic bijection fully determined by `seed` (and `index_count`)**; with 90 rounds it is a
cryptographically strong, near-uniform permutation. **Without the seed an adversary cannot predict or bias any
validator's landing slot/committee better than guessing** — biasing the shuffle *reduces to predicting/
controlling the RANDAO-derived seed* (§3). Honest note: `compute_shuffled_index` builds the whole permutation
(O(n)), wrapped in a 256-entry LRU as a spec-evaluation optimization (not consensus-affecting).

---

## 2. Ethereum — the proposer loop is stake-weighted rejection sampling.

`compute_proposer_index (:859-875)`: a uniformly-shuffled candidate is **accepted with probability
`effective_balance / MAX_EFFECTIVE_BALANCE`**:
```python
candidate_index = indices[compute_shuffled_index(i % total, total, seed)]
random_byte = hash(seed + uint_to_bytes(i // 32))[i % 32]
if effective_balance * 255 >= MAX_EFFECTIVE_BALANCE * random_byte: return candidate_index   # :873  accept ∝ stake
```
`get_beacon_proposer_index (:1117-1124)` mixes the proposer-domain seed with `state.slot`, so **each slot's
proposer is independently seed-determined**.

**Characterization:** selection probability is **proportional to stake** (a 32-ETH-cap validator is always
accepted; a half-balance one ~50%), and the per-slot seed mix means a per-slot, independent draw. Honest notes:
(a) the loop is an **unbounded `while True`** — termination relies on ≥1 positive-balance validator (guaranteed
for an active set) but is theoretically unbounded; (b) `random_byte` reuses a hash block for 32 consecutive `i`
(standard efficiency, no bias); (c) the **32-ETH cap** means stake above it confers no extra proposer weight (a
pre-Electra economic property, not a flaw).

---

## 3. Ethereum — `get_seed` is domain-separated, and the committee is a permutation slice. **No cross-role grinding.**

`get_seed (:1067-1074)` = `hash(domain_type ‖ epoch ‖ randao_mix)`, with the mix read from `epoch +
EPOCHS_PER_HISTORICAL_VECTOR − MIN_SEED_LOOKAHEAD − 1` (the 1-epoch lookback). `compute_committee (:881-892)`
takes a **contiguous slice `[start,end)` of the shuffled list** under the attester seed.
**Characterization:** the same RANDAO entropy produces **independent seeds for the proposer (`0x00…`) vs attester
(`0x01…`) roles** — preventing cross-role correlation/grinding — and the **1-epoch lookback locks the committee
in *before* that epoch's RANDAO reveals occur**, limiting last-revealer grinding to the accepted 1-bit-per-slot.
The committee is exactly a deterministic slice of the swap-or-not permutation; *an adversary cannot bias
committee/proposer assignment without controlling the RANDAO mix one epoch ahead.*

---

## 4. Algorand — the binomial-CDF sortition. **Sub-user count ∝ stake, cryptographically.**

`Select (sortition.go:44-59)` maps the 32-byte VRF output to a **uniform `ratio ∈ [0,1)`** (big-int / `0xff…ff`,
264-bit precision) and walks the CDF of `Binomial(n = money, p = expectedSize/totalMoney)`:
```cpp
boost::math::binomial_distribution<double> dist(n, p);
for (j = 0; j < money; j++) { if (ratio <= cdf(dist, j)) return j; }   // sortition.cpp:12-17  invert the binomial CDF
return money;
```
**Characterization:** the VRF output (verified at `credential.go:78` *before* sortition) is inverted through the
binomial CDF, giving each account an expected `money·p = money·expectedSize/totalMoney` sub-user selections —
**exactly proportional to stake**, and **unpredictable/unbiasable pre-reveal** because the ratio is a verified
VRF value. Honest notes: the walk is O(money) worst-case; it uses **`double`-precision Boost binomial CDF**, so
**cross-platform float determinism** is a load-bearing assumption (the module **pins Boost 1.65.1** to keep CDF
results bit-reproducible — a deliberate determinism guard).

---

## 5. Algorand — the lowest-VRF proposer credential. **Stake-proportional, with a counter domain-separation subtlety.**

A weight-`w` credential simulates `w` selections; `lowestOutput (credential.go:170-208)` hashes the credential
`w` times with counters `i = 1..w` and keeps the **minimum** big-int, and the proposal with the **globally lowest
`lowestOutput` wins** (`Less :141-146`). The address is mixed into the hash to **decorrelate same-VRF-key
accounts** (`:80-91`). **Characterization:** higher-stake accounts (more sub-users `w`) get more chances at a low
value → stake-proportional proposer odds. **Correctness-critical subtlety (flagged in the code's own comments):**
the counter **starts at `i = 1`, not `0`**, to domain-separate from the `iter = 0` hash used for weight selection
— reusing `iter = 0` would make weight-1 credentials non-uniform and disadvantaged in tie-breaking. A deliberate,
security-relevant design choice.

---

## 6. Algorand — the two-phase lookback. **Decouples "which randomness" from "whose stake."**

`selector.go`: the **seed** for round `r` is from `seedRound = r − SeedLookback` (`δ_s = 2`), while **stake and
total circulation** are from `balanceRound = r − 2·SeedRefreshInterval·SeedLookback` (defaults `2·100·2 = 400`
rounds back, `320` after v8). The seed is re-randomized via the `SeedRefreshInterval` mechanism (mixing an old
block digest into the seed).
**Characterization:** the **balance snapshot is hundreds of rounds in the past**, so an adversary **cannot
move/restake funds to grind their committee membership** — by the time they could observe the relevant seed,
the balance that determines their sortition weight was already finalized far earlier. This two-phase
decoupling + VRF-verify-before-sortition is the **anti-grinding core** of Algorand leader election.

---

## 7. Verdict & residual

both systems make leader/committee selection a **deterministic function of verified randomness an adversary
can't predict ahead of a fixed lookback, applied to stake measured at a past frozen snapshot** — so the only
lever is grinding the randomness, which both bound (Ethereum: 1-epoch RANDAO lookahead + domain-separated
`get_seed`; Algorand: seedRound/balanceRound two-phase lookback + VRF-verify-before-sortition). The mapping is
near-uniform (Ethereum's 90-round swap-or-not; Algorand's 264-bit VRF→[0,1)→binomial-CDF). **No finding.**
**Residuals / load-bearing assumptions**, named: (a) the accepted **1-bit last-revealer withholding bias**
(RANDAO and VRF-with-withholding alike — a protocol property, fixable only by VDFs/SSLE); (b) Ethereum
`compute_proposer_index` is an **unbounded loop** relying on a non-empty positive-balance active set; (c)
Algorand's sortition uses **`double`-precision Boost CDF with a pinned Boost version** — exact selection counts
depend on cross-platform float determinism; (d) Algorand's `lowestOutput` **counter-starts-at-1** domain
separation is correctness-critical (flagged in its own comments). None is a vulnerability in the reviewed code —
each is a precisely-located assumption that keeps the scheme unbiased.

*Read-only, public-source. No transaction sent, no live system probed, no funds touched. Deep expansion of
`AUDIT-VALIDATOR-OPS-SWEEP.md` §V3.*
