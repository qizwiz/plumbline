# Contest-Day Runbook

The keyboard sequence when scope drops. Written for JH; written assuming he's tired, the timer is running, and Claude isn't watching.

Every command in this file has been verified to exist in the repo (T14 verification 2026-06-06). If a command doesn't behave as described, the runbook is wrong — file an issue rather than improvise.

---

## ⚡ TL;DR — the 8-line play

```bash
# 1. Clone the target scope into examples/
git clone <contest-repo-url> examples/<contest-name>

# 2. Sanity-baseline: slither, free, fast
slither examples/<contest-name> 2>&1 | tee examples/<contest-name>/slither.txt

# 3. sol_intent recall pass (LLM-driven, costs ~$1-2)
python sol_intent.py examples/<contest-name> --recall \
    | tee examples/<contest-name>/leads.txt

# 4. sol_match: score leads vs ANY ground-truth-shaped seeds you have
python sol_match.py examples/<contest-name>/leads.txt <seeds.txt> 0.65

# 5. sol_verify: discharge what we can mechanically
python sol_verify.py examples/<contest-name>

# 6. Triage: open `leads.txt`, the slither output, and CONFIRMED set
#    side-by-side. Promote the union to candidate submissions.

# 7. For each candidate that's a structural-fit for one of our 5
#    TLA+ FailureModes, write the spec; run TLC; submission cites
#    the counterexample.

# 8. Submit, log a rep, push.
```

---

## Section 0 — Pre-contest (1 day before)

These steps want to be done BEFORE the clock starts. They're the "load the gun" steps.

### 0.1 — Confirm cloud loop is alive

```bash
gh run list --workflow loop.yml --limit 5
```

Expect: a recent green run. If red, see § Troubleshooting / cloud loop dead.

### 0.2 — Codespace warm

The local Python env is for grammar + TLC. The codespace is for `sol_intent` / `sol_match` / `model_rep` (anything that imports `fastembed` or `anthropic`).

```bash
gh codespace list
# pick the plumbline codespace; if stale, recreate:
gh codespace create -R qizwiz/plumbline -m premiumLinux
```

### 0.3 — Confirm secrets

```bash
gh secret list -R qizwiz/plumbline
# expect at minimum: ANTHROPIC_API_KEY, HF_TOKEN (per T13)
```

If a secret is missing, set it before scope drops. Setting it during the contest costs real-time minutes.

### 0.4 — Spec-retrieval index built

In codespace:
```bash
python tools/spec_retrieval.py build
python tools/spec_retrieval.py query "reentrancy external call before state update" 5
```

Expect: at least one of our 5 TLA+ specs in top-5. If not, see § Troubleshooting / retrieval is silent.

---

## Section 1 — Scope drops

### 1.1 — Pull the target

```bash
cd ~/src/plumbline
git clone <contest-repo-url> examples/<contest-name>
# IMPORTANT: do NOT add an .ANSWERS.md yourself yet — that contaminates
# any later calibration drill on this corpus.
```

### 1.2 — Take a deliberate 5 minutes BEFORE running anything

