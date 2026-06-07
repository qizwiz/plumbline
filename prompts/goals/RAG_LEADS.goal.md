Between-contest goal: RAG over .ANSWERS.md history to improve
sol_intent recall on cold corpus. Attacks the ENSEMBLE bottleneck
directly (sequence cold ceiling = 0.17 single-prompt). v0 retrieval-
augmented few-shot, A/B against baseline, leakage-controlled. ~$5,
<4000 chars; 8-step.

---

Build a retrieval index over confirmed findings from 4 corpora
(NOT including sequence), inject top-K retrieved findings into
sol_find.md as few-shot examples, re-run sol_intent on sequence,
score vs baseline. The headline is recall delta.

DONE WHEN ALL EIGHT HOLD:

1. tools/build_findings_index.py exists (~80 LOC). Scans
   examples/<corpus>/.ANSWERS.md across all 5 corpora, extracts one
   finding per ## H- / M- / L- heading, lifts identifiers per
   spec_retrieval._lift_idents, embeds via fastembed bge-small,
   writes tools/findings_index.pkl with EACH finding tagged by
   source corpus (so we can exclude leakage at query time).

2. My transcript shows `python tools/build_findings_index.py`
   reporting saved-to path + total finding count (expected
   40-60: 12 sequence + ~7 boss-bridge + ~7 puppy-raffle + ~11
   t-swap + ~7 thunder-loan).

3. tools/rag_query.py exists. Takes (lead_chunk_text, exclude_corpus,
   k=3) and returns the top-K findings as a formatted
   "## SIMILAR PAST FINDINGS" markdown block, EXCLUDING any finding
   tagged with exclude_corpus.

4. prompts/sol_find_rag.md exists — a variant of sol_find.md that
   includes a `{retrieved_findings}` slot near the top, plus 2
   sentences of guidance: "Below are similar bugs from past audits.
   Use as inspiration; the target corpus may have ENTIRELY different
   bug shapes."

5. sol_intent.py is modified to accept `--rag` (additive flag, default
   off). When --rag is on: for each chunk before LLM call, run
   rag_query against the corpus name extracted from --recall path,
   inject the retrieved block into the prompt template.

6. My transcript shows
   `python sol_intent.py examples/sequence --recall --rag` exit 0.
   Output saved to examples/sequence/sol-intent-rag.txt. LLM cost
   tracked.

7. examples/sequence/rag-ab.md exists with the comparison:
   - baseline recall (from existing examples/sequence/sol-intent-leads.txt
     scored vs .ANSWERS.md): 0.0-0.17
   - rag recall (from new sol-intent-rag.txt scored vs .ANSWERS.md):
     0.NNN
   - delta: +/- 0.NNN
   - missed-mechanism set difference: bugs RAG caught that baseline
     missed + vice versa
   - honest verdict paragraph: did retrieval help, hurt, or do nothing?

8. `git push origin main` succeeded; git log shows ≥1 commit touching
   tools/build_findings_index.py + sol_intent.py + rag-ab.md.

CONSTRAINTS:

- $5 ceiling per goal contract — surface BEFORE the 2nd RAG run if it
  would exceed.
- LEAKAGE CONTROL: the index MUST exclude sequence findings when
  testing on sequence. Hard-fail if exclude_corpus is not respected.
- Don't modify sol_find.md (the baseline prompt). The RAG variant
  is a separate file so the A/B is honest.
- reps.jsonl is append-only — the new RAG rep gets logged but doesn't
  rewrite the baseline rep.
- v0 retrieves K=3 by default. Don't grid-search K mid-goal — that's
  a re-run.
- Honest reporting: if recall delta is ZERO or NEGATIVE, ship the
  result. RAG isn't magic; the data is the data.

OPERATING DISCIPLINE:

- The headline metric is RECALL DELTA on sequence. Precision delta is
  secondary (more leads = more noise expected).
- Per ENSEMBLE precedent: judge non-determinism is real. Run sol_score
  twice on each output and report the band, not just point estimates.
- Self-critique at step 7: "did I cherry-pick the K value, the
  exclude-corpus list, or the retrieved findings to make the result
  look better?" Answer in rag-ab.md.

OUT OF SCOPE:

- Production wire-up to all 5 corpora (this is sequence-A/B, not
  deployment).
- Tuning K, embedder, prompt structure beyond v0 — separate session
  if v0 lights up.
- RAG-guided CA/NCA mutation (needs more mutation reps first).
- Generalizing to non-Solidity domains.

If recall delta is NEGATIVE on sequence, surface — the retrieved
findings are confusing the model, not helping. Don't iterate prompt
structure mid-goal; that's the next session's work.
