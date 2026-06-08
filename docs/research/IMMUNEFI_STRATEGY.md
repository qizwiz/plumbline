# Deep-research synthesis: Immunefi strategy for plumbline

Source: deep-research workflow 2026-06-08, 109 subagents, 4.2M tokens.
113 claims extracted → 25 adversarially verified → **19 confirmed (3-0), 6 killed.**

Adversarial verification matters here: SIX claims were refuted that would
have been load-bearing if I'd taken them at face value. Notably the
"contractual SLAs of 48h/14d/14d" and the "5 reports per 48h rate limit"
both got killed (0-3 and 1-2). Don't act on them.

## Headline

**Immunefi is structurally different from Code4rena/Sherlock.** It's a
winner-take-all continuous bug bounty, not a ranked-share contest. The
verified data tells a specific story:

| dimension | finding | confidence |
|---|---|---|
| Submission format | 7-section markdown into dashboard form | 3-0 |
| Severity scale | **4-tier V2.3** (not 5-tier — research question was wrong) | 3-0 |
| PoC requirement | Runnable Foundry/Hardhat against local fork ONLY | 3-0 |
| Median Critical payout | **$20,000** (mean $114k, heavy-tailed) | 3-0 |
| First-reporter-wins | Duplicates earn zero; placeholders prohibited | 3-0 |
| No-Fix-No-Pay | 4 legit close reasons including "decides not to fix" | 3-0 |

The honest read: **plumbline-quality detection is necessary but not
sufficient** on Immunefi. Speed + completeness + first-mover advantage
on the right asset matter as much as the finding quality.

## 1. Submission format (7-section markdown)

Verified primary sources (3-0):
- https://immunefisupport.zendesk.com/hc/en-us/articles/12435277406481-Bug-Report-Template
- https://immunefi.com/blog/security-guides/how-to-submit-bug-reports-that-get-paid/
- https://immunefisupport.zendesk.com/hc/en-us/articles/4812946166801-Bug-Report-Submission-Form

The dashboard form has these required sections (markdown-rendered):

```
Title
Bug Description
  - Brief / Intro
  - Details
Impact
Risk Breakdown
Recommendation
References
Proof of Concept
```

**Each section must be filled in its own field on the dashboard form.**
Lumping into Bug Description, or putting PoC code outside the PoC field,
explicitly causes the report to not be escalated.

### Form mechanics (3-0 verified)

Beyond the markdown sections, the form requires:

- **Program**: dropdown selection AND retyping the program name as redundant confirmation
- **Asset**: dropdown of codebase URLs from the program scope. "Other" is allowed but **rejection-likely unless the finding is direct loss of funds**.
- **Impacts**: select one or more from the program's enumerated "Impacts In Scope" list. **No custom impacts.** Severity is the HIGHEST selected impact's tier.
- Selecting out-of-scope impacts is typical-rejection-cause.

Implication for plumbline: the JSON schema must constrain `program`,
`asset`, and `impacts` to enumerated values pulled from the target
program's bounty page at submission time — not free text.

## 2. Severity: V2.3 = 4-tier, by impact-type

Verified primary source (3-0):
- https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3/

**Important correction**: the research question assumed V2.2's 5-tier
scale (Critical/High/Medium/Low/None). V2.3 is **4-tier**:

| tier |
|---|
| Critical |
| High |
| Medium |
| Low |

There is no "None". Severity is set by **impact-type criteria** across
three category tables (Blockchain/DLT, Smart Contracts, Websites and
Apps). The V2.3 spec itself does NOT define USD thresholds — monetary
caps are **program-specific** and applied after classification.

### Smart Contract Critical impacts (enumerated)

For plumbline's smart-contract focus, V2.3 Critical for Smart Contracts is:

1. Direct theft of user funds
2. Direct NFT theft
3. Permanent freezing of funds/NFTs
4. Governance manipulation
5. Manipulable RNG
6. Unauthorized NFT minting
7. Unintended NFT alteration
8. Protocol insolvency

