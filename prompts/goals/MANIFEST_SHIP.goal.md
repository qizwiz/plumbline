Primitive: ship ONE new universal-template manifest from a banked PoC
test file. Runs every cycle the queue has a MANIFEST_SHIP_<X> row pending.

The pipeline already exists. This goal exists so the autonomous loop
can grind it without any human in the path:
  - tools/manifest_from_poc.py extracts a draft from PoC_X.t.sol
  - tools/manifest_lint.py --run verifies it forge-PASSes
  - tools/manifests/_README.md has the schema + the prank-consumption rule

Why this exists: each successful cycle adds one verified manifest to
the registry. After ~5 cycles plumbline has manifests for most banked
PoCs. The corpus IS the asymmetry; growing it is the highest-leverage
single move.

---

Your QUEUE row's goal name is "MANIFEST_SHIP <X>" where X identifies
ONE PoC test file. The row's notes column tells you the full PoC path,
target contract, target source path, and forge_root.

DO ONE THING: produce a verified manifest for PoC X, commit, exit.

PROCEDURE (terminal — do not invent steps):

1. Read prompts/goals/QUEUE.md. Find the row whose goal is exactly
   yours (the one marked in-progress at the moment you start). Parse
   the notes column: it contains four required fields separated by
   semicolons, in this order:

      poc=<path>; target=<ContractName>; target_path=<rel>; forge_root=<rel>

   Example notes:
      poc=corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd/test/PoC_DustRewardResetsVesting.t.sol; target=dreUSDs; target_path=../contracts/dreUSDs.sol; forge_root=corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd

2. Pick a shape name. Strip "PoC_" prefix and ".t.sol" suffix from the
   PoC filename. Verify a matching TLA+ spec exists at
   docs/tla/<shape>.tla. If absent, that's your null result — STOP and
   honestly report "no TLA+ shape for <name>".

3. Run the extractor:
      python3 tools/manifest_from_poc.py \\
        --poc <poc> --shape <shape> \\
        --target <target> --target-path <target_path> \\
        --forge-root <forge_root> \\
        --out tools/manifests/<short>-<shape>.json

   <short> is a hyphenated 1-3-word target nickname like "dre" or
   "puppy-raffle". Look at existing manifests for naming convention.

4. The draft has TODO_INVARIANT_NAME and a placeholder invariant_assert
   block. Read docs/tla/<shape>.tla — the `INVARIANTS` line names the
   real invariant. Fill it in.

5. Write a real invariant_assert_block: 2-4 lines of Solidity that
   assert what the TLA+ INVARIANT promises. If the PoC already asserts
   it (look for assertGt / assertEq / assertLt / vm.expectRevert with
   a comment), use the same condition.

6. Paste a 6-state TLC trace head into tlc_trace_head. If the TLA+
   spec has a corresponding _TTrace.tla file, use the first 6 states.
   Otherwise summarize the PoC's action sequence as 6 states.

7. Static lint:
      python3 tools/manifest_lint.py --manifest <out> 2>&1

   It must print "(lint clean)" with 0 errors and 0 warnings. If WARN
   about vm.prank consumption fires, fix the manifest before
   proceeding: convert bare vm.prank pairs to vm.startPrank /
   vm.stopPrank or cache argument expressions.

8. End-to-end:
      python3 tools/manifest_lint.py --manifest <out> --run 2>&1

   It must print "forge: PASS — PASS". If FAIL, iterate the manifest
   (NEVER the emitted .t.sol — it's regenerated) until it PASSES, up to
   5 attempts. After 5 failed iterations, honestly report null and
   STOP.

9. Commit:
      git add tools/manifests/<out>
      git commit -m "autonomous: true — ship <shape> manifest for <target>"

DONE WHEN ALL FIVE HOLD:

1. tools/manifests/<new>.json exists and has no TODO_ placeholders.
2. python3 tools/manifest_lint.py --manifest <new> exits 0 with
   "(lint clean)" and 0 warnings.
3. python3 tools/manifest_lint.py --manifest <new> --run prints
   "forge: PASS — PASS" — i.e. trace_to_forge emits, forge compiles,
   the test runs and passes.
4. The manifest is committed to master via git commit (autonomous: true).
5. Your final message describes which PoC was shipped and the forge
   pass output, OR honestly reports the null result.

NULL-HONEST is acceptable. Faking work is not. If the env is broken,
the TLA+ spec is absent, or 5 lint iterations fail to produce a PASS,
say so and STOP.
