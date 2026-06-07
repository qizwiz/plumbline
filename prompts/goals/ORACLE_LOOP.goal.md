Between-contest goal: oracle-grounded self-correction loop. Use
spec_retrieval shape match as the FORCING FUNCTION to make the LLM
ground each lead in the matched spec's mechanics — the multi-hop
reasoning prompt-injection alone can't trigger. Per deep-research
top-3 #3. Attacks the M-02 gap HYBRID_RAG just left open. ~$3-8.
<4000 chars; 8-step.

---

For sol_intent leads on examples/sequence, second-pass loop: each
lead matching a TLA+ shape (cos > 0.55) gets revised by LLM to
GROUND it in spec mechanics (name variables, describe invariant
violation). Compare to hybrid-RAG 0.42. Headline = does M-02
surface.

DONE WHEN ALL EIGHT HOLD:

1. tools/oracle_loop.py exists, ≤120 LOC. Takes (leads.txt, corpus
   path). For each lead, calls spec_retrieval.query_top(k=1). If
   cos > 0.55, calls anthropic with the lead + matched spec's
   invariant + a revision prompt. Outputs revised-leads.txt where
   matched leads are GROUNDED in spec terms and unmatched leads
   pass through unchanged.

2. prompts/oracle_loop.md exists — the revision prompt: "Given this
   lead and a structurally-matching bug-class shape from a TLA+
   FailureMode library, REWRITE the lead as: (a) the spec's
   variables instantiated for this code, (b) the specific invariant
   that violates, (c) one-line attack path. If the shape doesn't
   actually apply, return the original lead unchanged with a NOTE."

3. Smoke test: transcript shows
   `echo "validateUserOp called by EntryPoint" | python tools/oracle_loop.py - sequence`
   returns a revised lead that names ERC4337StaticSigDoS's
   ExpectedSigner variable and describes the static-sig invariant
   violation. M-02 mechanism made explicit.

4. sol_intent.py accepts --oracle-loop flag (additive). Pipeline
   becomes: hybrid-rag generate → oracle_loop revise → output.

5. My transcript shows
   `python sol_intent.py examples/sequence --recall --hybrid-rag --oracle-loop`
   exit 0. Output saved to examples/sequence/sol-intent-oracle-loop.txt.
   LLM cost tracked (expect hybrid-rag cost + N_matched_leads * ~$0.10).

6. examples/sequence/oracle-loop-ab.md exists with 4-way:
   - cold (ENSEMBLE): 0.08-0.17
   - rag-only (RAG_LEADS): 0.42 stable
   - hybrid-rag (HYBRID_RAG): 0.42 apples-to-apples
   - oracle-loop (this goal): 0.NNN
   - delta vs hybrid-rag: +/- 0.NNN

7. M-02 SPECIFIC CHECK: transcript spot-checks M-02. Prediction:
   forcing the LLM to ground the lead in ERC4337StaticSigDoS's
   variables (msg.sender = ENTRY_POINT) makes the multi-hop
   reasoning explicit. If M-02 STILL misses, escalation is actual
   TLC execution per lead (v1, future goal).

8. `git push origin main` succeeded; commit touches
   tools/oracle_loop.py + sol_intent.py + oracle-loop-ab.md.

CONSTRAINTS:

- $8 ceiling (higher than usual because the loop adds per-matched-
  lead LLM calls). Surface BEFORE the 2nd full run if it would
  exceed.
- Only the SUBSET of leads matching a TLA+ shape gets revised.
  Unmatched leads pass through unchanged — no wasted LLM calls.
- Don't modify spec_retrieval.py or hybrid_rag_query.py — oracle
  loop is a NEW composing layer.
- Don't auto-execute TLC per lead in v0 — that's v1 scope. The
  loop only forces the LLM to REASON IN SPEC TERMS.
- If oracle-loop recall ≤ hybrid-rag recall: ship honestly. The
  forcing-function hypothesis didn't pan out; next escalation is
  actual TLC execution.

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: M-02 surfaces this time because the revision
  prompt FORCES the LLM to articulate caller-context transformation.
- If M-02 surfaces but recall lift is ≤+0.05, the headline win is
  M-02 specifically, not topline recall. Report both.
- Self-critique: did I write the revision prompt to nudge the LLM
  toward M-02 specifically vs let the spec do the work? Answer in
  oracle-loop-ab.md.

OUT OF SCOPE:

- Actual TLC execution per lead (v1 — write goal if v0 lights up).
- halmos in the loop (separate verifier).
- LM fine-tuning (corpus too small).
- Sweep across other corpora (sequence A/B only).

If the loop revises ZERO leads (i.e., no spec_retrieval match >0.55
on any sol_intent lead), the failure is upstream — the leads are
too generic to match any shape. Surface this; the fix is improving
sol_intent prompt to surface more shape-grounded leads, not iterating
the loop.