### Mapping plumbline's 9 TLA+ FailureMode shapes to V2.3 Smart Contract impacts

| FailureMode shape | Most likely Critical impact |
|---|---|
| SignatureReplay | Direct theft of user funds |
| PartialSignatureReplay | Direct theft of user funds |
| CrossWalletSigReplay | Direct theft of user funds |
| ReentrancyDrain | Direct theft of user funds OR Protocol insolvency |
| ERC4337StaticSigDoS | Direct theft of user funds (DoS on validation) |
| Uint64FeeOverflow | Protocol insolvency OR Unauthorized mint |
| Create2NonIdempotent | Permanent freezing of funds |
| FlagBypassesValidationChain | Direct theft of user funds |
| MissingAwait | (impact-type depends on context; case-by-case) |

This mapping is good news for plumbline: 8 of 9 shapes plant cleanly in
V2.3 Critical impact buckets. The shapes ARE the language Immunefi reasons
about, not orthogonal to it.

## 3. PoC: runnable Foundry/Hardhat on local fork — or auto-reject

Verified (3-0) primary sources:
- https://immunefisupport.zendesk.com/hc/en-us/articles/12435277406481-Bug-Report-Template
- https://immunefisupport.zendesk.com/hc/en-us/articles/15427337783057-Bug-Report-Submission-Checklist
- https://github.com/immunefi-team/forge-poc-templates (485★, last push 2025-03-31)
- https://immunefi.com/blog/security-guides/immunefi-poc-templates/

Hard rules:

- **MUST be**: Hardhat or Foundry test file, OR an attack contract
- **MUST NOT be**: a list of steps, pseudo-code, screenshots, the
  project's own contracts, or a unit test
- **MUST NOT touch**: mainnet or public testnet —
  **live-network exploitation triggers immediate permanent ban**
- **Canonical approach**: forking mainnet locally via Foundry/Hardhat

Their PoC template repo at github.com/immunefi-team/forge-poc-templates
covers:
- Reentrancy
- Flash Loan
- Price Manipulation
- Sandwich attacks
- Boilerplate + oracle mocks

Refuted (0-3) — do NOT rely on these:
- That PoCs **must** extend a base `PoC` contract with a `snapshot()` modifier — this is recommended scaffolding, NOT mandatory structure.
- That Foundry is **the canonical** framework — Foundry templates exist but Hardhat is also acceptable.

### Implication for plumbline

Today: plumbline's TLC counterexample is a state trace, not a Foundry
test. Bridging requires a `tlc_trace → forge test` translator. This is
the missing layer if we want to target Immunefi at scale.

For tomorrow's Sherlock contest, this also matters — Sherlock contests
typically require Foundry PoCs for High/Medium. The translator is a
**Sherlock-tomorrow asset, not just Immunefi-someday**.

Suggested artifact (not yet built): `tools/tlc_to_forge.py` that takes
a TLC `.trace` output + the matched FailureMode spec, emits a Solidity
test file. The 9 shapes are finite — a shape-by-shape template approach
is tractable.

## 4. Payout reality (sobering)

Verified (3-0) primary sources:
- https://immunefi.com/blog/research/nearly-every-long-running-bug-bounty-program-on-immunefi-has-found-a-critical-bug/
- https://mitchellamador.com/p/94-of-long-running-bug-bounty-programs

| stat | value | source |
|---|---|---|
| Median Critical bounty | **$20,000** | Immunefi research blog |
| Mean Critical bounty | $114,355 | (heavy-tailed by Wormhole-class outliers) |
| Total paid Jan 2021–Feb 2026 | $107.3M across 593 programs | Immunefi research blog |
| Rate of Critical among confirmed reports | ~1 in 5 | Immunefi research blog |
| P(program has ≥1 Critical, by age) | 1y: 61.4% / 3y: 87.2% / 5y: 93.9% | Immunefi research blog |
| Fraction of active programs surfacing ≥1 Critical/year | ~50% | Immunefi research blog |

