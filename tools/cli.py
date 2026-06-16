"""plumbline CLI — one command for the one thing.

  plumbline scan <dir>                     ranked audit-priority list
  plumbline scan <dir> --top 30            change number shown
  plumbline scan <dir> --blame Contract.fn explain a single function
  plumbline scan <dir> --json              structured output for piping
  plumbline scan <dir> --no-color          disable color
  plumbline scan <dir> --quiet             only the ranked list

Score = blend of (call-graph centrality, Ollivier-Ricci curvature, structural
detector hits). Tier = red (top 25%) / yellow (next 25%) / gray (rest).
Ranking saved to .plumbline/scan-<timestamp>.json for blame and diff.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import networkx as nx
from sol_graph import analyze


# ---------- ANSI -------------------------------------------------------------

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


class C:
    """Color codes. Disabled if not a TTY."""
    def __init__(self, enabled: bool):
        if enabled:
            self.RED = "\033[31m"
            self.RED_B = "\033[1;31m"
            self.YEL = "\033[33m"
            self.YEL_B = "\033[1;33m"
            self.GRY = "\033[90m"
            self.DIM = "\033[2m"
            self.B = "\033[1m"
            self.RST = "\033[0m"
            self.UND = "\033[4m"
        else:
            self.RED = self.RED_B = self.YEL = self.YEL_B = ""
            self.GRY = self.DIM = self.B = self.RST = self.UND = ""


# ---------- Ricci (shared with tools/run_ricci_signal.py) --------------------

def _ricci_per_node(G: nx.DiGraph) -> dict[str, float]:
    UG = G.to_undirected()
    sp_cache = {}

    def sp(u, v):
        key = (u, v) if u <= v else (v, u)
        if key not in sp_cache:
            try:
                sp_cache[key] = nx.shortest_path_length(UG, u, v)
            except nx.NetworkXNoPath:
                sp_cache[key] = 10
        return sp_cache[key]

    def mass(u, alpha=0.5):
        nbrs = list(UG.neighbors(u))
        if not nbrs:
            return {u: 1.0}
        m = {u: alpha}
        share = (1 - alpha) / len(nbrs)
        for n in nbrs:
            m[n] = share
        return m

    def wass(m1, m2):
        items1 = list(m1.items())
        demand = dict(m2)
        total = 0.0
        for u, s_u in items1:
            if s_u <= 0:
                continue
            for v in sorted(demand.keys(), key=lambda v: sp(u, v)):
                if s_u <= 1e-9:
                    break
                d_v = demand.get(v, 0)
                if d_v <= 0:
                    continue
                take = min(s_u, d_v)
                total += take * sp(u, v)
                demand[v] -= take
                s_u -= take
        return total

    edge_curvs = {}
    for u, v in UG.edges():
        d = sp(u, v)
        if d == 0:
            edge_curvs[(u, v)] = 0.0
            continue
        edge_curvs[(u, v)] = 1 - (wass(mass(u), mass(v)) / d)

    node_curvs = {}
    for n in UG.nodes():
        incident = [k for (u, v), k in edge_curvs.items() if u == n or v == n]
        node_curvs[n] = sum(incident) / len(incident) if incident else 0.0
    return node_curvs


# ---------- ranking ----------------------------------------------------------

DETECTOR_LABELS = {
    "narrowing-cast": "cast",
    "unchecked-erc20": "erc20.unchecked",
    "unchecked-call": "call.unchecked",
    "tx-origin": "tx.origin",
    "no-return": "return.missing",
}


def _pctile(values: list[float], v: float, higher_is_better: bool = True) -> int:
    """Return 1-100 percentile of v in values. higher_is_better=True means top = p99."""
    if not values:
        return 50
    n = len(values)
    if higher_is_better:
        below = sum(1 for x in values if x < v)
    else:
        below = sum(1 for x in values if x > v)
    return max(1, min(100, int(round(100 * below / n))))


def rank(G: nx.DiGraph, dets: list, top_red: int = 10, top_yel: int = 20) -> list[dict]:
    """Return ranked list of nodes with score + reasons + file:line.

    Tier is ABSOLUTE: top_red = "red" (audit first), top_yel-top_red = "yellow",
    everything else = "gray". This gives Mariam a triage, not a sort.
    """
    n_nodes = G.number_of_nodes()
    if G.number_of_edges() == 0:
        return [{
            "name": n, "score": 0.0, "tier": "low",
            "reasons": [], "centrality": 0.0, "curvature": 0.0,
            "file": G.nodes[n].get("rel"), "line": G.nodes[n].get("line"),
            "rank": i + 1, "of": n_nodes,
        } for i, n in enumerate(sorted(G.nodes()))]

    pr = nx.pagerank(G)
    UG = G.to_undirected()
    if nx.is_connected(UG):
        G_sub = G
    else:
        largest = max(nx.connected_components(UG), key=len)
        G_sub = G.subgraph(largest).copy()
    ricci = _ricci_per_node(G_sub)

    det_by_node: dict[str, list[str]] = {}
    for f, sev, kind, msg in dets:
        det_by_node.setdefault(f["id"], []).append(kind)

    pr_vals = list(pr.values())
    pr_max = max(pr_vals) if pr_vals else 1.0
    ricci_vals = list(ricci.values())
    r_min = min(ricci_vals) if ricci_vals else 0
    r_max = max(ricci_vals) if ricci_vals else 1
    r_range = r_max - r_min or 1.0

    items = []
    for n in G.nodes():
        cent = pr.get(n, 0) / pr_max
        curv = ricci.get(n, 0)
        curv_norm = (r_max - curv) / r_range
        det_count = len(det_by_node.get(n, []))
        det_boost = min(det_count * 0.15, 0.45)
        score = 0.45 * cent + 0.45 * curv_norm + det_boost
        # Deprioritize view/pure functions: high PageRank because they're called
        # everywhere, but they don't mutate state — rarely bug sites. Halve the
        # score so they sink below real audit targets but stay visible.
        mut = G.nodes[n].get("mut")
        if mut in ("view", "pure"):
            score *= 0.5

        # Interpretable percentiles
        cent_pct = _pctile(pr_vals, pr.get(n, 0), higher_is_better=True)
        curv_pct = _pctile(ricci_vals, curv, higher_is_better=False)  # low curv = top

        # Reasons in human terms (percentile, not raw float)
        reasons = []
        if cent_pct >= 90:
            reasons.append(f"hub p{cent_pct}")
        if curv_pct >= 90 and curv < 0:
            reasons.append(f"curv p{curv_pct}")
        for kind in det_by_node.get(n, []):
            reasons.append(f"+{DETECTOR_LABELS.get(kind, kind)}")
        if mut in ("view", "pure"):
            reasons.append(f"-{mut}/2")

        items.append({
            "name": n,
            "score": score,
            "centrality": pr.get(n, 0),
            "curvature": curv,
            "centrality_pct": cent_pct,
            "curvature_pct": curv_pct,
            "reasons": reasons,
            "detectors": det_by_node.get(n, []),
            "file": G.nodes[n].get("rel"),
            "line": G.nodes[n].get("line"),
        })
    items.sort(key=lambda x: -x["score"])

    # Absolute tier caps — Mariam wants triage, not sort
    for i, it in enumerate(items):
        it["rank"] = i + 1
        it["of"] = n_nodes
        if i < top_red:
            it["tier"] = "high"
        elif i < top_yel:
            it["tier"] = "med"
        else:
            it["tier"] = "low"
    return items


# ---------- output -----------------------------------------------------------

GLYPH = {"high": "🔴", "med": "🟡", "low": "⚪"}


def _osc8(url: str, text: str) -> str:
    """OSC-8 terminal hyperlink — Kitty/iTerm/WezTerm render this as clickable."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def print_human(items, files_n, fns_n, edges_n, top, scan_time, c: C, path: Path):
    bar = "┃"
    print()
    print(f"  {c.B}plumbline scan{c.RST}  {c.DIM}{path}{c.RST}")
    print(f"  {c.DIM}{files_n} files · {fns_n} functions · {edges_n} call edges · {scan_time:.2f}s{c.RST}")
    print()
    show = items[:top]
    tier_color = {"high": c.RED_B, "med": c.YEL_B, "low": c.GRY}
    last_tier = None
    headers = {"high": "high — audit first",
               "med":  "med  — audit second",
               "low":  "low  — skim only"}
    use_links = c.RED != ""  # only when color is on (proxy for "interactive terminal")
    for i, it in enumerate(show, 1):
        if it["tier"] != last_tier:
            tlabel = headers[it["tier"]]
            print(f"  {bar} {GLYPH[it['tier']]} {tier_color[it['tier']]}{tlabel}{c.RST}")
            last_tier = it["tier"]
        rs = " ".join(it["reasons"]) if it["reasons"] else c.DIM + "—" + c.RST
        name = it["name"]
        rel = it.get("file") or "?"
        line = it.get("line") or 1
        # file:line, abbreviated (only last 2 path segments) to keep the column tight
        rel_short = "/".join(rel.split("/")[-2:]) if rel else "?"
        loc = f"{rel_short}:{line}"
        if use_links:
            # absolute path for the link, short label for display
            abs_path = str((path / rel).resolve()) if rel else str(path)
            loc_display = _osc8(f"file://{abs_path}#L{line}", loc)
        else:
            loc_display = loc
        name_col = f"{tier_color[it['tier']]}{name}{c.RST}"
        print(f"  {bar}    {i:>3}.  {name_col:54s}  {c.DIM}{loc_display:28s}{c.RST}  {c.DIM}{rs}{c.RST}")
    print(f"  {bar}")
    print()
    n_high = sum(1 for x in items if x["tier"] == "high")
    n_med = sum(1 for x in items if x["tier"] == "med")
    print(f"  {c.RED_B}{n_high}{c.RST} high · {c.YEL_B}{n_med}{c.RST} med · "
          f"{c.GRY}{len(items)-n_high-n_med} low{c.RST}  out of {len(items)} functions")
    print()


