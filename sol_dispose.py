"""
sol_dispose — pragmatic precision (grounded, not sound). Turns the wide-net finder's ~1300 noisy leads into
~30 ranked, triageable candidates:
  1. DEDUP — embedding-cluster the redundancy (the same issue restated across 19 chunks x 8 lenses).
  2. GROUP by contract (parse the Contract::function location).
  3. DISPOSE per contract — focused LLM judges the cluster reps against the real source (protect HIGH-sev
     structural finds, demand a concrete mechanism for the rest).
  4. RANK by severity + call-graph centrality (hubs first).
Not sound (that needs halmos+compile), but triageable — which is what a contest actually needs.

  python sol_dispose.py <candidates.txt> <source-dir>
"""
from __future__ import annotations

import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sol_graph
import sol_match
import prompt_improve as pi
import invariant_agent as agent

_SEV = {"high": 3, "medium": 2, "low": 1}


def _dedup(cands, thr=0.86):
    """Greedy embedding-cluster: collapse near-duplicate leads to representatives."""
    if len(cands) <= 1:
        return cands
    V = sol_match._embed(cands)
    keep, kept_vecs = [], []
    for i, c in enumerate(cands):
        v = V[i]
        if all(float(np.dot(v, kv)) < thr for kv in kept_vecs):
            keep.append(c); kept_vecs.append(v)
    return keep


def _contract_of(lead):
    m = re.search(r"\b([A-Z]\w+)\s*(?:::|\.)\s*([A-Za-z_]\w*)", lead)
    return (m.group(1), m.group(2)) if m else (None, None)


def dispose(cands_path, root):
    cands = [l.strip().lstrip("-* ").strip() for l in open(cands_path, encoding="utf-8", errors="replace")
             if len(l.strip()) > 12]
    reps = _dedup(cands)
    files, fns, G, dets = sol_graph.analyze(root)
    pr = (lambda: __import__("networkx").pagerank(G))() if G.number_of_edges() else {}
    contract_file = {}
    for f in fns:
        contract_file.setdefault(f["contract"], f["rel"])
    src = {rel: s for rel, s in __import__("sol_intent").collect(root)[2]}
    # group reps by contract
    by_contract = {}
    for c in reps:
        ct, _ = _contract_of(c)
        by_contract.setdefault(ct or "?", []).append(c)
    tmpl = open(os.path.join(HERE, "prompts/sol_dispose.md")).read()
    kept = []
    for ct, cs in by_contract.items():
        rel = contract_file.get(ct)
        source = src.get(rel, "")
        if not source:                      # no source located -> can't verify; keep top-severity raw
            continue
        out = agent._ask(pi.render(tmpl, candidates="\n".join(f"- {x}" for x in cs[:40]),
                                   source=source[:120000]), 2500)
        lines = out.splitlines()
        i = next((k for k, l in enumerate(lines) if l.strip().upper().startswith("KEPT")), None)
        if i is None:
            continue
        for l in lines[i + 1:]:
            s = l.strip()
            if s.startswith("- ") and "NONE" not in s.upper():
                kept.append(s[2:])
    # rank by severity then centrality of the named function
    def score(k):
        sev = _SEV.get((re.search(r"SEV=(\w+)", k) or [None, "medium"])[1].lower(), 2)
        ct, fn = _contract_of(k)
        cen = pr.get(f"{ct}.{fn}", 0.0) if ct and fn else 0.0
        return (sev, cen)
    kept.sort(key=score, reverse=True)
    return cands, reps, kept


if __name__ == "__main__":
    cands_path, root = sys.argv[1], sys.argv[2]
    raw, reps, kept = dispose(cands_path, root)
    print(f"=== sol_dispose: {len(raw)} leads -> {len(reps)} deduped -> {len(kept)} KEPT (ranked) ===\n")
    for k in kept:
        print("  ", k[:150])
    open("/tmp/disposed_ranked.txt", "w").write("\n".join(kept) + "\n")
