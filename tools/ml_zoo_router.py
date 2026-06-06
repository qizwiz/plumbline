"""
ml_zoo_router — multi-class verifier-router classifier per ADR-006.

Forked from tools/ml_zoo.py. Differences:
  - Reads reps_routed.jsonl (per-row verifier_route from relabel_for_router)
  - Multi-class (4 classes: slither_will_catch, halmos_will_decide,
    tlc_will_decide, human_only) instead of binary {real, noise}
  - Training label = verifier_route[0] (cheapest-sufficient)
  - 5-fold STRATIFIED CV with top-1 + top-2 accuracy + avg cost
  - Saves tools/router_classifier.pkl + tools/router_results.json

Same featurizer as ml_zoo (fastembed 384-d + 6 engineered features) so
that route_lead.py inference uses the same pipeline.

Acceptance per ADR-006 + ROUTER_TRAIN.goal.md: top-2 >= 0.85 AND avg
cost <= 1.5. Both numbers printed to stdout.

Usage:
    python tools/ml_zoo_router.py train       # fit, compare, save winner
    python tools/ml_zoo_router.py compare     # just print comparison
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ml_zoo  # reuse engineered_features

REPS_ROUTED = os.path.join(HERE, "reps_routed.jsonl")
MODEL_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "router_classifier.pkl")
META_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "router_results.json")

# Class set (must match relabel_for_router.RULES output and ADR-006)
CLASSES = ("slither_will_catch", "halmos_will_decide",
           "tlc_will_decide", "human_only")
# Cost weights per ADR-006 §Routing policy (slither=0 since free, others
# anchored at 1.0 per run; human_only is the most expensive escalation)
COST = {
    "slither_will_catch": 0.0,
    "halmos_will_decide": 1.0,
    "tlc_will_decide":    1.0,
    "human_only":         2.0,
}


def build_router_dataset() -> tuple[list[str], list[int], list[list[float]]]:
    """Read reps_routed.jsonl; for each row with non-empty verifier_route,
    yield one sample per LEAD with the row's primary route (routes[0]) as
    the label. Same featurizer as ml_zoo."""
    leads_out: list[str] = []
    labels_out: list[int] = []
    label_to_idx = {c: i for i, c in enumerate(CLASSES)}
    for line in open(REPS_ROUTED, encoding="utf-8"):
        if not line.strip(): continue
        r = json.loads(line)
        routes = r.get("verifier_route") or []
        if not routes:
            continue  # ambiguous; needs manual
        primary = routes[0]
        if primary not in label_to_idx:
            continue
        leads = r.get("leads") or []
        for lead in leads:
            if not isinstance(lead, str): continue
            leads_out.append(lead)
            labels_out.append(label_to_idx[primary])
    eng = [ml_zoo.engineered_features(l) for l in leads_out]
    return leads_out, labels_out, eng


def featurize(leads: list[str], eng: list[list[float]]) -> np.ndarray:
    """Concat fastembed embedding + engineered features."""
    from fastembed import TextEmbedding
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    emb = np.array(list(embedder.embed(leads)))
    eng_arr = np.array(eng)
    return np.concatenate([emb, eng_arr], axis=1)


def _models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    return {
        "LogisticRegression":  LogisticRegression(class_weight="balanced",
                                                  max_iter=2000, random_state=0),
        "GradientBoosting":    GradientBoostingClassifier(n_estimators=200,
                                                          max_depth=3,
                                                          random_state=0),
        "RandomForest":        RandomForestClassifier(n_estimators=200,
                                                     class_weight="balanced",
                                                     random_state=0),
    }


def top_k_accuracy(probs: np.ndarray, y: np.ndarray, k: int) -> float:
    """Fraction of samples where the TRUE label is in the top-k predicted."""
    top_k_idx = np.argsort(-probs, axis=1)[:, :k]
    return float(np.mean([y[i] in top_k_idx[i] for i in range(len(y))]))


def avg_cost(probs: np.ndarray, threshold: float = 0.10) -> float:
    """Average sum of COST over verifiers above threshold. Slither always
    included (free) per ADR-006 policy."""
    costs = []
    for row in probs:
        idx_above = [i for i, p in enumerate(row) if p > threshold]
        # Always include slither (idx 0)
        if 0 not in idx_above:
            idx_above.append(0)
        costs.append(sum(COST[CLASSES[i]] for i in idx_above))
    return float(np.mean(costs))


def cross_validate(X, y):
    from sklearn.model_selection import StratifiedKFold
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    results = {}
    for name, ctor in _models().items():
        top1s, top2s, costs = [], [], []
        per_class_p, per_class_r, per_class_f1 = [], [], []
        for train_idx, test_idx in cv.split(X, y):
            from sklearn.base import clone
            from sklearn.metrics import precision_recall_fscore_support
            clf = clone(ctor)
            clf.fit(X[train_idx], y[train_idx])
            proba = clf.predict_proba(X[test_idx])
            y_te = y[test_idx]
            top1s.append(top_k_accuracy(proba, y_te, 1))
            top2s.append(top_k_accuracy(proba, y_te, 2))
            costs.append(avg_cost(proba))
            y_pred = clf.predict(X[test_idx])
            p, r, f1, _ = precision_recall_fscore_support(
                y_te, y_pred, labels=range(len(CLASSES)),
                average=None, zero_division=0)
            per_class_p.append(p); per_class_r.append(r); per_class_f1.append(f1)
        results[name] = {
            "top1": float(np.mean(top1s)),
            "top2": float(np.mean(top2s)),
            "avg_cost": float(np.mean(costs)),
            "per_class_precision": np.mean(per_class_p, axis=0).tolist(),
            "per_class_recall":    np.mean(per_class_r, axis=0).tolist(),
            "per_class_f1":        np.mean(per_class_f1, axis=0).tolist(),
        }
    return results


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    leads, labels, eng = build_router_dataset()
    if len(leads) < 40:
        print(f"FAIL  only {len(leads)} samples — see goal §'If training set "
              "too small' surface trigger")
        sys.exit(1)
    y = np.array(labels)
    print(f"dataset: {len(leads)} leads from {len(set(labels))} classes")
    cnts = {CLASSES[i]: int((y == i).sum()) for i in range(len(CLASSES))}
    print(f"per-class counts: {cnts}")

    X = featurize(leads, eng)
    results = cross_validate(X, y)

    print("\n=== 5-fold stratified CV results ===")
    print(f"{'model':<20} {'top1':>6} {'top2':>6} {'avg_cost':>10}")
    for name, r in results.items():
        print(f"  {name:<18} {r['top1']:>6.3f} {r['top2']:>6.3f} {r['avg_cost']:>10.3f}")

    best = max(results.items(), key=lambda kv: kv[1]["top2"])
    name, best_r = best
    print(f"\nWINNER: {name}  top1={best_r['top1']:.3f}  top2={best_r['top2']:.3f}  "
          f"avg_cost={best_r['avg_cost']:.3f}")

    print(f"\nper-class precision/recall/f1 ({name}):")
    print(f"{'class':<22} {'P':>6} {'R':>6} {'F1':>6}")
    for i, c in enumerate(CLASSES):
        print(f"  {c:<20} {best_r['per_class_precision'][i]:>6.3f} "
              f"{best_r['per_class_recall'][i]:>6.3f} "
              f"{best_r['per_class_f1'][i]:>6.3f}")

    if cmd == "train":
        # Retrain on full data
        from sklearn.base import clone
        clf = clone(_models()[name])
        clf.fit(X, y)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"model": clf, "classes": CLASSES,
                         "engineered_keys": [
                             "lead_len", "n_idents", "has_lens",
                             "has_violation", "has_line_ref", "n_promise"]
                         }, f)
        print(f"\nsaved model → {MODEL_PATH}")
    with open(META_PATH, "w") as f:
        json.dump({"results": results, "winner": name,
                   "top1": best_r["top1"],
                   "top2": best_r["top2"],
                   "avg_cost": best_r["avg_cost"],
                   "n_samples": len(leads),
                   "classes": list(CLASSES)}, f, indent=2)
    print(f"saved metrics → {META_PATH}")

    # Acceptance gate
    print(f"\n=== ACCEPTANCE (per ADR-006) ===")
    print(f"  top-2 >= 0.85 : {'PASS' if best_r['top2'] >= 0.85 else 'FAIL'} "
          f"(got {best_r['top2']:.3f})")
    print(f"  avg cost <= 1.5: {'PASS' if best_r['avg_cost'] <= 1.5 else 'FAIL'} "
          f"(got {best_r['avg_cost']:.3f})")


if __name__ == "__main__":
    main()
