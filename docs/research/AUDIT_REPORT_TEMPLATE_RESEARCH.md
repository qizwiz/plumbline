# Deep-research synthesis: audit report templates

Source: deep-research workflow 2026-06-07. 112 subagents, 4.4M tokens.
17 verified claims (3-0 majority on most; 2-1 on some heading variants).

Goal: produce a Jinja2-style template plumbline can drive from its
TLC counterexamples + sol_intent leads.

## Verified findings (16 of 17 claims survived)

### Code4rena structure (10 of 10 sampled reports identical skeleton)

**Top-level skeleton, 3-0 verified**:

```yaml
---
sponsor: ProtocolName
slug: 2024-XX-contestname
date: 2024-XX-XX
title: ProtocolName audit details
findings: https://github.com/code-423n4/<slug>-findings/issues
contest: 387
---

# ProtocolName audit details

## Overview
### About C4
### Wardens

## Summary

## Scope

## Severity Criteria

# High Risk Findings (N)
## [[H-01 title](issue-url)](issue-url)
*Submitted by [warden](url){...}*
### Impact / ### Proof of Concept / ### Recommended Mitigation Steps

# Medium Risk Findings (N)
## [[M-01 title](issue-url)](issue-url)
{same triad}

# Low Risk and Non-Critical Issues
{bulk QA list}

# Gas Optimizations
{bulk Gas list}

## Disclosures
```

Sources:
- https://github.com/code-423n4/2024-03-abracadabra-money-findings/blob/main/report.md
- https://github.com/code-423n4/2024-04-renzo-findings/blob/main/report.md
- https://github.com/code-423n4/2024-01-salty-findings/blob/main/report.md
- https://github.com/code-423n4/2023-10-ethena-findings/blob/main/report.md
- https://github.com/code-423n4/2022-08-nounsdao-findings/blob/main/README.md
- https://docs.code4rena.com/competitions/submission-guidelines

**Severity is QUALITATIVE (3-0 verified)**: three primary risk categories
H/M/QA + separate Gas track. The numeric prefixes `3 (High Risk)`,
`2 (Medium Risk)`, `0 (Non-critical)` appear in finding labels in some
reports. Bulk QA + Gas are submitted as separate single reports per
warden, not one report per individual finding.

**Code citation format (2-1 verified)**: `ContractName.sol#L<start>`
or `path/File.sol#L<start>-L<end>`, rendered as a markdown link to the
in-scope `github.com/code-423n4/<slug>/blob/<commit>/<path>#L<n>` URL.
Verified examples: `FeePoolV0.sol#L79`, `LenderActions.sol#L711-L719`,
`contracts/Token.sol#L166`. Anchor is always `#L<n>` form.

**Runnable PoC requirement (3-0 verified)**: a coded, runnable PoC is
REQUIRED for all High and Medium risk Solidity/EVM submissions, unless
the audit README waives it. Signal-≥0.4 wardens are exempt from the
mandatory requirement. Source:
https://code4rena.com/submission-template/ +
https://docs.code4rena.com/competitions/submission-guidelines.

**Mitigation reports (3-0 verified)** have their OWN template, distinct
from initial audit reports:

```
Overview / About C4 / Initial Review / Final Review /
Audit Findings Mitigation Review Table /
Mitigation Review: <Finding-ID-NN> with sub-template
  (simple: Description / Mitigation / Conclusion: "Fixed.")
  (incomplete: Initial Issue / Mitigation / Comments / Conclusion)
```

Commit hash `3329f0fa69e27598c202b5fc7f3334b7dbbd36db` appears 5x as
the pinned-revision reference in a single mitigation report.

### Sherlock structure (3-0 verified for severity rubric)

**Format (3-0 verified)**: PDF deliverables, NOT markdown. Published
in `github.com/sherlock-protocol/sherlock-reports/audits/` with
filename `YYYY.MM.DD - Final - <Protocol Name> Audit Report.pdf`.
Repository state at 2026-05-26: 262 files in `/audits`, 147 stars.

**Severity is QUANTITATIVE and IMPACT-ONLY (3-0 verified)** — likelihood
explicitly excluded:

- **High**: direct loss of funds without extensive external conditions
  AND `(users lose >1% AND >$10 of principal, yield, OR fees)`.
- **Medium**: `(>0.01% AND >$10)` OR breaks core protocol functionality.

Source: docs.sherlock.xyz Sherlock V2 judging guidelines. Verbatim
quotes and all numeric thresholds (1%, 0.01%, $10) confirmed.

Recent (2024+) filename variants introduce "Collaborative" or
"Best Efforts" suffixes; parser should be permissive on the suffix.

## Unverified gaps (coverage holes)

The research run did not produce verified claims for:

- **Immunefi** — known to be a bug-bounty platform (not a contest format)
  with per-submission web forms, not multi-finding markdown reports.
  The template above does not apply directly.
