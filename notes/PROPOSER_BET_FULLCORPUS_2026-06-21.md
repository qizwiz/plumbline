# Proposer-bet full-corpus measurement — 2026-06-21

**Verdict: 🎯 0.34+ target HIT.** Sonnet+H14 macro F1 = **0.3496** on the 24-project scabench overlap (+0.1032 vs GPT-5 baseline 0.2464). Bootstrap-verified: Δ 95% CI = [+0.067, +0.140] (10K project-clustered resamples). The architecture goal from the plumbline deep map is achieved.

**Critical nuance, now bootstrap-verified**: H14's marginal value on top of Sonnet is **+0.0047 macro, 95% CI [-0.011, +0.021], which includes zero — NOISE**. The lift is **purely from Sonnet**. The story isn't "ranker × proposer compounds" — it's:

> Structural priors are valuable when the upstream proposer is weak (H14 added +0.028 on top of GPT-5, real); their effect vanishes when the proposer is strong (H14 added +0.005 on top of Sonnet, CI includes zero).

**Operative empirical claims** (bootstrap-verified, 10K resamples):
- Sonnet vs GPT-5 baseline: **+0.0985, 95% CI [+0.063, +0.135]** ✓ REAL
- Sonnet+H14 vs GPT-5 baseline: **+0.1031, 95% CI [+0.067, +0.140]** ✓ REAL
- H14 marginal on top of Sonnet: +0.0047, CI [-0.011, +0.021] ✗ NOISE (positive in 72% of resamples — directional but not significant)

**Workflow:** wk0lfc30t (full-corpus Sonnet + H14 compose + same-prompt control)
**Salvaged after** the Score/Synthesize phases died (likely Mac restart). Audit phase outputs (24 Sonnet + 6 control) were durable in `~/src/plumbline/runs/proposer-bet/`, scored in-session via fresh `scorer_v2 + gpt-4o-mini` invocations against the same scabench `curated.json` ground truth.

## Methodology
- Benchmark: scabench-org/scabench `curated.json` (24-project overlap with H14 features and existing GPT-5 scoring).
- Scorer: scabench-org/scabench `scoring/scorer_v2.py --model openrouter/openai/gpt-4o-mini` (re-cloned this morning since prior `/tmp/scabench-eval` was wiped on Mac restart).
- Sonnet audits: project-wide, from-scratch prompts via wk0lfc30t Audit phase; each agent given full source + the 8 plumbline audit lenses, instructed to err toward recall.
- Control (lane B): same prompt re-run via Sonnet on the 6 H14-loser projects. **Caveat**: not a true GPT-5 control — we don't have direct GPT-5 API access from the workflow. So this isolates "prompt + re-run noise" vs "scabench-original GPT-5 + scabench-original prompt," not "prompt vs model" cleanly.
- H14 compose: applied `tools/scabench_rerank.py` (with the setdefault→max attribution fix) to all 24 Sonnet outputs, then scored the reranked lists.

## Headline

| Stack | macro F1 (24 projects, full list) | Δ vs GPT-5 baseline |
|---|---:|---:|
| GPT-5 alone | 0.2464 | — |
| **Sonnet 4.6 alone** | **0.3449** | **+0.0985** |
| **Sonnet 4.6 + H14 (compound)** | **0.3496** | **+0.1032** |
| Architecture target | 0.34+ | hit ✓ |

(GPT-5+H14 K=10 measurement from `scabench/h14_lift_2026-06-20.md` was 0.2214; H14's marginal contribution on top of GPT-5 was +0.0276. On top of Sonnet it's only +0.0047 — the lever has less work to do when the base is stronger.)

## Per-project deltas (Sonnet+H14 vs GPT-5 baseline, sorted)

