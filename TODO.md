# Plumbline TODO — weekend + ongoing

Tracks the work in flight as of 2026-06-06 02:50. The in-session task
list (TaskCreate) duplicates the top items; this file is the durable
copy that survives session restarts.

## Saturday morning (read + sanity-check)
- [ ] **T1**: Read LTLGuard (arxiv 2603.05728); notes → `docs/research/ltlguard-notes.md`. The precedent before authoring more TLA+.
- [ ] **T10**: Walkthrough with JH of pact's TLA+ + spec_learner + gen_tlc_model discipline. Output → `docs/adr/ADR-005-pact-tla-discipline-port.md`. *Blocked on JH availability.*
- [ ] **T2**: Start codespace; `python tools/spec_retrieval.py build`; verify 3 nearest-neighbor queries land on expected precedents.

## Saturday afternoon (the second FailureMode — tests retrieval is real)
- [ ] **T3**: Author `M02_ERC4337StaticSigDoS.tla` with `MissingAwait.tla` as retrieved few-shot context. TLC → counterexample → matches `examples/sequence/.ANSWERS.md` M-02. *Blocks T6.*
- [ ] **T6**: Author 3rd–5th FailureMode TLA+ modules; each verified by TLC. Candidates: H-1 puppy reentrancy, H-3 puppy uint64 overflow, H-2 sequence partial replay, M-04 sequence Factory.deploy non-idempotent.

## Sunday (measurement + publishable gaps)
- [ ] **T5**: Marginal recall: slither vs +halmos vs +TLC vs +sol_intent on 5 corpora. Output → `docs/research/marginal-recall-2026-06.md`. Publishable benchmark gap #1.
- [ ] **T11**: sol_intent ensemble 3× per corpus; μ ± σ + union-of-leads recall. ~$5 LLM. The contest-readiness headline metric.
- [ ] **T4**: Reframe `ml_zoo` classifier as verifier-router; output classes `{slither_will_catch, halmos_will_decide, tlc_will_decide, human_only}`. Retrain on existing 41 reps with hand-labeled routing labels.

## Sunday evening / week (architecture deepening)
- [ ] **T8**: Wire `llguidance` or XGrammar for constrained TLA+ decoding. Lark grammar from tlaplus VS Code extension. Measure V-syntax pre/post per LTLGuard's framing.
- [ ] **T12**: Write Solidity→TLA+ pipeline as `docs/research/solidity-to-tla-pipeline.md`. Publishable benchmark gap #2. Depends on T3, T6, T5.

## Ongoing / hygiene
- [ ] **T13**: Verify cloud GH Actions loop is still alive; set `HF_TOKEN` as Actions secret if missing.
- [ ] **T7**: Push `reps.jsonl`, retrieval corpus, classifier model to HuggingFace as durable artifacts. Use existing `hf_mirror.py`; wire into cloud workflow.
- [ ] **T14**: Build `docs/CONTEST_RUNBOOK.md`. The exact keyboard sequence JH executes when contest scope drops.
- [ ] **T9**: Calibration drill (human vs model on identical corpus). *Blocked on JH executing it.*

## Backlog / nice-to-have
- [ ] Read Steenhoek et al. ICSE 2023 (arxiv 2212.08109) — the OOD warning paper. Cross-check our verifier-router framing against their reproducibility results.
- [ ] Vendor Apalache too (alternate TLA+ model checker; faster on unbounded state).
- [ ] Track which retrieval queries return weak similarity → that's a signal for "we need a new FailureMode class here."
- [ ] Per-FailureMode README files documenting bug shape + the specific Solidity contracts that exhibit it (cross-reference back to `examples/<corpus>/.ANSWERS.md`).

## Decisions parked for review
- **Apalache vs TLC.** Currently using TLC (pact convention, simpler bounded models). Revisit if model state space explodes on multi-actor TLA+ specs (e.g. ERC-4337 with N bundlers + M users).
- **Constrained decoding library.** llguidance has Lark grammar support natively; XGrammar has 100x speedup on CFG via context-independent/dependent partitioning. Pick after T8 prototyping.
- **NCA proper vs GAT proxy.** ARCHITECTURE §3 says "frame as NCA, build as GAT for now." Revisit when corpus is large enough to train a real iterative-diffusion model.

## Use what we have — JH's reminder

- **Codespace** (`organic-dollop-9qjvgq9pp39xpr`) for: any heavy compute (sol_intent runs, TLC verification, classifier training), any work that benefits from the pre-built venv + Foundry + halmos + tla2tools.
- **HuggingFace** (qizwiz account) for: durable storage of reps.jsonl, the TLA+ corpus, the classifier model, eventually the verified-spec dataset for the community. Survives any local disk crisis.
- **GH Actions cloud loop** (`.github/workflows/loop.yml`) for: hands-off iteration when scope changes. Push to a watched path → reps + classifier + maybe-prompt-rewrite land back on `main`.
