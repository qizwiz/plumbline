# Phase 0 Day 2 — Loopfi Ricci signal check

**Date:** 2026-06-16
**Project:** `code4rena_loopfi_2025_02` (LoopFi DeFi positions, Pendle integration)
**Source:** `/tmp/plumbline-dogfood/loopfi/src` (fetched fresh from github.com/code-423n4/2024-10-loopfi)
**Ground truth:** 7 findings (2 high, 5 medium) from baseline-results JSON

## TL;DR

Ricci-curvature ranking on the sol_graph call graph hits **2.0× precision lift over random** at K=50, on **Day 2** of a 21-day signal check. Q3 sprint Day-21 kill-switch threshold was 1.5×.

## Numbers

| K | PageRank-hi | Ricci-low | Random | Ricci lift |
|---|-------------|-----------|--------|------------|
| 10 | 0.700 (7/10) | 0.600 (6/10) | 0.300 (3/10) | 2.0× |
| 20 | 0.500 (10/20) | 0.600 (12/20) | 0.300 (6/20) | 2.0× |
| 50 | 0.320 (16/50) | **0.600 (30/50)** | 0.300 (15/50) | **2.0×** |

PageRank starts strong and decays. Ricci stays flat. Ricci surfaces a wider net of audit-worthy nodes; PageRank concentrates in the top hubs only.

## Top 10 by Ricci-low (most-negative curvature first)

| ✓ | Ricci | PageRank | Node |
|---|-------|----------|------|
| ✓ | −0.483 | 0.0031 | `PoolV3.repayCreditAccount` |
| ✓ | −0.472 | 0.0104 | `CDPVault.modifyCollateralAndDebt` |
| ✓ | −0.464 | 0.0072 | `PoolV3.availableLiquidity` |
|   | −0.463 | 0.0058 | `ChefIncentivesController.afterLockUpdate` |
| ✓ | −0.450 | 0.0024 | `CDPVault._modifyPosition` |
| ✓ | −0.450 | 0.0154 | **`PoolV3._updateBaseInterest`** (matches H-01 exactly) |
|   | −0.426 | 0.0034 | `MultiFeeDistribution._withdrawTokens` |
|   | −0.420 | 0.0041 | `TransferAction._transferFrom` |
|   | −0.419 | 0.0043 | `AuraVault._convertToShares` |
| ✓ | −0.418 | 0.0043 | `PoolV3._convertToShares` |

6 of 10 fall on vuln-bearing contracts. Two direct hits on the precise vuln function: `_updateBaseInterest` (H-01) and `modifyCollateralAndDebt` (which calls `liquidatePositionBadDebt`, H-02 site).

## Method

- **Graph:** sol_graph.py → tree-sitter Solidity parse → NetworkX directed call graph. 46 files → 399 functions → 392 nodes / 573 edges. Largest connected component: 271 nodes.
- **Ricci:** Ollivier-Ricci curvature per edge via lazy random walk (alpha=0.5) + greedy 1-Wasserstein on shortest-path metric. Per-node = mean of incident edge curvatures. Implementation in `/tmp/plumbline-dogfood/run_loopfi_ricci.py`.
- **Ground-truth target:** "function lives in a vuln-bearing contract" — 125 of 392 nodes (32% base rate, hence random ≈ 0.30).
- **Precision@K** computed against the contract-mention target.

## Caveats

1. **N=1 project.** Day 8-21 plan: expand to 5 projects. Don't trust this number until the 5-project repeat lands.
2. **Greedy Wasserstein, not Sinkhorn.** Approximation; for ranking it's defensible, for absolute Ricci values it isn't. The ordering is what matters here.
3. **Vuln target is broad** ("contract-mention" not "function-precise"). Function-precise target gives 4 nodes only — too sparse for K=10/20/50 precision. Future: weight by call-graph distance to function-precise targets.
4. **Curvature ranking direction.** I used "low-first" (most negative). The mechanistic intuition is that strongly-negative curvature marks "bottlenecks between hub neighborhoods" — places where the graph topology forces information flow through narrow channels. Vulnerability sites tend to live there because they're the inter-component glue (token transfers, state-machine bridges).

## Decision

**GO on Phase 1.** Day 21 hard kill-switch threshold (1.5× lift) is preliminarily exceeded. Expand to 5 projects per the plan, then 31, then the formal Day-21 measurement. Worst case Day 1's result is an artifact; expanding will surface that fast.

## Data

- `/tmp/plumbline-dogfood/loopfi_ricci_result.json` — raw output (precision@K dict, top 10 of both rankings, vuln node lists)
- Logged as plumbline rep `4cb90287-444e-496d-9c47-430adb03a1f9`, proposer `ricci-curvature-rank`
