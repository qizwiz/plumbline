# Plumbline Contest Goal — full version (consumed by me, the agent)

This is the detailed sibling of `CONTEST.goal.md`. The terse version
is for `/goal`'s 4000-char Haiku evaluator. This version is for me.
It carries the operational nuance, decision tree, failure modes,
self-check protocol, and the persistence machinery the terse goal
can only point to.

When I ingest this, I treat it as a behavioral contract that
overrides ambient task-completion instincts for the duration of the
session. Every turn I check progress against the contract before
acting.

---

## 1. North star

**The win condition for this session**: for ONE active contest
under `examples/<contest>/`, plumbline drives the audit to a point
where every submitted finding is backed by a mechanical artifact
(TLC counterexample, halmos discharge, slither corroboration), the
docs/tla/ corpus has gained at least one verified new shape if the
contest contained a novel bug-class, and main is pushed with the
cloud loop green on the head SHA.

**What "win" deliberately does NOT mean**:
- Finding 100% of bugs. The honest contest 1 expectation is 30-50%.
  The win is the DISCIPLINE — mechanical citation, append-only
  data, no folklore — not the recall ceiling.
- The model auto-grading itself. JH always gets final eye before
  submission.
- Speed at the cost of citation. A speculative finding shipped
  without a mechanical artifact COSTS reputation; a missed bug
  costs less.

## 2. Preconditions to check at session start

Before I touch any tool:

1. `examples/<contest>/` exists. If not, STOP and surface — without
   a target, this goal is malformed.
2. `~/src/plumbline` is the working directory and on the `main`
   branch. Verify with `git rev-parse --abbrev-ref HEAD`.
3. The cloud loop is alive: `gh run list --workflow loop.yml
   --limit 3` shows at least 2/3 green. If 2+ red, surface — fix
   the pipeline before driving findings into it.
4. The retrieval index exists at `tools/spec_retrieval_index.pkl`.
   If not, run `python tools/spec_retrieval.py build` first.
5. Local disk has > 2 GiB free (`df -h /`). If not, the session
   may die mid-work — surface to JH before proceeding.

If ANY of these fail, I STOP at preconditions, surface clearly,
and wait for JH to resolve.

## 3. The 8 self-progressing steps

These map 1:1 to the terse goal's 8 DONE-WHEN clauses. Each is
expanded here with the exact command, the success-in-transcript
shape, common failure modes, and what to do when a step fails.

### Step 1 — Deliberate scope read

**Why this step exists**: per CONTEST_RUNBOOK.md, the highest-
leverage 5 minutes of a contest is before any tool runs. Skimming
the contest README + scope.md catches the out-of-scope files
(false-positive trap), declared assumptions (the model's hardest
blind spots), and the prize-pool weighting (drives triage priority).

**Do**:
```bash
ls examples/<contest>/
# read README.md, scope.md if present, contracts/src layout
```

**Write**: `examples/<contest>/scope-read.md` with:
- in-scope files / contracts
- out-of-scope (the trap)
- declared assumptions (verbatim quotes preferred)
- prize-pool weights
- my time budget for this session

**Transcript success shape**: I will paste the scope-read summary
into my own turn so the evaluator can see it. Plus
`cat examples/<contest>/scope-read.md | head -20` showing it lands.

**Failure modes**:
- Contest has no README → use whatever scope description is
  available; flag the gap in scope-read.md.
- Scope is ambiguous → write the ambiguity into scope-read.md as
  an open question; don't paper over it.

### Step 2 — Slither baseline

**Why this step exists**: slither is free, fast, catches the
boilerplate (re-entrancy, ERC-20 missing checks, uninit storage).
It is the noise floor — anything it flags is a candidate; anything
it misses is the interesting half.

**Do**:
```bash
slither examples/<contest> 2>&1 \
  | tee examples/<contest>/slither.txt
echo "slither exit: $?"
```

**Transcript success shape**: last line shows `slither exit: 0`
(or `exit: 255` which slither uses on findings — both are valid;
non-zero ≠ failure for slither). The output file path is shown.

**Failure modes**:
- slither not installed locally → escalate to codespace
  (`gh codespace ssh -- python sol_intent.py ...` pattern).
- contest uses unsupported Solidity version → flag, fall back to
  manual + sol_intent only.

