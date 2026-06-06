"""
spec_retrieval — the retrieval corpus that conditions TLA+ generation.

Per ARCHITECTURE.md §3b (NCA-as-fluency-teacher curriculum step 1):
    "Every successful (bug-shape, TLC-verified TLA+ spec) triple goes
    into a vector index. Next generation retrieves nearest neighbors as
    few-shot context. Weekend-tractable."

This file IS that index, in the smallest viable form. No training,
no fine-tuning — pure embedding lookup over a hand-authored corpus.
Compounds with every verified spec added.

Per RESEARCH-NOTES-2026-06-06.md (LTLGuard arxiv 2603.05728): this
retrieval-augmented few-shot approach is what lifts a 14B open model
from 10% syntactic validity to 92.8%, and to 75-78% semantic accuracy
on the nl2spec hard benchmark — without fine-tuning. The lift is in
the retrieval, not the model.

USAGE
  # Build/refresh the index (run on every commit that adds a TLA+ module)
  python tools/spec_retrieval.py build

  # Query: get nearest TLA+ specs by description
  python tools/spec_retrieval.py query "signature replay nonce missing"
  python tools/spec_retrieval.py query "function default mutable list"
  python tools/spec_retrieval.py query "ERC-4337 entrypoint scheduler DoS"

  # Show all indexed specs
  python tools/spec_retrieval.py list
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TLA_DIRS = [
    os.path.join(HERE, "docs/tla"),
    os.path.join(HERE, "docs/tla/imported"),
]
INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "spec_retrieval_index.pkl")


def _read_header(path: str) -> tuple[str, str]:
    """Return (module_name, header_description). The header is everything
    between the `(* ... *)` directly after the MODULE line."""
    text = open(path, encoding="utf-8", errors="replace").read()
    name_match = re.search(r"MODULE\s+(\w+)", text)
    name = name_match.group(1) if name_match else os.path.basename(path)
    # Everything between the first `(*` and the matching `*)` is the
    # spec's natural-language description.
    body_match = re.search(r"\(\*(.*?)\*\)", text, re.DOTALL)
    if body_match:
        desc = body_match.group(1).strip()
        # Drop the asterisk-marker lines used as visual borders
        desc = "\n".join(ln.lstrip(" *") for ln in desc.splitlines())
    else:
        desc = text[:1000]
    return name, desc


def _iter_specs():
    for tla_dir in TLA_DIRS:
        if not os.path.isdir(tla_dir):
            continue
        for fn in sorted(os.listdir(tla_dir)):
            if not fn.endswith(".tla"):
                continue
            yield os.path.join(tla_dir, fn)


def build():
    sys.path.insert(0, HERE)
    import sol_match  # for the same embedder sol_match uses

    specs = []
    for path in _iter_specs():
        name, desc = _read_header(path)
        specs.append({
            "name": name,
            "path": os.path.relpath(path, HERE),
            "description": desc,
            "description_head": desc[:200].replace("\n", " "),
        })

    if not specs:
        print("no TLA+ specs found under", TLA_DIRS)
        sys.exit(1)

    print(f"indexing {len(specs)} specs...")
    descriptions = [s["description"] for s in specs]
    embeddings = sol_match._embed(descriptions)

    payload = {
        "specs": specs,
        "embeddings": embeddings,
        "embed_model": "BAAI/bge-small-en-v1.5",
    }
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(payload, f)

    print(f"saved → {INDEX_PATH}")
    print(f"  corpus size: {len(specs)}")
    print(f"  embedding dim: {embeddings.shape[1]}")
    for s in specs:
        print(f"  {s['name']:36s} ({s['path']})")


def query(query_text: str, k: int = 3):
    if not os.path.isfile(INDEX_PATH):
        print(f"no index at {INDEX_PATH} — run: python tools/spec_retrieval.py build")
        sys.exit(1)
    sys.path.insert(0, HERE)
    import sol_match
    import numpy as np

    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    specs = payload["specs"]
    embs = payload["embeddings"]

    q = sol_match._embed([query_text])[0]
    sims = embs @ q  # cosine, since fastembed already unit-norms
    order = np.argsort(-sims)[:k]

    print(f"query: {query_text}")
    print(f"top {k}:\n")
    for rank, i in enumerate(order, 1):
        s = specs[i]
        print(f"  {rank}. {s['name']:36s}  cos={sims[i]:.3f}  ({s['path']})")
        print(f"     {s['description_head']}")
        print()


def list_specs():
    if not os.path.isfile(INDEX_PATH):
        print(f"no index at {INDEX_PATH} — run: python tools/spec_retrieval.py build")
        sys.exit(1)
    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    for s in payload["specs"]:
        print(f"  {s['name']:36s} ({s['path']})")
        print(f"    {s['description_head']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("usage: python tools/spec_retrieval.py query <text> [k]"); sys.exit(1)
        text = sys.argv[2]
        k = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        query(text, k=k)
    elif cmd == "list":
        list_specs()
    else:
        print(f"unknown: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
