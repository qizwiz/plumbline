Exploratory goal: CA/NCA SVM — smallest viable kernel for grammar-
driven evolution over the TLA+ FailureMode corpus. ~30 min wall, $0
LLM. The MEASUREMENT is the 4-bucket count; null result IS a valid
result and gets shipped, not iterated-away. <4000 chars; 8-step.

---

For each of plumbline's 9 own-corpus TLA+ shapes, generate 5 single-
step grammar-respecting structural mutations. Run each mutation
through Lark + TLC. Classify into 4 buckets. The count in the
NOVEL bucket determines whether grammar-driven evolution is real
on our lattice.

DONE WHEN ALL EIGHT HOLD:

1. tools/spec_mutator.py exists, ≤200 LOC. Takes a .tla file, applies
   one of: swap binary op (= ↔ /=, + ↔ -, etc.), replace boolean
   literal (TRUE ↔ FALSE), swap two declared variables, replace one
   CONSTANT value. Random selection per mutation, fixed seed for
   reproducibility.

2. My transcript shows `python tools/spec_mutator.py --runs 5` invoked
   over docs/tla/*.tla (own corpus only, 9 specs) producing 45 total
   mutation attempts. Output prints per-attempt: spec, mutation_kind,
   bucket.

3. ca_svm_report.json exists at project root with one entry per
   attempt: spec_name, mutation_kind, bucket
   (broken | fixed | equivalent | novel), original_trace_hash,
   new_trace_hash. 45 entries.

4. The 4 BUCKET COUNTS print to stdout in a final summary line, e.g.
   `broken=22 fixed=8 equivalent=13 novel=2`. These four numbers
   sum to 45.

5. CA_SVM_RESULT.md exists with:
   - the 4-bucket count
   - per-spec breakdown (one row per spec, count per bucket)
   - if novel > 0: 3 examples (spec, mutation, original trace head,
     new trace head)
   - the verdict paragraph: "grammar-driven evolution IS / IS NOT
     real on our lattice based on N of 45 novel mutations"

6. If novel > 0: docs/tla/mutations/ contains the novel-mutation
   .tla files (one per novel example, capped at 5). Otherwise the
   directory may not exist — that's fine.

7. validate_reps.py passes (no reps written; inference-only goal).

8. `git push origin main` succeeded; commit touches tools/spec_mutator.py
   AND CA_SVM_RESULT.md.

CONSTRAINTS:

- $0 LLM. Lark + TLC are local.
- 5 mutations per spec is the budget. Don't expand mid-goal to
  "make the result more interesting" — that's a re-run.
- Mutations are SINGLE-STEP (one production change per spec).
  Compound mutations are out of scope.
- Mutation selection is RANDOM (fixed seed for reproducibility).
  Don't hand-design mutations to land in the novel bucket.
- If novel == 0, that IS the result. Do NOT keep tweaking until
  it lights up. The honest signal is the 4-bucket count.
- Don't modify any existing .tla in docs/tla/. Mutations write to
  a temp dir; only successful "novel" survivors get archived
  under docs/tla/mutations/.
- Run TLC with a 30-second timeout per mutation. If TLC OOMs or
  hangs, mutation goes in the BROKEN bucket with reason logged.

OPERATING DISCIPLINE:

- The HEADLINE METRIC is the NOVEL count. Per CA/NCA theory: if
  random single-step mutations can navigate the lattice to
  structurally-distinct attractors, the lattice has a real
  generative structure. If novel == 0, either (a) the mutation
  set is too narrow, (b) the lattice is too tight, or (c) the
  shapes are too similar — all three are surfaced as next-session
  hypotheses, not failures.
- Self-critique: "did I bias mutation selection toward shapes I
  expect to succeed?" Answer in CA_SVM_RESULT.md.
- "Different trace" means the SEQUENCE of state-variable values
  differs at any step where both traces have data. Same first-
  violation step but different VALUES → novel. Same VALUES at
  same step → equivalent.

OUT OF SCOPE:

- Full CA layer (this is the SVM, not the system).
- NCA training (learned dynamics — separate session if SVM lights up).
- Fitness-driven mutation (random for v0).
- Compound multi-step mutations.
- Mutation across spec BOUNDARIES (each mutation modifies one .tla).

If Lark parse failures dominate (broken > 35 of 45), the mutation
set is too aggressive for the grammar. Surface that result; the
fix is a narrower mutation set, not a different lattice.
