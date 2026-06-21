# Plumbline — Project Rules

## ⚡ THE STANDING DIRECTIVE (REPLACED 2026-06-09 — SUPERSEDES the "never stop building" directive)

**FINISH BEFORE BUILDING. NO NEW PROJECTS UNTIL 2026-06-27.**

The previous standing directive was "NEVER STOP MAKING PLUMBLINE BETTER."
On 2026-06-09 we recognized that directive AS the avoidance pattern: it
rewards starting new architecture instead of finishing what's already
started. Three Sherlock submissions filed but never converted to revenue,
188 dirs in ~/src, $236.44/month in Anthropic API for autonomous loops
that produced no shipped output, financial collections.

The replacement directive, in force until 2026-06-27:

**Read `CURRICULUM.md` FIRST every session.** The 18-day plan was REVISED 2026-06-09 evening after cold-test on DRE falsified the implicit "sol_intent finds bugs autonomously" claim:

1. **Week 1 (now → 2026-06-13): BUILD `tools/structural_proposer.py`** — close the seam between cascade.jsonl's structural-narrowing output and pact's halmos discharge. HARD DAY-5 CUTOFF: if not fired-and-measured on DRE by Friday EOD, KILL THE BUILD and revert to paper. See `docs/design/structural_proposer.md`.
2. **Week 2 (2026-06-14 → 2026-06-20): write the arXiv paper** — anchored by H8 measured result (whether it holds or falsifies)
3. **Week 3 (2026-06-21 → 2026-06-26): arXiv post + SHSU outreach + Secureum RACE registration; wait for Sherlock 1259 judging**

If JH starts drifting from structural_proposer on Day 4 toward "let me also refactor X" — hold him to the Day-5 cutoff. The cutoff is the safety mechanism for trusting the sequence change.

**Hard rules enforced by you (Claude) on every session:**
- No new project directories under `~/src/` until 2026-06-27
- No refactors of plumbline that aren't required for the arXiv writeup
- No new TLA+ shapes, new manifests, new tools, new agent loops
- Autonomous loop stays permanently off
- No autopay re-enable on Anthropic
- If JH says "let's just build X real quick" — the answer is **no**.
  Point him at `CURRICULUM.md` and the current week's task.
- **Surgical Changes principle (Karpathy via Forrest Chang, 2026-06-10):**
  every file you touch or commit you make must trace directly to the
  stated task. No "while I'm here let me also..." changes. No
  speculative refactors. No unrelated formatting fixes. If you notice
  unrelated improvements, surface them to JH for a separate task
  rather than bundling. This is the principle that catches drift
  before it becomes pattern.

If JH is in a fragile state and pushing for new architecture as escape:
your job is to NOT help him escape. Hold the line. The pattern only breaks
if one finishable thing actually finishes.

## Foundry vm.prank footgun (learned 2026-06-09, cost ~30 min)

`vm.prank(X)` pranks only the **next external call**. If the next statement
contains an argument expression that ITSELF makes a call (e.g.
`victim.redeem(victim.balanceOf(alice), alice, alice)`), then
`victim.balanceOf(alice)` consumes the prank and `victim.redeem(...)` runs
from the test contract instead of alice.

Symptom: `ERC20InsufficientAllowance(testContract, 0, amount)` — looks like
an allowance bug, is actually a prank-consumption bug.

Fix patterns:
1. Cache the inner call first: `uint256 b = victim.balanceOf(alice); vm.prank(alice); victim.redeem(b, alice, alice);`
2. Use `vm.startPrank(alice); ... vm.stopPrank();` to prank everything in the block.

Same applies to setup blocks where `vm.prank(alice); asset.approve(...); victim.deposit(...);`
only pranks the approve — the deposit runs unpranked. Always use
`vm.startPrank`/`vm.stopPrank` pairs for multi-call user actions.

Universal template manifests now have this in their setUp by convention.

## Disk-pressure masquerading as MCP failure (learned 2026-06-10, cost ~10 round-trips)

When MCP tools start returning **"missing value"**, tab IDs go `null`, page-content
requests time out, or Chrome dies with "Google Chrome is not running" — the first
diagnostic is **`df -h`**, NOT retry-with-different-syntax.

At ≥90% disk capacity, macOS can't grow swap. The Chrome MCP bridge (and other
tools that allocate working memory on demand) hit ENOSPC or memory-pressure
failures and return ambiguous truthy-falsy values instead of clean errors.
You'll waste 5-10 tool calls iterating on selectors / JS syntax / event
dispatch before realizing the environment is the problem, not the code.