**Caveat (verified in adversarial pass)**: this data is **Immunefi
self-reported** via their own blog + the CEO's personal newsletter. No
independent third-party dataset exists. Treat as platform-marketing-adjacent;
Immunefi has reputational stake in accuracy but no audit trail.

### Realistic EV for solo whitehat

Median, not mean, is the planning number. **$20,000 per Critical** is the
honest expected value per accepted Critical.

Apply haircuts:
- Duplicate rate (first-reporter-wins): plumbline-shape findings against
  mature programs likely face HIGHER duplicate risk because the shape
  vocabulary is well-known.
- No-Fix-No-Pay rate: legitimately closed reports earn zero, including
  "project decides not to fix" — this is in the verified close-reasons list.
- Out-of-scope-impact rejection: structurally unavoidable per
  V2.3-by-impact-type rules — if your shape's impact isn't in the program's
  enumerated list, the report can't be filed.

A conservative model: $20k × 0.5 (accepted) × 0.7 (not duplicate) × 0.9
(survives no-fix-no-pay) ≈ **$6,300 per submitted Critical**.

## 5. The "first complete report" rule

Verified (3-0) primary sources:
- https://immunefisupport.zendesk.com/hc/en-us/articles/7789428643217-Bug-Bounty-Program-and-Report-FAQs
- https://immunefisupport.zendesk.com/hc/en-us/articles/22617181023889

Hard rules:

- **Only the first COMPLETE report wins**. Duplicates earn zero, regardless
  of time elapsed.
- **Partial/placeholder submissions are PROHIBITED** and do NOT reserve
  first-reporter status.
- Projects can legitimately close without payment for exactly four
  reasons:
  1. Duplicate of a previously-reported (but pending) report
  2. Known issue (with proof)
  3. Non-security issue (e.g., UI bug)
  4. Project decides not to fix it
- **No-Fix-No-Pay**: payment is contingent on a fix landing. Any subsequent
  fix (including non-code mitigation) re-triggers obligation and is
  mediation-eligible.

### Strategic implication

Speed AND completeness on first submission both matter enormously:

- **Speed**: duplicate risk = total payout loss. Plumbline's TLC discharge
  is a competitive advantage here because the shapes are pre-verified.
- **Completeness**: placeholder submissions are explicitly prohibited.
  Can't reserve priority while finishing the PoC.

The honest comparison: **tomorrow's Sherlock contest is a much more
controlled EV proposition than Immunefi's winner-take-all race against
unknown competing whitehats.**

## 6. Refuted claims — do NOT rely on these

These all failed adversarial verification. Listed explicitly so we
don't accidentally cite them:

| claim | vote |
|---|---|
| "PoCs must extend a base `PoC` contract with `snapshot()` modifier" | 0-3 |
| "Bug Report Template has General/Program Questions/Bug Report Creation/PoC/Post-Submission structure" | 1-2 |
| "Foundry is THE canonical PoC framework" | 0-3 |
| "94% of 5+ yr programs have ≥1 confirmed Critical" (vs ~94% verified weaker) | 1-2 |
| "5 reports per 48h rate limit, immutable" | 1-2 |
| "Contractual SLAs: 48h ack / 14d decision / 14d payout" | 0-3 |

**Particularly relevant**: SLAs and rate limits are NOT verified.
Timing expectations should not be operationally planned around.

## 7. Open questions (NOT answered by this research)

These were in the original question but did NOT survive verification:

1. **Top-5 programs by plumbline shape coverage** with current bounty
   caps. Needs a fresh pass scraping `immunefi.com/explore` against the
   9 FailureMode shapes. The verified findings DO say Wormhole, Sky
   (MakerDAO), Lido, ERC4337 community, and 593 total programs exist,
   but the matching exercise wasn't done in this pass.

2. **KYC reality for non-US wallets**. The verified claim set is silent
   on this. Important operational question for solo audit.

3. **Empirical triage/decision/payout time distribution**. The
   contractual-SLA claim was REFUTED (0-3). Public disclosure feed could
   be scraped but wasn't.

