# Morning Brief — 2026-06-06 ~04:30

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

### ⚠️ Honest gap
- **T19**: retrieval recall is imperfect — "missing await coroutine" query did NOT return MissingAwait in top-5. The bge-small-en-v1.5 embedder lacks bug-shape vocabulary and clusters all specs in a ~0.12 cos range. Workaround used overnight: hand-pick a second precedent when authoring. Longer-term fix: hybrid BM25+dense, or a domain-tuned embedder.

### 🛑 Waiting on you
- **T10**: Saturday walkthrough of pact's TLA+/spec_learner/gen_tlc_model discipline. Cheap for you (~30 min); unlocks the full Solidity port without me inventing parallel conventions that drift.
- **T9**: calibration drill — cold-audit one corpus (suggest **sequence** — it's the truly novel one), write to `examples/sequence/MY_FINDINGS.md`, run `tools/manual_rep.py`. The diff between your recall and the model's on identical ground truth is the only honest signal for 90%-plumbline on contest day.
- **T13**: set HF_TOKEN as a GH Actions secret (if not already) so the HF mirror step in the cloud workflow can fire.

## Commit log overnight (latest first)
```
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
- T16 done; T8 (constrained decoding) is next on the substrate path but it needs llguidance OR XGrammar wired to an actual LLM call — first such spend would burn API tokens, so I'll NOT execute T8 autonomously. Instead, scheduling toward T14 (contest-day runbook, zero spend) and T15 (slither on the 5 corpora — gives us the T5 baseline at $0).

## Task list at this moment
- ✅ T1, T2, T3, T6, T16, T18 complete (6 tasks closed overnight)
- ⏸️ T4-T5, T7-T15, T17 pending — see TODO.md for full plan
- ⛔ T8 paused — needs JH approval before LLM spend
- 🆕 T19 — retrieval embedder gap, investigation-track

## Honest cost ledger overnight
- $0 spent on LLM API. All work was reading (WebFetch), file edits, local TLC, codespace compute that's already paid for.

---
*This file rewritten on every overnight pulse. If you see this with "no new commits today," I either hit a blocker I couldn't get past, or I drifted and the meta-loop didn't catch me. The git log is the audit.*