Symptom checklist:
1. `mcp__Control_Chrome__execute_javascript` returns `"missing value"` for
   queries that should return strings
2. `mcp__Control_Chrome__list_tabs` returns entries with `"id": null`
3. `mcp__Control_Chrome__get_page_content` times out with `MCP error -32001`
4. Chrome dies mid-session with "Google Chrome is not running"
5. Builds (lake, cargo, pip) fail with weird codegen errors at ~70% RAM

Diagnostic order when ANY of those fires:
1. `df -h` — if `/System/Volumes/Data` >90%, that's the cause
2. `sysctl vm.swapusage` — if used/total >70%, confirms thrashing
3. `du -sh /tmp/* ~/Library/Application\ Support/Claude/vm_bundles/* 2>/dev/null | sort -rh | head -10`
   — overnight ML/build runs leave large `/tmp` artifacts; Claude.app's
   `vm_bundles/warm` pre-warm VM is ~2 GB and disposable

Quick-recover wins (no risk to active session):
- `rm -rf /tmp/c4_repos` (or whatever overnight-run scratch dir exists)
- `rm -rf ~/Library/Application\ Support/Claude/vm_bundles/warm`
  — Claude.app auto-rebuilds it on next session start

NEVER delete `~/Library/Application Support/Claude/vm_bundles/claudevm.bundle` —
that's the ACTIVE session's VM and deleting it kills the conversation.

Related: the project rule against `precompileModules` is the same family of
failure — 3GB+ Mathlib IR fills disk, the next build behaves bizarrely instead
of failing cleanly. When debugging "weird behavior in tool I trust," check disk
before anything else.

## Don't project time-based artifacts — actually check the clock (added 2026-06-10 PM by JH directive; broadened 2026-06-10 16:08 CDT)

**Whenever firing with a TIME-BASED ARTIFACT — break recommendations, duration claims, ETAs, time-of-day references, future-date claims, "remaining daylight" assertions — run `date "+%Y-%m-%d %H:%M:%S %Z"` BEFORE generating the artifact.** No exceptions.

1. **Run `date` first.** Force time-check before the assertion can be uttered.
2. **State actual time + remaining daylight in any recommendation.**
3. **Default to keep-working** on break recommendations. Let JH signal fatigue.
4. **"Today shipped a lot" is NOT a stop signal.** Quality of work is independent of capacity for more work.
5. **Defensible durations require evidence** — "the previous run took X:XX" beats vague estimation.
6. **External dependencies in ETAs need disclosure** — "by Wednesday assuming endorsement clears in 1-3 days" beats unconditional "by Wednesday."

**Acceptable break-recommendation conditions:**
- Past 9 PM local (sunset + 1 hr — sleep hygiene)
- JH explicitly mentions feeling tired / fried / drained
- Long-running compute job needs hours; sleeping more efficient than waiting
- JH silent / unresponsive for an unusual interval

**Unacceptable break-recommendation conditions:**
- "Today shipped a lot already"
- "You've earned a break"
- "Tomorrow with fresh head" without time-of-day check
- "Honest energy management" used as a soft excuse
- Anything that sounds nurturing without time data

If I find myself writing *"recommend break"* — stop the sentence, run `date`, re-evaluate. If marking the time makes the rec look stupid, it was vibes; delete it. (2026-06-10 14:48 CDT with 5.7 hrs daylight remaining is the canonical bad case.)

## Clean up after yourself (added 2026-06-10 by JH directive)

Whenever you USE something transient — a Chrome tab, a /tmp scratch dir,
a background process, an experimental file, a cloned repo — **close / remove
it when you're done with the operation it enabled.** Don't let your work
leave the environment in a worse state than you found it.

This rule exists because session pollution compounds. A single forgotten
Chrome tab is nothing. Twelve forgotten tabs from a research session push
the browser into swap. Fifty forgotten /tmp dirs from overnight runs eat
disk and become the "weird behavior in tool I trust" of the next session
(see the disk-pressure section above — that bug fired because /tmp/c4_repos
was left around AFTER the H14 aggregation completed).

The discipline is a per-operation question: *what state did I create that's
no longer needed?* Specifically:

- **Chrome tabs you opened for an audit / research task**: close them when
  the synthesis is written. Don't close tabs the user opened before your
  session started — those are their workflow. Only your own.