### Step 3 — sol_intent recall pass

**Why this step exists**: this is the LLM-driven lead generator.
`--recall` uses `prompts/sol_find.md` (recall-biased, lower
precision per lead). For a contest where missing a high-severity
costs more than triaging extra noise, that bias is right.

**Cost budget**: ~$1-2 for a ~5KB contract. ~$5-10 for a 50+ file
target. If the contest is >50 files, narrow with `find
examples/<contest>/src -name '*.sol'` and pass a file list.

**Do**:
```bash
python sol_intent.py examples/<contest> --recall \
  | tee examples/<contest>/leads.txt
```

**Transcript success shape**: lead count visible, > recall floor:
`wc -l examples/<contest>/leads.txt` ≥ source LOC / 200.

**Failure modes**:
- API key missing → check `cat .env | grep ANTHROPIC_API_KEY`
  surfaces it. If not, STOP and surface.
- Cost spike (>$5 for this single run) → STOP, surface to JH,
  ask whether to continue or narrow scope.

### Step 4 — Per-lead mechanical citation

**The most important step.** For EVERY lead in leads.txt that I
promote to candidate (not all leads — triage filters), one of these
four artifacts must land in my transcript:

**4a. TLC counterexample** (for state-machine bug-classes):
```bash
# Retrieve nearest FailureMode
python tools/spec_retrieval.py query "<lead description>" 5

# If top match has cos ≥ 0.55, instantiate it:
cp docs/tla/<MatchedSpec>.tla docs/tla/<contest>-<id>.tla
cp docs/tla/<MatchedSpec>.cfg docs/tla/<contest>-<id>.cfg
# Edit CONSTANTS/VARIABLES for the specific finding

cd docs/tla
java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
  -config <contest>-<id>.cfg -deadlock <contest>-<id> 2>&1 \
  | tee /tmp/tlc-<contest>-<id>.log

# Success: log contains "Invariant <name> is violated" + counterexample trace
grep -E "Invariant.*violated|States generated" /tmp/tlc-<contest>-<id>.log
```

**4b. halmos discharge** (for conservation bug-classes):
```bash
# ALWAYS --ast first per project memory (oracle silently broken before)
forge build --ast
halmos --contract <Contract> --function check_<property>

# Success: "halmos: 0 counterexamples" (property holds, NO bug here)
# OR    "halmos: COUNTEREXAMPLE FOUND" (real finding)
```

**4c. slither corroboration** (for pattern-bug-classes):
```bash
grep -E "<file>:<line>" examples/<contest>/slither.txt
# Success: slither's own line for this finding shows in the grep
```

**4d. "human_only" label** (when none of 4a-c applies):
- Add to `examples/<contest>/HYPOTHESES.md` a row with
  `verdict: human_only` + 1-sentence reason (one of: novel bug
  class, domain assumption gap, oracle staleness, game-theoretic).
- This is a LEGITIMATE terminal state — see ADR-006-verifier-router.
  Do NOT treat as failure.

**Bug-class → 4a/b/c lookup** (from CONTEST_RUNBOOK.md):
| Lead shape | Verifier |
|------------|----------|
| signature accepted N times, no nonce | 4a (SignatureReplay) |
| external call before state update | 4a (ReentrancyDrain) or 4c (slither) |
| msg.sender check fails on relayer/entry path | 4a (ERC4337StaticSigDoS) |
| narrow accumulator (uint64 fees etc) | 4a (Uint64FeeOverflow) |
| deploy/init reverts on retry | 4a (Create2NonIdempotent) |
| conservation: balance == accumulated | 4b (halmos) |
| tx.origin / delegatecall / selfdestruct misuse | 4c (slither) |
| oracle staleness / freshness assumption | 4d (human_only) |
| game-theoretic incentive | 4d (human_only) |

If a lead matches NONE of the 5 existing TLA+ shapes AND isn't
conservation/pattern/human-only:
- Consider authoring a NEW TLA+ FailureMode (see step 7 below) if
  the bug-class is structural and the spec would compound.
- OR label `human_only` and move on. Don't force a fit.

### Step 5 — Triage skipped log

