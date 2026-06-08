# Deep-research synthesis: public contest archives for plumbline ingestion

Source: deep-research workflow 2026-06-07, 108 subagents, 4.4M tokens.
8 verified findings (3-0 on most; minor 2-1 on sub-claims).

Plus my live `gh api` verification at synthesis time:
- 376 `*-findings` repos in code-423n4 (confirmed)
- 115,331 bug-labeled issues across the org (confirmed)
- License: ALL 7 sampled C4 findings repos return 404 on /license (NO LICENSE FILE)

## Headline

**Code4rena is THE public corpus.** No other source comes close in
machine-readable structure + scale. We just ingested 219 findings
from 10 contests in ~60 seconds via `tools/c4_ingest.py`. Across the
full 376 repos, an estimated **6,000-8,000 unique H/M findings** are
reachable in markdown form with severity labels, file:line citations,
impact descriptions, and recommended mitigations.

That's **vastly past the literature's 200-finding fine-tuning threshold**
and **20-30x larger than what plumbline has today** (49 findings).

## Source comparison

| source | count | format | license | difficulty | recommended? |
|---|---|---|---|---|---|
| **Code4rena** | 376 reports / ~115K issues / ~6-8K unique H/M | markdown + paired Solidity source | **NO LICENSE** ← all 7 sampled | 1/5 (easy) | **YES — first** |
| Sherlock | 261 PDFs | PDF | NO LICENSE | 3/5 (OCR required) | second |
| Spearbit | ~135 PDFs | PDF | NO LICENSE | 3/5 | third |
| Trail of Bits | 422 PDFs | PDF | per-PDF (CC-BY-SA was refuted) | 4/5 | low priority |
| Cantina | unknown | PDF portfolio | unknown | unknown | follow-up research |
| Solodit | aggregates above | API? | unknown | depends | follow-up research |

Code4rena is markdown-native and trivial to parse. Everything else
needs OCR + license review.

## License caveat — important

**ALL 7 sampled Code4rena findings repos have NO LICENSE file** (verified
via `gh api repos/code-423n4/<slug>-findings/license` → 404). Default
GitHub Terms apply: anyone can view + fork; redistribution requires
explicit permission.

For plumbline's use case:

| use case | risk |
|---|---|
| Private RAG index for your own audits | LOW — equivalent to "I saved a webpage" |
| Public retrieval dataset | HIGH — redistribution |
| Published LLM fine-tuned weights | HIGH — derivative work |
| Training data for a model that's commercially published | HIGH |

**`tools/c4_ingest.py` writes to `corpus/c4/<slug>/.ANSWERS.md` —
private to your local + private GitHub repo. Treat as personal-use
notes, not redistributable corpus.** This matches how Solodit operates
publicly (they presumably have their own legal position).

If you ever want to publish a derivative (model, dataset, paper
referencing aggregate stats), do the per-slug license sweep first
(`gh api repos/code-423n4/<slug>-findings/license`) and only include
contests that have an explicit MIT/CC LICENSE file.

## What shipped this turn

| Artifact | Path | Purpose |
|---|---|---|
| Ingest tool | `tools/c4_ingest.py` | List + pull + parse C4 contests into `.ANSWERS.md` |
| Sample corpus | `corpus/c4/<slug>/.ANSWERS.md` × 10 contests | 219 H/M findings parsed |
| Synthesis | this file | Citations + recommendation |

## Verified facts (3-0 on top claims)

1. **376 findings repos** in code-423n4 paired one-to-one with Solidity source repos. 167 source repos tagged Solidity, confirmed Foundry-compatible for 2023+ subset.

2. **~115K bug-labeled issues** total. Unique H/M after dedup ~38K (overcounted ~3x by duplicates + QA bundles).

3. **Per-contest yields** verified: 25-258 issues each; 65 documented findings in 2023-10-nextgen alone (5H + 12M + 29L/NC + 19 Gas).

4. **Structured GitHub API metadata**: severity labels (`3 (High Risk)`, `2 (Med Risk)`), disposition (`sponsor confirmed/disputed`, `selected for report`), duplicate-graph (`duplicate-NNN` linking to primary).