def print_blame(items, target: str, c: C):
    matches = [it for it in items if it["name"] == target
               or it["name"].endswith("." + target) or it["name"].startswith(target + ".")]
    if not matches:
        print(f"  no match for {target!r}")
        sys.exit(2)
    print()
    for it in matches:
        tier_color = {"high": c.RED_B, "med": c.YEL_B, "low": c.GRY}[it["tier"]]
        loc = f"{it.get('file','?')}:{it.get('line','?')}"
        print(f"  {c.B}{it['name']}{c.RST}  {c.DIM}{loc}{c.RST}")
        print(f"  rank {it['rank']} of {it['of']}     "
              f"tier {tier_color}{it['tier']}{c.RST}     "
              f"score {it['score']:.3f}")
        print()
        print(f"    {c.DIM}centrality (call-graph hub){c.RST}      "
              f"p{it.get('centrality_pct', 50)}     "
              f"{c.DIM}({it['centrality']:.4f} raw){c.RST}")
        print(f"    {c.DIM}curvature (graph bottleneck){c.RST}    "
              f"p{it.get('curvature_pct', 50)}     "
              f"{c.DIM}({it['curvature']:+.3f} raw){c.RST}")
        dets = it.get('detectors') or []
        print(f"    {c.DIM}structural detectors{c.RST}             "
              f"{', '.join(dets) if dets else '(none)'}")
        print()
        if it["reasons"]:
            print(f"  {c.DIM}why it ranks here:{c.RST}")
            for r in it["reasons"]:
                print(f"    · {r}")
        else:
            print(f"  {c.DIM}no signal fired above p90 — ranked by composite residual.{c.RST}")
        print()