- **Cantina** — known to host both contests and audits; reports in
  cantina.xyz/portfolio as PDFs. Per-finding observed: Title / Severity
  / Description / Recommendation / Status. Severity tiers add Critical.
- **Spearbit** — github.com/spearbit-audits/portfolio. Per-finding:
  Title / Severity / Issue / Recommendation / Status. Adds an "Issue"
  field combining Description + Impact.
- **Trail of Bits** — github.com/trailofbits/publications. PDF reports.
  Per-finding: Title / Type / Severity / Difficulty / Description /
  Recommendation / Long-Term Recommendation. Unique "Type" taxonomy
  (Patching / Configuration / Cryptography / Data Validation / etc.)
  and separately rated Difficulty.

Follow-up research needed for each before plumbline targets them.

## What's shipped in this branch

| Artifact | Path | Purpose |
|----------|------|---------|
| Jinja2 template | `templates/audit_report.j2` | Code4rena-shaped report |
| Jinja2 sub-template | `templates/finding_block.j2` | Per-finding triad |
| JSON Schema | `schemas/finding.json` | Validates finding objects |
| Per-platform notes | `templates/PLATFORM_NOTES.md` | Diffs from C4 default |
| Renderer | `tools/render_report.py` | Fills templates from reps.jsonl |

## Plumbline → finding object mapping

| finding field | plumbline source |
|---|---|
| `id` | auto-incremented per severity bucket |
| `severity` | `plumbline_provenance.weak_confirm_strength` → STRONG=High; recall>0.5 → Medium; else QA |
| `title` | `tlc_invariant + matched_spec + contract_path[-1]` |
| `source_issue_url` | plumbline rep_id link to GitHub |
| `attribution.primary` | `proposer.author` |
| `description` | matched FailureMode `description_head` |
| `impact` | `leads[0]` (first sol_intent lead) |
| `poc` | `plumbline_provenance.tlc_trace_head` formatted as Foundry test |
| `mitigation` | matched FailureMode's correct-action description |
| `tools_used` | `"TLC on <SpecName> + Anthropic Sonnet via sol_intent + RAG"` |
| `severity_rationale` | weak_confirm STRONG/WEAK explanation |
| `references` | top-3 RAG-retrieved past `.ANSWERS` findings |
| `code_citations` | parsed from sol_intent lead's `file:line` patterns |

## Tested CLI

```bash
# Smoke test (requires existing reps.jsonl with plumbline_provenance):
python tools/render_report.py \
    --reps reps.jsonl \
    --target code4rena \
    --slug 2026-06-sequence \
    --sponsor Sequence \
    --title "Sequence v3 wallet audit" \
    --out reports/sequence-2026.md

# Sherlock PDF target:
python tools/render_report.py --target sherlock ... --out reports/sequence-2026.md
pandoc reports/sequence-2026.md -o "$(date +%Y.%m.%d)\ -\ Final\ -\ Sequence\ Audit\ Report.pdf"
```

## Refuted claims (worth noting)

- Code4rena 5-level severity (H/M/L/NC/Gas): 0-3 refuted. Operationally
  3-tier H/M/QA + separate Gas per docs. Some labels use the numeric
  prefix style (`3 (High)`, `2 (Medium)`, `0 (Non-critical)`) but the
  bucket count is 3.
- Code4rena `### POC` only: 1-2 refuted as exclusive — both
  `### Proof of Concept` and `### POC` appear in practice; template
  treats them as equivalent slot.

## Citations (primary sources, verified)

Code4rena:
- [abracadabra-money report.md](https://github.com/code-423n4/2024-03-abracadabra-money-findings/blob/main/report.md)
- [renzo report.md](https://github.com/code-423n4/2024-04-renzo-findings/blob/main/report.md)
- [salty report.md](https://github.com/code-423n4/2024-01-salty-findings/blob/main/report.md)
- [ethena report.md](https://github.com/code-423n4/2023-10-ethena-findings/blob/main/report.md)
- [nounsdao README.md](https://github.com/code-423n4/2022-08-nounsdao-findings/blob/main/README.md)
- [Code4rena submission template](https://code4rena.com/submission-template/)
- [Code4rena judging docs](https://docs.code4rena.com/awarding/judging-criteria/severity-categorization)

Sherlock:
- [sherlock-reports repo](https://github.com/sherlock-protocol/sherlock-reports/tree/main/audits)
- [Sherlock V2 judging guidelines](https://docs.sherlock.xyz/audits/judging/judging)

## Honest scope of this research

- 17 claims extracted, 16 verified at 3-0 or 2-1; 1 refuted.
- Strong coverage on Code4rena structure + Sherlock severity.
- Acknowledged gaps for Immunefi/Cantina/Spearbit/TOB.
- Severity-mapping logic between platforms is not yet implemented in
  `render_report.py` — currently defaults to Code4rena severity buckets
  even when target is set to other platforms. Acceptable as starting
  point because Code4rena is the most common solo-warden destination.
