# Shape graph mutations — architecture for plumbline's evolutionary shape discovery

## Why this matters

Operator-level mutations (swap binop, swap bool, add state var, add guard)
were measured against the held-out 146 Sherlock-graded findings on
2026-06-08. **54 attempts → 2 novel survivors, both anti-similarity-rejected.**
The negative result is grounded: TLC sees different counterexamples but
the embedding space sees the same shape. Operator-level perturbations
preserve semantic identity.

The correct frame is **graph-level mutation**: a TLA+ spec IS a graph
(nodes = state variables/actions/predicates; edges = reads/writes/sequencing).
Mutations should rewrite the graph, not the strings.

The connection to the project's Rule 30 / SFI-ABM frame is direct: each
TLA+ spec is a CA over its state space; the rewrite system over all
possible CAs is itself a dynamical system; the shape library is the
attractor set under the held-out-coverage fitness landscape.

## Architecture

```
TLA+ spec ←──→ AST (Lark or tree-sitter-tla+)
                 ↓
              spec_graph (NetworkX MultiDiGraph):
                nodes = {var, action, predicate, invariant}
                edges = {reads, writes, conjuncts, next_disjunct, init_assigns}
                 ↓
              apply graph_mutation → mutated_spec_graph
                 ↓
              serialize back to TLA+
                 ↓
              TLC verify (fitness gate #1: produces non-vacuous counterexample)
                 ↓
              embed signature, measure cos delta vs parent + coverage
              on the 146 unmatched Sherlock findings (fitness gate #2)
                 ↓
              if pass both gates → bank as new shape
```

## The five killer graph mutations (ranked by expected discovery yield)

### 1. action_subdivide

Split one atomic action into `A_pre` and `A_post` with a new intermediate
state on the relevant variable's domain. **REENTRANCY emerges from
non-reentrant specs via this single rewrite.**

```
input:  action A == /\ slot[e] = Live
                    /\ slot' = [slot EXCEPT ![e] = Cleared]
                    /\ paid' = [paid EXCEPT ![e] = paid[e] + X]

output: SlotStates' = SlotStates ∪ {"InFlight"}
        action A_pre  == /\ slot[e] = Live
                         /\ slot' = [slot EXCEPT ![e] = "InFlight"]
                         /\ paid' = [paid EXCEPT ![e] = paid[e] + X]
        action A_post == /\ slot[e] = "InFlight"
                         /\ slot' = [slot EXCEPT ![e] = "Cleared"]
        Next' = old Next disjoined with A_pre and A_post
```

