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
        contract = r.get("contract", {})
        if by == "path":
            # Prefer project_id when present — survives /tmp paths and
            # works across worktrees. Fall back to basename(path).
            key = contract.get("project_id") or os.path.basename(
                (contract.get("path") or "?").rstrip("/")
            )
        else:
            key = contract.get(by) or contract.get("path", "?")
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
    cols = ["corpus", "n", "proposer", "rec", "prec", "P@10", "P@20", "P@50", "lift@50"]
    print(f"  {cols[0]:36s} {cols[1]:>3s}  {cols[2]:20s} {cols[3]:>11s} {cols[4]:>11s} {cols[5]:>6s} {cols[6]:>6s} {cols[7]:>6s} {cols[8]:>8s}")
    print(f"  {'-'*36} {'-'*3}  {'-'*20} {'-'*11} {'-'*11} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")
    for key, grp in sorted(groups.items()):
        # split by proposer kind for honest comparison (manual vs sol_intent)
        by_proposer = defaultdict(list)
        for r in grp:
            by_proposer[r.get("proposer", {}).get("kind", "?")].append(r)
        for kind, sub in sorted(by_proposer.items()):
            rec = [r["score"].get("recall") for r in sub if r["score"].get("recall") is not None]
            prec = [r["score"].get("precision") for r in sub if r["score"].get("precision") is not None]
            # Pull precision@K and lift from verifier.result if present
            p_at = {10: [], 20: [], 50: []}
            lifts = []
            for r in sub:
                vr = (r.get("verifier", {}) or {}).get("result") or {}
                used_verifier_lift = False
                if isinstance(vr, dict):
                    for K in (10, 20, 50):
                        cell = vr.get(str(K)) or vr.get(K)
                        if isinstance(cell, dict):
                            # Use explicit key presence — `0.0 or x` would
                            # silently substitute precision for a legit zero
                            # ricci_low score, inflating the displayed P@K.
                            if "ricci_low" in cell and cell["ricci_low"] is not None:
                                p_at[K].append(cell["ricci_low"])
                            elif "precision" in cell and cell["precision"] is not None:
                                p_at[K].append(cell["precision"])
                            rand = cell.get("random")
                            ricci = cell.get("ricci_low")
                            if K == 50 and rand is not None and ricci is not None and rand > 0:
                                lifts.append(ricci / rand)
                                used_verifier_lift = True
                # Fallback per rep — not gated on whether the group already
                # has any lifts (the old `not lifts` guard dropped subsequent
                # reps' fallbacks after the first verifier-derived one).
                lor = (r.get("score", {}) or {}).get("lift_over_random")
                if lor is not None and not used_verifier_lift:
                    lifts.append(lor)
            rec_s = _fmt(rec)
            prec_s = _fmt(prec)
            p10 = _fmt(p_at[10], width=2)
            p20 = _fmt(p_at[20], width=2)
            p50 = _fmt(p_at[50], width=2)
            lift_s = f"{statistics.mean(lifts):.2f}×" if lifts else "—"
            print(f"  {key:36s} {len(sub):>3d}  {kind:20s} {rec_s:>11s} {prec_s:>11s} {p10:>6s} {p20:>6s} {p50:>6s} {lift_s:>8s}")
    print()


def _fmt(xs, width=None):
    if not xs:
        return "—"
    mu = statistics.mean(xs)
    if len(xs) == 1:
        return f"{mu:.2f}"
    sd = statistics.stdev(xs)
    # When the slot is narrow (P@K columns), only show μ; otherwise μ±σ.
    if width is not None and width <= 2:
        return f"{mu:.2f}"
    return f"{mu:.2f}±{sd:.2f}"


if __name__ == "__main__":
    main()