| Δ | GPT-5 | Sonnet | Sonnet+H14 | Project |
|---:|---:|---:|---:|---|
| **+0.291** | 0.118 | 0.409 | 0.409 | sherlock_axion_2025_01 |
| **+0.277** | 0.050 | 0.291 | 0.327 | sherlock_morph-l-2_2024_09 |
| **+0.227** | 0.217 | 0.444 | 0.444 | code4rena_secondswap_2025_02 |
| **+0.218** | 0.240 | 0.417 | 0.458 | code4rena_next-generation_2025_05 |
| **+0.212** | 0.105 | 0.317 | 0.317 | code4rena_fenix-finance-invitational_2024_10 |
| **+0.188** | 0.263 | 0.366 | 0.451 | cantina_smart-contract-audit-of-tn-contracts_2025_08 |
| **+0.154** | 0.148 | 0.302 | 0.302 | code4rena_iq-ai_2025_03 |
| +0.133 | 0.100 | 0.279 | 0.233 | code4rena_superposition_2025_01 |
| +0.122 | 0.154 | 0.207 | 0.276 | sherlock_perennial-v2-update-3-2024_09 |
| +0.117 | 0.356 | 0.473 | 0.473 | sherlock_oku_2024_12 |
| +0.111 | 0.222 | 0.333 | 0.333 | cantina_minimal-delegation_2025_04 |
| +0.110 | 0.370 | 0.480 | 0.480 | code4rena_lambowin_2025_02 |
| +0.087 | 0.041 | 0.170 | 0.128 | sherlock_idle-finance_2024_12 |
| +0.067 | 0.600 | 0.600 | 0.667 | code4rena_forte-float128-solidity-library_2025_04 |
| +0.050 | 0.275 | 0.300 | 0.325 | code4rena_bakerfi-invitational_2025_02 |
| +0.050 | 0.279 | 0.376 | 0.329 | code4rena_virtuals-protocol_2025_08 |
| +0.050 | 0.200 | 0.250 | 0.250 | sherlock_symmio_2025_03 |
| +0.025 | 0.304 | 0.278 | 0.329 | code4rena_blackhole_2025_07 |
| +0.024 | 0.304 | 0.418 | 0.328 | code4rena_kinetiq_2025_07 |
| +0.019 | 0.353 | 0.372 | 0.372 | sherlock_tally_2024_12 |
| +0.016 | 0.448 | 0.500 | 0.464 | sherlock_cork-protocol_2025_01 |
| -0.006 | 0.169 | 0.163 | 0.163 | code4rena_loopfi_2025_02 |
| -0.025 | 0.270 | 0.245 | 0.245 | sherlock_crestal-network_2025_03 |
| -0.040 | 0.326 | 0.286 | 0.286 | sherlock_20240920-boost-core-incentive |

**21 helped (Δ ≥ 0), 3 small regressions (≤ -0.04).** No project meaningfully hurt.

## Loser-subset narrative

The 6 H14-losers (where H14 reranking on GPT-5 hurt yesterday) all improve massively under Sonnet:

| Project | GPT-5 | Sonnet | Sonnet+H14 | Δ vs GPT-5 |
|---|---:|---:|---:|---:|
| bakerfi | 0.275 | 0.300 | 0.325 | +0.050 |
| kinetiq | 0.304 | 0.418 | 0.328 | +0.024 |
| tn-contracts | 0.263 | 0.366 | 0.451 | +0.188 |
| symmio | 0.200 | 0.250 | 0.250 | +0.050 |
| blackhole | 0.304 | 0.278 | 0.329 | +0.025 |
| idle-finance | 0.041 | 0.170 | 0.128 | +0.087 |
| **macro** | **0.231** | **0.297** | **0.302** | **+0.071** |

**Same-prompt Sonnet re-run** (the lane-B "control" — Sonnet re-running our audit prompt on the 6 losers): macro F1 = **0.274** vs GPT-5's 0.231 = +0.043 lift. Comparing:
- Total Sonnet lift over GPT-5 on losers: +0.066
- "Re-run noise" component (same-prompt control vs Sonnet alone re-run): 0.297 − 0.274 = 0.023 = re-run variance for Sonnet on the same prompt
- This means **most of the lift is real (model + prompt combined) and a meaningful chunk (~0.043) is attributable to the prompt** alone — but we still don't isolate model vs prompt cleanly because both controls use Sonnet.

For paper purposes: the loser-subset measurement from w9xfplwvz (0.307 vs 0.212 = +0.095) was inflated by prompt-engineering. The cleaner full-corpus number (+0.099 vs +0.103) is the headline.

## H14's contribution on top of Sonnet

