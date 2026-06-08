Build plumbline's graph-level shape mutation engine. Operator-level
mutations were measured insufficient on 2026-06-08 (54 attempts,
2 novel survivors, all anti-similarity-rejected). The right level
is graph rewrites on the TLA+ spec AST.

See docs/architecture/SHAPE_GRAPH_MUTATIONS.md for the full design.

---

DONE WHEN ALL EIGHT HOLD:

1. tools/spec_graph.py exists. It parses a TLA+ spec to a NetworkX
   MultiDiGraph (nodes: var/action/predicate/invariant; edges:
   reads/writes/conjuncts/next_disjunct) AND serializes the graph
   back to valid TLA+ that TLC accepts unchanged from the original
   (round-trip test passes on all 9 existing shapes).

2. tools/shape_evolve.py has an `action_subdivide` graph mutation that
   splits an action with `paid' = paid + X`-shaped predicate into
   pre/post atomic steps with intermediate state. Applied to ALL 9
   existing shapes, produces ≥3 TLC-discharged novel survivors.

3. tools/shape_evolve.py has a `state_inject_with_correlation` mutation
   that adds a state variable AND a constraint coupling it to an
   existing variable. Produces ≥2 TLC-discharged novel survivors.

4. At least ONE of the novel survivors from #2 or #3 passes:
   - anti-similarity penalty (cos to closest existing < 0.85)
   - coverage gate (≥ 5 of the 146 unmatched Sherlock findings come
     within cos > 0.7 of its signature)

5. That ONE novel survivor gets BANKED:
   - docs/tla/<NewShape>.tla committed
   - structural_cascade.SHAPES updated
   - A_QUERIES + SHAPE_HEURISTICS extended with new shape's signature
   - tlc_to_forge.SHAPE_TEMPLATES gets a new entry
   - templates/foundry_poc/_README.md status row added (template TODO)

6. After bank: re-run tools/calibrate_against_sherlock.py and verify
   the 93.7% corpus coverage number either stayed flat or improved.
   No regressions.

7. tools/shape_evolve.py run with --runs 10 on the new operators produces
   a JSON ranking output committed to
   corpus/calibration/shape_evolve_ranking.json.

8. git log shows ≥3 commits: the parser/serializer, the mutations, the
   banked shape + calibration re-run. All pushed.

CONSTRAINTS:

- No LLM in the mutation operators (sound determinism). LLM may draft
  candidate Foundry PoC templates AFTER a shape is banked.
- TLC discharge is the ONLY signal for whether a mutation is structurally
  valid. No human-in-the-loop validation.
- Anti-similarity threshold 0.85 to avoid rediscovering the parent shape.
- Coverage threshold 5 findings to avoid banking shapes that match only
  one outlier finding.
- Bank step must be atomic: if ANY of the 5 sub-steps fails, ROLLBACK.

OUT OF SCOPE:

- LLM-driven mutations (separate goal, after deterministic operators
  prove out)
- Foundry PoC template verification on the new shape (separate goal —
  requires a target contract that exhibits the new bug class)
- Subgraph_transplant (the most complex operator; do action_subdivide
  + state_inject_with_correlation first)
- Cross-shape composition (action_compose) — listed in design doc as
  the next priority after the two simpler operators ship

WHY THIS GOAL EXISTS:

The 2026-06-08 shape_evolve negative result (operator-level mutations
all rejected by anti-similarity) is the empirical evidence for moving
to graph-level mutations. The architecture is laid out in
docs/architecture/SHAPE_GRAPH_MUTATIONS.md.

If this goal completes successfully, plumbline crosses from a 9-shape
hand-curated library to a 10+-shape self-discovered library, with the
infrastructure to keep growing until the audit-bug distribution
saturates against the Sherlock corpus.
