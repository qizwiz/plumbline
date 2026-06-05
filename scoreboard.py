"""
scoreboard — read reps.jsonl, print per-corpus aggregate stats.

The honest fitness signal isn't any single rep — sol_intent is stochastic, so
per-rep recall/precision are noisy. The signal is the MEAN over N reps per
corpus, with the standard error. That's what we'd train a Layer-2 policy
against once it exists.

  python scoreboard.py
  python scoreboard.py --by sha256_dir       # group by content hash instead of path
  python scoreboard.py --corpus puppy-raffle # restrict the aggregate to one corpus
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REP_LOG = os.path.join(HERE, "reps.jsonl")


def main():
    by = "path"
    corpus_filter = None
    args = sys.argv[1:]
    if "--by" in args:
        by = args[args.index("--by") + 1]
    if "--corpus" in args:
        corpus_filter = args[args.index("--corpus") + 1]

    if not os.path.exists(REP_LOG):
        print(f"no reps yet at {REP_LOG}")
        return

    rows = [json.loads(l) for l in open(REP_LOG) if l.strip()]
    groups = defaultdict(list)
    for r in rows:
        key = r.get("contract", {}).get(by) or r.get("contract", {}).get("path", "?")
        if by == "path":
            key = os.path.basename(key.rstrip("/"))
        if corpus_filter is not None and corpus_filter not in key:
            continue
        groups[key].append(r)

    if corpus_filter is not None and not groups:
        print(f"no reps match corpus filter {corpus_filter!r}")
        return

    shown = sum(len(g) for g in groups.values())
    fhint = f"   filter: {corpus_filter!r}" if corpus_filter else ""
    print(f"\n  total reps: {len(rows)}   shown: {shown}   groups: {len(groups)}{fhint}   log: {REP_LOG}")
    print()
    cols = ["corpus", "n", "proposer", "recall (μ±σ)", "precision (μ±σ)", "leads (μ)", "findings"]
    print(f"  {cols[0]:32s} {cols[1]:>3s}  {cols[2]:12s} {cols[3]:>15s} {cols[4]:>18s} {cols[5]:>10s} {cols[6]:>9s}")
    print(f"  {'-'*32} {'-'*3}  {'-'*12} {'-'*15} {'-'*18} {'-'*10} {'-'*9}")
    for key, grp in sorted(groups.items()):
        # split by proposer kind for honest comparison (manual vs sol_intent)
        by_proposer = defaultdict(list)
        for r in grp:
            by_proposer[r.get("proposer", {}).get("kind", "?")].append(r)
        for kind, sub in sorted(by_proposer.items()):
            rec = [r["score"].get("recall") for r in sub if r["score"].get("recall") is not None]
            prec = [r["score"].get("precision") for r in sub if r["score"].get("precision") is not None]
            leads = [r["score"].get("n_leads") for r in sub if r["score"].get("n_leads") is not None]
            findings = sub[0]["score"].get("n_findings") if sub else None
            rec_s = _fmt(rec)
            prec_s = _fmt(prec)
            leads_s = f"{statistics.mean(leads):.1f}" if leads else "—"
            f_s = str(findings) if findings is not None else "—"
            print(f"  {key:32s} {len(sub):>3d}  {kind:12s} {rec_s:>15s} {prec_s:>18s} {leads_s:>10s} {f_s:>9s}")
    print()


def _fmt(xs):
    if not xs:
        return "—"
    mu = statistics.mean(xs)
    if len(xs) == 1:
        return f"{mu:.2f}"
    sd = statistics.stdev(xs)
    return f"{mu:.2f}±{sd:.2f}"


if __name__ == "__main__":
    main()
