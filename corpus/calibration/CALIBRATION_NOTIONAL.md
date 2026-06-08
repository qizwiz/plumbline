# Calibration: plumbline RAG corpus vs Notional Exponent (Sherlock contest, July 2025)

## Source

- **Contest**: github.com/sherlock-audit/2025-06-notional-exponent
- **Judging repo**: github.com/sherlock-audit/2025-06-notional-exponent-judging
- **Final report PDF**: `2025.06 Notional Exponent Audit Report.pdf` (in judging repo)
- **Date audited**: July 2 - July 18, 2025
- **Scope**: 54 Solidity files (~384KB) across src/

## Ground truth

Parsed from the PDF via pdftotext (strip form-feed page-break chars):

- **11 High** + **26 Medium** = **37 graded H/M findings**

Saved to `corpus/calibration/notional-ground-truth.jsonl` (one JSON per line).

## What this calibration measures

**NOT** "did plumbline find these bugs." That requires running sol_intent on the source (LLM spend, deferred).

**INSTEAD**: does plumbline's 1240-finding RAG corpus contain semantic priors for these real bugs? This is the RAG availability baseline — it bounds the best sol_intent could do given perfect detection-of-prior.

Method: for each ground-truth finding title, embed via bge-small-en-v1.5 with identifier-lifting, find the nearest neighbor in the 1240-finding index, measure cosine similarity. Threshold cos>0.7 considered "semantically reachable prior."

## Result: 32/37 = 86.5% corpus coverage

| Severity | Total | cos>0.7 | Coverage |
|----------|-------|---------|----------|
| High | 11 | 11 | **100%** |
| Medium | 26 | 21 | 80.8% |
| **Total** | **37** | **32** | **86.5%** |

Every High finding has a strong semantic prior in the corpus. Mediums miss 5 of 26 at the cos>0.7 threshold.

## Where the corpus has gaps

The 5 ground-truth findings with no strong RAG prior (cos<0.7):

| ID | Title (truncated) | Top-1 match | cos |
|---|---|---|---|
| M-1 | Hard-Coded Mainnet WETH Address Breaks | EIP712 incorrect | 0.691 |
| M-8 | Emission rewards keep accruing | Emission schedule not followed | 0.694 |
| M-17 | User unable to migrate edge case | Cannot unstake from YieldETHStakingEtherfi | 0.673 |
| M-22 | Setup with asset=WETH and Curve | Flashlender#flashLoan mintProfit | 0.664 |
| M-24 | Convex cannot be configured | Vault.claimRewards Convex changes op | 0.685 |

These are all protocol-integration-specific edge cases (chain-specific addresses, emission schedules, migration paths, integration setup, Convex specifics). Not generic bug classes — they require domain knowledge of the specific integrations.

## Honest interpretation

**What this number means:**
- The corpus contains rich semantic priors for high-impact bug classes.
- All 11 Highs are reachable; the RAG context could surface relevant prior art to sol_intent.
- This is a **necessary** condition for recall, not a sufficient one. Coverage is a ceiling, not a measurement.

**What this number does NOT mean:**
- It does NOT mean plumbline would have detected 86.5% of these findings on this contest.
- It does NOT mean sol_intent + RAG produces useful leads on the actual source.
- It does NOT account for false positives / noise.
- The matches found are thematic, not mechanical (e.g., H-1 "cross-contract reentrancy" matched to a "reentrancy if recipient malicious" prior — same class, different mechanism).

## Next step (deferred for budget)

Run sol_intent on the actual Notional source (~$5-6 estimated for 54 files at current pricing). Compare its produced leads to ground truth. Real recall number.

```bash
cd ~/src/plumbline
python tools/sol_intent.py corpus/calibration/notional-source/notional-v4/src \
    --hybrid-rag --output leads.jsonl
python tools/sol_score.py leads.jsonl corpus/calibration/notional-ground-truth.jsonl
```

## Honest scope

This calibration measures ONE platform (Sherlock), ONE contest (Notional Exponent, July 2025), corpus baseline. It's a sample of 1 contest. Not a generalization to "plumbline catches 86% of Sherlock bugs." Run on 5-10 more past contests to make the number robust.

**It IS:** the first time plumbline's corpus has been graded against external ground truth. Previous numbers (0.42 cold sol_intent recall on examples/sequence) were self-graded against own .ANSWERS.md.
