Between-contest goal: CFG_DECODE — replace cfg_generator's free-form
LLM call with tool-use + JSON Schema constrained decoding. v0 on
ERC4337StaticSigDoS (M-02's spec) only. ~$5-10. <4000 chars; 8-step.

HONEST SCOPE: This makes cfg generation deterministic and
syntactically-correct-by-construction. It does NOT, on its own, fix
the v1 noise problem revealed by weak_confirm.py (the spec's
BuggyAction fires regardless of cfg content). The expected outcome
is: M-02 stays WEAK after this goal, but cfgs are now clean.

---

For ERC4337StaticSigDoS specifically, replace cfg_generator's
unconstrained LLM call with Anthropic tool-use + JSON Schema. The
schema enforces valid CONSTANTS shape; the model populates the schema
from the lead; we convert JSON → .cfg syntactically. Measure: does
M-02 STRONG-surface now (per weak_confirm), or does it stay WEAK?

DONE WHEN ALL EIGHT HOLD:

1. tools/cfg_decode.py exists, ≤200 LOC. Has a function
   `generate(spec_name, lead) -> (cfg_text, status)` matching
   cfg_generator's API. For specs without a schema, falls back to
   the existing cfg_generator.

2. schemas/erc4337_static_sig_dos.json exists — JSON Schema for
   ERC4337StaticSigDoS's CONSTANTS (Calls: list of identity tokens,
   EntryPoint: scalar identity, User: scalar identity). Field
   descriptions explain how leads should populate them.

3. prompts/cfg_decode.md exists — the tool-use prompt for v0:
   "Given a lead and a TLA+ spec's CONSTANTS schema, populate the
   schema such that the resulting cfg models the bug-class shape
   the lead describes."

4. Smoke test: my transcript shows
   `python tools/cfg_decode.py ERC4337StaticSigDoS "validateUserOp
   called by EntryPoint forwards msg.sender wrong"` produces a
   schema-valid .cfg with status="schema-decoded".

5. TLC integration: cfg_decode-generated .cfg runs through TLC
   successfully (Authorized4337CallsExecute violated, counterexample
   produced). My transcript shows the TLC output.

6. cfg_generator.py modified to call cfg_decode FIRST for specs that
   have a schema; falls back to its existing LLM path otherwise.
   Single new flag/code-path, no removal.

7. Re-run TLC oracle on examples/sequence using the new code path:
   `python sol_intent.py examples/sequence --recall --hybrid-rag --tlc-oracle`
   Output saved to examples/sequence/sol-intent-tlc-oracle-decode.txt.
   Apply weak_confirm filter, count STRONG vs WEAK per spec.

8. examples/sequence/cfg-decode-result.md exists with:
   - schema-decoded count vs LLM-fallback count
   - per-spec STRONG/WEAK distribution before vs after CFG_DECODE
   - M-02 status (STRONG / WEAK / MISSED)
   - HONEST verdict: did constrained decoding change anything?

CONSTRAINTS:

- $10 ceiling. Schema-decoded cfg generation costs ~$0.30/call;
  ~80 leads → ~$25 if every spec had a schema. v0 limits to
  ERC4337StaticSigDoS only.
- Don't modify the spec files (.tla) — that's LEAD_CONDITIONED_SPEC
  scope.
- Don't extend to other specs in v0. If ERC4337 result is positive,
  extension is v1 work.
- Honest report. If schema-decoded cfgs produce IDENTICAL TLC
  behavior to LLM-decoded cfgs (which is the predicted outcome),
  the v0 conclusion is "constrained decoding alone doesn't fix
  noise — must edit specs."

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: cfg generation is now deterministic, BUT M-02
  stays WEAK (predicted) because the noise problem is in the spec
  architecture, not the cfg. If M-02 unexpectedly goes STRONG, that
  upgrades the goal to a positive result and warrants extending
  schemas to other specs.

OUT OF SCOPE:

- Modifying TLA+ spec files to add lead-conditioned actions
  (LEAD_CONDITIONED_SPEC goal, write if v0 confirms predicted null).
- Local-model constrained decoding (xgrammar/llguidance — Anthropic
  doesn't expose logit-level constraints; tool-use is the
  Anthropic-native equivalent).
- Schemas for the other 8 specs.

If schema validation fails on the model's tool output >50% of the
time, the prompt is unclear. Surface that case; the fix is prompt
iteration, not schema relaxation.
