# Plumbline Curriculum — 18-Day Sit-Still Bet

**Author:** Jonathan Hill (with Claude as discipline-keeper)
**Started:** 2026-06-09
**Ends:** 2026-06-27 (Sherlock 1259 judging window)

---

## Why this file exists

Pattern recognized 2026-06-09: every previous "I'll commit to X" project for JH
has ended with JH starting a NEW architecture project instead of finishing the
committed one. The architecture-of-the-thing is the avoidance pattern.

This curriculum exists so each Claude session reads it, sees the commitment,
and refuses to help start anything new until 2026-06-27.

**The bet:** finishing ONE thing where "done" is yes/no externally given is
worth more than ten new architectures. Three things on the schedule. All
externally graded. No new ones allowed.

---

## HARD RULES — enforced every session

1. **No new project directories under `~/src/`** until 2026-06-27.
2. **No refactors of plumbline** that aren't required for the arXiv writeup.
3. **No new TLA+ shapes, no new manifests, no new tools, no new agent loops.**
4. **Autonomous loop stays permanently off** (`.autonomous_lock` deleted).
5. **No autopay re-enable on Anthropic.** Pay-as-you-go from balance only.
6. **Every session opens with:** read this file, report yesterday's delta,
   work the current task. No exceptions.

If JH says "let's just build X real quick" — the answer is **no, not until
2026-06-27.** Point him at the current week's task.

---

## REVISED 2026-06-09 EVENING — sequence change

After today's cold-test on DRE revealed sol_intent solo produced ZERO violations on the Sherlock #1 codebase, and after studying pact's invariant_agent + plumbline's structural_cascade output, we identified that the seam between "structural narrowing" and "LLM-text proposer" is much smaller to close than initially thought: cascade.jsonl already emits the rich object (corpus_top1, tla_top1_shape, halmos_status) the proposer needs. See `docs/design/structural_proposer.md`.

EV analysis favors building structural_proposer FIRST, then writing the paper with H8 results as the headline rather than as future work. Discipline preserved by hard Day-5 cutoff: if structural_proposer isn't fired-and-measured on DRE by Friday EOD (2026-06-13), revert to paper-first immediately. No "almost there, give me one more day."

## Week 1 — Days 1-5 (2026-06-09 → 2026-06-13): structural_proposer build + H8 test

**Goal:** Working `tools/structural_proposer.py` fired on DRE with a measured recall number by EOD Friday.

### Day 1 (today, 2026-06-09)
COMPLETE. Bleed stopped, 14 commits, Section 1 + 7 + 3.1 written, cold-test falsified the implicit Sherlock-#1-from-sol_intent claim, structural_proposer design doc landed.

### Day 2 (Tue 2026-06-10) — Pass A corpus annotation
- Author `tools/annotate_corpus_invariants.py`
- For each of 1,240 findings in `findings_index.pkl`, LLM-extract a halmos-shaped structural invariant from the title prose
- Add `structural_invariant` field per finding
- Validate on 50 sampled findings — manually confirm the extracted invariant is faithful to the bug
- Re-pickle `findings_index.pkl`
- Cost: ~$5 OpenRouter; effort: 4-6 hours

### Day 3 (Wed 2026-06-11) — structural_proposer core
- Author `tools/structural_proposer.py::propose_check(cascade_entry, corpus, shapes_dir)`
- Compose pact's `_propose_prompt` style with corpus_top1.structural_invariant + tla_top1_shape's INVARIANT as conditioning
- Integration test on a single cascade.jsonl entry from puppy-raffle
- Effort: 6-8 hours

### Day 4 (Thu 2026-06-12) — DRE end-to-end
- Run mine_contest.py + structural_proposer + halmos_check.run_halmos + gauntlet on DRE
- Score output against Sherlock #1 answer key
- Effort: 4-6 hours

### Day 5 (Fri 2026-06-13) — HARD CUTOFF + measurement
- If structural_proposer produced ≥1 lead matching Sherlock #1 mechanism: H8 holds. Paper sequence proceeds (week 2).
- If structural_proposer produced zero relevant leads: H8 falsified on DRE. PIVOT TO PAPER. Write the falsification result honestly into Section 7. Days 6-12 become paper writing with original "comparable to Slither" framing.
- If structural_proposer isn't running by EOD: KILL THE BUILD. Revert to paper. No "I just need one more day."

## Week 2 — Days 6-12 (2026-06-14 → 2026-06-20): paper writeup

