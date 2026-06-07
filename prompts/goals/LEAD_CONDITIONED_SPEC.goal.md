Between-contest goal: LEAD_CONDITIONED_SPEC — modify each TLA+ spec
to take a parameter such that its `BuggyAction` only fires when the
cfg encodes the matching mechanism path. Per CFG_DECODE v0's finding
that cfg-decoding alone doesn't fix M-02 noise. ~$10. <4000 chars;
8-step.

HONEST SCOPE: This is architectural surgery on the spec corpus.
v0 modifies ONLY ERC4337StaticSigDoS. v1 (separate goal) extends
to all 9. Each spec edit requires TLC re-verification.

---

For ERC4337StaticSigDoS, add a `path_choice: {Direct, ViaEntryPoint}`
constant. Modify `SubmitBuggy` to fire only when path_choice =
ViaEntryPoint. Modify cfg_decode to derive path_choice from lead
vocabulary. Verify: M-02-flavored lead → path_choice=ViaEntryPoint
→ TLC fires; unrelated lead → path_choice=Direct → TLC does NOT fire.

DONE WHEN ALL EIGHT HOLD:

1. docs/tla/ERC4337StaticSigDoS.tla modified: add CONSTANT
   `PathChoice` with type {Direct, ViaEntryPoint}; modify
   `SubmitBuggy` action's enabling condition to require
   PathChoice = ViaEntryPoint. Lark grammar still PASSES.

2. docs/tla/ERC4337StaticSigDoS.cfg defaults updated to set
   PathChoice = ViaEntryPoint (so the existing default behavior
   still discharges the bug; regression preserved).

3. schemas/ERC4337StaticSigDoS.json adds a `PathChoice` field with
   enum {"Direct", "ViaEntryPoint"} and a description telling the
   LLM which lead patterns map to each value.

4. prompts/cfg_decode.md tweaked to instruct the LLM: "if the lead
   mentions EntryPoint, msg.sender forwarding, validateUserOp,
   UserOperation, ERC-4337, or 4337 EntryPoint, set
   PathChoice=ViaEntryPoint; otherwise PathChoice=Direct."

5. Smoke test 1 (M-02-flavored): my transcript shows cfg_decode
   produces PathChoice=ViaEntryPoint AND TLC fires
   Authorized4337CallsExecute.

6. Smoke test 2 (unrelated, Uint64 overflow lead): cfg_decode
   produces PathChoice=Direct AND TLC does NOT fire any invariant
   violation. THIS IS THE CRITICAL TEST — if it fails, the spec
   modification isn't actually conditioning on path_choice
   correctly.

7. examples/sequence/lead-conditioned-result.md exists with:
   - test 1 + 2 cfg outputs and TLC results
   - regression check: original tests on existing specs still pass
   - per-spec STRONG/WEAK breakdown if pipeline was re-run
   - HONEST verdict: does conditioned firing change M-02 surface?

8. `git push origin main` succeeded; commit touches
   docs/tla/ERC4337StaticSigDoS.tla + .cfg + schemas/ +
   prompts/cfg_decode.md + lead-conditioned-result.md.

CONSTRAINTS:

- $10 ceiling. Smoke tests + optional pipeline re-run.
- v0 modifies ONLY ERC4337StaticSigDoS. Don't touch other .tla
  files in this goal. Extension to other specs is v1 work.
- The modified spec MUST regression-test: the existing test cases
  / cfg defaults still produce the bug discharge they always did.
- Don't reduce the .55 retrieval threshold or change cfg_generator
  fallback logic — just modify the one spec + its surrounding
  artifacts.
- Honest report. If the conditioned spec STILL fires on unrelated
  leads (because the LLM mis-derives PathChoice), the result is a
  null and the next escalation is per-spec custom prompts.

OPERATING DISCIPLINE:

- PREDICTED HEADLINE: Test 2 produces PathChoice=Direct AND TLC
  does NOT fire. If both hold, the architecture works. If only one
  holds, it's partial. If neither, the architecture doesn't fix
  the noise.

OUT OF SCOPE:

- Extending PathChoice to the other 8 specs (LEAD_COND_SWEEP, v1).
- Per-spec custom cfg_decode prompts (separate experiment).
- Modifying spec invariants — only the BuggyAction's enabling
  condition gets the new parameter.

If the modified .tla fails Lark grammar validation, surface — the
fix is grammar extension, not weakening the validation. If TLC
fails to discharge the original bug on the default cfg, the spec
edit broke regression — revert and surface.