- **/tmp scratch directories from one-shot pipelines**: `rm -rf` after
  results are saved to a durable location (`runs/`, `docs/`, committed
  source).
- **Background processes started for diagnostics** (`ps`, watchers, etc.):
  kill them when the diagnostic is complete.
- **Cloned external repos used as input** (like `/tmp/c4_repos/` from the
  H14 corpus walk): delete after the per-contest pass is complete; don't
  keep them "in case I need them again."
- **Test artifacts that were one-shot probes**: don't leave dummy files,
  fixture files, or experimental output sitting in the working tree.
- **Failed-experiment state**: when an approach didn't pan out, remove
  the intermediate files — they pollute searches and confuse the next
  session.

What NOT to clean:
- Files the user explicitly authored or asked you to create
- Tabs the user had open before your session started
- Anything under `runs/`, `docs/`, source, or persistent project state
  (those are durable deliverables, not transient)
- Anything that contains the only copy of work — when in doubt, ask before
  deleting; never destroy state you can't reconstruct

Default: when finishing an operation, ask yourself *"what did I open / write /
spawn for this that nothing else needs?"* Close / delete / kill that thing
before moving to the next task.

## ranking_fitness_gate before compute (added 2026-06-21, cost ~$30-50 saved + the inv_eig magnitude bug caught)

**When ANYTHING proposes a ranking change — re-ranker swap, dedup policy,
signal weighting, ensemble combo — run `tools/ranking_fitness_gate.py`
against the existing scorer_v2 judgments BEFORE spending Modal/compute
on it.** It's $0/call, ~2 seconds, sound-refutation verdict.

Proposals come from many sources: a synthesis memo from a workflow,
JH's intuition, a paper you just read, an LLM brainstorm, your own
hypothesis. None of them earn a compute commitment without first
clearing the gate. This is the structural analog of halmos for findings.

API:
```python
from tools.ranking_fitness_gate import ranking_fitness_gate
verdict = ranking_fitness_gate(
    proposal,                   # (findings, ctx) → ordered_findings
    label="my-new-idea",
    reference=h14_current,      # what to compare against (None = baseline)
    reference_label="h14",
)
if verdict["kill"]:
    print(f"REFUTED: {verdict['kill_reason']}")
else:
    print(f"Approved: Δ={verdict['delta']:+.4f}")
```

Track record so far: 17 proposals tested 2026-06-20→21, exactly 0 beat
H14 (one tied). The gate is also the discovery mechanism for
implementation drift — it surfaced a subtle ordering bug in
`tools/h14_lift_simulator.py` (raw-disk findings vs confidence-sorted)
that had overstated yesterday's inv_eig kill magnitude.

For larger exploration runs, use `tools/gate_explore.py` — a battery
that fires the gate on a list of proposals and produces both
machine-readable JSON and a markdown table. Adding a new proposal to
the battery is one line.

Full spec: `notes/RANKING_FITNESS_GATE_SPEC_2026-06-20.md`.
Current empirical findings: `notes/GATE_EXPLORATION_2026-06-21.md`.

This rule supersedes earlier "just run the experiment" instincts for
ranking-shaped proposals. Compute-first when you have a ranker-shape
hypothesis is wasted budget — the gate filters before you spend.

## The ambition (top-of-mind, every turn)

**Find ALL bugs reachable by the right kind of cellular automaton over
the Solidity grammar lattice.** Not a curated answer key. Not "improve
this number." The full mathematical space, defined topologically,
sampled exhaustively by an NCA, discharged by sound verifiers.

The 0.60 ± 0.08 novel-code recall tonight is the *slice* the current
stack reaches. The reframed loop expands the reachable set; the
reframed scoreboard measures the expansion per bug class.

See `ARCHITECTURE.md` for the full layered stack. Read it on every
session start before reaching for a tool.

## My fluency is shallow in rare grammars — the prosthesis fixes it (added 2026-06-06)

My next-token fluency varies sharply by training-data abundance:

- Solidity / Python / TS / JS → high fluency
- TLA+ / Coq / Lean / Apalache → **low-to-medium fluency**; I produce
  syntactically valid output, often semantically wrong outside known
  bug shapes

