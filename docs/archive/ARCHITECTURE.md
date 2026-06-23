# Plumbline Architecture — the Mathematical Space of Bugs

The ambition: **find ALL bugs reachable by the right kind of cellular
automaton over the Solidity grammar lattice.** Not a curated list of
findings on five corpora. The full set, defined topologically, sampled
exhaustively by an NCA, discharged by sound verifiers.

Today plumbline scores 0.60 ± 0.08 on novel-code recall and treats that
as ground truth. That's not the ceiling. That's the slice of bug-space
the current stack reaches. The architecture below describes how to
expand the reachable set, and how to know we're expanding it.

---

## The full stack

```
                    Solidity grammar
                          │
            ┌─────────────┴─────────────┐
            │                            │
        SYNTHESIS                   REAL CONTRACTS
        from grammar               (contests, audits)
            │                            │
            └─────────┬──────────────────┘
                      │
                program lattice
              (AST + SlithIR + CFG/DFG)
                      │
        ┌─────────────┼─────────────┐
        │             │             │
       NCA          sol_intent    slither
   (proposer)      (proposer)    (proposer)
        │             │             │
        └─────────────┼─────────────┘
                      │
                  candidate
                    leads
                      │
                   ML router      ◄─── (ml_zoo classifier
                      │                  with engineered features)
        ┌─────────────┼─────────────┐
        │             │             │
     halmos          TLC          slither
   (per-tx)       (temporal)     (pattern)
        │             │             │
        └─────────────┼─────────────┘
                      │
              verifier verdicts
                      │
                  sol_match
              (grounded scoring)
                      │
                  reps.jsonl
                  (append-only)
                      │
                self-improving
                  prompt_improve
```

---

## The layers, in honest order

### 1. Grammar (the lattice)

Solidity's grammar generates an effectively infinite set of syntactically
valid programs. Topology comes from the AST + SlithIR three-address
form + control-flow + dataflow edges.

**Why it matters**: the lattice is our source of unbounded labeled data
via synthesis (mutate clean contracts to inject known bug patterns).
Data scarcity is what's been capping the classifier at ROC-AUC 0.80; the
grammar removes that cap.

### 2. Synthesis (unbounded labeled data)

`tools/synth_bugs.py` (TODO):
- Take a `.ANSWERS.md` finding as a seed pattern
- Mutate a clean contract to introduce structural variations of the bug
  (rename identifiers, swap equivalent type-correct alternatives, inject
  no-op statements, reorder commutative operations)
- Output: `(contract_text, label_per_node)` pairs at arbitrary scale

**Why it matters**: training data for the NCA. Pact's spec_learner is
the Python analog; we port the pattern to Solidity.

### 3. NCA — TWO jobs, possibly one joint model

Per JH (2026-06-06): "you might need NCA (or something else) to teach
yourself model-checker fluency." The NCA does TWO things, which may be
two models or one joint model over `(program × spec)`.

#### 3a. NCA-as-verifier-router (Solidity grammar)

**WARNING from the literature (RESEARCH-NOTES-2026-06-06.md):** Building
this layer as a primary bug-finder is the trap. ReVeal trained on
BigVul drops to F1=0.5 on Devign. GPT-4o on May-2025 Linux CVEs hits
96% accuracy with F1=0. No DL bug-classifier discriminates before-fix
vs after-fix on VentiVul. The OOD collapse is *categorical*, not a
tuning issue.

**Corrected framing**: the NCA's job is **verifier-routing**, not
bug-classification. Given a lead from sol_intent (or any proposer),
predict *which verifier in our stack will discharge it successfully*.
That problem doesn't OOD-collapse because the verifiers themselves are
sound regardless of which lead they receive. The router only has to
learn the **taxonomy of leads**, not the **truth of bugs**.

Concretely, the NCA's output per lead is a distribution over:
`{slither_will_catch, halmos_will_decide, tlc_will_decide,
human_only}`. The lead is then sent to the predicted-cheapest verifier
that can handle it. Wrong predictions cost wasted verifier time but
never produce false-positive findings — because the downstream verifier
either confirms or refutes mechanically.

**Original bug-finder framing (kept for reference, not endorsed)**:

A neural cellular automaton over the program lattice:
- Cells = SlithIR statements (or AST nodes; resolution choice TBD)
- Cell state = vector embedding (semantic + tainted? + ownership? +
  cei-position? + reentrancy-class? + arithmetic-risk?)
- Local update rule = small neural network shared across all cells
- Edges = control flow + dataflow (defines neighborhood)
- Run T iterations until convergence; read off bug-class labels

**Why this and not "just a GNN"**: NCAs explicitly emphasize **iterative
diffusion under a uniform local rule**. This matches what auditors
actually do — propagate concern from "this function takes msg.value"
through the call graph until a violation crystallizes. The basin of
attraction around a bug is much larger than the exact bug pattern,
and the NCA learns the basin, not the point.

