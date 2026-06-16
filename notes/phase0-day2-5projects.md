# Phase 0 Day 2 — 5-project Ricci signal check

**Date:** 2026-06-16
**Tool:** `tools/run_ricci_signal.py` (new)
**Time:** 14 seconds wall-clock for 5 projects after bootstrap

## Headline

Ricci-low precision@K averaged across **N=4** projects (1 failed to fetch):
- K=10: **0.61× random** (honest lift below 1.0)
- K=20: **0.66×**
- K=50: **0.67×**

Per the Q3 sprint's Day-21 hard kill-switch (Ricci > 1.5× random), this is **NO-GO as observed**.

## Per-project numbers

| Project | Findings | Nodes | Base rate | K=10 lift | K=20 | K=50 |
|---|---|---|---|---|---|---|
| `code4rena_loopfi_2025_02` | 7 | 392 | 0.319 | **2.00×** | 2.00× | 1.87× |
| `code4rena_iq-ai_2025_03` | 9 | 61 | 0.574 | 0.43× | 0.64× | 0.30× |
| `code4rena_liquid-ron_2025_03` | 5 | — | — | (empty tarball URL in curated.json — fetch failed) |
| `code4rena_secondswap_2025_02` | 30 | 61 | 0.049 | 0.00× | 0.00× | 0.00× |
| `code4rena_fenix-finance-invitational_2024_10` | 15 | 770 | 0.042 | 0.00× | 0.00× | 0.50× |

## But — the measurement is unreliable, and I should not declare NO-GO yet

Two failure modes are confounded:

**(A) Ground-truth extraction is regex on free-form vuln descriptions.**

`corpus/scabench/curated.json` vulnerabilities only carry `(finding_id, severity, title, description)`. No structured file/function fields. My regex extracts `ContractName.sol#functionName` and `Contract::function` patterns — which works for projects where audit reports follow that style (loopfi) and fails for projects where they don't (iq-ai, secondswap).

Evidence of extraction failure:
- iq-ai: regex flagged **35 of 61 nodes (57%)** as vulnerable. Almost everything's flagged → no precision signal possible.
- secondswap: regex flagged **3 of 61 nodes (5%)**. Three targets is not enough to compute precision@10/20/50.
- fenix: regex flagged **32 of 770 nodes (4%)**. Same problem.

**(B) Ricci on small or disconnected graphs degenerates.**

iq-ai has 61 nodes / 36 edges. Largest connected component is 26 nodes. There's not enough geometric structure to differentiate. Real Ricci-curvature literature wants graphs with at least a few hundred well-connected nodes.

## What I'd want to do before declaring NO-GO

1. **Fix ground-truth extraction.** Two paths:
   - **Cheap:** small Claude call per project to extract `(file, function)` tuples from each vuln description into a canonical JSON. ~$0.05 per project × 31 projects = $1.55 total. Validates against my regex as a sanity check.
   - **Gold-standard:** manual labeling. 15 hours total. Resists drift.

2. **Filter the projects.** Drop secondswap/fenix-style projects where vuln descriptions don't carry function names at all — those are unmeasurable for any function-level ranking method, not just Ricci. Project filter: at least N=10 confirmed (file, function) tuples extractable.

3. **Drop the per-function precision target. Use coarser "contract-level" target.** "Did Ricci surface a function in a vuln-bearing contract?" was my original target — it works for loopfi precisely because base rate was 0.319 (Goldilocks zone). On iq-ai it broke because base rate 0.574 ≈ "everything". Need to renormalize precision against base rate (precision lift, not raw precision).

## What's solid regardless

- **Pipeline runs end-to-end on 5 projects in 14 seconds.** `tools/run_ricci_signal.py` is reusable; adding the next 26 projects is the same one-liner.
- **Loopfi result is real and reproducible.** 2.0× lift, two of seven findings located in top-10 by name (`PoolV3._updateBaseInterest`, `CDPVault.modifyCollateralAndDebt`).
- **Plumbline bootstrap shipped.** `./bootstrap.sh` works from a cold clone in ~28 seconds.
- **Identity fix shipped.** Scoreboard now groups by `project_id`, not `basename(path)`.

## Honest call

Loopfi's 2.0× is now visible as the **outlier**, not the rule. But the rule isn't measurable yet either — ground-truth extraction is doing too much work.

Next session: spend $1.55 on LLM-extracted ground-truth across all 31 projects, then re-run the signal check. If it still fails the 1.5× threshold, that's a clean NO-GO and the Q3 plan pivots to Option B (different signal: persistent homology? spectral?). If it passes, Phase 1 lights up.

This is the "negative-result note" the Q3 plan said to write if Phase 1 NO-GO'd. Difference: I'm holding the conclusion because the measurement is confounded, not because I'm hoping for a different answer.
