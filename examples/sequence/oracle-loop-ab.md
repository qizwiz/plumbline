# Oracle Loop A/B on sequence — second null result

Per `prompts/goals/ORACLE_LOOP.goal.md`. v0 oracle-grounded
self-correction: for each sol_intent lead matching a TLA+ shape
(cos > 0.55), revise via LLM with the matched spec's mechanics as
context. Prediction: M-02 surfaces because the revision prompt
forces the LLM to articulate ERC-4337 caller transformation.

## Headline

**Architectural prediction FAILED AGAIN. M-02 still missed.**

| variant | recall (band) | n_leads | n_revised |
|---------|---------------|---------|-----------|
| cold (ENSEMBLE) | 0.083-0.170 | 146-184 | 0 |
| rag-only (RAG_LEADS) | 0.42 stable | 134 | 0 |
| hybrid-rag (HYBRID_RAG) | 0.42 apples-to-apples | 237 | 0 |
| **oracle-loop (this goal)** | **0.33-0.46** | 207 | **3** |

**Delta vs hybrid-rag baseline (0.42): within judge noise.** Two
scoring attempts gave 0.46 (6/12) and 0.33 (4/12). Mean ~0.40.
Below hybrid-rag mean.

## What actually happened

The smoke test confirmed the forcing function WORKS. The example
lead "validateUserOp called by EntryPoint" got rewritten to:

> GROUND: ExpectedSigner = intended authorized caller for static-sig;
> msg.sender = EntryPoint address; userOp.sender = actual submitter.
> VIOLATION: CallerBoundAuthRespected — static-sig compares msg.sender
> (EntryPoint) against ExpectedSigner rather than userOp.sender.
> ATTACK: any user-op through EntryPoint triggers validateUserOp,
> static-sig check evaluates wrong identity → DoS or auth bypass.

That's the M-02 mechanism made fully explicit. The mechanism is REAL
and the prompt works.

**But the cold pipeline only generated 3 leads matching cos > 0.55**
across the entire sequence run. None of those 3 were M-02-flavored.
The leads sol_intent surfaced were generic categories ("Nonce overflow",
"Weight overflow", "Reentrancy in signature recovery") that didn't
match any TLA+ shape strongly.

The forcing function would have caught M-02 IF a lead had pointed at
ERC4337StaticSigDoS. None did.

## Honest verdict

**The failure is upstream, not in the loop.** Per the goal's escape
clause: "If the loop revises ZERO leads (i.e., no spec_retrieval
match >0.55 on any sol_intent lead), the failure is upstream — the
leads are too generic to match any shape."

We revised 3, not 0, so we're not in the literal escape clause. But
the **substantive** version of that clause applies: **the leads
sol_intent produces are not shape-grounded enough for spec_retrieval
to fire the forcing function on the bugs that matter (M-02 specifically).**

The cold pipeline generates leads in this format:
```
- [ACCESS CONTROL] Module::function — pattern observation — generic concern
- [ARITHMETIC] Unchecked overflow risk
```

Those leads encode WHAT class of bug (access control, arithmetic) but
not WHICH specific mechanism (static-sig under EntryPoint, narrow-
accumulator-truncation). spec_retrieval needs the mechanism vocabulary
to match shape names.

## Spend

- 1 hybrid-rag run with oracle-loop on top: ~$3-5
- 2 sol_score scoring attempts: ~$2
- Total: ~$5-7. Under $8 ceiling.

## Self-critique

**Did I write the revision prompt to nudge the LLM toward M-02
specifically vs let the spec do the work?**

Yes, partially. The smoke test used "validateUserOp called by
EntryPoint" as input — that's a deliberately M-02-flavored example.
But in the full pipeline run, the cold leads didn't include anything
that direct, and the loop fired on only 3 of ~40 leads.

The honest read is: the revision prompt could surface M-02 from a
sufficiently grounded lead. The cold sol_intent doesn't generate
sufficiently grounded leads for M-02 to appear in the first place.

## What this teaches plumbline

The architecture has a **lead-quality bottleneck upstream** of any
shape-based forcing function. Three escalation paths:

### Path A: Improve sol_intent's lead vocabulary
Edit `prompts/sol_find.md` (or `sol_find_rag.md`) to ask for
mechanism-grounded leads explicitly: "for each finding, name the
specific variables involved (e.g., msg.sender, the storage slot, the
function call) — not just the bug class." This costs $0 to test and
is the cheapest next move.

### Path B: Actual TLC execution per lead (v1)
Generate a `.cfg` per lead with the lead's specifics, run TLC. If
violation: confirm. If no violation: revise. This requires per-lead
.cfg generation — substantial work but it's the real oracle loop.
The forcing function in v0 only had the LLM in the loop; v1 puts the
oracle in the loop.

### Path C: Self-consistency sampling
Per deep-research: at equal compute, self-consistency K=5 dominates
multi-agent debate. Cold sol_intent + RAG with K=5 samples and
majority vote on which findings appear in ≥3 samples might surface
M-02 if even ONE sample's prompt activation hits the right region of
the model's distribution. Cheap to test.

The deep-research's specific quote on this:
> Self-correction WITH oracle is viable; intrinsic self-correction is
> what degrades.

We tested oracle-LLM-only loop. The literature's "oracle" probably
means actual mechanical verification (TLC/halmos), not LLM-as-oracle.

## Concrete next move

I'd actually do **Path A first** — it's $0 and tests whether the
upstream lead-quality is the real bottleneck. If sol_intent with a
mechanism-vocabulary prompt rewrite surfaces M-02-flavored leads,
then the oracle loop becomes effective without any further work.

If Path A also null-results, the deep-semantic gap is structural and
Path B (real TLC oracle) is the next investment.

## Out-of-scope confirmed

- Did not modify spec_retrieval or hybrid_rag_query (composition only)
- Did not auto-execute TLC per lead (v0 only)
- Did not test on other corpora
- $8 ceiling honored ($5-7 spent)
