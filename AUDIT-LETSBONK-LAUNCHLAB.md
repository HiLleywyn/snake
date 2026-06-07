# LetsBonk.fun / Raydium LaunchLab — Trust-Surface Map & Auditability Note

**Target:** LetsBonk.fun, a Solana bonding-curve launchpad running on **Raydium
LaunchLab** (program `LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj`).
**Artifacts reviewed (all public):** the LaunchLab **IDL** (account/instruction shapes),
the **SDK** `raydium-sdk-V2/src/raydium/launchpad/*` (a *client-side mirror* of the curve
math), and the **live configs** at `launch-mint-v1.raydium.io/main/{configs,platforms}`.
**Posture:** defensive, recompute-grounded. No exploit, no PoC. No bare "safe"; verdicts
say "enforced by constraint X" / "not enforced in reviewed path" / "unverifiable from
public artifacts." Anything exploitable would be routed privately to Raydium — none was
found, and (see §0) none *could* be, from these artifacts.

---

## §0. The decisive fact: this target is at the bottom of the auditability ladder

**The LaunchLab on-chain program is closed-source.** There is no published Rust for the
deployed BPF bytecode. What is public is:

- the **IDL** — the *shape* of accounts and instructions, not their logic;
- the **SDK** — a TypeScript re-implementation of the curve math that *claims* to mirror
  the program but is never reconciled against the bytecode by any on-chain consumer;
- the **configs** — parameters and authority wallets.

This is strictly weaker than every prior target in the corpus, and it sharpens the
"verified ≠ running" corollary from `AUDIT-GOVERNANCE-CEILING.md`:

| Auditability rung | Example | What you trust |
|---|---|---|
| Source = running, reproducible build | Sui, Litecoin (cloned at tag) | the compiler |
| Verified source, but proxy can swap it | WLFI (`0x3722` verified ≠ `0x59a3` running) | the upgrade key |
| **No source; vendor SDK mirrors opaque bytecode** | **LaunchLab / LetsBonk** | **the vendor's claim that the SDK == the bytecode** |
| No source, no SDK | a raw unverified program | nothing checkable |

LaunchLab sits on the **third** rung. The SDK is a *summary* of the program; the program
is the source state; **no one decompresses the summary back to the bytecode on-chain.**
That is exactly the §10 Compression/Expansion signature — *scale-change without
recomputation is the operational signature of a 6b trust boundary* — applied to the audit
itself. Therefore:

> **A Bucket-1 conservation verdict on LetsBonk is not derivable from public artifacts.**
> The curve math below is what the launchpad is *documented/SDK'd* to do; whether the
> deployed program *enforces* it is unverifiable without the bytecode. I will not
> manufacture a verdict the evidence cannot support.

What *is* derivable from public artifacts is the **trust-surface map** (§1), the
**three-coordinate placement** (§2), and **where the realistic open-source attack surface
actually is** (§3) — which, usefully, matches the strategic steer that prompted this:
the integrations, not the (unreadable) core.

---

## §1. Trust-surface map (from IDL + SDK + configs)

### Pool lifecycle & state (`LaunchpadPool` layout)

A per-token bonding curve holds value in `vaultA` (the launched token) and `vaultB`
(quote — WSOL or USD1). State tracks `status` (trading → migrated), `virtualA/virtualB`
(initial virtual reserves), `realA/realB` (traded amounts), `totalSellA`,
`totalFundRaisingB`, and three fee accumulators: `protocolFee`, `platformFee`,
`migrateFee`. Identity/authority pointers: `configId` (the bonding-curve config),
`platformId` (the platform config — this is the "LetsBonk" tenant), `creator`, and
**`mintProgramFlag`** (SPL vs **Token-2022** — see §3).

### The curve (constant product, SDK mirror)

`x·y=k` over `(virtualB + realB)` and `(virtualA − realA)`. Rounding in the SDK is
**pool-favorable both directions** — `getAmountOut` floors (buyer gets fewer tokens),
`getAmountIn` ceils (`ceilDivBN`, buyer pays more) — the correct anti-extraction
direction, *if the on-chain program matches* (unverifiable, per §0). The init-param
solver (`getInitParam`) derives virtual reserves `x0,y0` via nested `mul/div` with a
`denominator = tfMinusMf·totalSell/supplyMinusSellLocked − totalFundRaising`; with the
default config it is positive, but it is **config-driven** — a platform supplying its own
curve params controls whether this stays well-formed. (Client-side guard throws on
`x0<0||y0<0`; the on-chain guard is unverifiable.)

### Live trust parameters (from configs)

- **Default curve:** supply `1e15`, `totalSellA 793.1e12`, `totalFundRaisingB 85e9`
  (≈85 SOL), `tradeFeeRate 2500`, `maxLockRate 800000`, `minMigrateRateA 150000`.
- **Authority wallets (the governance ceiling, §2):** `protocolFeeOwner rayvTL…`,
  `migrateFeeOwner rayHQt…`, `migrateToAmmWallet RAYzrepo…`, `migrateToCpmmWallet
  RAYpQbF…`, platform fee/lock-NFT wallets `rayfqP1…`/`RaysvGD…`.
- **Fee split (platform config):** `feeRate 7500`, `creatorFeeRate 500`, and a
  `creatorScale/burnScale/platformScale` split of migration proceeds. A platform can set
  `requiresPlatformAuth` and its own curve.

### Instruction surface (IDL)

