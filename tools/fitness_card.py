"""
fitness_card — render reps.jsonl as a single PNG showing per-corpus recall
and precision over rep order. The honest one-image summary; no embedding,
no Layer 2, no fancy stats — just the raw fitness signal vs time.

  python tools/fitness_card.py             # writes docs/fitness.png
  python tools/fitness_card.py --out X.png

Requires: matplotlib. Skips gracefully if absent (CI shouldn't fail just
because the chart can't render).
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP_LOG = os.path.join(HERE, "reps.jsonl")
DEFAULT_OUT = os.path.join(HERE, "docs", "fitness.png")


def main():
    out = DEFAULT_OUT
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping. Install with: pip install matplotlib")
        return 0

    if not os.path.isfile(REP_LOG):
        print(f"no reps at {REP_LOG}")
        return 1

    rows = [json.loads(l) for l in open(REP_LOG) if l.strip()]
    # Filter to rows that have a real (non-null) score
    rows = [r for r in rows if r.get("score", {}).get("recall") is not None]
    if not rows:
        print("no scored reps to render")
        return 0

    # Group by corpus basename
    series = defaultdict(list)  # name -> list of (idx_in_file, recall, precision)
    for i, r in enumerate(rows):
        name = os.path.basename(r["contract"]["path"].rstrip("/"))
        series[name].append((
            i,
            r["score"].get("recall") or 0.0,
            r["score"].get("precision") or 0.0,
        ))

    fig, (ax_r, ax_p) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    colors = plt.cm.tab10.colors

    for k, (name, pts) in enumerate(sorted(series.items())):
        xs = [p[0] for p in pts]
        rs = [p[1] for p in pts]
        ps = [p[2] for p in pts]
        c = colors[k % len(colors)]
        ax_r.plot(xs, rs, marker="o", color=c, label=name, linewidth=1.5, markersize=6)
        ax_p.plot(xs, ps, marker="s", color=c, label=name, linewidth=1.5, markersize=6)

    ax_r.set_ylabel("recall")
    ax_r.set_ylim(-0.05, 1.05)
    ax_r.axhline(1.0, color="grey", linewidth=0.5, linestyle="--")
    ax_r.legend(loc="lower right", fontsize=8)
    ax_r.set_title(f"plumbline rep fitness  ({len(rows)} reps scored)")
    ax_r.grid(alpha=0.3)

    ax_p.set_ylabel("precision")
    ax_p.set_xlabel("rep order (in reps.jsonl)")
    ax_p.set_ylim(-0.05, 1.05)
    ax_p.grid(alpha=0.3)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"wrote {out}  ({len(rows)} reps, {len(series)} corpora)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
