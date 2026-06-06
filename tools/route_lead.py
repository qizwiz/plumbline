"""
route_lead — inference CLI for the verifier-router (ADR-006).

Reads one lead per line from stdin, prints ordered (verifier, probability)
tuples for each. Default top-k=2 (ADR-006 §Routing policy: try the top-2
in cost order).

Loads tools/router_classifier.pkl produced by ml_zoo_router.py and uses the
SAME featurizer (fastembed bge-small-en-v1.5 + 6 engineered features).

Usage:
    echo "signature accepted twice no nonce" | python tools/route_lead.py
    echo "lead" | python tools/route_lead.py --top-k 3
"""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ml_zoo

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "router_classifier.pkl")


def featurize(leads: list[str]) -> np.ndarray:
    from fastembed import TextEmbedding
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    emb = np.array(list(embedder.embed(leads)))
    eng = np.array([ml_zoo.engineered_features(l) for l in leads])
    return np.concatenate([emb, eng], axis=1)


def main():
    top_k = 2
    if "--top-k" in sys.argv:
        top_k = int(sys.argv[sys.argv.index("--top-k") + 1])

    leads = [ln.strip() for ln in sys.stdin if ln.strip()]
    if not leads:
        print("(no leads on stdin)", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(MODEL_PATH):
        print(f"FAIL  model not found at {MODEL_PATH} — run "
              "tools/ml_zoo_router.py train first", file=sys.stderr)
        sys.exit(2)

    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    clf = bundle["model"]
    classes = bundle["classes"]

    X = featurize(leads)
    proba = clf.predict_proba(X)

    for i, lead in enumerate(leads):
        ranked = sorted(zip(classes, proba[i]), key=lambda kv: -kv[1])
        # Always include slither if not in top-k (ADR-006 §Routing policy)
        top = ranked[:top_k]
        if not any(c == "slither_will_catch" for c, _ in top):
            top = top + [("slither_will_catch", 0.0)]
        parts = [f"{c.replace('_will_catch','').replace('_will_decide','').replace('_only','')} "
                 f"({p:.2f})" for c, p in top]
        if len(leads) > 1:
            print(f"[{i+1}] {lead[:60]}")
            print(f"    {', '.join(parts)}")
        else:
            print(", ".join(parts))


if __name__ == "__main__":
    main()
