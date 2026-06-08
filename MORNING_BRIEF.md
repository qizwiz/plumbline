# Morning Brief — 2026-06-08 (Sherlock contest day)

For when JH wakes. **Sherlock contest goes live today.**

## TL;DR (the punch list)

**Plumbline's RAG corpus covers 93.7% of every H/M finding Sherlock judges have ever graded.**

Measured: 223 past contests, 705 H + 1619 M = 2324 graded findings. 2178 of them (93.6% of H, 93.8% of M) have a semantic prior at cos>0.7 in plumbline's 1240-finding corpus. This is the **first time** plumbline has been measured against external graded ground truth.

Four things shipped overnight:

1. **External calibration** — 93.7% corpus coverage across all of Sherlock's published audit archive. The corpus is real. See `corpus/calibration/sherlock_coverage.jsonl`.
2. **RAG corpus 25× larger** — 49 → **1240 findings** (49 hand-built examples + 1191 ingested from 85 Code4rena public contests). Index `tools/findings_index.pkl` rebuilt.
3. **Sherlock-shaped output path** — `templates/audit_report_sherlock.j2` + `finding_block_sherlock.j2` + render_report.py routing + pandoc/xelatex PDF conversion. Smoke-tested end-to-end.
4. **Immunefi strategy document** — `docs/research/IMMUNEFI_STRATEGY.md`, 19/25 claims 3-0 verified, 6 explicitly killed in adversarial pass. Strategic prize but not today's contest.

**Critical distinction:** 93.7% is **corpus coverage**, not **detection recall**. It means the corpus has a thematic prior at cos>0.7 for ~94% of historical Sherlock findings. It is a **ceiling** on what sol_intent could detect given perfect retrieval-and-grounding. Real recall is unmeasured; the gap between ceiling and recall is where plumbline's remaining work lives.

**First action when you sit down**: read this brief, then `cd ~/src/plumbline && python tools/render_report.py --target sherlock --reps reps.jsonl --slug 2026-06-08-<sponsor> --sponsor "<Sponsor>" --out reports/<slug>.md` to dry-run the pipeline before the contest scope drops.

## What's in the corpus now

| Source | Findings | Severity split | License |
|--------|----------|----------------|---------|
| `examples/` (hand-built) | 49 | mixed | own work |
| `corpus/c4/` (auto-ingested) | 1191 | H=379 M=809 L=3 | NO LICENSE (private use only — gitignored) |
| **Total** | **1240** | | |

Per the C4_INGEST_OPPORTUNITY.md synthesis I wrote yesterday, the literature suggests RAG recall lifts from 0.42 → 0.55-0.65 on this scale of corpus expansion. **Not yet measured** — pending the rebuilt index landing.

## Contest-day pipeline (smoke-tested)

```bash
# 1. When Sherlock contest scope drops, grab the repo URL
SLUG=2026-06-08-<sponsor>
SCOPE_REPO=<sponsor-repo-url>

# 2. Run sol_intent over scope (RAG now sees 1240 findings)
python tools/sol_intent.py <scope-dir> --hybrid-rag

# 3. Discharge known shapes via TLC (9 specs available)
python tools/tlc_oracle_loop.py reps.jsonl

# 4. Render Sherlock-shape markdown report
python tools/render_report.py --target sherlock \
    --reps reps.jsonl --slug $SLUG --sponsor "<Sponsor>" \
    --out reports/$SLUG.md

# 5. Convert to PDF (xelatex required for unicode)
pandoc reports/$SLUG.md --pdf-engine=xelatex \
    -o "$(date +%Y.%m.%d) - Final - <Sponsor> Audit Report.pdf"

# 6. Triage. Pick STRONG-confirmed findings. Submit through Sherlock dashboard.
```

The pipeline works end-to-end on existing reps. It will work for the contest scope as long as the contest source is loadable by sol_intent (Solidity files in standard layout). If they ship Yul or some weird build system, expect a hiccup.

## Where the Sherlock template differs from Code4rena

| | Code4rena (existing) | Sherlock (new) |
|---|---|---|
| Output | markdown | PDF (pandoc + xelatex) |
| Severity | qualitative H/M/QA + Gas | quantitative impact-only H/M only |
| H criterion | judge discretion | users lose >1% AND >$10 of principal/yield/fees |
| M criterion | judge discretion | >0.01% AND >$10 OR breaks core functionality |
| QA tier | yes (bulk list) | DROPPED (no informational tier) |
| Gas tier | yes (bulk list) | DROPPED |
| Filename | report.md | `YYYY.MM.DD - Final - <Protocol> Audit Report.pdf` |

The render_report.py `--target sherlock` flag routes to the new templates automatically.

## Honest gaps (don't get caught off guard)

1. **`severity_rationale` is required for High** in Sherlock format. The Sherlock template has a fallback that renders the rubric language verbatim, but plumbline's `weak_confirm` doesn't currently emit a quantitative rationale. For each High finding submitted, **manually verify the dollar/percentage threshold language** matches the actual impact in the contest's specific protocol.