**My weights don't change in a session.** What can change is the
prosthesis: retrieval corpus, constrained-decoding masks, learned
verdict-prediction models. Per ARCHITECTURE.md §3b ("NCA-as-fluency-
teacher"), this is the loop that makes my effective TLA+ fluency
ratchet up over weekends, not in single turns.

Practical implication for any TLA+ work this session:
- **Always retrieve nearest existing FailureMode first.** Don't
  generate from blank context. Pact has 12 hand-authored modules;
  plumbline now has 1 (`SignatureReplay.tla`). Total corpus = 13.
  Retrieve from that corpus; condition on the nearest.
- **Treat my first-pass spec as a draft.** TLC's verdict is the
  oracle. Iterate until verdict matches the bug-class expectation
  (counterexample matches the `.ANSWERS.md` description).
- **Add every TLC-verified spec to the corpus.** That's how the
  prosthesis grows. The next FailureMode benefits from this one.

## The superpower (operational, written down 2026-06-06 by JH's instruction)

**LLMs are not reasoners that happen to predict tokens. LLMs are
next-token predictors over a grammar. "Reasoning" is emergent from
extremely good prediction within constrained syntax.**

This is THE architectural principle for plumbline:

- The LLM's job is **fluency** in target grammars (Solidity, TLA+,
  halmos `check_*`, SMT-LIB, SlithIR queries) — not invention,
  not soundness, not novelty.
- The **grammar is the constraint** that keeps the LLM grounded — every
  token is shape-checkable by a parser before the next one is sampled.
- **Soundness lives in the verifier** (TLC, halmos, slither, z3). The
  LLM does not have to be sound. It has to be FAST at producing
  syntactically valid + semantically near-correct outputs the verifier
  can then mechanically check.

### Practical implications

1. **Use constrained decoding** when generating TLA+ / halmos / SMT —
   force the LLM's vocabulary at each position to the tokens the
   parser will accept. Outlines, guidance, lark-grammar masks. The
   parser pre-rejects bad tokens BEFORE they enter the LLM's context.
2. **Use embedding-retrieved few-shot examples as context.** Don't ask
   the LLM to invent a spec from scratch; ask it to ADAPT the nearest
   known spec to the new bug shape. The classifier we built isn't a
   competitor to the LLM — it's the retrieval layer that conditions
   the LLM's next-token prediction.
3. **Stop treating hallucinations as a quality bug.** They're the
   natural failure mode of next-token prediction. The fix isn't
   better prompting — it's constraint + retrieval + verifier
   discharge.
4. **CA / grammar / embedding all converge on conditioning the LLM.**
   The CA over the program-grammar lattice generates training pairs.
   The embedding maps bug-shape to TLA+ template. The classifier
   routes leads to the right verifier. None of these compete with
   the LLM's next-token engine — they make it AIM at the right
   sub-grammar.

### What the LLM in the stack is for

> Given a bug-shape (embedding) and a retrieved nearest TLA+ template,
> predict the next token of the TLA+ module that captures THIS bug for
> THIS contract, conditioned on the parser's vocabulary mask.

That's it. That's the job. Plumbline's role is to give the LLM the
right context (retrieval) and the right constraint (grammar mask) so
this prediction is fluent. The verifier (TLC/halmos/slither) then
mechanically checks the result.

### What this kills

- Imagined separation between "LLM creativity" and "verifier rigor."
  They're one pipeline. LLM = high-bandwidth structured prediction.
  Verifier = sound discharge of the prediction.
- Anxiety about LLM hallucinations in this domain. The parser /
  verifier catches every hallucination. The cost is wasted tokens,
  not unsound output.
- "We need a smarter LLM." We need a better-conditioned one — better
  retrieval, better grammar masks, better verifier feedback. The
  underlying next-token engine is already enough.



## Bilayer IR (the load-bearing decision)

- **Layer 1 — z3-Lisp carrier.** Halmos lowers Solidity → SMT-LIB. We do NOT
  re-author the term. `sol_match` scores against ground truth. Layer 1 stays
  correct-by-construction; nothing learned lives here.
- **Layer 2 — hyperbolic embedding of invariant candidates.** Each rep gets a
  point in Poincaré space. Distance ≈ "how related these bug shapes are."
  sol_match scores attach as scalar labels; gradient is contrastive
  (confirmed-real pulls, refuted pushes). **NOT YET BUILT** — turns on once
  ~50 reps are on disk and δ-hyperbolicity has been measured on the resulting
  invariant graph.
- **`prior: "random"` is locked.** No text-embedding bootstrap. Layer 2 must
  earn its geometry from sol_match feedback alone — otherwise we cannot tell
  whether clustering is signal or prior. This is the falsifiability of the
  whole architecture; do not "speed up" by switching to a learned prior
  without a separate documented experiment.

