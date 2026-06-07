# Plumbline `/goal` library

Three goal-prompts, one per plumbline operating mode. Each is
≤4000 chars (the documented `/goal` hard limit), decomposed into
≤8 self-progressing steps (the documented Stop-hook block cap),
and built around the Anthropic-prescribed structure: one
measurable end state, a stated check, constraints that hold along
the way.

## Use

```bash
# Pick the one matching the session's mode, paste into Claude Code:
/goal "$(cat prompts/goals/CONTEST.goal.md)"

# or for between-contest:
/goal "$(cat prompts/goals/CORPUS_GROWTH.goal.md)"
```

`/goal` clears automatically when its condition is met. To pause
mid-session, use `/goal pause`. To force-clear, use `/goal clear`.
Goal state is restored on `--resume`.

## Which goal for which mode?

| Goal | When | Time budget | Cost |
|------|------|-------------|------|
| `CONTEST.goal.md` | An active contest is open and JH wants plumbline driving it | 1-3 days | ~$20 LLM ceiling enforced as a constraint |
| `ENSEMBLE.goal.md` | Want measured variance bands on sol_intent recall before contest day | 1-2 hours | ~$15 (3 runs × $5) |
| `RECALL_PROMPT.goal.md` | Cold sol_intent recall on a known corpus is bad and you want to fix it via prompt edit + A/B | 1-2 hours | ~$5 (one re-run) |
| `ROUTER_TRAIN.goal.md` | Implement ADR-006 verifier-router (schema → relabel → trainer → CLI) | 2-4 hours | $0 |
| `HYBRID_ROUTER.goal.md` | Close the tlc-routing gap by composing spec_retrieval as a pre-check before the ML router | 30-60 min | $0 |
| `CORPUS_GROWTH.goal.md` | Add ONE new TLA+ FailureMode shape (pair with `SHAPES_BACKLOG.md`) | 1-3 hours | $0 |
| `CA_SVM.goal.md` | Smallest viable kernel for grammar-driven evolution (mutator + 4-bucket measurement) | 30 min | $0 |
| `RAG_LEADS.goal.md` | Inject retrieved past .ANSWERS findings as few-shot to attack the sol_intent recall gap | 1 hour | ~$5 |
| `HYBRID_RAG.goal.md` | Combine RAG + spec_retrieval injection to close the M-02-style gap (shape exists in docs/tla/ but not .ANSWERS) | 1-2 hours | ~$5 |
| `ORACLE_LOOP.goal.md` | Oracle-grounded self-correction: each shape-matched lead gets revised by LLM to ground in spec mechanics. v0 — no TLC execution. | 2 hours | ~$3-8 |
| `MARGINAL_RECALL.goal.md` | T15 — per-verifier marginal recall across 5 corpora; ADR-006 step 5 prerequisite | 1-2 hours | $0 |
| `CALIBRATION.goal.md` | JH has 1-3 hours for cold-audit; or grading a finished contest | 1-3 hours | $0-2 |

## Design notes

These are written against verified Anthropic guidance (see
`docs/research/CLAUDE_GOAL_DESIGN_RESEARCH.md` for the deep-research
verdict). Material constraints:

1. **The evaluator (Haiku by default) sees only the transcript.** It
   cannot read files independently. Every "done when" check is
   written so its verification surfaces in Claude's own stdout
   (`grep`, `git log`, TLC's `Invariant ... violated`, etc.).

2. **8-block Stop-hook cap.** Each goal decomposes into 8 steps.
   Going beyond 8 requires `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=N` in
   the environment.

3. **Append-only data contracts.** All goals preserve the
   reps.jsonl + retrieval corpus invariants from CLAUDE.md.

4. **"Human only" is a legitimate terminal.** A goal can complete
   by routing to JH explicitly. This is by design — see
   ADR-006-verifier-router.md.

## What these goals deliberately don't do

- They don't require the CA / NCA layer (ARCHITECTURE.md §3 future
  work, out of scope per JH's "deliberately future" framing).
- They don't require constrained-decoding (T8 still pending).
- They don't blanket-trust LLM output. Every claim cited.

## Updating

These prompts are append-only-history (track changes in git, but
don't break old contest sessions that reference them by hash). If
a goal needs structural change, fork it as `CONTEST_v2.goal.md`
and leave v1 alone for any in-flight session resuming via
`--resume`.
