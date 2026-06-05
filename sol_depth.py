"""
sol_depth — the DEPTH + VERIFY layer. The breadth pass skims; this focuses. Pick the highest-value targets
from the graph (PageRank hubs + name-matched suspects: oracle/inflation/incentive/reward/cast-heavy), give
each function its OWN adversarial pass with its callees as context, and DETERMINISTICALLY verify any
arithmetic witness (recompute value vs type bound — real math, not the LLM's word). breadth finds the easy
ones; depth+verify is for the deep oracle/economic/arithmetic findings breadth skips past.

  python sol_depth.py <dir> [topk]
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import networkx as nx

import sol_graph
import prompt_improve as pi
import invariant_agent as agent

_SUSPECT = re.compile(r"oracl|twap|price|inflation|incentiv|reward|donation|checkpoint|swap|getv3|"
                      r"getowner|manageutil|exitpool|getpooltokens|liquidity|epoch|vest|cast|narrow", re.I)


def targets(fns, G, topk=10):
    """Highest-value functions to deep-dive: PageRank hubs + name-matched suspects, deduped."""
    chosen = {}
    if G.number_of_edges():
        pr = nx.pagerank(G)
        for fid in sorted(pr, key=pr.get, reverse=True):
            chosen[fid] = "hub"
            if len(chosen) >= topk:
                break
    by_id = {f["id"]: f for f in fns}
    for f in fns:
        if _SUSPECT.search(f["id"]) and f["vis"] in ("public", "external") and f["id"] in by_id:
            chosen.setdefault(f["id"], "suspect")
    return list(chosen.items())[: topk + 8]


def context_for(fid, fns, G, budget=30000):
    by_id = {f["id"]: f for f in fns}
    tgt = by_id.get(fid)
    if not tgt:
        return None, ""
    target_src = f"// {tgt['rel']}  {tgt['sig']}\n{tgt['body']}"
    ctx = []
    for callee in list(G.successors(fid))[:8] if fid in G else []:
        c = by_id.get(callee)
        if c and c["body"]:
            ctx.append(f"// callee {c['id']}\n{c['body'][:3000]}")
    return target_src[:budget], "\n\n".join(ctx)[:budget]


def _verify_witness(line):
    """Deterministically check a cast-truncation witness: does the claimed value exceed the type bound?"""
    mt = re.search(r"cast=(u?int)(\d+)", line)
    mv = re.search(r"value=([0-9]+|2\*\*\d+)", line)
    if not (mt and mv):
        return None
    bits = int(mt.group(2))
    raw = mv.group(1)
    val = (2 ** int(raw.split("**")[1])) if "**" in raw else int(raw)
    bound = (2 ** (bits - (1 if mt.group(1) == "int" else 0))) - 1
    return val > bound  # True = truncation confirmed (value exceeds type)


def deep(root, topk=10):
    files, fns, G, dets = sol_graph.analyze(root)
    tmpl = open(os.path.join(HERE, "prompts/sol_depth.md")).read()
    findings = []
    for fid, why in targets(fns, G, topk):
        tsrc, ctx = context_for(fid, fns, G)
        if not tsrc:
            continue
        out = agent._ask(pi.render(tmpl, target=tsrc, context=ctx or "(no callees resolved)"), 2500)
        if "NO EXPLOIT FOUND" in out and "location" not in out.lower():
            continue
        # parse findings (location lines) + verify witnesses
        verdict = ""
        for wl in re.findall(r"WITNESS:.*", out):
            v = _verify_witness(wl)
            if v is True:
                verdict = " [VERIFIED-truncation]"
            elif v is False:
                verdict = " [witness-fails-check]"
        loc = re.search(r"location\**:?\s*([A-Za-z_][\w.]*::[A-Za-z_]\w*|[A-Za-z_][\w.]*\.[A-Za-z_]\w*)", out)
        head = re.search(r"\*\*attack\*\*:?\s*(.+)", out)
        findings.append({"target": fid, "why": why,
                         "loc": loc.group(1) if loc else fid,
                         "summary": (out.split("**attack**")[0][:200] if "**attack**" in out else out[:200]),
                         "verdict": verdict, "raw": out})
    return findings


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    topk = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    fs = deep(root, topk)
    print(f"=== sol_depth: {len(fs)} deep findings at hubs/suspects ===")
    for f in fs:
        print(f"  [{f['why']}] {f['loc']}{f['verdict']}: {f['summary'].strip()[:120]}")