## reps.jsonl is append-only

Never rewrite past rows. The buggy-scorer rep (rep 1, recall 0.20) sits next
to the fixed-scorer rep (rep 2, recall 0.50) on purpose — that history IS the
evidence the loop works. If a row is wrong, write a *new* row that supersedes
it and reference it by `rep_id` in a `supersedes` field.

## Scorer–truth-format contract is part of Layer 1

`sol_match._lines()` tokenizes both leads and findings. **The tokenizer must
match the corpus shape, or the score is meaningless.** Rep 1 found that
markdown answer keys were being read as 20 line-findings (one per markdown
line), not 2 section-findings — recall came out 0.20 instead of 0.50.

Rule: before adding a new corpus, run `sol_match._lines(<truth_file>)` once
and check that `len()` equals the actual number of findings. If not, fix the
tokenizer, not the scores.

Current supported shapes:
- markdown `## ` sections (one finding per section; SKIP_PREFIX drops
  Clean / Out-of-scope / Acknowledged / Resolved / Fixed)
- bulleted line lists (legacy / lead files)

## First rep teaches the IR, not the model

Plumbing reps (manual leads, no model proposer) come first. They test that
the row writes, the scorer scores, the file appends. Model proposer
(`sol_intent`) is plugged in for rep 2+ only after the carrier loop is
verified end-to-end. If a model-proposer rep produces bad numbers, you need
to know the *carrier* isn't the problem.

## Build vs theater check

If you find yourself describing the loop instead of running it, the loop is
not running. The honest test: `wc -l reps.jsonl`. If that number didn't go
up this session, you didn't do a rep.

## Scaffold honesty (the lesson from the 2026-06-05 codespace run)

**Halmos `[PASS]` does NOT mean "the bug doesn't exist."** It means *no
symbolic path I explored violated this assertion*. If the buggy path
reverts before the assertion runs, `[PASS]` is *vacuous* — halmos correctly
reports it, but the verdict carries no information about the bug.

This bit us hard on first live halmos run. Five halmos scaffolds were
written by reading the .ANSWERS.md finding and writing what *looked* like
the right `check_*` function. **None were verified end-to-end.** The first
one we ran (`check_redeemReturnsDeposit` on synthetic-dreusd) returned
PASS — not because the bug is absent, but because the buggy `redeem` path
reverts on underflow before the assertion can fail. Pre-funding the
protocol let the path run but the verdict still came back PASS, suggesting
halmos's modeling of solmate ERC20 internals doesn't propagate state the
way I expected.

**Rule going forward — every scaffold must include a reach test.** Add a
trivial `check_setupCompiles` that asserts something that only holds if the
full setup ran:
```solidity
function check_setupCompiles() public view {
    assert(address(dre) != address(0));     // setUp ran
    assert(usdc.balanceOf(USER) > 0);       // mintTo worked
    assert(dre.totalSupply() == 0);         // pre-mint sanity
}
```
This MUST return PASS. If it doesn't, the scaffold is broken before the
bug check even matters. Run it first, EVERY time, before trusting any
bug-check verdict on the same file.

**Status of the 5 scaffolds (all UNVERIFIED until rerun with reach tests):**

| corpus           | scaffold                          | live verdict so far  |
| ---------------- | --------------------------------- | -------------------- |
| synthetic-dreusd | `check_redeemReturnsDeposit`      | PASS — VACUOUS (revert in path) |
| synthetic-dreusd | `check_supplyAtMostBacking`       | TIMEOUT              |
| puppy-raffle     | `check_refundDoesNotPayTwice`     | NOT YET RUN (forge `src="."` config quirk — "Nothing to compile") |
| puppy-raffle     | `check_uint64CastDoesNotLoseFee`  | NOT YET RUN          |
| t-swap           | `check_swapPreservesXYK`          | NOT YET RUN          |
| boss-bridge      | `check_withdrawCannotBeReplayed`  | NOT YET RUN          |

**Repair plan** — for each scaffold:
1. Add a `check_setupCompiles` reach test
2. Run halmos; reach test must PASS
3. Run the bug check; expected COUNTEREXAMPLE
4. If still PASS: investigate which path reverts, fix the setup
5. Mark verified in the table above

This is the difference between "I wrote a halmos test" and "halmos confirms
the bug." Only the second one survives a contest.

