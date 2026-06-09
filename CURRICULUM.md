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

## Week 1 — Days 1-7 (2026-06-09 → 2026-06-15): arXiv writeup

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
| 2026-06-09 | 1 | Stop the bleed: 4 cron loops killed, autopay off, curriculum written | DONE | Anthropic balance −$2.84; routines + GHA workflows disabled; 1 hour clean |

---

## When this curriculum ends (2026-06-27)

Open this file. Read the Daily Log. Read the Sherlock judging results.
Re-evaluate. Write the next curriculum from evidence. Or write none and
take a week off. Either is allowed. **What's not allowed is starting a
new architecture project on day 19 to escape the result.**
