# Morning Brief — 2026-06-06 ~05:30

For when JH wakes. Updated continuously by overnight pulses.

## TL;DR

**Five Solidity FailureModes now exist (was one) and four cover distinct bug-class shapes.** Corpus grew 10 → 13 specs. Every spec TLC-discharged with counterexample matching its `.ANSWERS.md` entry. Zero LLM-API spend overnight.

### ✅ Wins overnight
- **T1 (LTLGuard read)**: complete. `docs/research/ltlguard-notes.md`. Headline: 14B open model + constrained decoding + retrieval-augmented few-shot hits 75-78% semantic on nl2spec hard, no fine-tuning. **V6 (no grammar in prompt) ≥ V7 (everything)** — confirms our "prosthesis not prompting" principle.
- **T2 (retrieval index built and tested)**: complete with caveats. 10 → 13 specs in corpus now (framework modules filtered out automatically). Atomic-proposition lifting works on Solidity + Python identifiers. 2-of-3 verification queries returned expected precedent in top-5.
- **T3 (M-02 ERC4337StaticSigDoS)**: ✅ TLC-verified. Counterexample at state 2: c1 → ViaEntryPoint → reverted. Matches `examples/sequence/.ANSWERS.md` M-02 exactly. Few-shot context: SignatureReplay (retrieved, cos=0.585) + MissingAwait (hand-picked).
- **T6 (3rd–5th FailureModes)**: ✅ all three landed.
  - **H-1 ReentrancyDrain** (puppy-raffle) — Live→Calling→Cleared lifecycle. Counterexample: ReenterBuggy in the Calling window drives paid=2*TicketPrice.
  - **H-3 Uint64FeeOverflow** (puppy-raffle) — narrow-accumulator mod-wrap. Counterexample at state 4: actual=12, tracked=2 (wrap modulo MaxValue=10).
  - **M-04 Create2NonIdempotent** (sequence) — same salt, two calls, two outcomes (Deployed then Reverted). Bundler/relayer crash captured.
- **T16 (TLA+ Lark grammar)**: ✅ vendored. `grammar/tla_failuremode.lark` validated against all 5 specs (5/5 PASS via `tools/validate_tla_grammar.py`). Covers the structural form (module header, sections, definitions, expressions, temporal ops, fairness, bulleted conjunctions, primed names). T8 (constrained decoding) is now unblocked — the grammar is the S lever per LTLGuard (V3 → 15.7%, V4 → 87.1% syntactic validity).
- **T14 (contest-day runbook)**: ✅ `docs/CONTEST_RUNBOOK.md`. 8-line TL;DR + 8 sections (pre-contest, scope-drop, baselines, TLA+ match with bug-class lookup table, mechanical verify, submission, triage under time pressure, troubleshooting, post-contest). Every command verified to exist in the repo. Two appendices document what the runbook deliberately doesn't do + memory of past mistakes (halmos `--ast` requirement, oracle-silently-broken episode).
- **T12 (Solidity→TLA+ pipeline note)**: ✅ `docs/research/solidity-to-tla-pipeline.md`. Arxiv-shaped working note. 8 sections: abstract, problem, architecture diagram, bug-class taxonomy table, engineering findings (including honest report of embedder-discrimination gap), NOT-scope (not slither/halmos replacement, not CA system yet), future work, reproducibility. Frames the LTLGuard-shaped pipeline as substrate for the CA work, not a replacement.
- **T4 (verifier-router ADR)**: ✅ `docs/adr/ADR-006-verifier-router.md`. Reframes ml_classifier from binary-confidence to multi-class router. Labels: `{slither_will_catch, halmos_will_decide, tlc_will_decide, human_only}`. Key insight: classifier outputs work-allocation, not truth — verifiers remain the soundness layer, so OOD mis-routing only costs runs, never causes missed bugs. Includes 5-step implementation plan (schema change → relabel → multi-class trainer → inference → wire-up). Steps 1-4 self-contained; step 5 waits on T15 marginal-recall data.

### ⚠️ Honest gap
- **T19**: retrieval recall is imperfect — "missing await coroutine" query did NOT return MissingAwait in top-5. The bge-small-en-v1.5 embedder lacks bug-shape vocabulary and clusters all specs in a ~0.12 cos range. Workaround used overnight: hand-pick a second precedent when authoring. Longer-term fix: hybrid BM25+dense, or a domain-tuned embedder.

