Between-contest goal: hybrid RAG that injects BOTH .ANSWERS findings
AND matched TLA+ shape descriptions into sol_intent prompts. Closes
the M-02 gap (shape exists in docs/tla/ but not in .ANSWERS, so
RAG-only missed it). Per IS_RAG_THE_BEST.md top-1 recommendation.
~$5, <4000 chars; 8-step.

---

For examples/sequence, hybrid retrieval combining (a) past .ANSWERS
via rag_query (b) matched TLA+ shapes via spec_retrieval into one
few-shot block. Re-run sol_intent, score, compare to RAG-only
baseline 0.42. Headline = recall delta vs RAG-only.

DONE WHEN ALL EIGHT HOLD:

1. tools/hybrid_rag_query.py exists, ≤100 LOC. Calls both
   rag_query.retrieve (with exclude_corpus) AND
   spec_retrieval.query_top (no exclusion — TLA+ shapes are shared
   across contests by design). Formats unified block:
   "## RELEVANT PAST EVIDENCE" with sub-sections for past .ANSWERS
   findings and matched TLA+ shape descriptions.

2. My transcript shows a smoke-test invocation:
   `echo "ERC4337 entrypoint signature validation" | python tools/hybrid_rag_query.py sequence 3`
   returns BOTH a boss-bridge/t-swap signature finding AND the
   ERC4337StaticSigDoS shape description in the same block.

3. prompts/sol_find_hybrid_rag.md exists — variant of sol_find_rag.md
   that names the slot {{retrieved_evidence}} (broader label since
   it now includes shapes not just findings) and tweaks the guidance
   to mention both inspiration sources.

4. sol_intent.py accepts --hybrid-rag flag (additive, default off).
   When set: corpus extracted from path; rag_query excludes that
   corpus; spec_retrieval doesn't exclude.

5. My transcript shows
   `python sol_intent.py examples/sequence --recall --hybrid-rag`
   exit 0. Output saved to examples/sequence/sol-intent-hybrid-rag.txt.
   LLM cost tracked.

6. examples/sequence/hybrid-rag-ab.md exists with three-way comparison:
   - cold baseline (ENSEMBLE): 0.08-0.17
   - rag-only (RAG_LEADS result): 0.42 stable
   - hybrid-rag (this goal): 0.NNN
   - delta vs rag-only: +/- 0.NNN
   - per-judge band (2 score attempts)

7. M-02 check: transcript spot-checks whether M-02 surfaced. Goal's
   architectural prediction is that injecting ERC4337StaticSigDoS
   shape surfaces M-02. If M-02 still misses, that's honest signal —
   prompt-injection insufficient for deep-semantic bugs; escalate to
   self-correction-with-oracle (deep-research top-3 #3).

8. `git push origin main` succeeded; git log shows ≥1 commit
   touching tools/hybrid_rag_query.py + sol_intent.py + hybrid-rag-ab.md.

CONSTRAINTS:

- $5 ceiling per goal contract — one hybrid-rag run + 2 scoring
  attempts, then stop.
- LEAKAGE: .ANSWERS index excludes target corpus (sequence here);
  spec_retrieval does NOT exclude (TLA+ shapes are shared
  vocabulary, not corpus-specific).
- Don't modify prompts/sol_find_rag.md or rag_query.py — hybrid is
  a NEW layer composing them, not replacing.
- v0 retrieves top-3 from each source for K=6 total injection.
  Don't grid-search K mid-goal.
- Honest report: compare vs the RAG-ONLY baseline (0.42), not vs
  cold (0.08-0.17). The win bar is +0.05 or more delta over 0.42.
- If hybrid-rag recall ≤ rag-only recall: ship honestly. RAG plus
  spec_retrieval injection didn't help. The deep-research's
  prediction was 0.10-0.20 lift; null result is honest signal.

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: M-02 surfaces. If recall lifts but M-02 still
  misses, that's partial pass — lift came from other shapes.
- Self-critique at step 6: did I bias K, threshold, or prompt
  structure? Answer in hybrid-rag-ab.md.
- Combined injection ≤ 2000 tokens to avoid context pressure.

OUT OF SCOPE:

- Embedder fine-tuning (premature; see IS_RAG_THE_BEST.md).
- LM fine-tuning (corpus < 200, premature).
- Self-correction-with-oracle loop (deep-research top-3 #3; separate
  session if this goal doesn't deliver).
- Authoring new TLA+ shapes (CORPUS_GROWTH.goal.md).

If --hybrid-rag run somehow exceeds the $5 ceiling per the LLM call
cost estimate, surface — the hybrid block is longer than RAG-only,
and cost-per-chunk may scale differently than the budget assumed.
