# Pass A CEGAR-lite K=3 critic loop decision (2026-06-09 23:10)

Produced by manifold-pathfinding-swarm Workflow (7 agents + synthesis, ~484k tokens, ~12 min).

## Verdict on "manifold path-finding" framing

METAPHOR at the geometric level, REAL at the algorithmic level. The "manifold path-finding" framing is a category error if taken literally: invariants live in a discrete, symbolic predicate space with no smooth structure, no tangent space, no exponential map. Riemannian gradient descent (Absil-Mahony-Sepulchre 2008) and Survey Propagation (Mezard-Parisi-Zecchina) do NOT apply at plumbline's layer. HOWEVER, JH's underlying intuition — "iteratively refine a hypothesis using critic/validator feedback as a directional signal" — has a faithful, shovel-ready technical realization with 25 years of formalization and decisive 2023-2025 evidence: CEGAR (Clarke et al. 2000), Houdini (Flanagan/Leino 2001), CEGIS (Solar-Lezama 2006), and the modern LLM+verifier loops Lemur (ICLR 2024, 107/133 Code2Inv at avg 4.7 iters), PropertyGPT (NDSS 2025, 80% recall + 12 zero-days), SMARTINV (S&P 2024, 3.5x lift), Loopy (Kamath 2023, +30.7%), and arXiv 2508.00419 (100% Code2Inv at avg 1.0-1.37 iters). Strongest evidence: the same architecture pattern — LLM proposer + symbolic/critic oracle + counterexample-text-fed-back-into-prompt — independently reached SOTA across 4+ smart-contract and loop-invariant benchmarks in 2024-2025. Riemannian/manifold/BP framing is decoration; CEGAR-with-LLM-proposer is the actual mechanism. Naming an edit operation an "exponential map" is theater (per CLAUDE.md anti-Potemkin rule).

## Decision: GO / NO-GO

