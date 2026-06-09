"""
measure_reps — aggregate precision/recall over reps.jsonl.

Computes the headline numbers for the arXiv writeup (Section 3.3 / Section 5
limitations / Section 7 H1 baseline). Reproducible — re-run after appending
new reps to regenerate.

Usage:
  python3 tools/measure_reps.py
  python3 tools/measure_reps.py --by-proposer
  python3 tools/measure_reps.py --top-n 10

Reads reps.jsonl, filters to entries with score.precision and score.recall
fields populated by sol_match, computes mean/median/stdev per proposer and
aggregate. Prints a markdown-formatted table suitable for paste into the
paper.
"""
from __future__ import annotations
import argparse, json, statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPS_PATH = HERE / "reps.jsonl"


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def load_reps() -> list[dict]:
    rs = []
    with open(REPS_PATH) as f:
        for ln in f:
            try:
                rs.append(json.loads(ln))
            except Exception:
                pass
    return rs


def scored(reps: list[dict]) -> list[dict]:
    out = []
    for r in reps:
        s = r.get("score")
        if isinstance(s, dict) and "precision" in s and "recall" in s:
            if s["precision"] is not None and s["recall"] is not None:
                out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--by-proposer", action="store_true",
                    help="Group by proposer kind")
    ap.add_argument("--top-n", type=int, default=5, help="Show top-N by F1")
    args = ap.parse_args()

    reps = load_reps()
    sc = scored(reps)

    print(f"# Plumbline measurement (reps.jsonl)\n")
    print(f"- Total reps: {len(reps)}")
    print(f"- Reps with precision+recall scored: {len(sc)}")
    print()

    if args.by_proposer:
        by = defaultdict(list)
        for r in sc:
            p = r.get("proposer", {}).get("kind", "unknown") if isinstance(r.get("proposer"), dict) else "unknown"
            by[p].append(r)
        print("## By proposer\n")
        print("| Proposer | N | Precision | Recall | F1 |")
        print("|---|---|---|---|---|")
        for kind, rs in sorted(by.items(), key=lambda x: -len(x[1])):
            ps = [r["score"]["precision"] for r in rs]
            rcs = [r["score"]["recall"] for r in rs]
            pm = statistics.mean(ps)
            rm = statistics.mean(rcs)
            print(f"| {kind} | {len(rs)} | {pm:.3f} | {rm:.3f} | {f1(pm, rm):.3f} |")
        print()

    ps = [r["score"]["precision"] for r in sc]
    rcs = [r["score"]["recall"] for r in sc]
    pm = statistics.mean(ps)
    rm = statistics.mean(rcs)
    print(f"## Aggregate (N={len(sc)})\n")
    print(f"- **Mean precision:** {pm:.3f}  (median {statistics.median(ps):.3f}, stdev {statistics.stdev(ps):.3f})")
    print(f"- **Mean recall:**    {rm:.3f}  (median {statistics.median(rcs):.3f}, stdev {statistics.stdev(rcs):.3f})")
    print(f"- **F1:**             {f1(pm, rm):.3f}")
    print()

    print(f"## Top {args.top_n} by F1\n")
    print("| F1 | Precision | Recall | Contract |")
    print("|---|---|---|---|")
    for r in sorted(sc, key=lambda x: f1(x["score"]["precision"], x["score"]["recall"]), reverse=True)[:args.top_n]:
        p = r["score"]["precision"]
        rr = r["score"]["recall"]
        contract = r.get("contract", {})
        path = contract.get("path", "?").split("/")[-1] if isinstance(contract, dict) else "?"
        print(f"| {f1(p, rr):.3f} | {p:.3f} | {rr:.3f} | {path} |")


if __name__ == "__main__":
    main()
