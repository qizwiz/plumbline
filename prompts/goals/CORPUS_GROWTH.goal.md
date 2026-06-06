Between-contest goal: grow the verified FailureMode corpus.

Use when there's no active contest but you want plumbline more
capable for the next one. <4000 chars; 8-step decomposed.

---

By session end, the docs/tla/ corpus has gained at least one new
TLA+ FailureMode (TLC-discharged, counterexample matching a real
contest finding), and the retrieval index is rebuilt.

DONE WHEN ALL EIGHT HOLD:

1. My transcript shows I ran `python tools/spec_retrieval.py list`
   and the output names ≥6 specs (was 5 at session start).

2. The new module's .tla file exists under docs/tla/ and has a
   `MODULE <name>` header + the standard FailureMode comment block
   citing concrete instance (examples/<corpus>/.ANSWERS.md <id>).

3. My last TLC run printed `Invariant <name> is violated` on the
   new spec, plus a counterexample trace of ≤5 states.

4. The new spec covers a STRUCTURAL bug-class shape distinct from
   the existing five (signature-replay, reentrancy, caller-bound-
   auth-misread, narrow-accumulator-truncation, idempotency-
   violation). If it's the same shape as an existing one, surface
   that and ask whether to merge instead.

5. The new spec passes the Lark grammar: my transcript shows
   `python tools/validate_tla_grammar.py` reporting `PASS  <name>.tla`.

6. The retrieval index was rebuilt: my transcript shows
   `python tools/spec_retrieval.py build` reporting saved-to path
   and corpus size of 14 (was 13).

7. A short retrieval check: `python tools/spec_retrieval.py query
   "<bug-class description>" 3` returns the new module at top-1
   with cos > 0.4. If it doesn't, the description was too generic
   — refine before declaring done.

8. git log --oneline -3 shows a commit landing all of: the new
   .tla + .cfg + (if needed) updated retrieval pickle, and `git
   push origin main` completed successfully.

CONSTRAINTS:

- One spec per session — DON'T batch. Each new spec compounds the
  retrieval corpus; better to validate one cleanly than three loosely.
- Use atomic-proposition lifting for the description text per
  LTLGuard / tools/spec_retrieval.py._lift_idents.
- Hand-pick a second precedent if retrieval top-1 is wrong (per
  T19 embedder gap).
- No new SLOC in tools/ unless absolutely necessary. Corpus growth,
  not infrastructure.
- New spec MUST cite an actual finding from one of the 8 example
  corpora — no synthetic / made-up bug shapes.

OUT OF SCOPE:

- Anything LLM-spend related ($0 budget this goal).
- Constrained-decoding wire-up.
- Verifier-router schema migration (defer to its own session).

If no example corpus has a finding matching a new structural shape
(all 8 .ANSWERS.md files exhausted of distinct shapes), stop and
surface: the corpus may already cover the high-frequency shapes,
and the next corpus growth needs a real new contest.