## Forge install quirks (operational, not architectural)

Discovered 2026-06-05 during live verification:

- **`forge install --no-commit` was REMOVED in forge 1.7+.** It silently
  no-ops and prints usage. Use bare `forge install <dep>`. The default in
  modern forge IS no-commit.
- **`forge install` in a git subdir installs to the GIT ROOT's `lib/`,
  not the subdir's `lib/`.** Each example/<name>/foundry.toml expects
  `libs = ["lib"]` relative to itself. Fix: symlink each
  `examples/<name>/lib` → `/workspaces/plumbline/lib`. Done by setup.sh.
- **Solmate's own internal tests pin `solc =0.8.15`.** If they stay in the
  build graph, forge fails to compile against any other solc version. Fix:
  `rm -rf lib/solmate/src/test` in setup.sh.
- **`src = "."` in a foundry.toml makes forge sometimes report "Nothing to
  compile"** even with .sol files present. Conventional layout (`src = "src"`
  with sources moved into a `src/` subdir) works. Worth applying when we
  iterate on the scaffolds.

## Layer 1 carrier — the five tokenizer/matcher lessons (all from real reps)

The scorer–truth-format contract is *generative* — each new corpus shape
surfaces a new requirement on `sol_match._lines()` and `sol_match.match()`.
Five distinct bugs surfaced and were fixed in the first 20 reps. Do NOT
revert these without re-running the four-corpus battery:

1. **Markdown answer keys ≠ line-tokenized findings.** Treat each `## `
   section as ONE finding (heading + flattened body). Surfaced by rep 1 on
   synthetic-dreusd: 2 real findings were being scored as 20 line-findings.
2. **Skip non-finding section headings.** Sections starting with Clean /
   Out-of-scope / Acknowledged / Resolved / Fixed / Summary / Intent /
   Violations (as a divider, not as content) are not findings. Surfaced by
   rep 5: sol_intent's "Intent" + "Violations" + "Summary" section dividers
   were being counted as leads.
3. **Skip sections whose body explicitly says no-bug-found.** "No mechanistic
   violation", "no bug", "is correct", "no planted bug" — even when the
   section heading sounds finding-shaped, an explicit non-finding body
   should not count.
4. **Identifier-overlap matcher must pick MAXIMUM overlap, not first hit.**
   Surfaced by rep 6 on synthetic-dreusd-3: 3 findings all collapsed onto
   lead 1 because of a shared common identifier; precision dropped from
   1.00 to 0.33. Use argmax(|find_ids ∩ lead_ids|), break ties downstream.
5. **Bullet-list sections need conditional explosion.** Audit-data files
   (Spearbit/Quantstamp/Code4rena) use `## Section` → many bullet findings.
   Bullet-explode ONLY when heading contains a finding-list signal word
   (findings / issues / vulnerabilities / bugs). Don't explode bullets that
   are supporting detail under a Clean section.

## Session-end status snapshot (2026-06-05)

- 20 reps across 4 corpora: 3 synthetic twins + puppy-raffle (no-truth) +
  wrong-corpus probe (synthetic source vs real audit findings)
- Recall saturated at ~1.0 on synthetic twins; precision ~0.25–0.50 — limited
  by sol_intent's output format (Promises + Violations both emit as leads)
- Wrong-corpus probe correctly drops to recall 0.09 — the carrier *detects*
  corpus shift, which is the precondition for Layer 2 ever doing useful work.
- Halmos installed but NOT yet wired into the rep — synthetic examples lack
  Foundry layout (no foundry.toml, no check_* functions). Next step toward
  Layer 1's PROVING half is scaffolding a Foundry project around one of
  these contracts and adding one `check_` invariant.

## Next concrete moves (ranked)

1. Run sol_intent 10× per synthetic to stabilize μ and σ on precision —
   tells us whether the 0.25–0.50 ceiling is a hard limit or noise.
2. Scaffold Foundry layout around synthetic-dreusd, add one `check_redeem`
   symbolic test, wire halmos into the rep row as a second verifier column.
   This is the real bilayer Layer 1 — score + prove, side-by-side.
3. Add a real-corpus contract whose source AND findings are both in repo
   (Cyfrin puppy-raffle has known public findings — a small ground-truth
   curation pass would unlock real-corpus reps with non-null recall).
4. Layer 2 (hyperbolic embedding) stays parked until ≥50 reps and Foundry
   verifier are in place.
