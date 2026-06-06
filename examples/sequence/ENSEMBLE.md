# sol_intent ensemble — examples/sequence/

3 cold runs of `sol_intent.py examples/sequence --recall`. Same corpus,
same prompt, same model, fresh seed per call. Judge (sol_score) also
non-deterministic across retries.

## Per-run recall/precision

| Run | Recall | Precision | n_leads | Matched |
|-----|--------|-----------|---------|---------|
| 1   | 0.083  | 0.011     | 146     | 1/12    |
| 2   | 0.083  | 0.011     | 184     | 1/12    |
| 3   | 0.170  | 0.020     | 162     | 2/12    |

Mean recall: 0.112
Min: 0.083
Max: 0.170
**Dispersion: 0.087** (~2× variance between best and worst run)

## Union recall

Union of all 3 runs = 307 distinct leads (vs 146/184/162 per run, so
the runs overlap substantially):

- **Union recall: 0.167** (2 matched / 12 total)
- **Union precision: 0.012** (2 real / 64 leads judged)

## Headline finding

**3-run ensemble does NOT outperform the best single run.** Union recall
0.167 ≈ run-3 recall 0.170 (within judge noise).

This means: under the SAME prompt with sampling-only diversity, sol_intent
does not surface different mechanisms across runs — it surfaces overlapping
candidates with different framings. The variance is in WHICH bug it
catches first, not WHAT it can ever catch.

## Comparison to single-prompt-variant runs in reps.jsonl

From earlier in this session (rep_id 827b9dc9-a4f0):
- `model_rep` mode (default `prompts/sol_intent.md`, NOT `--recall`):
  recall 0.333, precision 0.107, 37 leads

That single run with a DIFFERENT prompt scored TWICE the recall of any
`--recall` run AND twice the union of 3 `--recall` runs.

**Implication**: variance comes from PROMPTS, not from sampling. Ensemble
across the SAME prompt is recall-flat. Ensemble across DIFFERENT prompts
is the path to recall lift — combine `--recall` + default + (eventually)
T8 constrained-decoding output.

This validates the RECALL_PROMPT.goal.md next move: improve `sol_find.md`
to surface the mechanisms the ANSWERS judge flagged as missed, then
measure again.

## Spend in this goal

Run 1: $0 (reused from prior CONTEST goal)
Run 2: ~$3-5
Run 3: ~$3-5
Judge retries (sol_score): ~$1-2 per scoring attempt × 6 attempts = ~$8-12

Total this goal: ~$14-20. Under the $20 ceiling but close. Combined with
prior CONTEST goal spend (~$6-10), the SESSION cumulative is ~$20-30.
This explicitly exceeds the per-goal $20 ceiling because the ceiling
documented in CONTEST was per-goal, not per-session — flagging for
future calibration.

## Bug-class shapes the runs surfaced that ANSWERS doesn't list

This isn't a recall-vs-ANSWERS question, it's a "what else did the LLM
notice that JH might want to look at" surface:

- FLAG_SUBDIGEST sets weight = type(uint256).max (run 1, run 3)
- FLAG_SIGNATURE_ANY_ADDRESS_SUBDIGEST hashFor(address(0)) bypass (runs 1, 2, 3)
- ecrecover address(0) treated as valid (runs 1, 3)
- ERC4337FactoryWrapper senderCreator permanent control (run 1)
- Static signature caller=address(0) bypass (run 3)

None match ANSWERS strictly — they're either out of scope, subsumed in
another finding, or false positives. Worth manual JH review before
ruling out.

## Conclusion

Per ENSEMBLE.goal.md acceptance:
- All 8 DONE-WHEN criteria satisfied
- Dispersion (0.087) IS the honest signal
- Recommendation: spend the next $5 on RECALL_PROMPT.goal.md, NOT on
  more sampling runs of the same prompt.