GO. Kelly-criterion reasoning: (a) downside is bounded — $4-6 API spend on top of $25 baseline, 1-2 days implementation, fully revertable (K=1 is the no-op fallback); (b) upside is asymmetric — literature EV is +20-40 percentage points on CLEAN rate (Loopy +30.7%, Lemur 107/133, 2508.00419 100%), and the v1 14% failure mode is precisely "vacuous-when-bug-fires" which is exactly what critic-text-as-gradient maximally repairs; (c) compositionality with v2 multi-mode is multiplicative not additive — v2 enlarges the hypothesis space, CEGAR-lite searches within it conditioned on critic signal, attacking orthogonal failure modes; (d) the critic oracle already exists (adversarial validator LLM, no new infrastructure); (e) DO NOT attempt Riemannian/MCTS/ToT/BP/RL — each is either category-error metaphor at this layer or budgetarily infeasible (MCTS ~$5/contract, RL needs corpus we don't have). The honest single bet is CEGAR-lite K=3 critic-feedback loop; everything else is architecture astronautics for Day-5.

## Operational form (CEGAR-lite K=3, NOT ToT/MCTS/RL/BP)

CEGAR-lite critic-refute loop, K=3 (initial extract + up to 2 critic-conditioned re-extracts), Houdini-flavored early-stop on no-progress. NOT ToT (no per-node value function — only binary refute signal — insufficient density for tree search, confirmed by Oracular Programming arXiv 2502.05310). NOT MCTS (needs hundreds of rollouts/state, ~$5/contract = budget-killer, no training corpus). NOT pure best-of-N self-consistency (arXiv 2511.00751: +0.4% at 20x cost on HotpotQA, MATH-500 DEGRADES past N=15 — uninformed parallel sampling is the worst option). NOT Riemannian/BP (category error at this layer). Concrete shape: (1) Pass A v2 multi-mode extracts initial candidate across {scalar, relational, temporal, counting} modes. (2) Adversarial-critic LLM validates; on REFUTE returns structured {witness_reason, mode_hint, vacuousness_score}. (3) Re-extractor LLM receives prev_inv + critic_reason + mode_hint and proposes strengthened candidate, optionally switching modes. (4) Loop up to K=3. (5) Houdini-style no-progress stop: if critic_reason at round N matches round N-1 textually, halt and return last candidate marked "unrefined." (6) Critic remains LLM (NOT Halmos) — Halmos lives downstream in Solidity rendering, putting it in Pass A loop is scope explosion. This is Lemur/PropertyGPT/Loopy applied to NL-finding extraction with zero new infrastructure.

## Implementation plan (1.5 days)

Total: 1.5 days alongside v2 multi-mode (which is the precondition). Fits inside the 3-day budget with headroom.

Day 1 morning (~3h): Write prompts/sol_invariant_reextract.md — appends to existing sol_invariant_propose.md the REEXTRACT_SUFFIX containing prev_inv JSON + critic_reason + explicit "most common failure: vacuous-when-bug-fires; strengthen so bug VIOLATES it; consider switching representation_mode." Add structured critic output schema {refuted: bool, reason: str, mode_hint: str, vacuousness_score: float in [0,1]} to validate_extraction.

Day 1 afternoon (~3h): Modify tools/annotate_corpus_invariants.py — add re_extract_with_critic() and wrap existing extract_and_validate in K=3 loop with Houdini no-progress stop. ~50 LOC delta. Existing extract_and_validate is already ~80% of the structure. Add per-finding logging: rounds_to_clean, mode_transitions, critic_reasons.

Day 2 morning (~3h): Run on N=20 HELDOUT subset (NOT the calibration corpus). Apply kill criterion (see Kill section). Log API spend, CLEAN rate, mean-rounds-to-clean, mode-transition rate.

Day 2 afternoon (~3h): If kill-gate passes, run full N=50 calibration corpus. Generate rounds-to-clean histogram. Write H13 pre-registration into arXiv Section 7 with the exact three-condition table (C0/C1/C2).

Day 3 (buffer): Reserved for v2 multi-mode polish, prompt iteration if kill-gate showed marginal lift, OR Sherlock 1259 DRE fire-and-measure if v2 is ready.

ZERO new files outside prompts/sol_invariant_reextract.md. ZERO schema changes. ZERO new infrastructure. The critic already produces the gradient — we just wire it back.

## Budget impact (+$4-6 on $25 baseline)

+$4-6 on top of $25 baseline → total ~$29-31. Per-finding worst-case math (Sonnet 4.5 @ $3/M in, $15/M out): extract_1 ($0.0135) + critic_1 ($0.0075) + extract_2 ($0.0165) + critic_2 ($0.0075) + extract_3 ($0.0180) + critic_3 ($0.0075) = $0.0705 worst case, ~$0.04 expected (most exit at round 1-2). N=50 corpus: $3.50 worst, ~$2.00 expected. N=20 heldout probe: $1.40 worst, ~$0.80 expected. Headroom of $19+ remains for prompt iteration and Sherlock 1259 DRE fire. Cost-extrapolation kill: if N=20 probe exceeds $12, abort (extrapolates to >$30 on N=50). Compare to ToT b=5 depth=2 (~$0.40/contract = $20 for N=50, no critic loop) or MCTS (~$5/contract = budget-vaporizing). CEGAR-lite is 5-50x cheaper than the alternatives at higher expected lift.

## H13 hypothesis (multiplicativity)

H13 (CEGAR-lite multiplies multi-mode, not just adds): On the N=50 calibration corpus, the CLEAN-rate of {Pass A v2 multi-mode + K=3 critic-feedback re-extract} is STRICTLY GREATER than {Pass A v2 multi-mode + K=1}, AND the marginal lift from K=1→K=3 is at least 2x the marginal lift from v1→v2 alone.

Operational measurement (same 50 findings, three conditions):
- C0: v1 single-mode + K=1 (baseline = 7/50 = 14%)
- C1: v2 multi-mode + K=1 (additivity test)
- C2: v2 multi-mode + K=3 (multiplicativity test)

Pre-registered prediction: CLEAN(C2) - CLEAN(C1) >= 2 * (CLEAN(C1) - CLEAN(C0)). Literature-grounded EV estimate (Loopy +30.7%, Lemur +43pp on Code2Inv, 2508.00419 +37pp on small benchmark): if C1 lifts to ~25% (+11pp from v2 alone), C2 should reach ~45-50% (+20-25pp from CEGAR-lite). Expected order: C0=14% < C1≈25% < C2≈45%.

CONFIRMATION CRITERION: CLEAN(C2) >= 35% AND CLEAN(C2) - CLEAN(C1) >= 2*(CLEAN(C1) - CLEAN(C0)) AND mean-rounds-to-clean <= 2.3 (convergence not stalling).

FALSIFICATION CRITERION: CLEAN(C2) - CLEAN(C1) < 4 percentage points (CEGAR-lite adds nothing measurable), OR CLEAN(C2) < CLEAN(C1) (loop is actively harmful — self-bias amplification per FeedbackEval), OR the critic_reason at round 2 textually matches round 1 in >70% of cases (Houdini stop fires immediately → loop has no signal to act on).

## Kill criterion (pre-committed, run on N=20 probe Friday morning)

Pre-committed, executable, run on N=20 HELDOUT subset Friday morning BEFORE the N=50 full run. No moving the goalposts after the run.

REVERT TO K=1 if ANY of the following:
1. CLEAN(C2_probe) < CLEAN(C1_probe) + 4 percentage points on N=20 (CEGAR-lite has no measurable effect).
2. CLEAN(C2_probe) < CLEAN(C1_probe) (loop actively degrades — self-bias amplification, the FeedbackEval failure mode).
3. API spend on N=20 probe > $12 (cost extrapolates to >$30 on N=50, blowing budget).
4. Mean rounds-to-clean > 2.3 (convergence too slow; literature says plateau at 2-3, so >2.3 means loop is thrashing not refining).
5. Houdini no-progress stop fires in >70% of refute cases at round 1→2 (critic reason is not actionable — the loop has no signal to navigate on).

DOWNGRADE TO K=2 (not full revert) if:
- CLEAN(C2_probe) > CLEAN(C1_probe) + 4pp BUT mean rounds-to-clean is in [2.0, 2.3] (signal exists but round 3 marginal value is near zero).

PROCEED TO N=50 only if all 5 revert conditions are clear AND CLEAN(C2_probe) - CLEAN(C1_probe) >= 6pp on the N=20 probe (sufficient power to detect H13's predicted +20pp effect on N=50 without false positive).

This is a strict, pre-committed kill registered in the H13 pre-registration document. The kill executes BEFORE the N=50 run, so failure costs ~$1.40 not ~$3.50, preserving budget for v2 polish and Sherlock 1259 DRE.