**Hardness connection**: CA reachability has a natural complexity
class. Some bug classes correspond to CAs whose dynamics are
incompressible (Rule-30-like — Ω(n) lower bound on finding them).
Those bugs are the contest-winners. Compressible bug classes are what
slither catches in milliseconds. The NCA's measured complexity per bug
class IS the contest-relevance ranking.

**Honest scope**: training a useful NCA is a multi-week project, not a
weekend. The minimum viable version is a graph-attention GNN with a
small number of message-passing rounds (≈ NCA with explicit aggregation).
We start there, frame as NCA architecturally, scale up.

#### 3b. NCA-as-fluency-teacher (TLA+ grammar)

My base-model TLA+ fluency is shallow — TLA+ is rare in training data
relative to Python / JS / TS. I can predict syntactically valid TLA+
tokens; my semantic accuracy drops fast outside bug classes that look
like patterns I've already seen. `SignatureReplay.tla` worked because
"signature replay" lives near patterns I've trained on. It won't
generalize.

The NCA-as-fluency-teacher takes a `(bug-shape, TLA+-spec-under-
generation)` pair and predicts TLC's verdict (or distance-to-verdict)
BEFORE TLC runs. This becomes a fast feedback signal during decoding:

```
  generate token sequence
        │
  constrained-decoding mask (grammar parser)        ← cheap, syntactic
        │
  fluency-NCA predicts TLC outcome from partial spec ← cheap, learned
        │
  TLC runs only on candidates the NCA scored high   ← expensive, sound
        │
  verdict feeds back as labeled training pair
        │
  fluency-NCA retrains on (program, partial-spec, TLC-verdict) triples
        │
  next generation: NCA is sharper, more candidates routed efficiently
```

My weights don't change; the prosthesis around me does. Effective
fluency improves at inference time as the loop turns.

#### 3c. The joint NCA (if 3a and 3b collapse into one model)

The joint lattice: pairs `(Solidity AST node, TLA+ AST node)` with
edges representing "this spec element references this program
element." State on each cell propagates the joint signal "spec
captures the bug at this program location" through the unified graph.
One model; two readings:
- Project onto Solidity nodes → bug-class label per program location
- Project onto TLA+ nodes → spec-quality score per spec element

The compression is elegant and the training signal compounds. Worth
trying once we have data; not worth committing to before the
sub-models work standalone.

### Realistic curriculum for getting NCA-3b working

The fluency-NCA doesn't need a graph model from day one. The curriculum:

1. **Retrieval corpus** (zero training; pure conditioning).
   Every successful `(bug-shape, TLC-verified TLA+ spec)` triple goes
   into a vector index. Next generation retrieves nearest neighbors as
   few-shot context. My in-context fluency improves as the corpus
   grows. **Weekend-tractable.**
2. **Syntactic-feature classifier on TLC outcomes.** As we accumulate
   `(spec, TLC-verdict)` pairs, train tonight's ml_zoo (retargeted)
   to predict TLC verdict from spec features. Use as gate: "should I
   actually run TLC on this candidate?" **Week-tractable.**
3. **Graph-structured NCA over joint lattice.** When the corpus is
   large enough that retrieval saturates, train the real NCA on the
   joint `(program × spec)` lattice. **Multi-week.**

The ratchet: every TLC verification this weekend feeds (1), which
enables (2) next week, which enables (3) the week after. **Nothing in
the architecture requires having (3) to start — (1) compounds from the
first verified spec onward.**

### 4. LLM (next-token fluency over target grammars)

Per CLAUDE.md "The superpower": the LLM is a next-token predictor over
constrained grammars. Its job in this stack is **fluency in target
grammars** (Solidity, TLA+, halmos check_*, SMT-LIB), conditioned by:
- Embedding-retrieved nearest known example as few-shot context
- Grammar mask at each decoding step (constrained decoding)
- Verifier feedback as gradient (prompt_improve when grounded score weak)

The LLM doesn't have to be sound. It has to be fluent. The verifier
discharges every output.

### 5. Verifiers (soundness substrate)

Each verifier has a specific scope:

| Verifier | Scope | Labels |
|----------|-------|--------|
| slither / aderyn | Syntactic AST patterns | `(program, matches_pattern_X)` |
| halmos / z3 | Per-tx symbolic EVM | `(program, invariant) → {holds, violated, timeout}` |
| TLC / Apalache | Temporal multi-actor | `(spec, property) → {holds, counterexample}` |
| sol_match | Identifier overlap + embedding | `(lead, finding) → {match, no-match}` |

The LLM authors specs/checks/queries against each verifier's grammar.
The verifier discharges. **No verifier in our current stack catches the
NCA's residual** — that's exactly where novel bug classes live, and
where human-LLM reasoning closes the gap.

