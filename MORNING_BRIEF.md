# Morning Brief — 2026-06-06 ~04:00

For when JH wakes. Updated continuously by overnight pulses.

## TL;DR

Two wins, one honest gap, three things waiting on you.

### ✅ Wins overnight
- **T1 (LTLGuard read)**: complete. Notes in `docs/research/ltlguard-notes.md`. Headline: 14B open model + grammar-constrained decoding + retrieval-augmented few-shot hits 75-78% semantic accuracy on nl2spec hard — without fine-tuning. **V6 (no grammar in prompt) ≥ V7 (everything)** — confirms our "prosthesis not prompting" principle.
- **T2 (retrieval index built and tested)**: complete with caveats. 10 specs in corpus (3 framework modules filtered out automatically). Atomic-proposition lifting per LTLGuard works on both Solidity and Python identifiers. Two of three verification queries returned the expected precedent in top-5.

### ⚠️ Honest gap
- **T19 (new task)**: retrieval recall is imperfect — "missing await coroutine" query does NOT return MissingAwait in top-5. The bge-small-en-v1.5 embedder lacks bug-shape vocabulary and clusters all 10 specs in a 0.119 cos range. Workaround: hand-pick a second precedent when authoring; longer-term fix is hybrid BM25+dense or a domain-tuned embedder.

### 🛑 Waiting on you
- **T10**: Saturday walkthrough of pact's TLA+/spec_learner/gen_tlc_model discipline. Cheap for you (~30 min); unlocks the full Solidity port without me inventing parallel conventions that drift.
- **T9**: calibration drill — cold-audit one corpus (suggest sequence — it's the only truly novel one), write to `examples/sequence/MY_FINDINGS.md`, run `tools/manual_rep.py`. The diff between your recall and the model's on identical ground truth is the only honest signal for 90%-plumbline on contest day.
- **T13**: set HF_TOKEN as a GH Actions secret (if not already) so the HF mirror step in the cloud workflow can fire.

## Commit log overnight
```
3b92fe0  fix(retrieval): extract focused 'bug class:' paragraph, not full header
a1dd2ff  fix(retrieval): require 'bug class:' marker — exclude framework modules
1ccd4ad  feat(retrieval): atomic-proposition lifting per LTLGuard
f5b8d0a  doc(research): T1 done — LTLGuard pipeline notes
```

## What I'm doing next (and why)
- **T3**: author M-02 ERC4337StaticSigDoS.tla. Use SignatureReplay (top-1 for the query) + MissingAwait (hand-picked) as the few-shot context. TLC verify. If it works, second Solidity FailureMode lands and retrieval corpus compounds.

## Task list at this moment
- ✅ T1, T2, T18 complete
- 🟢 T3 in progress (M-02 authoring)
- ⏸️ T4-T17 pending — see TODO.md for full plan
- 🆕 T19 added — retrieval embedder gap, investigation-track

## Honest cost ledger overnight
- $0 spent on LLM API. All work was reading (WebFetch), file edits, local TLC, codespace compute that's already paid for.

---
*This file rewritten on every overnight pulse. If you see this with "no new commits today," I either hit a blocker I couldn't get past, or I drifted and the meta-loop didn't catch me. The git log is the audit.*