Open `README.md` and `scope.md` if the contest provides one. Note:
- the in-scope files
- the out-of-scope files (false-positive trap if you flag these)
- declared assumptions (these are the model's hardest blind spots)
- prize-pool weighting (high/med/low — drives your triage priority)

This 5 minutes is the highest-leverage time you'll spend.

---

## Section 2 — Baselines (run all three in parallel)

These three baselines give you the lower bound on findings and orient triage.

### 2.1 — slither (free, ~1 min)

```bash
slither examples/<contest-name> 2>&1 \
  | tee examples/<contest-name>/slither.txt
```

Slither catches the boilerplate (re-entrancy, ERC-20 missing checks, uninit storage). It is high precision on its known patterns and **near-zero recall on novel logic bugs**. Use it as a noise floor: anything slither flags is a candidate; anything it misses is the interesting half.

### 2.2 — sol_intent (LLM, ~$1-2, ~5 min)

```bash
python sol_intent.py examples/<contest-name> --recall \
  | tee examples/<contest-name>/leads.txt
```

The `--recall` flag uses `prompts/sol_find.md` instead of `prompts/sol_intent.md` — recall-biased, more leads, lower precision per lead. Right for a contest where missing a high-severity bug costs more than triaging extra noise.

Cost guardrail: a single run on a ~5KB contract is ~$1-2. If the target is 50+ files, budget ~$5-10 per run.

### 2.3 — Optional: sol_intent ensemble (3 runs, ~$5)

Per T11: variance closure via ensemble.

```bash
for i in 1 2 3; do
  python sol_intent.py examples/<contest-name> --recall \
    > examples/<contest-name>/leads-${i}.txt
done
# union of leads
cat examples/<contest-name>/leads-*.txt \
  | sort -u \
  > examples/<contest-name>/leads-union.txt
```

Use the union as the candidate set for the next stage.

---

## Section 3 — TLA+ FailureMode match

For each candidate lead, ask: **is this a structural fit for one of our 5 verified FailureModes?**

```bash
# Quick retrieval:
python tools/spec_retrieval.py query "<short description of lead>" 5
```

If a TLA+ FailureMode matches structurally (cosine ≥ ~0.55 + manual sanity-check), instantiate it:

1. Copy the matched `.tla` to `docs/tla/<contest-name>-<finding-id>.tla`
2. Rewrite CONSTANTS/VARIABLES for THIS finding's shape
3. Run TLC:
   ```bash
   cd docs/tla
   java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
     -config <contest-name>-<finding-id>.cfg \
     -deadlock <contest-name>-<finding-id>
   ```
4. If TLC reports the invariant VIOLATED, the counterexample IS the submission's proof. Quote it verbatim in the submission body.

### Bug-class → FailureMode lookup table

| Lead description shape | Matches | Lift from |
|------------------------|---------|-----------|
| signature accepted multiple times, no nonce | should-be-one-shot-no-guard | `docs/tla/SignatureReplay.tla` |
| external call before state update, attacker re-enters | should-be-one-shot-guard-misplaced | `docs/tla/ReentrancyDrain.tla` |
| msg.sender check fails when called via EntryPoint / relayer | caller-bound-auth-misreads-msg-sender | `docs/tla/ERC4337StaticSigDoS.tla` |
| accumulator declared narrower than its true range | narrow-accumulator-truncation | `docs/tla/Uint64FeeOverflow.tla` |
| deploy/initialize reverts on second call to same target | idempotency-violation | `docs/tla/Create2NonIdempotent.tla` |

If the lead matches NONE of these shapes, it's a NEW bug-class. Don't force a fit. Either:
- write a new TLA+ FailureMode (~30 min) and add to the retrieval corpus, or
- submit it without TLA+ backing (the verbal mechanism in the lead has to carry the submission)

---

## Section 4 — Mechanical verification (where possible)

### 4.1 — sol_verify (halmos-backed conservation check)

```bash
python sol_verify.py examples/<contest-name>
```

What it does: for each candidate lead matching the conservation-invariant shape, calls halmos with a generated check. Stamps each as CONFIRMED or escalated.

Per CLAUDE.md: this is the trust-kernel layer — if it says CONFIRMED, the finding has a halmos discharge. **A CONFIRMED finding outweighs a verbose narrative one.** Lead with these in the submission.

### 4.2 — halmos directly (when sol_verify isn't applicable)

```bash
forge build --ast
halmos --contract <ContractName> --function <fn>
```

For property tests:
```bash
halmos --contract <ContractName> --function check_<property>
```

Caveat from memory `project_pact_halmos_oracle_broken.md`: ALWAYS pass `--ast` to forge first, or halmos silently runs stale artifacts.

---

## Section 5 — Submission

For each CONFIRMED candidate:

### 5.1 — Write the submission

Use the contest's template. Always include:
- **Title** (≤ 80 chars, mechanism in title not symptoms)
- **Severity** (use `severity.py` to sanity-check your call)
- **Vulnerability detail** (the mechanism — what makes it fire)
- **Impact** (what attacker gets / what victim loses; in real units)
- **Proof of Concept** (either a Foundry test, or the TLC counterexample, or halmos output — never just prose)
- **Recommended mitigation** (specific code change, not "use a library")

### 5.2 — Log the rep

```bash
python tools/manual_rep.py examples/<contest-name>
# generates a rep with proposer.kind=manual, author=JH
```

This adds to `reps.jsonl` and is what the cloud loop will eventually consume to improve the system.

### 5.3 — Push the work

```bash
git add examples/<contest-name>/ reps.jsonl docs/tla/<contest-name>-*.{tla,cfg}
git commit -m "feat(contest): <contest-name> findings + TLA+ specs"
git push origin main
```

The cloud loop picks this up automatically on next pulse (per T13).

---

## Section 6 — Triage when time pressure hits

Contest clock is running, you have N candidates and time for ⌈N/2⌉. Prioritize:

1. **CONFIRMED by sol_verify or halmos** — these are the closest to free submissions
2. **TLA+ counterexample exists** — high-credibility, clear submission shape
3. **Slither + sol_intent both flagged same area** — corroborated, lower noise risk
4. **Sole flag, no corroboration, no mechanical discharge** — last priority; risk of triage waste

For each you DROP, log the reason in `examples/<contest-name>/triage-skipped.md`. This is how next contest's runbook gets smarter.

---

## Section 7 — Troubleshooting

### cloud loop dead

```bash
gh run list --workflow loop.yml --limit 5
# pick the latest red, get its log:
gh run view <run-id> --log
```

Common causes (from memory):
- `GITHUB_TOKEN` lacks contents:write — see workflow `permissions:` block
- `.venv/bin/python` doesn't exist on runner — `model_rep.py` and `flywheel.py` should use `sys.executable`
- HF_TOKEN expired — refresh from `huggingface.co/settings/tokens`

### retrieval is silent / returns weak matches

If `spec_retrieval.py query` returns cos < 0.45 for everything: the corpus doesn't have a structural neighbor for this contest's bug shape. That's a SIGNAL — not a tool failure. It means this contest has a NEW class. Write a new TLA+ FailureMode for it; do not force the closest existing match.

(T19 tracks the deeper embedder discrimination gap. As of 2026-06-06 the corpus has 13 specs and 5 distinct shapes.)

### sol_intent costs spike

Symptoms: a single run costs > $5. Causes:
- Target has many large files (Solidity in `node_modules/` or `lib/`)
- `--recall` was passed on a target that's already large

Mitigation: pre-trim with `find examples/<contest-name>/src -name '*.sol'` and pass a narrowed file-list; or run on subdirectories.

### TLC counterexample doesn't match the reported bug shape

The TLA+ spec is wrong, not the contest. Revisit the spec: is the buggy action capturing the actual mechanism, or a similar-looking one? When in doubt, compare side-by-side with the `<Correct>` action defined in the same module.

---

## Section 8 — Post-contest

Within 24 hours of the contest closing:

1. Pull the contest's published findings list
2. Diff against `examples/<contest-name>/MY_FINDINGS.md` + `leads.txt`
3. Score:
   ```bash
   python sol_score.py examples/<contest-name>/leads.txt \
     examples/<contest-name>/published-findings.txt
   ```
4. Update `examples/<contest-name>/.ANSWERS.md` with the verified findings (this contest becomes a future calibration corpus)
5. For each MISSED HIGH/MED:
   - Was it a known bug-shape we don't have a TLA+ spec for? → Write the spec.
   - Was sol_intent's recall too low? → Improve the recall prompt; rerun the cloud loop on the existing corpora.
   - Was it slither-only? → That's fine; slither stays in the runbook.

Each post-contest cycle should add at least one new FailureMode to the corpus or fix at least one prompt regression.

---

## Appendix A — Things this runbook deliberately doesn't do

- **No autonomous prompt rewriting.** `prompt_improve.py` exists, but rewriting prompts mid-contest is high-variance. Save it for between-contest cycles.
- **No constrained-decoding (T8).** Not wired yet. The retrieval+TLC stack is sufficient for the first contests; T8 is a precision-boost for later.
- **No sol_z3 in the canonical path.** It's experimental; the conservation-flow runs through halmos.
- **No Lean discharge in the canonical path.** Lean is the trust kernel for the *pact* commercial product, separate from the contest path. Stays in the wings.

---

## Appendix B — Memory of past mistakes (so we don't repeat them)

From the project memory:

- ALWAYS use `--ast` with `forge build` before halmos (else halmos silently runs stale artifacts and reports a fake-PASS).
- pact's verifiable findings overlap with bandit/semgrep (commodity); the differentiated path is Django/interproc — same for plumbline, the differentiated path is the TLA+/halmos hybrid, not the LLM-only lead generation.
- "PROVED" claims are only as good as the invariant is faithful to the contract's actual promise.
- The halmos oracle has been silently broken before. ALWAYS confirm the verifier actually RAN your target before trusting its output. Check the counterexample file timestamp.

---

*Maintained as part of T14. Last verified 2026-06-06. If a command in this file fails, fix the runbook or the command — don't improvise.*
