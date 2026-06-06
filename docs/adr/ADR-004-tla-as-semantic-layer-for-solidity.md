# ADR-004: TLA+ as Semantic Layer for Solidity Bug Classes

**Status**: Proposed
**Date**: 2026-06-06
**Predecessor**: pact-standalone/docs/adr/ADR-003-tla-as-semantic-layer.md

---

## Context

Plumbline's verifier stack as of tonight:

1. **Slither / aderyn** — syntactic pattern matching over Solidity AST
2. **Halmos / z3** — symbolic EVM execution; per-transaction invariant checking
3. **sol_intent** (LLM) — semantic lead proposal from contract + NatSpec
4. **sol_match** — deterministic identifier-overlap + embedding scorer

Measured tonight on 5 corpora (~100 curated findings):
- Cyfrin teaching corpora: sol_intent recall 0.80–0.86
- Sequence (novel post-cutoff): sol_intent recall 0.60 ± 0.08

The 40% miss on sequence isn't a model weakness — it's a *category* gap.
Several findings (M-02 ERC-4337 DoS, M-01 cross-wallet session replay, H-02
session-call frontrunning, L-03 nonce reverts) are **temporal / multi-actor
/ liveness** properties. None of slither, halmos, or LLM-pattern-recall is
shaped for them.

Pact-standalone solved the analogous problem for Python checkers in 2026-05
via ADR-003: every `FailureMode` gets a corresponding TLA+ module that
specifies the bug class formally. TLC verifies the property over a
representative finite model. The spec — not the Python — is the auditable
truth.

This ADR adopts the same discipline for Solidity bug classes in plumbline.

---

## Decision

**Every Solidity FailureMode in plumbline has a corresponding TLA+ module
in `docs/tla/`.**

The TLA+ module specifies:

- **The state space**: variables modeling the lifecycle of the bridge / vault
  / signature / position / share / etc. (whatever the concrete bug operates
  on). Storage variables map to TLA+ VARIABLES; function-local effects map
  to transitions.
- **The transitions**: actions corresponding to public functions of the
  Solidity contract under analysis. Pre-conditions encode `require` /
  `modifier` gates; post-conditions encode state-write effects.
- **The temporal property**: the `[]` / `<>` / `~>` formula the protocol
  *promises* to uphold. NatSpec guarantees → invariants. Liveness
  guarantees → eventual / leadsto properties.

The TLC model checker verifies the property over all reachable states in a
bounded finite model defined by `<Module>.cfg`. **A counterexample IS the
bug** in mechanically checked form — the sequence of actions that drives
the system to a state violating the protocol's stated promise.

---

## Mapping pact's pattern to Solidity

| pact (Python)                             | plumbline (Solidity)                             |
| ----------------------------------------- | ------------------------------------------------ |
| `failure_mode.py` checker function         | `examples/<corpus>/.ANSWERS.md` finding section   |
| `_CORO_CONSUMERS` frozenset                | `tools/sol_intent.py` lens list + `.ANSWERS.md`   |
| `gen_tlc_model.py` AST → cfg generator     | (TODO) Slither IR → cfg generator                 |
| `docs/tla/<FailureMode>.tla`               | `docs/tla/<FailureMode>.tla`                      |
| `spec_learner.py` self-improving corpus    | (TODO) reuse pact's, retarget at Solidity bugs    |
| `tla2tools.jar`                            | (TODO) vendor from pact (~1.5 MB; commit-safe)    |

The bug class IS the TLA+ module name. `.ANSWERS.md` findings reference
their TLA+ module by name. Each TLA+ module verifies the *property* the
finding describes — not the implementation, not the patch.

---

## Coverage targets (rolling, measured per-corpus)

For each `.ANSWERS.md` finding marked as a TLA+-suitable bug class:

- A `docs/tla/<FailureMode>.tla` module exists
- A `docs/tla/<FailureMode>.cfg` model instantiates it with concrete
  constants drawn from the corpus contract (signers, recipients, etc.)
- TLC runs in plumbline CI on every push
- A counterexample for the buggy version is exhibited (proof the spec
  matches the bug)
- The corrected version (where the contract has been patched in
  upgradedProtocol/ etc.) passes TLC (proof the patch closes the gap)

**Realistic by end of weekend:**
- `SignatureReplay.tla` (boss-bridge H-3) — TLC exhibits counterexample
- 1 more FailureMode TLA+ module per major bug class on sequence
- `tools/tlc_rep.py` integrates TLC verdict as `verifier.kind="tlc"` rep

**Lofty by end of week:**
- 1 TLA+ module per High-severity finding across all 5 corpora (~25 modules)
- `gen_tlc_model.py` Solidity-side equivalent: SlithIR → cfg generator
  (mirrors pact's AST extraction pattern)
- Cloud workflow runs TLC per module on every push; results land in
  `reps.jsonl` as `verifier.kind="tlc"`, scored against the corpus's
  `.ANSWERS.md`
- Marginal recall measurable per layer: `slither ⊂ +halmos ⊂ +tlc ⊂ +sol_intent`

---

## Why this matters for contest day

The contest-day stack with TLA+ becomes:

1. Slither / aderyn → pattern floor (instant, free, ~40% of findings)
2. sol_intent --recall → semantic leads (LLM, paid, fills the gap above
   slither, ~80% on Cyfrin / ~60% on novel)
3. ML classifier → predicts per-lead which verifier should adjudicate
4. Halmos → discharges per-transaction invariants
5. **TLC → discharges temporal / multi-actor / liveness invariants**
6. Human → arbiter where no verifier settles

The category gap on novel-code recall is what TLA+ specifically closes. We
won't know the magnitude until we measure, but tonight's sequence findings
strongly suggest the temporal/multi-actor class is responsible for ~5–8 of
the 12 sequence findings — the difference between 0.60 and 0.85 recall on
novel code.

---

## Open questions

- **Solidity → TLA+ semantic translation discipline.** msg.sender,
  msg.value, storage layout, reentrancy ordering, gas accounting — these
  must be modeled consistently across modules. Open: do we adopt a
  "Solidity preamble" module (similar to pact's `Pact.tla` meta-spec)?
- **Apalache vs TLC.** TLC is the model-checker pact uses. Apalache is
  faster on unbounded state but has subset syntax. Tonight's first
  module targets TLC for compatibility with pact's existing tooling;
  the trade-off is revisited if scaling forces a move.
- **Auto-generation vs hand-authoring.** Pact's `gen_tlc_model.py`
  generates `.cfg` from live Python; for Solidity, the analog generates
  `.cfg` from SlithIR. The TLA+ module itself stays hand-authored
  (the bug class is a human-named pattern). Open: how far auto-gen
  scales before the spec author has to fork a manual variant.