### 🛑 Waiting on you
- **T10**: Saturday walkthrough of pact's TLA+/spec_learner/gen_tlc_model discipline. Cheap for you (~30 min); unlocks the full Solidity port without me inventing parallel conventions that drift.
- **T9**: calibration drill — cold-audit one corpus (suggest **sequence** — it's the truly novel one), write to `examples/sequence/MY_FINDINGS.md`, run `tools/manual_rep.py`. The diff between your recall and the model's on identical ground truth is the only honest signal for 90%-plumbline on contest day.
- **T13**: set HF_TOKEN as a GH Actions secret (if not already) so the HF mirror step in the cloud workflow can fire.

## Commit log overnight (latest first)
```
d85afab  doc(adr): ADR-006 — reframe ml_classifier as verifier-router (T4)
450b40b  doc(research): T12 — Solidity→TLA+ pipeline note (arxiv-shaped working note)
ca85874  doc(brief): T14 done — CONTEST_RUNBOOK.md landed
c15de79  doc(contest): T14 — CONTEST_RUNBOOK.md, the keyboard sequence for scope-drop day
c7c3508  doc(brief): T16 done — Lark grammar 5/5 PASS, T8 unblocked
963ec17  feat(grammar): T16 — vendor minimal Lark CFG for plumbline TLA+ subset
e882903  doc(brief): T3 + T6 complete — 5 FailureModes verified overnight
1d91373  feat(tla): M-04 Create2NonIdempotent — fifth FailureMode, TLC-verified
29cd349  feat(tla): H-3 Uint64FeeOverflow — fourth FailureMode, TLC-verified
2fb1803  feat(tla): H-1 ReentrancyDrain — third FailureMode, TLC-verified
ae4084a  feat(tla): M-02 ERC4337StaticSigDoS — second FailureMode, TLC-verified
a1dd2ff  fix(retrieval): require 'bug class:' marker — exclude framework modules
3b92fe0  fix(retrieval): extract focused 'bug class:' paragraph, not full header
1ccd4ad  feat(retrieval): atomic-proposition lifting per LTLGuard
f5b8d0a  doc(research): T1 done — LTLGuard pipeline notes
```

## Bug-class shapes now covered in the corpus (5 distinct)

| Shape | TLA+ module | Source bug |
|-------|-------------|------------|
| should-be-one-shot, no guard | `SignatureReplay.tla` | boss-bridge H-3 |
| should-be-one-shot, guard after external call | `ReentrancyDrain.tla` | puppy-raffle H-1 |
| caller-bound auth misreads msg.sender via EntryPoint | `ERC4337StaticSigDoS.tla` | sequence M-02 |
| narrow-accumulator truncation | `Uint64FeeOverflow.tla` | puppy-raffle H-3 |
| idempotency violation | `Create2NonIdempotent.tla` | sequence M-04 |

This is the seed library. Each addition to the corpus increases the cone of bug shapes the LLM-as-fluency-prosthesis can pattern-match against.

## What I'm doing next (and why)
- T14, T12, T4 done. Next zero-spend candidates: T17 (always-fires checklist), T13 (verify cloud loop via gh CLI). T15 requires slither which isn't local (codespace only). T8/T11 require LLM spend — paused. T9/T10 require JH directly. Scheduling toward T17 (checklist gives JH a clean status surface for any pulse) then T13 (loop-alive check).

## Task list at this moment
- ✅ T1, T2, T3, T4, T6, T12, T14, T16, T18 complete (9 tasks closed overnight)
- ⏸️ T5, T7, T13, T15, T17 pending zero-spend
- ⛔ T8, T11 paused — needs JH approval before LLM spend
- ⏸️ T9, T10 — JH directly
- 🆕 T19 — retrieval embedder gap, investigation-track

## Honest cost ledger overnight
- $0 spent on LLM API. All work was reading (WebFetch), file edits, local TLC, codespace compute that's already paid for.

---
*This file rewritten on every overnight pulse. If you see this with "no new commits today," I either hit a blocker I couldn't get past, or I drifted and the meta-loop didn't catch me. The git log is the audit.*
