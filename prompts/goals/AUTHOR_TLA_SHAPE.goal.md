Primitive: author ONE new TLA+ shape under docs/tla/, modeled after an
existing banked PoC test that has no matching shape yet.

The dependency chain for plumbline corpus growth is:
  TLA+ shape (docs/tla/<X>.tla) → PoC test → manifest → forge PASS

MANIFEST_SHIP is starved when the PoC has no matching shape. This
goal closes that gap: every PoC test in the corpus that exercises
a structural bug deserves an abstract TLA+ shape so the loop can
also exercise it on FUTURE contests with the same shape.

---

Your QUEUE row's notes column tells you which PoC to model:
  poc=<path>; shape_name=<X>; invariant=<I>

Example notes:
  poc=corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd/test/PoC_FirstDepositorInflation.t.sol; shape_name=FirstDepositorInflation; invariant=ShareInflationBounded

DO ONE THING: produce docs/tla/<X>.tla + docs/tla/<X>.cfg, TLC-discharge
the spec, commit.

PROCEDURE:

1. Read prompts/goals/QUEUE.md. Find your row (in-progress). Parse
   semicolon notes to get poc, shape_name, invariant.

2. Read the PoC. Understand: what action sequence does it execute,
   what invariant does it violate? The TLA+ spec should ABSTRACT
   that — not transcribe the PoC.

3. Model after an existing shape with similar mechanism. Read 1-2
   existing docs/tla/*.tla files to copy the comment-header
   convention + Sections layout (Constants, Variables, Init, Next,
   Spec, Invariants).

4. Write docs/tla/<shape_name>.tla. Required structure:
   - MODULE header
   - Comment block citing the concrete instance (PoC path)
   - EXTENDS Integers, FiniteSets, TLC
   - CONSTANTS with concrete sample (Workers, Authorizations, etc.)
   - VARIABLES tracking the state the invariant cares about
   - Init / Actions (3-5 distinct actions max — abstract!)
   - Next, Spec
   - INVARIANT <invariant> — the property the PoC violates

5. Write docs/tla/<shape_name>.cfg:
   - SPECIFICATION Spec
   - INVARIANT <invariant>
   - CONSTANTS bindings, small finite sample
   - CHECK_DEADLOCK FALSE  (most bug-class specs deadlock; that's OK)

6. Discharge:
      cd docs/tla
      java -XX:+UseParallelGC -jar tla2tools.jar -config <X>.cfg -deadlock <X> 2>&1 | tail -20

   Expected: TLC prints "Invariant <invariant> is violated." with a
   counterexample trace of ≤6 states. That IS the bug.

   If TLC prints "No error has been found" — the spec is over-modeled
   (already correct in spec). REVISE: weaken a guard, introduce the
   buggy branch as BuggyAction. Iterate until violation.

   Cap at 5 iterations. After 5 failures, null-result and STOP.

7. Add 6-line excerpt of the counterexample trace as a comment at the
   end of the .tla file (under "(* Counterexample (TLC discharge) *)").

8. Commit:
      git add docs/tla/<shape_name>.tla docs/tla/<shape_name>.cfg
      git commit -m "autonomous: true — TLA+ shape <shape_name> from <PoC basename>"

DONE WHEN ALL FIVE HOLD:

1. docs/tla/<shape_name>.tla exists and matches the convention of
   existing specs (MODULE header, comment block citing PoC, EXTENDS,
   CONSTANTS, VARIABLES, Init, Next, Spec, INVARIANT).
2. docs/tla/<shape_name>.cfg exists with SPECIFICATION + INVARIANT +
   CONSTANTS bindings.
3. TLC discharge prints "Invariant <invariant> is violated" with a
   counterexample.
4. Counterexample trace excerpt is pasted at the foot of the .tla.
5. Both files are committed to master with "autonomous: true" prefix.

NULL-HONEST is acceptable. Faking a spec that doesn't TLC-violate is
not. If 5 iterations fail, say so.

After this lands, the next MANIFEST_SHIP cycle for the same PoC will
have a matching shape and can ship its manifest.
