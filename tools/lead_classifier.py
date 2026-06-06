"""
lead_classifier — small supervised classifier on lead-text → P(real bug).

Trained on reps.jsonl: every historical lead, with a binary label derived
from sol_match (did it match a ground-truth finding?). No LLM in the
training loop. Embeddings come from fastembed (same model sol_match uses,
so the geometry already lives in venv).

Pipeline:
  python tools/lead_classifier.py train   # fits + saves to tools/lead_classifier.pkl
  python tools/lead_classifier.py predict "lead text here"
                                          # prints P(real)

Use as a post-filter on sol_intent output: drop leads with P(real) < threshold.
This raises precision without an extra LLM call — the noise leads have a
distinguishable embedding profile from real findings.

Honest scope: this is a *first viable* classifier. ~300 historical leads,
class-imbalanced. Treat the threshold as something to tune against held-out
reps (or, soon, against the precision number on the next sequence rep).
"""
from __future__ import annotations

import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import sol_match
import rep_log  # noqa: F401  (ensures the import path is intact)

REP_LOG = os.path.join(HERE, "reps.jsonl")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "lead_classifier.pkl")


def build_dataset() -> tuple[list[str], list[int]]:
    """For every historical sol_intent rep with a ground-truth file, re-run
    sol_match to get lead-level labels (lead_hit[j] = did lead j match some
    finding?). Return (lead_texts, labels)."""
    if not os.path.isfile(REP_LOG):
        raise FileNotFoundError(REP_LOG)

    leads_out: list[str] = []
    labels_out: list[int] = []

    for line in open(REP_LOG, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        kind = r.get("proposer", {}).get("kind")
        if kind != "sol_intent":
            continue
        truth_path = r.get("ground_truth_path")
        leads = r.get("leads") or []
        if not truth_path or not leads:
            continue
        if not os.path.isfile(truth_path):
            continue

        findings = sol_match._lines(truth_path)
        score = sol_match.match(leads, findings, threshold=0.80)
        # `pairs` is per-finding; reconstruct per-lead by checking lead_hit
        # via the matched-to-lead mapping in pairs[].
        lead_hit = [False] * len(leads)
        for finding, lead_text, _score, ok, _reason in score["pairs"]:
            if not ok:
                continue
            try:
                j = leads.index(lead_text)
            except ValueError:
                continue
            lead_hit[j] = True

        for lead, hit in zip(leads, lead_hit):
            leads_out.append(lead)
            labels_out.append(1 if hit else 0)

    return leads_out, labels_out


def train():
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        import numpy as np
    except ImportError:
        print("install: pip install scikit-learn")
        sys.exit(1)

    leads, labels = build_dataset()
    n = len(leads)
    n_pos = sum(labels)
    print(f"dataset: {n} leads  positive={n_pos}  negative={n - n_pos}")
    if n < 30:
        print("WARNING: dataset is small; classifier will be unstable")
    if n_pos < 5 or (n - n_pos) < 5:
        print("ERROR: too few examples in at least one class")
        sys.exit(1)

    # Embed via the same fastembed model sol_match uses (geometry is shared).
    X = sol_match._embed(leads)
    y = np.array(labels)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")

    # Cross-val for an honest estimate of generalization
    cv_scores = cross_val_score(clf, X, y, cv=min(5, n_pos, n - n_pos),
                                scoring="roc_auc")
    print(f"5-fold ROC-AUC: μ={cv_scores.mean():.3f}  σ={cv_scores.std():.3f}")

    clf.fit(X, y)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    print(f"saved → {MODEL_PATH}")

    # Also dump a quick threshold sweep on the training set so we have a
    # starting point for the --filter threshold
    probs = clf.predict_proba(X)[:, 1]
    print("\nthreshold sweep (training-set, for sanity only):")
    for t in [0.30, 0.40, 0.50, 0.60, 0.70]:
        keep = probs >= t
        if keep.sum() == 0:
            continue
        prec = (y[keep].sum() / keep.sum()) if keep.sum() else 0.0
        rec = (y[keep].sum() / y.sum()) if y.sum() else 0.0
        print(f"  t={t:.2f}  kept={int(keep.sum()):3d}/{n}  "
              f"precision={prec:.2f}  recall={rec:.2f}")


def predict(leads: list[str]) -> list[float]:
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(
            f"no classifier at {MODEL_PATH} — run: python tools/lead_classifier.py train"
        )
    with open(MODEL_PATH, "rb") as f:
        clf = pickle.load(f)
    X = sol_match._embed(leads)
    return clf.predict_proba(X)[:, 1].tolist()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "train":
        train()
    elif cmd == "predict":
        leads = sys.argv[2:]
        if not leads:
            print("usage: predict <lead text>...")
            sys.exit(1)
        probs = predict(leads)
        for l, p in zip(leads, probs):
            print(f"{p:.3f}  {l[:80]}")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
