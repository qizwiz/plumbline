Between-contest goal: Path B from ORACLE_LOOP. After three
consecutive null prompt-engineering experiments (HYBRID_RAG,
ORACLE_LOOP v0, LEAD_VOCAB), actual TLC execution per lead is
empirically warranted. v1 oracle loop: generate .cfg with lead
specifics → run TLC → confirm via counterexample OR revise via
LLM given oracle verdict. <4000 chars; 8-step.

---

For sol_intent leads on examples/sequence, second-pass loop:
each lead matching a TLA+ shape (cos > 0.55) gets a generated
.cfg, runs TLC, and either CONFIRMS (counterexample produced) or
REVISES (LLM given the "no violation" verdict to restate the lead).
Compare to oracle-loop v0 baseline (0.17-0.46 band). Headline: does
M-02 surface, confirmed via TLC.

DONE WHEN ALL EIGHT HOLD:

1. tools/tlc_oracle_loop.py exists, ≤180 LOC. For each shape-matched
   lead, calls a new tools/cfg_generator.py to produce a .cfg with
   constants derived from the lead text via LLM (uses
   prompts/cfg_gen.md). Runs TLC against the matched .tla + the
   generated .cfg. If TLC violates → CONFIRMED (attach counterexample);
   if TLC passes → ask LLM to revise lead with verdict context.

2. tools/cfg_generator.py exists, ≤80 LOC. Takes (spec_name,
   lead_text), returns a .cfg string with CONSTANTS set per the
   lead. Defaults to the existing .cfg's bounds if extraction fails.

3. prompts/cfg_gen.md exists — guidance for generating a .cfg from a
   lead. Includes the existing .cfg as template.

4. prompts/tlc_revise.md exists — when TLC says "no violation,"
   guidance to revise the lead: "the verifier ran your bug claim
   on a model of this code and found no violation. Either the claim
   is wrong, the model is too narrow, or the mechanism is different.
   Restate the lead more precisely or mark NOT-A-BUG."

5. sol_intent.py accepts --tlc-oracle flag. Pipeline: hybrid-rag
   generate → tlc_oracle_loop per shape-matched lead → output.
   Compose with --mechanism (separate flag).

6. Cold run:
   `python sol_intent.py examples/sequence --recall --hybrid-rag --tlc-oracle`
   exits 0. Output to examples/sequence/sol-intent-tlc-oracle.txt.
   LLM + TLC cost tracked. TLC runs MUST timeout at 30s/lead.

7. examples/sequence/tlc-oracle-ab.md exists with 6-way comparison
   including N_confirmed (TLC violations), N_revised (LLM revisions
   after TLC no-violation), N_skipped (no shape match). M-02 check
   is the key. Goal contract: M-02 surfaces with TLC counterexample
   attached.

8. `git push origin main` succeeded; commit touches
   tools/tlc_oracle_loop.py + tools/cfg_generator.py +
   prompts/cfg_gen.md + prompts/tlc_revise.md + sol_intent.py +
   tlc-oracle-ab.md.

CONSTRAINTS:

- $10 ceiling. v1 is more expensive than v0 (cfg generation +
  potential revision per matched lead). Surface BEFORE 2nd run.
- TLC timeout 30s/lead. If exceeded, mark NEEDS-LARGER-BOUND and
  pass through unchanged.
- v0 oracle_loop.py and prompts/oracle_loop.md stay unchanged.
- Don't regenerate .cfg via prompt iteration mid-goal. One attempt
  per lead, fall back to default bounds on parse fail.
- v1 inherits v0's hybrid-rag wrap — runs as second pass on
  --hybrid-rag output, not standalone.

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: M-02 surfaces with TLC counterexample
  attached. The ERC4337StaticSigDoS spec, instantiated for the
  sequence chunk, MUST fire its CallerBoundAuthRespected
  invariant violation if the LLM-extracted CONSTANTS encode "msg.sender =
  EntryPoint, expected = userOp.sender."
- If TLC fails to fire on a lead the .ANSWERS says is real, the
  failure is in cfg_generator (couldn't extract the right
  CONSTANTS) — report which constants were used vs what would
  have been needed.

OUT OF SCOPE:

- halmos in the loop (separate verifier).
- Multi-shape match per lead (use top-1 only in v1).
- Sweep across other corpora (sequence A/B only).
- LM fine-tuning (corpus too small).

If cfg_generator fails to produce parseable .cfg for >50% of
matched leads, the failure is in the LLM's .cfg-syntax extraction,
not the architectural premise. Surface and either fall back to
default .cfg (every lead uses the spec's existing .cfg unchanged)
or escalate to constrained-decoding (T8) for .cfg generation
specifically.