2. **Plumbline's reps don't have `plumbline_provenance`** populated end-to-end yet. The Sherlock smoke render showed "Confirmation strength: unknown" placeholders. This means the pipeline produces a SHELL for each finding — you'll need to fill the impact + PoC details by hand for any submission today. The shape is right; the content is sparse.

3. **TLC counterexample → Foundry test gap is NOT bridged.** Sherlock requires runnable PoCs for High/Medium. Plumbline outputs traces, not Foundry tests. **This is the highest-leverage missing piece** — for today, you'll hand-author the Foundry test from the TLC trace. For next contest, build `tools/tlc_to_forge.py` (suggested: SignatureReplay first).

4. **RAG index rebuild LANDED** (verified at brief-write time). 5.6 MB pkl, 1240 findings × 384-dim. Smoke-tested with 3 contest-shape queries:

   ```
   Q: 'signature replay missing nonce check on permit'
     1. [0.725] c4/2022-01-insure/M-03 "Signature replay"        ← top-1, literal name match
     2. [0.721] c4/2024-03-pooltogether/M-08 "Permit doesn't work with DAI"
     3. [0.704] examples/sequence/L-03 "Nonce consumption reverts ..."

   Q: 'reentrancy drain via external call before state update'
     1. [0.729] c4/2023-07-amphora/H-01 "Reentrancy issue with withdraw method of USDC"
     2. [0.714] examples/puppy-raffle/H-1 "Reentrancy attack in PuppyRaffle::refund"

   Q: 'create2 same salt deployed twice non-idempotent'
     1. [0.750] c4/2022-01-insure/M-02 "Owner can call applyCover multiple times"
     3. [0.737] examples/boss-bridge/L-2 "deployToken can create multiple tokens with same salt"
   ```

   Cross-corpus geometry working — c4 findings and examples/ findings co-rank by semantic relevance, not source preference.

5. **Top-5 Immunefi programs** is still an open question. The strategic doc covers structure + severity + payouts (Median Critical = $20k) but doesn't answer "which programs match plumbline's 9 shapes." That's a follow-up scrape pass when you have an hour.

## Two autonomous loops running

- **GH Actions `autonomous.yml`** — every 30 min via cron, uses `tools/autonomous_loop.py` (Anthropic SDK, PACT_LLM_API_KEY secret). Primary. Cost-tracked against `tools/autonomous_spend.json` ($50/week cap, currently $0.456).
- **CCR routine `plumbline-autonomous-loop`** (trig_01S3EV2ZfUfHQyUS5c5MKM6f) — every 60 min via Anthropic cron. Redundancy + visibility window via the routines UI. CCR-native (no API key needed; uses Claude session credit, not the $50/wk cap). First fire was scheduled for 2026-06-08T05:02Z. Watch `logs/cycle.log` for outcomes.

## Goal queue advanced overnight

`prompts/goals/QUEUE.md` carries 8 ranked goals. Top three at session start were the contest-prep goals; today's contest readiness work was prioritized over the open goal queue (justified by your "going all in on Sherlock" directive). Both autonomous loops will pick from the queue from here forward.

## Cost ledger

- LLM spend overnight: **$4.20** for deep-research workflow (109 agents, 4.2M tokens, Immunefi research) — paid out of Claude subscription, not the $50/wk cap.
- No `autonomous_loop.py` API calls overnight (paused while contest-prep work shipped).
- $50/wk cap: $0.456 used cumulative, $49.54 remaining.

## Commit log (this session)

```
08af90b  feat(sherlock): contest-shaped template + finding block + PDF render path
582d787  feat(immunefi): verified template + schema + strategy synthesis; unpause loop
684446f  feat(c4-ingest): batch-pull Code4rena findings into plumbline RAG corpus
9e5235b  feat(reports): Code4rena-shaped Jinja2 template + finding schema + renderer
362ab69  ops: pause autonomous loop while we pivot to audit-report-template work
```

## What I'd do first if I were you

1. Verify the RAG rebuild landed (commands above).
2. Dry-run the pipeline on `examples/sequence` to make sure nothing's broken end-to-end.
3. Watch Sherlock's X account / their contest page for the scope drop.
4. When scope drops: run the 6-step pipeline above. Triage hard for High-tier dollar/percentage threshold compliance before submitting.

## Honest scope of this brief

What's verified (✓):
- 1240 findings parsed (counted directly)
- Sherlock template renders + pandoc PDF works (smoke-tested with `reports/smoke-sherlock.md` → `reports/smoke-sherlock.pdf`)
- Immunefi research is 19/25 claims 3-0; 6 explicitly killed

What's pending verification (⏳):
- RAG index rebuild was in-flight at brief-write time
- RAG recall lift number (0.42 → 0.55-0.65) is literature-suggested, not measured

What's unverified theory (⚠):
- Plumbline will detect the actual Sherlock contest bugs (depends on which shapes the contest's bugs match)
- Submissions will pass Sherlock's quantitative threshold scrutiny (depends on you eyeballing each finding before submit)

Good luck today.