### 6. ML router (predict which verifier each lead belongs to)

`tools/ml_zoo.py` (built tonight): classifier on lead embeddings +
engineered features, currently predicts "real bug" vs noise. The
**reframe**: predict *which verifier should adjudicate this lead*.

| Lead shape | Routed to |
|------------|-----------|
| Pattern-class (CEI, missing modifier) | slither / aderyn (free) |
| Per-tx invariant (overflow, redeem-mint round-trip) | halmos |
| Temporal / multi-actor (replay, DoS, liveness) | TLC / Apalache |
| Novel-semantic (economic, MEV, governance) | LLM + human only |

The router's job: send each lead to the cheapest verifier that can
discharge it. Halmos costs $$ and timeouts; TLC costs $ and bounded
state space; slither costs nothing.

### 7. sol_match (the grounded oracle)

Deterministic identifier-overlap + embedding scorer. Same inputs →
same numbers, forever. The append-only `reps.jsonl` is its journal.
This is what keeps every other layer honest — every claim about
recall/precision routes through sol_match before it counts.

### 8. prompt_improve (closed-gradient self-improvement)

When per-corpus grounded recall drops below threshold, an LLM rewrites
the relevant prompt file given a transcript of misses. Already wired
into the cloud workflow; fires on weak scores; tonight no fire because
all 5 corpora ≥ 0.50.

---

## The realistic + lofty goals, rewritten with this ambition

### Realistic (this weekend)
- [x] First Solidity TLA+ FailureMode (`SignatureReplay.tla`) authored
- [ ] TLC actually verifies it; counterexample matches H-3
- [ ] Saturday walkthrough of pact's TLA+/spec_learner discipline
- [ ] 2nd FailureMode for a different bug class (M-02 ERC-4337 DoS;
      pure liveness)
- [ ] `tools/tlc_rep.py` logs TLC verdicts as `verifier.kind="tlc"` reps

### Lofty (this week)
- [ ] ~25 TLA+ modules, one per High finding across 5 corpora
- [ ] `gen_tlc_model.py` Solidity-side (SlithIR → cfg generator)
- [ ] `tools/synth_bugs.py` — unbounded grammar-synthesis of labeled
      (program, bug-class) pairs
- [ ] First NCA prototype (small graph-attention model, trained on
      synth pairs; predicts per-node bug-class) — minimum viable; not
      production
- [ ] Marginal recall measurable per layer: slither ⊂ halmos ⊂ tlc
      ⊂ sol_intent ⊂ NCA
- [ ] ML router reframed: predicts verifier-routing, not binary real/noise

### The mathematical-space-of-bugs target (multi-week, the real ambition)
- [ ] NCA's reachable set on a corpus enumerated explicitly: per bug
      class, what fraction of synth-generated instances does the NCA
      catch?
- [ ] Compression-class ranking per bug class: which bugs require
      incompressible NCAs (contest-relevant) vs compressible ones
      (slither-class)?
- [ ] Contest-day pipeline: push scope → NCA scans → ML routes →
      verifiers discharge → ranked findings ready in ~10 min, no human
      in the loop except final adjudication

---

## Honest cost / risk per layer

- **Grammar + synthesis**: tractable, well-precedented (SolidiFI, Slipper).
- **NCA training**: substantial. Requires graph encoder, labeled data
  at scale, careful evaluation against held-out real contracts.
  Minimum viable in a week; production-grade in months.
- **TLA+ FailureMode authoring**: 1-2 hours per bug class hand-authored,
  much faster with retrieval-augmented LLM generation + constrained
  decoding once we wire it.
- **Constrained decoding for TLA+**: lark grammar exists for TLA+;
  outlines/guidance support custom grammars; this is library work, not
  research.
- **Compression-class ranking**: theoretical. May produce no useful
  signal if the bug classes don't cleanly stratify. Worth measuring;
  not worth building infrastructure on speculation.

---

## What this CHANGES vs tonight's loop

Tonight's loop measured `sol_intent` recall against a curated answer
key on 5 corpora. The reframed loop measures **the NCA's reachable
set** against grammar-synthesized infinite test data, with the answer
key being whatever the verifier stack discharges.

Tonight's classifier predicted binary real/noise. The reframed
classifier predicts verifier-routing.

Tonight's "the loop is closed" means workflow runs reps. The reframed
"the loop is closed" means the NCA, the verifier stack, the LLM
generators, and the grounded scoreboard all feed each other's
training/conditioning signal — no human in the steady-state loop
except for architecture and novel-class adjudication.

The architecture above is the target. The bricks tonight (the
verifier-discharge pattern, the LLM-as-fluency principle, the first
TLA+ FailureMode) are the first three out of maybe twenty. The weekend
adds the next five.