def save_scan(items, target_dir: Path) -> Path:
    out_dir = target_dir / ".plumbline"
    out_dir.mkdir(exist_ok=True)
    # Stable, sortable timestamp filename
    ts_path = out_dir / f"scan-latest.json"
    payload = {
        "target": str(target_dir),
        "ranking": items,
    }
    ts_path.write_text(json.dumps(payload, indent=2, default=str))
    return ts_path


# ---------- main -------------------------------------------------------------

def cmd_scan(args):
    target = Path(args.dir).resolve()
    if not target.exists():
        print(f"plumbline: no such path: {target}", file=sys.stderr)
        sys.exit(2)
    n_sol = sum(1 for p in target.rglob("*.sol")
                if "node_modules" not in p.parts and "test" not in p.parts)
    if n_sol == 0:
        print(f"plumbline: no .sol files under {target}", file=sys.stderr)
        sys.exit(2)

    c = C(enabled=_supports_color() and not args.no_color)
    t0 = time.time()
    files, fns, G, dets = analyze(str(target))
    items = rank(G, dets)
    scan_time = time.time() - t0

    if args.json:
        print(json.dumps({
            "target": str(target),
            "files": len(files),
            "functions": len(fns),
            "edges": G.number_of_edges(),
            "ranking": items,
        }, indent=2, default=str))
        return

    if args.blame:
        print_blame(items, args.blame, c)
        return

    if not args.quiet:
        print_human(items, len(files), len(fns), G.number_of_edges(),
                    args.top, scan_time, c, target)
    saved = save_scan(items, target)
    if not args.quiet:
        print(f"  full ranking: {c.DIM}{saved}{c.RST}")
        if items:
            print(f"  why is #1 here? {c.B}plumbline blame {items[0]['name']}{c.RST}")
            print()


def main():
    p = argparse.ArgumentParser(
        prog="plumbline",
        description="audit-priority scanner for Solidity",
    )
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("scan", help="rank functions by audit priority")
    sp.add_argument("dir", help="directory containing Solidity sources")
    sp.add_argument("--top", type=int, default=20, help="how many to show (default 20)")
    sp.add_argument("--blame", help="explain a single function's ranking")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.add_argument("--no-color", action="store_true", help="disable ANSI color")
    sp.add_argument("--quiet", action="store_true", help="ranked list only, no header/footer")

    sb = sub.add_parser("blame", help="alias for `scan --blame <fn>`")
    sb.add_argument("fn", help="Contract.function to explain")
    sb.add_argument("--dir", default=".", help="directory to scan (default .)")
    sb.add_argument("--no-color", action="store_true")

    args = p.parse_args()
    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "blame":
        # Find latest scan and reuse it if possible; else rescan
        target = Path(args.dir).resolve()
        cache = target / ".plumbline" / "scan-latest.json"
        if cache.exists():
            data = json.loads(cache.read_text())
            items = data["ranking"]
            c = C(enabled=_supports_color() and not args.no_color)
            print_blame(items, args.fn, c)
        else:
            args.blame = args.fn
            args.top = 20
            args.json = False
            args.quiet = False
            cmd_scan(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
