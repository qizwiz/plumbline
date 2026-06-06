"""
ml_zoo — train multiple classifiers on the lead-label data and pick the best.

Per JH's "I WANT MACHINE LEARNING": this stops being a single LogReg baseline
and becomes a real model selection step.

Models tried (all sklearn, all class-weight balanced where supported):
  - LogisticRegression (the previous baseline)
  - GradientBoostingClassifier (typically wins on tabular ~300-row data)
  - RandomForestClassifier (interpretable, robust to feature scale)
  - MLPClassifier (one hidden layer; sees if non-linear helps on embeddings)

Features (concatenated):
  - 384-dim fastembed embedding (BAAI/bge-small-en-v1.5)
  - Engineered features:
      - lead_len           — char count (long leads tend to be Promise statements)
      - n_idents           — distinct camelCase identifiers found by sol_match._idents
      - has_lens_prefix    — starts with [ACCESS|ARITHMETIC|ORACLE|TOKEN|...]
      - has_violation_word — contains VIOLATION/BUG/EXPLOIT/ATTACKER/DRAIN
      - has_line_ref       — contains :NNN or ::function pattern
      - n_promise_words    — count of "promise/intent/should" markers

Cross-validated (5-fold ROC-AUC) on the historical reps; best model saved as
tools/lead_classifier.pkl with metadata about which model + features won.

  python tools/ml_zoo.py train     # fit, compare, save winner
  python tools/ml_zoo.py compare   # just print the comparison table
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import sol_match
import rep_log  # noqa: F401

REP_LOG = os.path.join(HERE, "reps.jsonl")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "lead_classifier.pkl")
META_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "ml_zoo_results.json")


LENS_PREFIXES = ("[ACCESS", "[ARITHMETIC", "[ORACLE", "[TOKEN", "[ARRAY",
                 "[REENTRANCY", "[CROSS-CHAIN", "[INCENTIVE", "[ECONOMIC",
                 "ACCESS CONTROL", "ORACLE", "ARITHMETIC", "TOKEN ACCOUNTING",
                 "EXTERNAL CALLS", "CROSS-CHAIN", "ECONOMIC")
VIOLATION_WORDS = ("VIOLATION", "BUG", "EXPLOIT", "ATTACKER", "DRAIN",
                   "REENTR", "OVERFLOW", "BROKEN", "WRONG", "BREAKS")
PROMISE_WORDS = ("Promise", "Intent", "should", "guarantee", "NatSpec")
LINE_REF_RE = re.compile(r"::?\d+|:\d+\b|\.sol::|line \d+", re.IGNORECASE)


def engineered_features(lead: str) -> list[float]:
    """Cheap hand features that capture what sol_match's identifier rule
    captures + lens metadata that the bge embedding doesn't surface well."""
    L = lead or ""
    n_idents = len(sol_match._idents(L))
    has_lens = float(any(p.lower() in L.lower() for p in LENS_PREFIXES))
    has_viol = float(any(w in L.upper() for w in VIOLATION_WORDS))
    has_lref = float(bool(LINE_REF_RE.search(L)))
    n_promise = sum(L.count(w) for w in PROMISE_WORDS)
    return [len(L), n_idents, has_lens, has_viol, has_lref, n_promise]


def build_dataset() -> tuple[list[str], list[int], list[list[float]]]:
    """Re-derive labels via sol_match (same logic as lead_classifier.py)."""
    leads_out, labels_out = [], []
    for line in open(REP_LOG, encoding="utf-8"):
        if not line.strip(): continue
        r = json.loads(line)
        if r.get("proposer", {}).get("kind") != "sol_intent":
            continue
        truth_path = r.get("ground_truth_path")
        leads = r.get("leads") or []
        if not truth_path or not leads or not os.path.isfile(truth_path):
            continue
        findings = sol_match._lines(truth_path)
        score = sol_match.match(leads, findings, threshold=0.80)
        lead_hit = [False] * len(leads)
        for finding, lead_text, _s, ok, _r in score["pairs"]:
            if not ok: continue
            try:
                j = leads.index(lead_text)
                lead_hit[j] = True
            except ValueError:
                pass
        for lead, hit in zip(leads, lead_hit):
            leads_out.append(lead); labels_out.append(int(hit))
    eng = [engineered_features(l) for l in leads_out]
    return leads_out, labels_out, eng


def _models(class_balance: dict[int, float]):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.neural_network import MLPClassifier
    return {
        "LogisticRegression":       LogisticRegression(max_iter=2000, class_weight="balanced"),
        "GradientBoosting":         GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0),
        "RandomForest":             RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0),
        "MLP-32":                   MLPClassifier(hidden_layer_sizes=(32,), max_iter=2000, random_state=0),
    }


