# Deep-research findings: Claude Code `/goal` design constraints

Source: deep-research workflow run 2026-06-06, 107 subagents,
4.1M tokens, 25 claims adversarially verified, 16 confirmed, 7
refuted. Used to design `prompts/goals/{CONTEST,CORPUS_GROWTH,CALIBRATION}.goal.md`.

## What `/goal` actually is (verified, 3-0)

A first-class Claude Code command (CHANGELOG v2.1.139+, docs at
[code.claude.com/docs/en/goal](https://code.claude.com/docs/en/goal)).
One active goal per session. Condition up to **4,000 characters**.

After every turn, a small fast model (Haiku by default) evaluates
the condition against the conversation transcript and returns
yes/no + short reason. Goal auto-clears on "yes." State is
restored on `--resume`.

## The evaluator's blind spot (verified, 3-0)

> "The evaluator judges your condition against what Claude has
> surfaced in the conversation. It doesn't run commands or read
> files independently."

This is the single most important design constraint. **Every check
must be writable as something Claude's own transcript output will
demonstrate.** Acceptable:

- "`npm test` exits 0" (Claude runs it, the result lands in transcript)
- "`git status` is clean"
- "TLC printed `Invariant NoOverpayment is violated` in the last bash output"

Not acceptable:

- "the bug exists" (no transcript-observable proof)
- "the corpus has 14 specs" without surfacing a `ls` / index output
  showing 14

## The 3-element condition structure (verified, 3-0)

Anthropic-prescribed shape for durable conditions:

1. **One measurable end state** — the terminal predicate
2. **A stated check** — how Claude proves it (the command that
   surfaces the evidence)
3. **Constraints that matter** — anything that must not change on
   the way there

All three plumbline goals follow this shape with explicit
section headers.

## Stop-hook persistence semantics (verified, 3-0)

If you want "don't stop until done" rather than evaluator-and-stop,
you need a Stop hook. Hook returns exit code 2 OR `decision: "block"`
with reason; the reason is fed back as Claude's next instruction.

**Hard cap: 8 consecutive blocks without progress.** Claude Code
overrides the hook after that. So either:

- Decompose into ≤8 self-progressing steps (the plumbline goals do this), OR
- Raise the cap: `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=N`

Plus: hooks MUST check `stop_hook_active` in input JSON to avoid
infinite loops (corroborated by anthropics/claude-code#55754).

For verification that requires running commands (TLC, halmos,
slither), use **agent-based Stop hooks** (`type: "agent"`, 60s
default timeout, up to 50 tool-use turns). Note: marked EXPERIMENTAL
by Anthropic. 60s may be tight for TLC on bounded models with N>4;
override with explicit `timeout: N`.

## Verified long-horizon best practices (use these)

| Practice | Source | Confidence |
|----------|--------|-----------|
| Sprint contracts (negotiate "done" before execution) | [anthropic.com/engineering/harness-design-long-running-apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) | high (3-0) |
| Feature file with explicit pass/fail (200+ rows, flip status never remove) | [anthropic.com/engineering/effective-harnesses-for-long-running-agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | high (2-1) |
| Context resets + structured handoffs | (same) | medium (2-1, model-conditional) |
| Save progress to memory; be persistent | [platform.claude.com](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | high (3-0) |
| Research-shape protocol: success criteria → competing hypotheses → confidence tracking → self-critique → hypothesis tree | (same) | high (3-0) |

The plumbline goals embed:

- **Sprint contract** structure (the 8 DONE WHEN steps + CONSTRAINTS section IS the contract)
- **Hypothesis tree** (CONTEST.goal step 5 requires `HYPOTHESES.md`)
- **Self-critique** (CONTEST.goal step 5: "what did I miss?")
- **Save-to-memory + be-persistent** (constraints section explicitly: append-only reps.jsonl, no autonomous prompt rewrites mid-contest)

## Refuted patterns (do NOT include)

These failed 3-vote verification and are NOT in the plumbline goals:

| Pattern | Refuted at | Why |
|---------|-----------|-----|
| 3-artifact persistence (progress.txt + git + startup routine) | 1-2 | Not actually documented as required pattern |
| Planner-expands-1-4-sentence-prompt to spec | 0-3 | Not Anthropic-prescribed for long-horizon goals |
| Initializer + coder agent split | 1-2 | One pattern among several, not THE pattern |
| `/goal` is third-party-only (no Anthropic docs) | 0-3 | False — `/goal` IS official Anthropic |
| CHANGELOG silent on input contract | 0-3 | CHANGELOG documents v2.1.139 addition + 2 bug fixes |
| Specific `--tokens` flag syntax | 1-2 | Mixed with community tool jthack/claude-goal which is unofficial |

## Open questions (acknowledged limits of this research)

1. Official maximum number of evaluator continuations before
   give-up — unspecified in fetched docs. jthack's community tool
   uses 500.
2. Does the evaluator see tool_result blocks that scrolled out of
   visible transcript? Ambiguous.
3. How does `/goal` interact with `--resume` across BREAKING
   context resets (auto-compaction events)? Docs guarantee
   restoration on `--resume` but not on auto-compact.
4. Is there a published pattern for chaining a `/goal` condition
   to a verifier-discharge artifact (e.g., a sentinel file written
   by TLC/halmos that gets `cat`ted to surface in transcript)?
   Plumbline goals use `tail` / `grep` patterns; production examples
   are not in fetched sources.

## Time-sensitivity caveats

- `/goal` is recent (May/June 2026 timeframe). Pre-v2.1.139 Claude
  Code does not have it. Verify version before relying.
- v2.1.140 + v2.1.141 fixed concrete bugs (hangs under
  `disableAllHooks`; evaluator firing while background shells /
  subagents running). Older v2.1.139 may exhibit the un-fixed
  evaluator-race.
- "Context anxiety" pattern is model-conditional per Anthropic's
  own source (Sonnet 4.5 needed mitigation, Opus 4.5+ does not).
  The handoff-artifact pattern in CORPUS_GROWTH.goal is defensive,
  not universally required.

## Sources cited

Primary (Anthropic):
- [code.claude.com/docs/en/goal](https://code.claude.com/docs/en/goal)
- [code.claude.com/docs/en/hooks-guide](https://code.claude.com/docs/en/hooks-guide)
- [docs.anthropic.com/en/docs/claude-code/hooks](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [github.com/anthropics/claude-code/blob/main/CHANGELOG.md](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- [anthropic.com/engineering/effective-harnesses-for-long-running-agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [anthropic.com/engineering/harness-design-long-running-apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

Community / corroborating (used as architectural references only,
not as authoritative for the official `/goal`):
- [github.com/jthack/claude-goal](https://github.com/jthack/claude-goal) — pre-dates official `/goal`, but its SQLite-keyed-by-session pattern + 500-continuation cap + 5-step completion audit prefigure the official architecture.
- [arxiv.org/abs/2603.19685](https://arxiv.org/abs/2603.19685) — long-horizon agent benchmarks.

Total: 24 sources fetched, 101 claims extracted, 25 verified, 16 confirmed.