4. **Honest EV/hour vs contests**. Would need: rejection rate, duplicate
   rate, no-fix-no-pay rate. None of these survived verification.

The Top-5 programs question is the most action-relevant gap. Suggest
a follow-up workflow run **specifically** scoped to scrape
`immunefi.com/explore` + program bounty pages, ranking by:
- in-scope impacts overlap with plumbline's 9 shapes
- bounty cap × probability-of-Critical × age-of-program
- KYC + payout-wallet requirements

## 8. Shipped artifacts

| Artifact | Path | Purpose |
|---|---|---|
| This research synthesis | `docs/research/IMMUNEFI_STRATEGY.md` | Citations + honest scope |
| JSON Schema | `schemas/immunefi_submission.json` | Validates one Immunefi submission |
| Jinja2 template | `templates/immunefi_submission.j2` | Markdown for the 7-section form |
| Platform notes update | `templates/PLATFORM_NOTES.md` (Immunefi section) | Per-platform render path |

## 9. Honest strategy for plumbline

**For tomorrow (Sherlock)**: Immunefi research does NOT directly help.
But the **tlc_to_forge translator** is a Sherlock-tomorrow asset too,
because both platforms require runnable PoCs. Build the smallest version
for at least ONE shape (suggest: SignatureReplay since it's most reused).

**For Immunefi as longer-term play**: the platform structurally favors
- Speed (first-complete-wins)
- Completeness (no placeholders)
- Impact-vocabulary fit (your finding's impact must be in the program's enumerated list)

Plumbline's TLC discharge is real competitive advantage for speed (shapes
pre-verified) and completeness (counterexample is the PoC seed). But:
- The tlc_to_forge gap is real
- The duplicate risk against an experienced field is real
- The "decides not to fix" close reason is real

**Honest EV claim**: Sherlock contests probably dominate per-hour for
solo whitehat at plumbline's current shape inventory, UNTIL the tlc_to_forge
translator + a verified program-shortlist pass exist. After both, Immunefi
becomes plausibly comparable or better.

## Citations

- [Immunefi Bug Report Template](https://immunefisupport.zendesk.com/hc/en-us/articles/12435277406481-Bug-Report-Template)
- [Immunefi VSCSv2.3](https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3/)
- [Bug Report Submission Form](https://immunefisupport.zendesk.com/hc/en-us/articles/4812946166801-Bug-Report-Submission-Form)
- [Bug Report Submission Checklist](https://immunefisupport.zendesk.com/hc/en-us/articles/15427337783057-Bug-Report-Submission-Checklist)
- [PoC Guidelines](https://immunefisupport.zendesk.com/hc/en-us/articles/9946217628561-Proof-of-Concept-PoC-Guidelines-and-Rules)
- [forge-poc-templates repo](https://github.com/immunefi-team/forge-poc-templates)
- [Immunefi-published Critical-bug research](https://immunefi.com/blog/research/nearly-every-long-running-bug-bounty-program-on-immunefi-has-found-a-critical-bug/)
- [Immunefi CEO 94% post (Mitchell Amador)](https://mitchellamador.com/p/94-of-long-running-bug-bounty-programs)
- [Bug Bounty Program FAQ](https://immunefisupport.zendesk.com/hc/en-us/articles/7789428643217-Bug-Bounty-Program-and-Report-FAQs)

## Honest scope

- **What this research answered (3-0 verified)**: submission format,
  V2.3 severity scale + smart-contract Critical impacts enumeration,
  PoC requirements + canonical tooling, payout stats (median $20k),
  first-complete-report-wins rule.
- **What it did NOT answer (failed verification or absent from sources)**:
  top-5 program shortlist, KYC reality, empirical timing distributions,
  rate limits, contractual SLAs, true EV/hour vs contests with all haircuts.
- **What is shipped**: docs + schema + Jinja2 template ready for one
  submission. The translator from plumbline output → Foundry test is
  NOT in this batch.