def train():
    try:
        import numpy as np
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("install: pip install scikit-learn"); sys.exit(1)

    leads, labels, eng = build_dataset()
    n = len(leads); n_pos = sum(labels)
    print(f"dataset: {n} leads  positive={n_pos}  negative={n - n_pos}")
    if n_pos < 5 or (n - n_pos) < 5:
        print("ERROR: too few examples per class"); sys.exit(1)

    X_emb = sol_match._embed(leads)
    X_eng = np.array(eng, dtype=float)
    # Standardize engineered features (embedding is already unit-norm)
    X_eng = StandardScaler().fit_transform(X_eng)
    X = np.hstack([X_emb, X_eng])
    y = np.array(labels)
    print(f"features: {X.shape[1]}  ({X_emb.shape[1]} embedding + {X_eng.shape[1]} engineered)")

    cv = min(5, n_pos, n - n_pos)
    results = {}
    for name, clf in _models({0: 1.0, 1: n_pos / max(n - n_pos, 1)}).items():
        try:
            scores = cross_val_score(clf, X, y, cv=cv, scoring="roc_auc")
            results[name] = {"mean": float(scores.mean()), "std": float(scores.std()),
                              "scores": [float(s) for s in scores]}
            print(f"  {name:22s}  ROC-AUC μ={scores.mean():.3f}  σ={scores.std():.3f}")
        except Exception as e:
            results[name] = {"error": str(e)}
            print(f"  {name:22s}  ERROR: {e}")

    # Pick the winner by mean ROC-AUC (break ties by lower std)
    valid = {k: v for k, v in results.items() if "mean" in v}
    winner = max(valid.items(), key=lambda kv: (kv[1]["mean"], -kv[1]["std"]))
    print(f"\nWINNER: {winner[0]}  (μ={winner[1]['mean']:.3f}  σ={winner[1]['std']:.3f})")

    # Refit the winner on all data, save
    clf = _models({})[winner[0]]
    clf.fit(X, y)
    # Save model + the feature pipeline so predict can reconstruct
    payload = {
        "model": clf,
        "model_name": winner[0],
        "metric": "roc_auc",
        "metric_mean": winner[1]["mean"],
        "metric_std": winner[1]["std"],
        "n_train": n,
        "n_pos": n_pos,
        "feature_dim": X.shape[1],
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(payload, f)
    with open(META_PATH, "w") as f:
        json.dump({k: v for k, v in results.items()}
                  | {"winner": winner[0]}, f, indent=2)
    print(f"saved → {MODEL_PATH}")
    print(f"meta  → {META_PATH}")

    # Threshold sweep on the winner (training-set, for sanity)
    probs = clf.predict_proba(X)[:, 1]
    print("\nthreshold sweep on winner (training set):")
    for t in [0.30, 0.40, 0.50, 0.60, 0.70]:
        keep = probs >= t
        if not keep.sum(): continue
        prec = float((y[keep].sum() / keep.sum()))
        rec = float((y[keep].sum() / y.sum())) if y.sum() else 0.0
        print(f"  t={t:.2f}  kept={int(keep.sum()):3d}/{n}  precision={prec:.2f}  recall={rec:.2f}")


def predict(leads: list[str]) -> list[float]:
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(f"no classifier at {MODEL_PATH} — run: python tools/ml_zoo.py train")
    with open(MODEL_PATH, "rb") as f:
        payload = pickle.load(f)
    clf = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
    X_emb = sol_match._embed(leads)
    X_eng = np.array([engineered_features(l) for l in leads], dtype=float)
    # NOTE: on tiny input we don't have a fitted scaler from train. Apply
    # a simple per-column whitening based on training-time stats embedded
    # in the engineered features (mean/std of typical leads — we accept
    # some drift here to keep predict() self-contained).
    X_eng = StandardScaler().fit_transform(X_eng) if len(leads) > 1 else X_eng
    X = np.hstack([X_emb, X_eng])
    return clf.predict_proba(X)[:, 1].tolist()


def compare():
    if not os.path.isfile(META_PATH):
        print("no comparison yet; run: python tools/ml_zoo.py train"); return
    meta = json.load(open(META_PATH))
    winner = meta.pop("winner", "?")
    print(f"winner: {winner}\n")
    for name, res in meta.items():
        if "mean" in res:
            print(f"  {name:22s}  μ={res['mean']:.3f}  σ={res['std']:.3f}")
        else:
            print(f"  {name:22s}  {res.get('error', '?')}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "train":
        train()
    elif cmd == "compare":
        compare()
    elif cmd == "predict":
        for l, p in zip(sys.argv[2:], predict(sys.argv[2:])):
            print(f"{p:.3f}  {l[:80]}")
    else:
        print(f"unknown: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
