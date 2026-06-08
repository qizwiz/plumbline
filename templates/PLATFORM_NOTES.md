# Per-platform notes

Diffs from the Code4rena-default `audit_report.j2` template +
`finding_block.j2`.

Verification status per platform from
`docs/research/AUDIT_REPORT_TEMPLATE_RESEARCH.md` (deep-research,
2026-06-07). Code4rena and Sherlock are well-verified; others have
acknowledged coverage gaps.

## Code4rena (DEFAULT, 3-0 verified)

Use `audit_report.j2` + `finding_block.j2` as-is.

**Critical reminders**:

- ID format: `H-NN`, `M-NN` zero-padded.
- Required per-finding triad: **Impact / Proof of Concept / Recommended Mitigation Steps**.
- **PoC must be runnable for High and Medium** submissions (Foundry diff against the project's test suite). Solo Foundry test file is acceptable. Prose-only PoC is auto-downgraded.
- Citations: `ContractName.sol#L<start>-L<end>` form, rendered as markdown link to `github.com/code-423n4/<contest-slug>/blob/<commit>/<path>#L<start>-L<end>`.
- Severity is QUALITATIVE — judges apply discretion.
- Bulk QA + Gas are submitted as **separate single reports** per warden, not individual finding-per-issue.
- Mitigation reports (post-fix) use a DIFFERENT structural template (`mitigation_report.j2`, TODO).

## Sherlock (3-0 verified for severity rubric; format is PDF not markdown)

**Format difference**: Sherlock deliverables are **PDFs**, published to `github.com/sherlock-protocol/sherlock-reports/audits/` with filename `YYYY.MM.DD - Final - <Protocol Name> Audit Report.pdf`.

**Render path**: generate markdown via `audit_report.j2`, then convert to PDF (e.g., via `pandoc` or `weasyprint`).

**Severity rubric is QUANTITATIVE and impact-only** (likelihood explicitly excluded):

- **High**: direct loss of funds without extensive external conditions AND `(users lose >1% AND >$10 of principal, yield, OR fees)`.
- **Medium**: `(>0.01% AND >$10)` OR breaks core protocol functionality.

`finding_block.j2` works but the `severity_rationale` field becomes **required** for any High. Render the rubric numbers in the rationale explicitly.

No "QA" tier — informational issues are dropped. Map plumbline's QA-tier findings to either Medium (if quantifiable) or omit.

Naming: file save as `YYYY.MM.DD - Final - <slug> Audit Report.pdf` matching the canonical naming pattern.

## Immunefi (3-0 verified for structure + V2.3 severity; see docs/research/IMMUNEFI_STRATEGY.md)

**Format**: ONE submission = ONE finding. Multi-finding report template does NOT apply. Use `templates/immunefi_submission.j2` per-finding (schema: `schemas/immunefi_submission.json`).

**7-section dashboard form (markdown-rendered, each section filled separately)**:

1. **Title**
2. **Bug Description** — with required Brief/Intro + Details subsections
3. **Impact**
4. **Risk Breakdown**
5. **Recommendation**
6. **References**
7. **Proof of Concept**

Lumping into Bug Description or putting PoC code outside the PoC field will explicitly cause the report to not be escalated (3-0 verified).

**Form mechanics**:

- `program` — dropdown selection + retype confirmation
- `asset` — codebase URL dropdown from program scope; "Other" is rejection-likely unless direct loss of funds
- `impacts` — **enumerated from program's "Impacts In Scope" list, NO custom impacts**; severity = highest selected impact's tier

**Severity is V2.3 = 4-tier** (NOT V2.2's 5-tier with "None" — research question premise was wrong):

- Critical
- High
- Medium
- Low

Set by impact-type criteria across three category tables (Blockchain/DLT, Smart Contracts, Websites and Apps). V2.3 spec does NOT define USD thresholds — monetary caps are program-specific.

**For Smart Contracts, Critical impacts (enumerated)**:

1. Direct theft of user funds
2. Direct NFT theft
3. Permanent freezing of funds/NFTs
4. Governance manipulation
5. Manipulable RNG
6. Unauthorized NFT minting
7. Unintended NFT alteration
8. Protocol insolvency

Plumbline's 9 TLA+ FailureMode shapes map cleanly onto these — see IMMUNEFI_STRATEGY.md §2.

**PoC hard rules** (3-0 verified):

- MUST be runnable Foundry/Hardhat test OR attack contract
- MUST NOT be prose, screenshots, pseudo-code, or unit tests
- MUST NOT touch mainnet or public testnet — **live exploitation = permanent ban**
- Local mainnet fork (Foundry/Hardhat) is canonical
- Official Foundry templates: github.com/immunefi-team/forge-poc-templates (485★)

**Payout reality** (3-0 verified, but Immunefi-self-reported):

- Median Critical: **$20,000**
- Mean Critical: $114k (heavy-tailed by Wormhole-class outliers)
- ~1 in 5 confirmed reports is Critical
- First COMPLETE report wins — duplicates earn zero; placeholders prohibited
- "No Fix, No Pay" — projects can legitimately close for 4 reasons including "decides not to fix"

**Refuted operational claims (do NOT plan around)**:

- Contractual SLAs of 48h ack / 14d decision / 14d payout (0-3 refuted)
- Rate limit of 5 reports per 48h (1-2 refuted)
- Mandatory `snapshot()` modifier on base PoC contract (0-3 refuted)

**Render path**:

```python
# tools/render_report.py target=immunefi → renders ONE submission per finding
# (NOT a multi-finding bundled report)
python tools/render_report.py --target immunefi --finding-id H-01 \
    --reps reps.jsonl --out submissions/wormhole-2026-06-08.md
```

**Open questions** (NOT answered in this research pass):

- Top-5 programs ranked by plumbline shape coverage
- KYC reality for non-US wallets
- Empirical timing distribution
- Honest EV/hour vs contests after all haircuts

See `docs/research/IMMUNEFI_STRATEGY.md` for citations + honest scope.

## Cantina (coverage gap)

**Known generally**:

- Hosts both contests (similar to C4) and one-off audits
- Final reports are PDFs published in their portfolio (cantina.xyz/portfolio)
- Per-finding structure observed in public reports: Title / Severity / Description / Recommendation / Status (Acknowledged / Fixed / Disputed)
- Severity tiers: Critical / High / Medium / Low / Informational

**Recommended action**: research pass on cantina.xyz/portfolio. Template likely adapts cleanly — drop QA/Gas tracks, add "Status" field to `finding.json`.

## Spearbit (coverage gap)

**Known generally**:

- Private audits with public reports on github.com/spearbit-audits/portfolio
- Markdown source + PDF render
- Per-finding: Title / Severity / Issue / Recommendation / Status
- Severity: Critical / High / Medium / Low / Informational / Gas

**Recommended action**: research pass on github.com/spearbit-audits. Add an `issue` field (their term for what C4 calls Impact + Description combined).

## Trail of Bits (coverage gap)

**Known generally**:

- Most professionally-formal; PDF deliverables in github.com/trailofbits/publications
- Report structure: Project Summary / Project Targets / Project Coverage / Findings Summary / Detailed Findings / Engagement-specific recommendations
- Per-finding: Title / Type / Severity / Difficulty / Description / Recommendation / Long-Term Recommendation
- Severity: High / Medium / Low / Informational + separately rated Difficulty (High / Medium / Low / Undetermined)
- Type taxonomy: Patching / Configuration / Cryptography / Data Validation / etc.

**Recommended action**: research pass on github.com/trailofbits/publications. The Type + Difficulty fields are unique; add to `finding.json` as platform-specific optional fields. Length is generally longer — TOB findings often run 1-2 pages each.

## Choosing a target at render time

```python
# tools/render_report.py
TARGET_PLATFORM = "code4rena"  # or "sherlock", "cantina", "spearbit", "tob"

if TARGET_PLATFORM == "code4rena":
    template = "audit_report.j2"
    output_ext = ".md"
elif TARGET_PLATFORM == "sherlock":
    template = "audit_report.j2"
    output_ext = ".pdf"  # via pandoc
    # require quantitative impact in severity_rationale
elif TARGET_PLATFORM == "tob":
    template = "tob_report.j2"  # TODO: derive after follow-up research
    # require Type + Difficulty in finding objects
```

## Honest scope of THIS template work

- Code4rena format: VERIFIED + complete.
- Sherlock severity rubric: VERIFIED; PDF render path: documented but not implemented.
- Immunefi / Cantina / Spearbit / TOB: stubs based on public knowledge; need follow-up deep-research before plumbline can target them safely.

Until those follow-up passes happen, treat the Code4rena template as plumbline's primary output. It is also serviceable for Cantina with minor adaptation (drop Gas track, add Status).