`buy*/sell*`, `migrateToAmm`/`migrateToCpmm` (the graduation seam), `claimVestedToken`
(creator vesting), `claimPlatformFee` / `claimCreatorFee`, and an `updateConfig`-style
admin path (`migrateCpLockNftScale`, etc.). Value-moving authority concentrates in the
migrate + claim instructions.

---

## §2. The three coordinates (what public artifacts *do* show)

- **Equivalence / 6b (`AUDIT…RETROSPECTIVE §9`):** the dominant equivalence here is
  *"the SDK/IDL behavior == the deployed bytecode."* It is discharged by **vendor trust
  alone** — there is no proof, no verified source, no on-chain reconciliation. This is the
  weakest discharge of any target reviewed.
- **Conservation floor (§11):** the curve *intends* a constant-product floor with
  pool-favorable rounding (medium-strength runtime arithmetic, *if enforced on-chain*).
  **Unverifiable from public artifacts** — the floor's existence is asserted by the SDK,
  not demonstrable. Verdict: **not establishable in the reviewed (public) path.**
- **Governance ceiling (`AUDIT-GOVERNANCE-CEILING.md`):** high and central. The program is
  an **upgradeable** Solana program under Raydium's upgrade authority (apex power: replace
  the bytecode wholesale — and there's no source baseline to diff against). Beneath it: the
  `ray*` fee/migration wallets, and per-platform `configId/platformId` admins who set
  curve params, fees, and `requiresPlatformAuth`. **trust-boundary debt, by design** — and
  more opaque than WLFI's, because the thing the upgrade key can change was never published
  in the first place.

---

## §3. Where the realistic *open-source* attack surface actually is

Because the core is unreadable, source-level review of LetsBonk itself is not possible from
public artifacts. The expected-value surface for this *class* — and the part that is
genuinely open source — is the **periphery**, which also matches the steer that prompted
this audit:

1. **Token-2022 launches (`mintProgramFlag`).** The pool state carries an SPL-vs-Token-2022
   flag. Token-2022 **transfer hooks** and **transfer-fee** extensions are the canonical
   place where a curve's value accounting silently breaks: if the curve credits `amountIn`
   but a transfer fee/hook diverts part of the transfer, `vaultA/vaultB` deltas diverge
   from the recorded `realA/realB`. *Whether LaunchLab restricts or correctly handles
   Token-2022 mints on the curve is exactly the high-value question* — and it is
   **unverifiable from the SDK** (the flag exists; the handling is in the bytecode). This
   is the single most worthwhile thing a researcher *with the bytecode or a devnet* should
   characterize, stated here as *where the trust concentrates*, not as an exploit.
2. **The migration/graduation seam (Bucket 6).** `migrateToAmm`/`migrateToCpmm` move the
   raised quote + remaining tokens into a Raydium AMM/CPMM pool, applying `migrateFee` and
   the `creatorScale/burnScale/platformScale` split. The conservation question "curve
   vault balances in == AMM pool + fees + burns out" is the classic launchpad settlement
   seam; authorization (who can trigger, can it be front-run or triggered early/late
   relative to `status`) is the trust boundary.
3. **Third-party integrations built *on* LaunchLab** — vaults, trading bots, and the
   open-source MCP/SDK wrappers (e.g. community `raydium-launchlab-mcp`). These *are*
   readable, and per the steer ("Meteora/Sanctum integrations, third-party vaults,
   wallets/bots") are the realistic place where reviewable bugs live: slippage/min-out
   handling, PDA/account-substitution validation, and trusting client-computed curve
   amounts (the SDK math) as if authoritative.

None of these is asserted as a vulnerability; each is named as a **trust concentration**
to characterize, consistent with defensive posture.

---

## Summary

| Item | Verdict |
|---|---|
| Curve rounding direction (SDK) | pool-favorable both ways **in the SDK mirror**; on-chain match **unverifiable** |
| Bucket-1 conservation (on-chain) | **not establishable from public artifacts** (closed-source program) |
| SDK/IDL ⇄ bytecode equivalence (6b) | discharged by **vendor trust only** — weakest in the corpus |
| Governance ceiling | **high** — upgradeable closed-source program + `ray*` wallets + per-platform admins |
| Token-2022 handling (`mintProgramFlag`) | **unverifiable; highest-value question** for a bytecode/devnet review |
| Migration seam authorization & conservation | **unverifiable; the classic launchpad settlement boundary** |
| Realistic open-source review target | the **periphery** (integrations/bots/vaults), not the core |

## Nothing routed privately — and why

No exploitable path was found, because **no source exists to find one in** from public
artifacts; I will not reverse-engineer the bytecode into exploit tooling, and I did not
fabricate a finding to satisfy a bug-hunting frame. The honest, defensible conclusion is
methodological and it is the real deliverable:

> **LetsBonk/LaunchLab is the corpus's clearest case of an unverifiable conservation
> floor under a high, opaque governance ceiling: you are asked to trust that an
> upgradeable, closed-source program faithfully implements a curve described only by a
> vendor SDK that nothing on-chain ever checks against the bytecode.** The strategically
> correct place to spend review effort on this *class* is the open-source periphery
> (Token-2022 curve handling characterized on devnet; the migration seam; third-party
> integrations), not the unreadable core — which is precisely the steer that prompted it.

Companion to `AUDIT-GOVERNANCE-CEILING.md` (this is its sharpest "no verified source at
all" instance) and `AUDIT-METHODOLOGY-RETROSPECTIVE.md` §9–§11 (equivalence / floor /
ceiling).