Apply to any spec with an "external-call-shaped" action (paid', balance',
transferred') → discovers the CEI-violation variant of that bug class.

Applied to SignatureReplay → discovers `ReentrantSignatureReplay`.
Applied to Uint64FeeOverflow → discovers `ReentrantFeeOverflow`.
Applied to Create2NonIdempotent → discovers `ReentrantDeployment`.

**Expected discovery yield: 5+ new shapes from this one mutation alone**
because we have 8+ existing specs with external-call-shaped actions.

### 2. action_compose(spec_A, spec_B, shared_var)

Unify two specs along a shared variable (or action signature). Produces
hybrid bug classes that span shape boundaries.

```
input:  SignatureReplay (vars: submissions, paid_total)
        Uint64FeeOverflow (vars: fees_uint64, fee_accumulator)
output: SignatureReplayWithFeeOverflow
        vars: submissions, paid_total, fees_uint64, fee_accumulator
        actions: SubmitBuggy combined with FeeAccrueBuggy
        invariant: NoDrain AND NoOverflow (conjunction)
```

The composition graph's embedding is far from either parent → likely
escapes anti-similarity penalty.

**Expected discovery yield: O(N²/2) where N = current shape count.**
At N=10 → 45 candidate compositions. Even if 10% TLC-discharge, that's
4 new hybrid shapes.

### 3. state_inject_with_correlation(spec, new_var, existing_var, correlation)

Add a new state variable AND a constraint coupling it to an existing
variable. Unlike naive add_state_var (which produces TLC type-errors),
this connects the new variable to the spec's behavior.

```
input:  spec SignatureReplay
output: new var: timestamp \in Nat
        new constraint: timestamp' > timestamp (monotonicity)
        new guard on existing actions: timestamp - submitted_at < FRESHNESS
        new invariant: stale-signature-detection
```

This is **exactly the protocol-integration bug class** — oracle staleness,
decimal mismatch, pause-bypass. The Notional 11 Highs we couldn't cover
were all in this family.

**Expected discovery yield: covers ~50 of the 146 unmatched Sherlock findings.**

### 4. invariant_strengthen(spec, conjunct)

Add a conjunct to the invariant. If TLC now finds a NEW counterexample
that didn't trigger before → discovered a sub-shape.

```
input:  ReentrancyDrain invariant: paid[e] <= TicketPrice
output: paid[e] <= TicketPrice AND drained_total <= reserves
```

Useful for discovering "secondary" invariants the original spec didn't
encode but real bugs violate.

### 5. subgraph_transplant(donor_spec, recipient_spec, subgraph)

Extract a subgraph (a coherent action + its referenced vars) from one
spec, embed in another. Effectively pattern reuse.

```
input:  donor: ERC4337StaticSigDoS (action: ValidateSignatureUnderEntryPoint)
        recipient: ReentrancyDrain
output: ReentrancyDrain extended with a sig-validation step that runs
        DURING the external-call window
```

## Sound fitness function (unchanged from operator-level)

1. **TLC discharge**: produces non-vacuous counterexample (length ≥ 2 transitions)
2. **Anti-similarity**: cos to closest existing shape < 0.85
3. **Coverage**: ≥ 5 of the 146 unmatched Sherlock findings come within cos > 0.7
4. **Forge test** (eventually): runnable PoC on a known target reproduces the exploit

All four gates are deterministic. No LLM-as-judge.

## Implementation order

| step | LOC est | dependency |
|---|---|---|
| TLA+ → spec_graph parser (Lark-based) | 200 | none |
| spec_graph → TLA+ serializer | 150 | parser |
| `action_subdivide` | 100 | parser + serializer |
| `state_inject_with_correlation` | 150 | parser + serializer |
| `action_compose` | 200 | parser + serializer + var-renaming utility |
| `invariant_strengthen` | 80 | parser + serializer |
| `subgraph_transplant` | 250 | parser + serializer + isomorphism |
| Run + score on the 146 unmatched | (reuse shape_evolve.py) | all above |

**Total ~1100 LOC, ~1-2 weeks for a single human, ~1-3 days for the
autonomous loop if the parser+serializer land first.**

## What banking a new shape mechanically requires

When fitness passes, atomically:
1. Write `docs/tla/<NewShape>.tla` + `<NewShape>.cfg`
2. Update `tools/structural_cascade.py` SHAPES list
3. Update `tools/structural_cascade.py` A_QUERIES with the new shape's
   AST signature (derived from spec_graph's reads/writes)
4. Update `tools/structural_cascade.py` SHAPE_HEURISTICS with detection rule
5. Update `tools/tlc_to_forge.py` SHAPE_TEMPLATES with new entry
6. Write `templates/foundry_poc/<NewShape>.t.sol.template`
   (can be drafted by LLM from the TLC counterexample trace; verify
    with `forge test` on a known target)
7. Update `templates/foundry_poc/_README.md` status table
8. Re-run cascade calibration; commit the new H/M recall number

Items 1-5 are mechanical from the TLA+ spec.
Items 6-7 need LLM + forge verification (verified pattern from
2026-06-08 ReentrancyDrain template).
Item 8 is the autonomous loop's existing capability.

## Open design questions

1. **Cycle detection on action_compose**: should we prevent
   `compose(compose(A, B), C)` from creating exponentially-large hybrids?
   Cap composition depth at 2.

2. **Naming conventions**: `ReentrantSignatureReplay` vs
   `SignatureReplay_subdiv` — preserve provenance in the shape name?

3. **Rollback semantics**: if a banked shape later proves to degrade
   recall (some other contest), how do we un-bank? Suggest a `shape_history`
   ledger with held-out recall per shape per banking event.

4. **LLM-driven graph mutations**: should there be a 6th mutation type
   that's LLM-proposed graph rewrites? Yes for the corpus-tail. The
   determinism guarantee covers the rest.

## Connection to grounded self-improvement

This is the structural layer for plumbline's evolutionary loop. The
fitness signal is sound (TLC + embedding + held-out coverage). The
mutation space is rich enough to actually discover new shape classes.
The bank step is atomic. The history is preserved.

Per JH's CLAUDE.md: this is the STRUCTURE for self-improvement. The
system improves itself, not the human improving the system. The human
designs the rewrite operators ONCE; the loop applies them indefinitely
until shape coverage saturates against the Sherlock corpus.

When saturation hits (no new mutation passes all fitness gates), plumbline
has captured the audit-bug distribution as encoded in 2324 Sherlock
H+M judgments. The shape library at that point IS plumbline's complete
detection capability.
