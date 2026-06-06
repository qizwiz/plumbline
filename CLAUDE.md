# Plumbline — Project Rules

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
