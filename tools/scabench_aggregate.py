"""
tools/scabench_aggregate.py — aggregate scorer_v2 per-project outputs into a
single scoreboard and a Markdown table suitable for the scabench/scorecard.md.

Reads:  runs/scabench-scores/score_*.json
Writes: runs/scabench-scores/aggregate.json + Markdown to stdout
"""
from __future__ import annotations
import json
import statistics
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
SCORES_DIR = HERE / "runs" / "scabench-scores"


def main():
    if not SCORES_DIR.is_dir():
        print(f"no scores dir at {SCORES_DIR}", file=sys.stderr)
        sys.exit(1)
    rows = []
    for p in sorted(SCORES_DIR.glob("score_*.json")):
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        rows.append({
            "project": d.get("project"),
            "expected": d.get("total_expected", 0),
            "found": d.get("total_found", 0),
            "tp": d.get("true_positives", 0),
            "fn": d.get("false_negatives", 0),
            "fp": d.get("false_positives", 0),
            "recall": d.get("detection_rate", 0),
            "precision": d.get("precision", 0),
            "f1": d.get("f1_score", 0),
        })

    if not rows:
        print("no score files found", file=sys.stderr)
        sys.exit(1)

    # Aggregates
    total_tp = sum(r["tp"] for r in rows)
    total_fn = sum(r["fn"] for r in rows)
    total_fp = sum(r["fp"] for r in rows)
    total_expected = sum(r["expected"] for r in rows)
    total_found = sum(r["found"] for r in rows)
    micro_precision = total_tp / max(1, total_tp + total_fp)
    micro_recall = total_tp / max(1, total_tp + total_fn)
    micro_f1 = (2 * micro_precision * micro_recall) / max(1e-9, micro_precision + micro_recall)
    macro_precision = statistics.mean([r["precision"] for r in rows])
    macro_recall = statistics.mean([r["recall"] for r in rows])
    macro_f1 = statistics.mean([r["f1"] for r in rows])

    aggregate = {
        "n_projects": len(rows),
        "total_expected": total_expected,
        "total_found": total_found,
        "total_tp": total_tp,
        "total_fn": total_fn,
        "total_fp": total_fp,
        "micro_precision": round(micro_precision, 4),
        "micro_recall": round(micro_recall, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "per_project": rows,
    }
    (SCORES_DIR / "aggregate.json").write_text(json.dumps(aggregate, indent=2))

    # Markdown
    print("# scabench scorer_v2 (gpt-4o-mini) results — plumbline eigenvector re-rank")
    print()
    print(f"**N projects:** {len(rows)}   |   "
          f"**Total expected vulns:** {total_expected}   |   "
          f"**Total tool findings:** {total_found}")
    print()
    print(f"**Micro F1:** {micro_f1:.4f}  (precision {micro_precision:.4f}, "
          f"recall {micro_recall:.4f})")
    print(f"**Macro F1:** {macro_f1:.4f}  (precision {macro_precision:.4f}, "
          f"recall {macro_recall:.4f})")
    print()
    print("## Per-project")
    print()
    print("| project | expected | found | TP | FN | FP | recall | precision | F1 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    rows.sort(key=lambda r: -r["f1"])
    for r in rows:
        print(f"| `{r['project']}` | {r['expected']} | {r['found']} | "
              f"{r['tp']} | {r['fn']} | {r['fp']} | "
              f"{r['recall']:.2%} | {r['precision']:.2%} | {r['f1']:.2%} |")
    print()
    print(f"Per-project scores: `runs/scabench-scores/score_*.json`.")
    print(f"Aggregate: `runs/scabench-scores/aggregate.json`.")


if __name__ == "__main__":
    main()
