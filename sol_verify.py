"""
sol_verify — the DISPOSE step. structure (sol_graph) PROPOSES deterministic candidates (high recall, low
precision); the LLM here DISPOSES — confirms each against the actual source or rejects it. The LLM judges
specific claims (what it's good at) instead of hunting 1.8MB (what it's bad at). This is the missing half
of "structure proposes, semantics disposes," and it targets the floor's catastrophic precision directly.

  python sol_verify.py <dir>
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sol_graph
import sol_intent
import prompt_improve as pi
import invariant_agent as agent


def verify(root, budget=110000):
    files, fns, G, dets = sol_graph.analyze(root)
    if not dets:
        return [], []
    # candidates grouped by the file they live in
    cand_by_file = {}
    for f, sev, kind, msg in dets:
        cand_by_file.setdefault(f["rel"], []).append(f"[{sev}] {kind}: {msg}")
    readme, adrs, sols = sol_intent.collect(root)
    src = {rel: s for rel, s in sols}
    rels = [r for r in cand_by_file if r in src]
    # pack candidate-bearing files into chunks under budget (source + candidates travel together)
    chunks, cur, sz = [], [], 0
    for rel in rels:
        piece = len(src[rel])
        if cur and sz + piece > budget:
            chunks.append(cur); cur, sz = [], 0
        cur.append(rel); sz += piece
    if cur:
        chunks.append(cur)
    tmpl = open(os.path.join(HERE, "prompts/sol_verify.md")).read()
    confirmed = []
    for ch in chunks:
        cands = "\n".join(c for rel in ch for c in cand_by_file[rel])
        source = "\n\n".join(f"// ===== {rel} =====\n{src[rel]}" for rel in ch)
        prompt = pi.render(tmpl, candidates=cands, source=source[:budget + 20000])
        out = agent._ask(prompt, 3000)
        lines = out.splitlines()
        i = next((k for k, l in enumerate(lines) if l.strip().upper().startswith("CONFIRMED")), None)
        if i is not None:
            for l in lines[i + 1:]:
                s = l.strip()
                if s.startswith("- ") and "NONE" not in s.upper():
                    confirmed.append(s[2:])
    n_cand = sum(len(v) for v in cand_by_file.values())
    return confirmed, [n_cand, len(dets)]


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    conf, stats = verify(root)
    print(f"=== sol_verify: {stats[1] if stats else 0} candidates proposed -> {len(conf)} CONFIRMED ===")
    for c in conf:
        print(" ", c[:140])
