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

## Immunefi (coverage gap — no verified primary-source claims survived)

**Known generally** (from docs at immunefi.com, NOT verified in this research batch):

- Bug bounty program (not contest); submissions go through the platform's whitehat dashboard, not as a report
- Each submission is a SINGLE finding, not a multi-finding report
- Required fields per their public templates: vulnerability classification (using their internal taxonomy), affected functions, exploit walkthrough, recommended fix
- Severity: their own 5-tier (Critical / High / Medium / Low / None)
- PoC must be runnable; rewards depend on impact disclosure quality

**Recommended action before targeting**: do a follow-up research pass specifically on Immunefi's whitehat docs + recently-disclosed reports. The structural template above won't apply; Immunefi uses a per-submission web form, not a markdown report.

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