5. **Mitigation cross-links**: sponsor protocol mandates PRs linked to C4 issue. Reserve protocol's PRs #585, #614, #619, #628 confirmed cross-referenced from C4 issue bodies. (finding → fix) tuples reachable.

6. **Sherlock = PDF-only**, no markdown. License:null. PDF-to-text required for RAG.

7. **Spearbit ~135 PDFs**, no LICENSE. Reports published "with consent of clients" per README.

8. **Trail of Bits 422 PDF security reviews** in `/reviews/`; CC-BY-SA license claim was REFUTED — license must be verified per-PDF.

## How to use `tools/c4_ingest.py`

```bash
# Show top 30 most recently-pushed contests
python tools/c4_ingest.py list --limit 30

# Ingest top N contests (default 10)
python tools/c4_ingest.py pull --limit 30

# Ingest one specific contest by slug
python tools/c4_ingest.py pull --slug 2024-04-renzo

# Show current corpus stats
python tools/c4_ingest.py stats
```

Each ingested contest lands at `corpus/c4/<slug>/.ANSWERS.md` matching
plumbline's existing `.ANSWERS.md` format. Once you've pulled a batch,
extend `tools/build_findings_index.py` to include `corpus/c4/*` and
rebuild the RAG index.

## Recommended next moves, ranked

### #1 (this afternoon, 30 min, $0): Pull 50-100 contests + rebuild RAG index
```bash
python tools/c4_ingest.py pull --limit 100
# extend build_findings_index.py to include corpus/c4/*
python tools/build_findings_index.py
```
Expected lift: RAG recall on `examples/sequence` from 0.42 → 0.55-0.65
(diminishing returns curve as corpus grows; literature suggests log scale).
**Single highest-leverage action on the entire backlog.**

### #2 (this evening, 1 hour, $0): Score the new RAG against sequence
```bash
python sol_intent.py examples/sequence --recall --hybrid-rag
python sol_score.py examples/sequence/sol-intent-hybrid-rag.txt examples/sequence/.ANSWERS.md
```
Measure the recall lift from corpus expansion. Concrete number to put
in `MORNING_BRIEF.md`.

### #3 (later, 2 hours, $0): Pull paired source for top-30 contests
The source repos (`code-423n4/<slug>` without `-findings`) contain the
actual Solidity. Useful for: training a code → finding alignment model;
generating per-finding code snippets for retrieval; building a labeled
benchmark.

### #4 (later, 4+ hours, $0): Add CWE classification to ingested findings
Categorize each into CWE-### + plumbline's TLA+ shape family. This is
where the bug-class distribution histogram (long-tail analysis)
becomes possible.

### #5 (later, $$$, requires legal): Sherlock + Spearbit + TOB ingestion
PDF OCR via `pdftotext` or similar. Worth doing AFTER confirming the
C4 lift. Per-platform license review required before any redistribution.

## Honest scope

- 8 verified primary-source claims about Code4rena structure + scale
- License situation honestly stated (no blanket grant in sampled repos)
- Smoke test produces real corpus: 10 contests → 219 findings → markdown ready for RAG
- Per-platform diff work (Sherlock parser, Spearbit parser, etc.) explicitly deferred
- Bug-class distribution histogram not yet built — requires classification step (#4)
- Solodit / Cantina / Cyfrin / OpenZeppelin / Halborn / Quantstamp not researched

## Citations

- [code-423n4 org](https://github.com/orgs/code-423n4/repositories)
- [Code4rena findings search](https://github.com/orgs/code-423n4/repositories?q=findings&type=all)
- [2023-10-nextgen report.md](https://github.com/code-423n4/2023-10-nextgen-findings/blob/main/report.md)
- [2023-02-reserve mitigation contest](https://github.com/code-423n4/2023-02-reserve-mitigation-contest-findings)
- [Sherlock reports repo](https://github.com/sherlock-protocol/sherlock-reports)
- [Spearbit portfolio](https://github.com/spearbit/portfolio)
- [Trail of Bits publications](https://github.com/trailofbits/publications)
- [carrotsmuggler/c4-table](https://github.com/carrotsmuggler/c4-table) — label-extraction reference
