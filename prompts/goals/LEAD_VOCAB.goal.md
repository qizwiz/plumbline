Between-contest goal: Path A from ORACLE_LOOP — edit the sol_intent
prompt to demand mechanism-grounded leads (name variables, file:line,
the specific transformation). Tests upstream-bottleneck hypothesis.
If the new prompt surfaces leads that the oracle loop can actually
fire on (>10 of ~40), M-02 may finally surface. ~$5, <4000 chars;
8-step.

---

Fork prompts/sol_find_hybrid_rag.md as sol_find_mechanism.md adding
explicit guidance to surface MECHANISM-level leads (name variables,
file:line, the specific transformation), not BUG-CLASS-level leads.
Run sol_intent + hybrid-rag + oracle-loop + mechanism on sequence.
Headline: oracle-loop revision rate climbs from 3/40 toward
saturation, and M-02 finally surfaces.

DONE WHEN ALL EIGHT HOLD:

1. prompts/sol_find_mechanism.md exists — variant of
   sol_find_hybrid_rag.md with NEW guidance section near the top
   demanding leads in this format:
   "function FILE:LINE — the SPECIFIC variables involved (e.g.,
   msg.sender, the storage slot, the function param) — the SPECIFIC
   transformation (e.g., msg.sender becomes EntryPoint during
   forwarding) — one-sentence why this is exploitable."
   The baseline sol_find_hybrid_rag.md stays UNCHANGED.

2. sol_intent.py accepts --mechanism flag (additive). When set:
   uses sol_find_mechanism.md prompt. Composes with --hybrid-rag
   and --oracle-loop.

3. Smoke test: my transcript shows the new prompt rendered for a
   1-file chunk; the guidance section is visible at the top with
   the variable-naming / file:line / transformation requirements.

4. Cold run:
   `python sol_intent.py examples/sequence --recall --hybrid-rag --oracle-loop --mechanism`
   exits 0. Output saved to examples/sequence/sol-intent-mechanism.txt.
   LLM cost tracked.

5. Oracle-loop revision count: transcript shows N_revised. **Target:
   >10** (up from 3 in ORACLE_LOOP). If N_revised stays at 3-5, the
   mechanism prompt isn't penetrating; surface this as upstream
   failure persists.

6. examples/sequence/mechanism-ab.md exists with 5-way comparison:
   - cold: 0.08-0.17
   - rag-only: 0.42 stable
   - hybrid-rag: 0.42 apples-to-apples
   - oracle-loop (was M-02 missed): 0.33-0.46
   - oracle-loop + mechanism (this goal): 0.NNN
   Plus N_revised before/after.

7. M-02 SPECIFIC CHECK: transcript spot-checks whether M-02 surfaced.
   The architectural prediction is that mechanism-grounded leads now
   match ERC4337StaticSigDoS at cos > 0.55, triggering the forcing
   function on the M-02 lead specifically. If M-02 STILL misses
   despite >10 revisions, the gap is genuinely deeper than prompt
   engineering — escalation is actual TLC execution per lead (v1).

8. `git push origin main` succeeded; commit touches
   tools/sol_intent.py + prompts/sol_find_mechanism.md +
   examples/sequence/mechanism-ab.md.

CONSTRAINTS:

- $5 ceiling. The new prompt is longer than sol_find_hybrid_rag.md
  by ~200 tokens; per-chunk cost scales modestly.
- Don't modify sol_find_hybrid_rag.md (the A/B baseline must hold).
- Don't reduce the oracle-loop cos threshold to force more
  revisions. The threshold is the gate; surface raw N_revised.
- Don't iterate the mechanism prompt within this goal — one rewrite
  attempt only. Honest report regardless of result.

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: M-02 surfaces AND N_revised > 10. Both must
  hold for clean win.
- Self-critique at step 6: did the mechanism prompt add value the
  model couldn't get from sol_find_hybrid_rag.md, or did it just
  bias the format superficially?
- If N_revised lifts but M-02 still misses, the loop fires on
  WRONG leads — the forcing function applies to non-M-02 shapes.
  Report which shapes the revised leads matched.

OUT OF SCOPE:

- Actual TLC execution per lead (v1 — escalation if this null-results).
- Other prompt variants beyond the single mechanism rewrite.
- Sweep across other corpora (sequence A/B only).
- Modifying spec_retrieval threshold (0.55 stays — that's a
  separate experiment).

If oracle-loop revision count INCREASES (>10) but M-02 still misses,
the upstream-bottleneck hypothesis is REFUTED — the leads are
mechanism-grounded but the spec match doesn't catch the M-02
mechanism. The escalation to Path B (real TLC oracle) becomes
empirically warranted, not just theoretically.
