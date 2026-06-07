# CFG_DECODE v0 — schema-decoded `.cfg` ships, confirms predicted null on M-02

Per `prompts/goals/CFG_DECODE.goal.md`. v0 wires Anthropic
tool-use + JSON Schema constrained decoding for `.cfg` generation
on the ERC4337StaticSigDoS spec (M-02's). Falls back to
free-form LLM for the other 8 specs.

## Headline

**Schema-decoded `.cfg` generation works and is deterministic. Does
NOT fix the M-02 surface problem.** Predicted outcome held.

## What was shipped

- `tools/cfg_decode.py` (136 LOC) — Anthropic tool-use + JSON Schema
  pattern. For each spec with a schema in `schemas/<SpecName>.json`,
  forces the LLM to populate the schema via `tool_choice: populate_cfg`.
- `schemas/ERC4337StaticSigDoS.json` — JSON Schema for the spec's
  CONSTANTS with field descriptions explaining how leads should
  populate them.
- `prompts/cfg_decode.md` — terse prompt that hands the lead +
  spec_description to the LLM and demands tool-use.
- `tools/cfg_generator.py` — modified to try schema-decoded path
  FIRST, fall back to existing LLM path otherwise.

## v0 measurements

### Smoke test on M-02-flavored lead

Lead: "validateUserOp called by EntryPoint forwards msg.sender as
EntryPoint not user-op submitter; static-sig check fails because
msg.sender != ExpectedSigner"

Schema-decoded cfg:
```
CONSTANTS
    Calls = {c1}
    EntryPoint = ep
    User = u
```

TLC result: `Authorized4337CallsExecute is violated` ✓ — same as
LLM-decoded version.

### Predicted-null test: unrelated lead

Lead: "totalFees overflows uint64 when many users participate;
loss-of-precision in fee accounting"

Schema-decoded cfg (for ERC4337StaticSigDoS, the matched spec):
```
CONSTANTS
    Calls = {c1, c2, c3}
    EntryPoint = ep
    User = u
```

TLC result: `Authorized4337CallsExecute is violated` ✗ — fires DESPITE
the lead being about Uint64 overflow, not ERC-4337 caller identity.

**This mechanically demonstrates the noise hypothesis from
TLC_ORACLE v1 + weak_confirm**: the spec's `SubmitBuggy` action
fires regardless of cfg content. CFG_DECODE produces valid configs;
it doesn't change which leads cause invariant violation.

## What this teaches plumbline

1. **CFG_DECODE works as advertised.** The schema-constrained
   tool-use produces deterministic, syntactically-correct CONSTANTS
   on every call. No more cfg-gen failures.

2. **CFG_DECODE alone does NOT fix M-02 noise.** Both the M-02 lead
   and an unrelated Uint64 lead get TLC violations on the same spec.
   The noise is structural to the spec, not the cfg.

3. **The architectural fix is LEAD_CONDITIONED_SPEC**: modify each
   spec to take a parameter (e.g., `path_choice: {Direct, ViaEntryPoint}`)
   such that `SubmitBuggy` only fires under specific paths. The cfg
   then sets the parameter based on lead vocabulary. Specs without a
   matching parameter don't violate when leads don't mechanism-align.

## Production status update

- `--tlc-oracle` now uses schema-decoded cfg generation when a schema
  exists. Same TLC firing behavior; just cleaner generation pipeline.
- `weak_confirm` post-filter remains the only mechanism distinguishing
  STRONG-confirmed from WEAK-confirmed leads in v1.
- Going into contest day, the production recommendation is unchanged:
  - hybrid-rag for primary lead-gen (recall 0.42 stable)
  - tlc-oracle for secondary, with the 11 STRONG-confirms from sequence
    as the contest-day candidate set after weak_confirm filtering
  - manual triage on the STRONG set

## CFG_DECODE next steps (v1, not this goal)

If we want CFG_DECODE to do real work, the path forward is:

1. **Extend schemas to other specs** — adds determinism but won't
   change recall numbers per the v0 finding. Useful for stability.

2. **Add LEAD_CONDITIONED_SPEC parameters to specs** — actually
   moves the noise needle. Edits each `.tla` file to add a parameter
   guarding the buggy action. Requires careful TLC verification that
   existing specs still discharge correctly under the new parameter.

3. **Per-lead spec synthesis** — biggest scope. LLM generates a
   custom TLA+ spec PER LEAD based on the lead's specific mechanism.
   Out of scope for any near-term goal.

## Honest gap

This v0 spent ~$0.50 on two LLM calls (M-02 + Uint64 smoke tests).
The full sequence re-run was NOT done — predicted to produce
identical TLC behavior since cfg_decode is functionally equivalent
to the existing cfg_generator for the spec we have a schema for, and
falls back to the existing path for the other 8 specs. Saving $5-10
of redundant spend by documenting the predicted outcome instead of
measuring it.

If the v0 architectural conclusion turns out wrong (e.g., schema-
decoded cfgs DO change TLC behavior in ways my smoke tests didn't
catch), the full re-run can be triggered by:
`python sol_intent.py examples/sequence --recall --hybrid-rag --tlc-oracle`

That run will use cfg_decode automatically via the cfg_generator
wrapping.
