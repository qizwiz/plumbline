"""
flywheel — the closed self-improving loop. One command. Every component.

This is the loop the session has been pointing at all night:

  1. PROPOSE       sol_intent --recall on each corpus (LLM)
  2. SCORE         sol_match against .ANSWERS.md (deterministic)
  3. LOG           append-only reps.jsonl
  4. RETRAIN       lead_classifier on the accumulated corpus (no LLM)
  5. IMPROVE       prompt_improve.improve_if_weak (LLM, only when grounded
                   score < THRESHOLD; sees the actual misses as transcript)
  6. REPEAT

The grounded gradient is sol_match's score per corpus. The LLM stays out of
the scoring (deterministic), out of the classifier (embedding + sklearn),
and only enters proposing + prompt-rewriting. That's "ML loop with minimal
LLM input."

GOALS (realistic, but lofty — measured per iteration vs the starting point
2026-06-06: 40 reps, classifier ROC-AUC 0.73±0.23, sequence recall 0.60±0.08,
sequence precision 0.25±0.09):

  After 5 iterations (~25 reps each, ~$5 each):
    REALISTIC
      [ ] reps.jsonl >= 100 rows                    (currently ~40)
      [ ] Cyfrin corpora recall μ >= 0.85            (currently 0.80-0.86 single-shot)
    LOFTY
      [ ] classifier ROC-AUC >= 0.80, σ <= 0.10      (currently 0.73 ± 0.23)
      [ ] sequence (novel) recall μ >= 0.70          (currently 0.60 ± 0.08)
      [ ] sequence precision μ >= 0.35               (currently 0.25 ± 0.09)

  After 10 iterations:
    LOFTY
      [ ] reps.jsonl >= 200 rows
      [ ] classifier ROC-AUC >= 0.85, σ <= 0.07
      [ ] sequence recall μ >= 0.75, σ <= 0.05
      [ ] sequence precision μ >= 0.40
      [ ] prompt rewrites converge (≤ 2-3 total across all iterations)

  CONTEST DAY TARGET:
      Mean recall on truly novel post-cutoff code >= 0.70 with 3-run ensemble
      gives ~85% effective bug coverage. That's a competitive baseline for
      a contest where typical winners catch 50-70% of findings.

Usage:
  python flywheel.py                 # one full iteration on all corpora
  python flywheel.py --iters 5       # 5 iterations
  python flywheel.py --corpora examples/sequence examples/puppy-raffle
                                     # restrict to specific corpora
  python flywheel.py --no-improve    # skip prompt_improve step (saves LLM)
  python flywheel.py --no-retrain    # skip classifier retrain
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

PY = sys.executable  # works in codespace AND in GH Actions runners
REPS = os.path.join(HERE, "reps.jsonl")

# All curated corpora. Each must have .ANSWERS.md.
DEFAULT_CORPORA = [
    "examples/puppy-raffle",
    "examples/t-swap",
    "examples/thunder-loan",
    "examples/boss-bridge",
    "examples/sequence",      # the novel post-cutoff corpus
]

# If per-corpus grounded score (recall in --recall mode) is below this,
# prompt_improve is given the missed-findings transcript and rewrites
# prompts/sol_find.md.
WEAK_RECALL_THRESHOLD = 0.50


def _load_reps() -> list[dict]:
    if not os.path.isfile(REPS):
        return []
    return [json.loads(l) for l in open(REPS) if l.strip()]


def _summarize(rows: list[dict], filter_fn=None) -> dict:
    rs = [r for r in rows if filter_fn(r)] if filter_fn else rows
    if not rs:
        return {"n": 0}
    rec = [r["score"].get("recall") for r in rs if r["score"].get("recall") is not None]
    prec = [r["score"].get("precision") for r in rs if r["score"].get("precision") is not None]
    sd = lambda xs: statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {
        "n": len(rs),
        "recall_mean": statistics.mean(rec) if rec else None,
        "recall_sd": sd(rec) if rec else None,
        "precision_mean": statistics.mean(prec) if prec else None,
        "precision_sd": sd(prec) if prec else None,
    }


def _run_one_rep(corpus: str, recall_mode: bool = True) -> dict | None:
    args = [PY, "model_rep.py"]
    if recall_mode:
        args.append("--recall")
    args.append(corpus)
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True, timeout=1500)
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        sys.stderr.write(f"[rep parse failed] {corpus}: {line[:200]}\n")
        return None


def _retrain() -> dict:
    proc = subprocess.run(
        [PY, os.path.join(HERE, "tools/lead_classifier.py"), "train"],
        cwd=HERE, capture_output=True, text=True, timeout=300,
    )
    return {
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-15:],
    }


def _maybe_improve(per_corpus_recall: dict[str, float]) -> dict:
    """If any corpus's recall is below WEAK_RECALL_THRESHOLD, call
    prompt_improve with a transcript of the misses. Returns whether
    a rewrite happened."""
    weakest = min(per_corpus_recall.items(), key=lambda kv: kv[1]) if per_corpus_recall else None
    if not weakest or weakest[1] >= WEAK_RECALL_THRESHOLD:
        return {"improved": False, "weakest": weakest}

    corpus, recall = weakest
    transcript = (
        f"Corpus {corpus}: grounded recall {recall:.2f} below threshold "
        f"{WEAK_RECALL_THRESHOLD}. The prompt at prompts/sol_find.md needs to "
        f"do better here. The missed findings are at {corpus}/.ANSWERS.md. "
        f"Rewrite the prompt to better surface this style of finding."
    )

    try:
        import prompt_improve as pi
        import invariant_agent as agent

        def _ask(p):
            return agent._ask(p, 8000)

        improved = pi.improve_if_weak("sol_find", recall, transcript, _ask)
        return {"improved": bool(improved), "weakest": weakest}
    except Exception as e:
        return {"improved": False, "weakest": weakest, "error": str(e)}


def iteration(corpora: list[str], do_improve: bool, do_retrain: bool) -> dict:
    """One full sweep through all corpora + retrain + maybe improve."""
    t0 = time.time()
    print(f"\n=== iteration  corpora={len(corpora)}  improve={do_improve}  retrain={do_retrain} ===")
    per_corpus = {}
    for c in corpora:
        rep = _run_one_rep(c)
        if rep is None:
            continue
        rec = rep.get("recall")
        prec = rep.get("precision")
        per_corpus[c] = rec
        print(f"  {c:36s}  recall={rec}  precision={prec}  leads={rep.get('n_leads')}")

    out: dict = {"per_corpus_recall": per_corpus, "duration_s": 0}

    if do_retrain:
        print("  retraining classifier...")
        out["retrain"] = _retrain()
        for line in out["retrain"]["stdout_tail"]:
            print(f"    {line}")

    if do_improve:
        print("  checking if prompt_improve fires...")
        out["improve"] = _maybe_improve(per_corpus)
        print(f"    improved={out['improve']['improved']}  weakest={out['improve'].get('weakest')}")

    out["duration_s"] = round(time.time() - t0, 1)
    return out


def _goals_snapshot() -> None:
    rows = _load_reps()
    print(f"\n=== STATE  ({len(rows)} reps in reps.jsonl) ===")
    cyfrin = ["puppy-raffle", "t-swap", "thunder-loan", "boss-bridge"]
    for c in cyfrin:
        s = _summarize(rows, lambda r: r.get("contract", {}).get("path", "").endswith(c)
                       and r.get("proposer", {}).get("kind") == "sol_intent")
        if s["n"]:
            print(f"  {c:14s} n={s['n']:2d}  recall μ={s['recall_mean']:.2f}±{s['recall_sd']:.2f}  "
                  f"precision μ={s['precision_mean']:.2f}±{s['precision_sd']:.2f}")
    s = _summarize(rows, lambda r: r.get("contract", {}).get("path", "").endswith("sequence")
                   and r.get("proposer", {}).get("mode") == "recall"
                   and not r.get("proposer", {}).get("classifier_filter"))
    if s["n"]:
        print(f"  sequence(rec)  n={s['n']:2d}  recall μ={s['recall_mean']:.2f}±{s['recall_sd']:.2f}  "
              f"precision μ={s['precision_mean']:.2f}±{s['precision_sd']:.2f}")


def main():
    args = sys.argv[1:]
    iters = 1
    if "--iters" in args:
        iters = int(args[args.index("--iters") + 1])
    corpora = DEFAULT_CORPORA
    if "--corpora" in args:
        i = args.index("--corpora") + 1
        corpora = []
        while i < len(args) and not args[i].startswith("--"):
            corpora.append(args[i]); i += 1
    do_improve = "--no-improve" not in args
    do_retrain = "--no-retrain" not in args

    print(f"flywheel: {iters} iter(s), {len(corpora)} corpus(a), improve={do_improve}, retrain={do_retrain}")
    _goals_snapshot()

    for i in range(1, iters + 1):
        print(f"\n--- iteration {i}/{iters} ---")
        result = iteration(corpora, do_improve, do_retrain)
        print(f"  duration: {result['duration_s']}s")

    _goals_snapshot()


if __name__ == "__main__":
    main()
