# Imported TLA+ modules — retrieval corpus seed

These 12 modules are copied verbatim from `pact-standalone/docs/tla/`
(2026-06-06). They are the **starter pack for plumbline's retrieval
corpus** per `ARCHITECTURE.md` §3b (fluency-teacher) and
`docs/research/RESEARCH-NOTES-2026-06-06.md` (LTLGuard pattern).

Each is a hand-authored FailureMode TLA+ spec for a Python bug class
in pact's checker library. The bug classes are Python-specific
(MutableDefaultArg, BareExcept, MissingAwait, etc.), but the
**structural patterns** they encode — CONSTANTS / VARIABLES / Init /
Next / Spec / INVARIANTS / PROPERTIES, plus the discipline of
hand-authored safety + liveness — are exactly what plumbline's
Solidity FailureMode modules will reuse.

## How they're used by plumbline

1. **Retrieval index**: `tools/spec_retrieval.py` indexes these
   modules + plumbline's own `../*.tla` by their header-comment
   description. Query returns the nearest neighbors by embedding
   cosine similarity.
2. **Few-shot context**: when authoring a new FailureMode, retrieve
   the 2–3 nearest modules and include them as few-shot examples in
   the generation prompt.
3. **Pattern lineage**: comparing a new spec to its retrieval
   nearest-neighbor makes drift visible. If the new spec doesn't
   *look like* its neighbors, either the bug class is genuinely
   novel (good) or the spec author drifted (catch it).

## Provenance

Copied from `~/src/pact-standalone/docs/tla/` at commit-time. Pact is
JH's primary checker project; plumbline is the Solidity-side
adaptation. License/attribution follow pact's repo conventions.

## Not vendored: `tla2tools.jar`

The TLC binary is at `../tla2tools.jar` (plumbline-level), also from
pact. Used for verifying modules in this directory and in `..`.