If H8 holds: paper uses H8 measured result as the headline finding ("structural-proposer beats sol_intent by X recall delta on DRE"). Sections 2-6 written in interview mode.

If H8 falsified: paper uses original baseline-comparable framing. Sections 2-6 written in interview mode.

Either way, **the paper has measured results to anchor every claim.**

## Week 3 — Days 13-18 (2026-06-21 → 2026-06-26): arXiv + SHSU + Secureum

- Day 13: arXiv submission + Zenodo dual-post
- Day 14-15: SHSU walk-in (CS + Math depts), endorsement outreach to Dr. Islam / Dr. Chapman / Mom warm intro
- Day 16-17: Cyfrin Updraft if time
- Day 18: register Secureum RACE; wait for Sherlock judging
- **Hard rule:** no new project directories. The "build something while waiting" urge is the pattern firing.

---

## Old Week 1 (DEPRECATED — preserved below for reference only)

The original Week 1 plan (arXiv writeup days 1-7) is preserved below. Don't follow it. The revised plan above is the active discipline.

### Day 2 (Tue 2026-06-10) — Baseline comparison: Slither + pact-Halmos vs plumbline

**Why this matters:** The paper's strongest reviewer-facing question is "is plumbline better than existing tools?" Today's measurement of plumbline's absolute numbers (P=0.38, R=0.73, F1=0.49 across N=85 reps) is meaningless without a comparison baseline. Slither is the universal baseline; Halmos is the symbolic-execution baseline. Both run against the same 7 corpora plumbline already scored.

**Scope (effective):** 7 unique projects, all with .ANSWERS.md ground truth — puppy-raffle, t-swap, thunder-loan, boss-bridge, sequence, synthetic-dreusd (x3 variants), DRE Sherlock 1259.

**Concrete steps (estimated 4-6 hours focused work):**

1. **Install Slither** (10 min):
   ```bash
   pip install slither-analyzer
   slither --version
   ```

2. **Author tools/compare_baselines.py** (1 hour) — reads reps.jsonl, extracts unique contract paths, runs Slither on each contract, parses Slither JSON output into a findings list, scores against .ANSWERS.md using the same sol_match scorer plumbline uses for itself, records per-project P/R. Same pattern as tools/measure_reps.py just shipped today.

3. **Run it:**
   ```bash
   python3 tools/compare_baselines.py --tool slither --out runs/2026-06-10-baselines/slither.jsonl
   python3 tools/measure_reps.py --reps runs/2026-06-10-baselines/slither.jsonl
   ```

4. **Stretch: same for Halmos** (3-4 hours) — pact already has halmos_check.py. Wire it through the same harness. May hit solc-version friction; document and skip if blocked.

5. **Output for the paper:** a single markdown table for paper Section 4:

   | Tool | N | Precision | Recall | F1 |
   |---|---|---|---|---|
   | Slither | 7 | ? | ? | ? |
   | Halmos | 7 | ? | ? | ? |
   | Plumbline (sol_intent) | 7 | 0.38 | 0.73 | 0.49 |
   | Plumbline (manual) | 3 | 0.67 | 0.51 | 0.58 |

6. **Honest reporting:** publish whichever direction the numbers fall. If plumbline loses on some, that goes in Section 5 (Limitations). If it wins on some, that's Section 4 (Contribution).

**Done criterion:** runs/2026-06-10-baselines/slither.jsonl exists; the comparison table is committed to the paper draft as Section 4.X "Comparison to baselines."

### Day 3-6 (Wed-Sun) — Paper sections

**Goal:** Post to arXiv (cs.SE or cs.CR) by end of day 7.

**Title (working):** "From TLA+ Counterexample to Foundry Exploit: A
Verifier-Discharged Pipeline for Smart-Contract Auditing"

**Existing material to lean on:**
- `docs/research/IMMUNEFI_STRATEGY.md` — the universal PoC quality bar
- `templates/foundry_poc/_universal.t.sol.template` — the universal template
- `tools/manifests/_README.md` — the manifest schema
- `tools/manifest_lint.py`, `tools/trace_to_forge.py`, `tools/manifest_from_poc.py`
- `reps.jsonl` — 88 reps of measured outcomes
- Sherlock 1259 issues #1 (first-depositor inflation) and #2 (paused-distributor)
  as case studies
- `docs/tla/PausedDistributorPricingAsymmetry.tla` — TLA+ counterexample case