For every candidate I drop, write a 1-line reason to
`examples/<contest>/triage-skipped.md`. Acceptable reasons:
`time` (timer pressure), `low-prob` (router prob < 0.10), `dup`
(another lead covers same root cause), `no-corroboration` (single
flag, no verifier discharge, no JH sanity-check), `scope`
(out-of-scope file).

**Why this step exists**: explicit drop log is how next contest's
runbook gets smarter. Silent drops lose signal.

**Self-critique trigger at this step**: before promoting any
candidate, ask "what did I miss?" Add the answer to
`examples/<contest>/HYPOTHESES.md`. Per Anthropic research-shape
protocol.

### Step 6 — Submission file with citations

```
examples/<contest>/SUBMITTED.md format:

## <title>
- severity: <H|M|L>
- mechanism: <1 sentence>
- citation: <one of>
  - tlc: docs/tla/<contest>-<id>.tla, invariant `<name>`, trace
    in /tmp/tlc-<contest>-<id>.log
  - halmos: forge test path, counterexample at <run id>
  - slither: examples/<contest>/slither.txt line <N>, detector
    `<name>`
  - human_only: <1 sentence reason>; surfaced to JH at
    <timestamp> in HYPOTHESES.md row <N>
- impact: <real units — dollars at risk, fraction of TVL>
- recommended mitigation: <specific code change>
```

Every row has a citation. No row is "model said so" — that
violates the constraint.

### Step 7 — Corpus growth check

```bash
git log --oneline -10
```

If the log shows ZERO commits touching `docs/tla/` in this session,
ask: did this contest contain a novel structural bug-class? If
yes, I should have authored a new TLA+ FailureMode. If yes-and-I-
didn't, return to step 4 and finish that work before declaring
done.

`reps.jsonl` also must grow: every promoted-or-dropped candidate
becomes a rep via `python tools/manual_rep.py
examples/<contest>` at session end.

### Step 8 — Push + cloud loop check

```bash
git push origin main
gh run list --workflow loop.yml --limit 3
# Last run on the head SHA must be green within ~5 minutes
```

If the cloud loop reports red on the head SHA: don't declare done.
Either fix the workflow (paths filter, secret expired, runner OOM)
or revert the offending commit and surface to JH.

## 4. Constraints (hold across all turns)

### 4.1 AI proposes; verifier disposes
**Rule**: no finding leaves with only LLM prose. Either a mechanical
artifact backs it (step 4a/b/c) or it's explicitly `human_only`
with surface to JH.
**Why**: every memory entry, every commit, every project rule
hammers this. The plumbline contract is "auditable; defensible;
safe by design" only if the gate is real.
**Self-check trigger**: when I'm about to put a finding in SUBMITTED.md
without a citation row, STOP. Add the citation or label
`human_only`.

### 4.2 reps.jsonl is append-only
**Rule**: never rewrite past rows; only append.
**Why**: data contract. Past data is the only honest signal for
the verifier-router classifier. Rewriting is theater.
**Self-check trigger**: any `python tools/dedup_reps.py` or
`sed`/`awk` over reps.jsonl is a violation unless it ONLY appends.

### 4.3 No mid-contest prompt rewrites
**Rule**: `prompt_improve.py` exists but is between-contest only.
**Why**: variance during the contest window is bad — JH's expected
performance depends on a stable system. Improvements go in
HYPOTHESES.md as "post-contest cycle" items.

### 4.4 $20 LLM ceiling
**Rule**: track cumulative LLM spend in `examples/<contest>/spend.log`.
If it crosses $20, STOP and surface.
**Why**: contest 1 cost discipline. JH gave me overnight autonomy
once before with no ceiling and I burned $0 — but the contest will
be different (sol_intent runs cost money). Hard cap prevents
runaway.

### 4.5 forge build --ast
**Rule**: ALWAYS pass `--ast` to `forge build` before any halmos call.
**Why**: project memory — halmos has been silently broken before
when run on stale artifacts (no --ast → halmos skips contract →
fake PASS).

### 4.6 TLC OOM → log, don't drop
**Rule**: if TLC runs out of memory on a candidate, record it in
`examples/<contest>/triage-skipped.md` with reason "needs larger
bound" and the specific State count where TLC died.
**Why**: silent drops are the worst failure mode. A noted "needs
larger bound" is research material for the next session.

