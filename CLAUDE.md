# Plumbline — Project Rules

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