**4-6 page structure:**
1. Motivation (1 page) — current state of audit-assist tooling; the "TLA+ →
   forge PoC" gap; why universal templates beat per-shape codegen.
2. Pipeline architecture (1.5 pages) — diagram + section per stage:
   TLA+ shape → manifest → universal template emit → manifest_lint static + run.
3. Case studies (1.5 pages) — Sherlock #1 (first-depositor inflation) and #2
   (paused-distributor pricing asymmetry). Show: TLA+ INVARIANT statement →
   counterexample trace → manifest → forge PASS.
4. Footgun catalog (0.5 page) — vm.prank consumption, pragma drift,
   extra_imports, forge_root resolution. Each one cost real session time;
   each is now lint-caught.
5. Limitations (0.5 page) — verifier-discharge is only as honest as the TLA+
   abstraction; LLM authoring of shapes is fluency-shaped not soundness-shaped;
   precision/recall numbers from reps.jsonl with confidence intervals.
6. Related work (0.5 page) — Halmos, Slither, TraceFix, LTLGuard, Cyfrin
   Updraft tooling.

**Day-by-day:**
- Day 1 (today): outline + Section 1 motivation draft
- Day 2: Section 2 pipeline architecture + figure
- Day 3: Section 3 case study #1 (first-depositor inflation)
- Day 4: Section 3 case study #2 (paused-distributor)
- Day 5: Sections 4-5 (footguns + limitations)
- Day 6: Section 6 related work + bibliography + cleanup
- Day 7: arXiv submission

**Done criterion:** the paper has a DOI / arXiv ID by 2026-06-15 23:59.
External graded by reviewers/readers.

---

## Week 2 — Days 8-14 (2026-06-16 → 2026-06-22): Cyfrin Updraft

**Goal:** Complete the smart-contract security curriculum, earn the badge.

**Why:** External pass/fail. Tightly maps to the work JH wants to do. Engages
the brain that loves failure-mode hunting. Costs $0.

**Mechanics:**
- 2 hours/day minimum on https://updraft.cyfrin.io
- Complete in order: Solidity Smart Contract Development → Smart Contract
  Security → Smart Contract Devops
- Hit every quiz checkpoint. Don't skip.
- Submit course completion for verifiable certificate.

**Done criterion:** Cyfrin badge URL pasted at the bottom of this file by
2026-06-22 23:59.

---

## Week 3 — Days 15-21 (2026-06-23 → 2026-06-29): Sherlock judging + sit-still

**This week is mostly waiting.** Sherlock 1259 judging happens this week.
That's the yes/no on issues #1 and #2.

**The only allowed work:**
- Register for the next Secureum RACE (https://secureum.xyz) — quarterly,
  multiple-choice, brutal, externally graded.
- Light: 1 paper/day from arXiv security-adjacent.
- NOTHING ELSE. No new projects. No "while I wait let me build X."

**Done criterion:** Survived the wait without starting a new project.
Sherlock judging results received. Next-bet decision made FROM EVIDENCE
(validated findings vs not), not from new architecture.

---

## Daily session checklist — read this every time

When opening Claude in any plumbline-related session:

1. **Read this file first.** Top to bottom.
2. **Read yesterday's CURRICULUM.md delta** (the "Yesterday I did X" log below).
3. **State today's intended task.** It MUST be from the current week's section.
4. **If tempted to start something new:** the answer is no. Point to the
   current week's task. Re-read the Hard Rules.
5. **End of session:** append one line to the Daily Log below.

---

## Daily Log (append-only — do not rewrite past entries)

| Date | Day | Worked on | Outcome | Notes |
|------|-----|-----------|---------|-------|
| 2026-06-09 | 1 | (a) Stop the bleed: 4 cron loops killed, autopay off, curriculum written. (b) arXiv Section 1 motivation, 5 paragraphs (~900 words) via interview mode. (c) Section 7 future-work note capturing the computational-material program. | DONE — exceeded Day 1 target | Bleed: Anthropic balance −$2.84; routines + GHA workflows disabled. Writeup: structural hypothesis → computational material → trust question → tool → division of labor. JH directed shapes; Claude transcribed; JH on mobile in interview mode. Commits: 8167633, 1dc52ee, 0f26be8. |

---

## When this curriculum ends (2026-06-27)

Open this file. Read the Daily Log. Read the Sherlock judging results.
Re-evaluate. Write the next curriculum from evidence. Or write none and
take a week off. Either is allowed. **What's not allowed is starting a
new architecture project on day 19 to escape the result.**