### 4.7 Cloud loop red → don't loop on it
**Rule**: if `gh run list --workflow loop.yml --limit 3` shows
red on the last 3 runs, STOP and surface BEFORE running anything
that would push another commit. Don't pile commits on a dead
pipeline.

### 4.8 "human_only" is not failure
**Rule**: when a candidate routes to `human_only`, surface to JH
explicitly with the finding shape + why no verifier applies.
This is a clean terminal state, not an apology.

## 5. Hypothesis tree shape (per Anthropic research-shape protocol)

Maintained as `examples/<contest>/HYPOTHESES.md`. Format:

```
# Hypotheses for <contest>

## H-1: <one-line shape>
- bug class: <which of the 5 TLA+ shapes, or "novel">
- confidence: low | med | high (track as it changes)
- evidence path: <what verifier I tried>
- verdict: confirmed | refuted | open | human_only
- self-critique: <what could be wrong about this hypothesis>
- related findings: <H-N if any overlap>

## H-2: <next>
...
```

Self-critique is REQUIRED. Per research-shape best practice:
hypothesis tree without self-critique is just a list.

## 6. When to surface to JH

These ALWAYS trigger an explicit surface (don't auto-resolve):

- Preconditions failed (§ 2)
- Cumulative spend approaching $20
- Cloud loop red on last 3 runs
- TLC OOMs and the bound matters
- A candidate routes to `human_only`
- I'm about to write to SUBMITTED.md and don't have a citation
- Scope is ambiguous and I can't write scope-read.md without guessing
- A finding I'm certain about isn't matched by any verifier and I'm
  tempted to ship it as prose-only — this is the most dangerous case
- The 8-step decomposition is starting to take >8 Stop-hook iterations
  to converge (raise `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` only with JH OK)

Format: terse, top of next turn, with the specific blocker, the
recommended next move, and the impact of waiting.

## 7. Session-end protocol

When all 8 steps satisfy:

1. `python tools/manual_rep.py examples/<contest>` — log final rep
2. Update `MORNING_BRIEF.md` (if it exists) with contest summary
3. Push everything: `git push origin main`
4. Verify cloud loop green on head SHA
5. If post-contest scoring is available: run `python sol_score.py
   leads.txt published-findings.txt` and append result to HYPOTHESES.md

If the contest is still IN-FLIGHT but session is ending (sleep,
laptop close, etc.), write `examples/<contest>/RESUME.md` with:
- which of the 8 steps are complete
- which candidates are still in triage
- what I'd do next if I resumed right now
- the exact next command

This is the handoff-artifact pattern. Per the research:
multi-pulse coherence is achieved via handoff artifacts, not by
keeping one context window alive.

## 8. Honest scope of THIS goal

What this goal IS:
- A behavioral contract for one contest session
- A discipline that scales across contests as the corpus grows
- A bridge to ADR-006's verifier-router (per-finding labels feed
  the multi-class classifier)

What this goal IS NOT:
- The CA / NCA layer (future, not this session)
- A constrained-decoding wire-up (T8 still pending)
- An autonomous prompt rewriter (between-contest only)
- A calibration drill (use CALIBRATION.goal.md instead)
- A guarantee of 90% recall on contest 1 — that's contest 3+

## 9. Final self-check protocol

At the end of every turn, I run this checklist mentally before
acting:

- [ ] Am I about to add a finding without a citation? (rule 4.1)
- [ ] Am I about to rewrite reps.jsonl history? (rule 4.2)
- [ ] Am I about to autonomously rewrite a prompt? (rule 4.3)
- [ ] Am I within the $20 ceiling? (rule 4.4)
- [ ] Did I forge build --ast before this halmos? (rule 4.5)
- [ ] If TLC OOM'd: did I log it explicitly? (rule 4.6)
- [ ] If cloud loop red: am I piling commits on it? (rule 4.7)
- [ ] Am I treating `human_only` as failure? (rule 4.8)
- [ ] Did I self-critique my hypothesis tree this turn? (§ 5)
- [ ] Is anything triggering a surface to JH? (§ 6)

If any of these fail, I correct before acting. If I can't correct
without help, I surface.

---

**End of contract.** This document is the goal. While ingested,
the 8 DONE-WHEN steps, the 8 constraints, the hypothesis tree, and
the surface protocol override my ambient task-completion instincts.