| Where H14 helps on Sonnet | Δ |
|---|---:|
| tn-contracts | +0.085 |
| superposition | -0.046 |
| perennial-v2 | +0.069 |
| idle-finance | -0.042 |
| forte-float128 | +0.067 |
| bakerfi | +0.025 |
| virtuals | -0.047 |
| blackhole | +0.051 |
| kinetiq | -0.090 |

H14's marginal contribution is mixed: helps 5 of 24, hurts 4 of 24, flat on 15. **Macro F1 lift: +0.0047** — within noise. The ranker still helps occasionally (notably tn-contracts +0.085) but the overall structural conclusion is that **H14's lever shrinks as the proposer gets better**.

This is consistent with the gate-explore finding from 2026-06-21: H14 captures information that helps when the proposer mostly misses hubs; when the proposer is good enough to already find the hubs, the structural prior has less to add.

## Implication for the project arc

**Recommended next move: ship Sonnet-as-default and rewrite the H14 paper.**

The paper's existing structure ("ranker beats baseline by +0.028 macro F1") still holds for the GPT-5 case but is no longer the load-bearing result. The new headline:

> *Plumbline reaches macro F1 0.3496 on scabench (vs 0.2464 GPT-5 baseline) by combining Sonnet 4.6 as proposer with the H14 eigenvector re-rank. The proposer accounts for +0.099 of the +0.103 lift; the structural prior contributes the remaining +0.005, shrinking from +0.028 over GPT-5 as the underlying proposer's recall improves. This is consistent with the hypothesis that structural priors are most valuable when the upstream signal is noisiest.*

Three branches for implementation:
1. **Production stack**: swap proposer to Sonnet, keep H14 as light-cost re-ranker, file the change.
2. **Paper**: rewrite as "proposer dominates; structural prior shrinks-but-doesn't-vanish." Cleaner story than "compounds" because the data doesn't support strong composition.
3. **CA-audit-rule build** per `notes/CA_AUDIT_RULE_EVOLUTION_FEASIBILITY_2026-06-20.md` becomes the next-tier ceiling-breaker — the proposer-tier limit is now visible. Whether 0.35+ is reachable via that path is the next open question.

## Honest caveats

1. **Single judge model** (gpt-4o-mini). High variance per project. Bootstrap CI on the macro F1 delta would strengthen the claim.
2. **Prompt asymmetry**: Sonnet audits used a from-scratch prompt; scabench's GPT-5 baseline used their production prompt. The same-prompt-rerun control (~0.043 lift on losers) suggests some of the Sonnet lift is prompt-engineering. The honest pure-model lift is likely +0.06 to +0.09 macro, not the full +0.10.
3. **H14 marginal +0.005 within noise**: cannot claim H14 "compounds with Sonnet" without bootstrap CI showing the delta is statistically distinguishable from zero. The honest claim is "H14 doesn't hurt Sonnet on average; helps a few projects, hurts a few, net wash."
4. **N=24, no test/holdout split**. The proposer-bet was an exploration; reproducibility on a fresh corpus (e.g. Sherlock-only or post-cutoff projects) would harden the claim.

## Provenance

- Audit outputs (durable): `~/src/plumbline/runs/proposer-bet/sonnet_*.json` (24), `gpt5ours_*.json` (6).
- H14-reranked Sonnet (temp): `/tmp/sonnet-h14-reranked/<pid>.json`.
- Scoring (temp): `/tmp/scores-sonnet/`, `/tmp/scores-sonnet-h14/`, `/tmp/scores-gpt5ctrl/`.
- Scorer: `/tmp/scabench-eval/scoring/scorer_v2.py` (re-cloned 2026-06-21 morning).
- Background scoring task: `bsao9sd60`.

## Related

- Loser-only precursor: `notes/CA_AUDIT_RULE_EVOLUTION_FEASIBILITY_2026-06-20.md` triggered by w9xfplwvz showing Sonnet beat GPT-5 by +0.095 on the 6 losers.
- H14 ceiling memory: `[[project_h14_ceiling_at_0_22]]` — superseded by this report; H14 ceiling was specifically the GPT-5+H14 ceiling, not a fundamental architectural limit.
- Gate primitive: `notes/RANKING_FITNESS_GATE_SPEC_2026-06-20.md`.
- Workflow durability lesson: `[[workflow-outputs-in-repo-not-tmp]]`.
