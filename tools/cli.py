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

        # Reasons in two parallel forms:
        #   - `reasons` (strings) for human rendering — keep for back-compat
        #   - `reasons_obj` (structured) for agent filtering — schema_version 1
        reasons = []
        reasons_obj = []
        if cent_pct >= 90:
            reasons.append(f"hub p{cent_pct}")
            reasons_obj.append({"kind": "hub", "percentile": cent_pct})
        if curv_pct >= 90 and curv < 0:
            reasons.append(f"curv p{curv_pct}")
            reasons_obj.append({"kind": "curv", "percentile": curv_pct, "raw": round(curv, 4)})
        for kind in det_by_node.get(n, []):
            tag = DETECTOR_LABELS.get(kind, kind)
            reasons.append(f"+{tag}")
            reasons_obj.append({"kind": "detector", "name": kind, "tag": tag})
        if mut in ("view", "pure"):
            reasons.append(f"-{mut}/2")
            reasons_obj.append({"kind": "demotion", "reason": mut, "factor": 0.5})

        items.append({
            "name": n,
            "score": score,
            "centrality": pr.get(n, 0),
            "curvature": curv,
            "centrality_pct": cent_pct,
            "curvature_pct": curv_pct,
            "reasons": reasons,
            "reasons_obj": reasons_obj,
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
    ts_path = out_dir / f"scan-latest.json"
    payload = {
        "target": str(target_dir),
        "ranking": items,
    }
    ts_path.write_text(json.dumps(payload, indent=2, default=str))
    return ts_path


def save_scan_payload(payload: dict, target_dir: Path) -> Path:
    """Save the full schema_version-1 payload (used by --json path)."""
    out_dir = target_dir / ".plumbline"
    out_dir.mkdir(exist_ok=True)
    ts_path = out_dir / "scan-latest.json"
    ts_path.write_text(json.dumps(payload, indent=2, default=str))
    return ts_path


# ---------- main -------------------------------------------------------------

def _sha256_dir(target: Path) -> str:
    """Stable hash over all .sol files under target (sorted by relpath).
    Identity for the directory's Solidity content — same files in, same hash out."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(target.rglob("*.sol")):
        if any(x in p.parts for x in ("node_modules", ".git")):
            continue
        rel = str(p.relative_to(target)).encode()
        h.update(rel + b"\x00")
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except (OSError, IOError):
            continue
    return h.hexdigest()


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

    # Idempotent scan: if --force not set, check whether the cached scan's
    # sha256_dir matches today's. If so, replay the cached result instantly.
    # Agent-side: a batch loop over 31 projects skips re-work after the first run.
    cache_path = target / ".plumbline" / "scan-latest.json"
    force = getattr(args, "force", False)
    current_sha = None
    if not force and cache_path.exists() and not args.blame:
        try:
            cached = json.loads(cache_path.read_text())
            if cached.get("sha256_dir"):
                current_sha = _sha256_dir(target)
                if cached["sha256_dir"] == current_sha:
                    if args.json:
                        cached["cache_hit"] = True
                        print(json.dumps(cached, indent=2, default=str))
                        return
                    # Human path: render from cache so the table still appears
                    items = cached["ranking"]
                    if not args.quiet:
                        print_human(items, cached["files"], cached["functions"],
                                    cached["edges"], args.top, 0.0, c, target)
                        print(f"  full ranking: {c.DIM}{cache_path} (cached){c.RST}")
                        if items:
                            print(f"  why is #1 here? {c.B}plumbline blame {items[0]['name']}{c.RST}")
                            print()
                    return
        except (json.JSONDecodeError, KeyError):
            pass  # fall through to fresh scan

    t0 = time.time()
    files, fns, G, dets = analyze(str(target))
    items = rank(G, dets)
    scan_time = time.time() - t0
    if current_sha is None:
        current_sha = _sha256_dir(target)

    payload = {
        "schema_version": 1,
        "command": "scan",
        "target": str(target),
        "sha256_dir": current_sha,
        "files": len(files),
        "functions": len(fns),
        "edges": G.number_of_edges(),
        "scan_time_s": round(scan_time, 3),
        "ranking": items,
    }

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        # still persist so blame/diff can read it
        save_scan_payload(payload, target)
        return

    if args.blame:
        print_blame(items, args.blame, c)
        return

    if not args.quiet:
        print_human(items, len(files), len(fns), G.number_of_edges(),
                    args.top, scan_time, c, target)
    saved = save_scan_payload(payload, target)
    if not args.quiet:
        print(f"  full ranking: {c.DIM}{saved}{c.RST}")
        if items:
            print(f"  why is #1 here? {c.B}plumbline blame {items[0]['name']}{c.RST}")
            print()


def cmd_corpus_ls(args):
    """List corpora in corpus/scabench/curated.json with rep counts."""
    from collections import defaultdict
    HERE = Path(__file__).resolve().parent.parent
    curated_path = HERE / 'corpus' / 'scabench' / 'curated.json'
    reps_path = HERE / 'reps.jsonl'
    if not curated_path.exists():
        print(json.dumps({"schema_version": 1, "error": "no corpus/scabench/curated.json"}))
        sys.exit(2)
    rep_counts = defaultdict(int)
    if reps_path.exists():
        for ln in open(reps_path):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            pid = r.get("contract", {}).get("project_id")
            if pid:
                rep_counts[pid] += 1
    curated = json.loads(curated_path.read_text())
    rows = []
    for p in curated:
        pid = p.get("project_id", "?")
        n_v = len(p.get("vulnerabilities", []))
        n_r = rep_counts.get(pid, 0)
        if args.untouched and n_r > 0:
            continue
        rows.append({
            "project_id": pid,
            "platform": p.get("platform"),
            "name": p.get("name"),
            "n_vulnerabilities": n_v,
            "n_reps": n_r,
        })
    rows.sort(key=lambda r: -r["n_vulnerabilities"])
    if args.json:
        print(json.dumps({
            "schema_version": 1,
            "command": "corpus.ls",
            "n_total": len(curated),
            "n_shown": len(rows),
            "rows": rows,
        }, indent=2, default=str))
    else:
        c = C(enabled=_supports_color() and not getattr(args, "no_color", False))
        for r in rows:
            mark = c.RED_B + "○" + c.RST if r["n_reps"] == 0 else c.GRY + "●" + c.RST
            print(f"  {mark}  {r['project_id']:50s}  {r['n_vulnerabilities']:>3} vulns  {r['n_reps']:>3} reps")


def cmd_run(args):
    """Fetch + scan + Ricci + log rep for one or more project_ids."""
    # Delegate to the existing research-loop runner; share its code rather
    # than re-import its main() so the CLI surface and the script stay aligned.
    import importlib.util
    HERE = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("run_ricci_signal", HERE / "run_ricci_signal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = [mod.run_one(pid) for pid in args.project_ids]
    if args.json:
        print(json.dumps({
            "schema_version": 1,
            "command": "run",
            "results": results,
        }, indent=2, default=str))


def cmd_reps_query(args):
    """Query reps.jsonl with filters. Returns matching rows + aggregate stats."""
    import statistics
    HERE = Path(__file__).resolve().parent.parent
    reps_path = HERE / "reps.jsonl"
    if not reps_path.exists():
        print(json.dumps({"schema_version": 1, "command": "reps.query", "rows": [], "n": 0}))
        return
    rows = []
    for ln in open(reps_path):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        # Filters
        contract = r.get("contract", {}) or {}
        corpus = contract.get("project_id") or os.path.basename(
            (contract.get("path") or "").rstrip("/"))
        if args.corpus and args.corpus not in corpus:
            continue
        proposer_kind = (r.get("proposer", {}) or {}).get("kind", "")
        if args.proposer and args.proposer not in proposer_kind:
            continue
        if args.leads_contain:
            leads = r.get("leads") or []
            if not any(args.leads_contain.lower() in str(l).lower() for l in leads):
                continue
        rows.append(r)
    rows = rows[-args.limit:] if args.limit > 0 else rows
    # Aggregate
    precs = [r["score"].get("precision") for r in rows if (r.get("score") or {}).get("precision") is not None]
    recs = [r["score"].get("recall") for r in rows if (r.get("score") or {}).get("recall") is not None]
    agg = {
        "n_total": len(rows),
        "precision_mean": round(statistics.mean(precs), 4) if precs else None,
        "precision_n": len(precs),
        "recall_mean": round(statistics.mean(recs), 4) if recs else None,
        "recall_n": len(recs),
    }
    if args.fields:
        # project to a subset of fields per rep to keep output small
        wanted = set(args.fields.split(","))
        slim = []
        for r in rows:
            slim_row = {}
            for k in wanted:
                if "." in k:
                    parts = k.split(".")
                    v = r
                    for part in parts:
                        v = (v or {}).get(part) if isinstance(v, dict) else None
                    slim_row[k] = v
                else:
                    slim_row[k] = r.get(k)
            slim.append(slim_row)
        rows = slim
    print(json.dumps({
        "schema_version": 1,
        "command": "reps.query",
        "filters": {"corpus": args.corpus, "proposer": args.proposer,
                    "leads_contain": args.leads_contain, "limit": args.limit},
        "aggregate": agg,
        "rows": rows,
    }, indent=2, default=str))


def cmd_diff(args):
    """Compare two scan outputs and report added/removed/moved rankings."""
    def _load(path_or_dir):
        p = Path(path_or_dir)
        if p.is_dir():
            p = p / ".plumbline" / "scan-latest.json"
        if not p.exists():
            print(json.dumps({"schema_version": 1, "command": "diff",
                              "error": f"no scan at {p}"}))
            sys.exit(2)
        return json.loads(p.read_text())
    a = _load(args.baseline)
    b = _load(args.target)
    items_a = a.get("ranking") or []
    items_b = b.get("ranking") or []
    rank_a = {it["name"]: it.get("rank", i + 1) for i, it in enumerate(items_a)}
    rank_b = {it["name"]: it.get("rank", i + 1) for i, it in enumerate(items_b)}
    names_a = set(rank_a)
    names_b = set(rank_b)
    added = sorted(names_b - names_a, key=lambda n: rank_b[n])[:50]
    removed = sorted(names_a - names_b, key=lambda n: rank_a[n])[:50]
    moved = []
    for name in names_a & names_b:
        delta = rank_a[name] - rank_b[name]   # positive = moved up
        if abs(delta) >= max(1, args.threshold):
            moved.append({"name": name, "from": rank_a[name], "to": rank_b[name], "delta": delta})
    moved.sort(key=lambda x: -abs(x["delta"]))
    print(json.dumps({
        "schema_version": 1,
        "command": "diff",
        "baseline": str(args.baseline),
        "target": str(args.target),
        "n_added": len(added),
        "n_removed": len(removed),
        "n_moved": len(moved),
        "added": added,
        "removed": removed,
        "moved": moved[:args.top],
    }, indent=2, default=str))


def cmd_surface(args):
    """Auto-generate a markdown report from reps + scans."""
    import statistics
    from collections import defaultdict
    HERE = Path(__file__).resolve().parent.parent
    reps_path = HERE / "reps.jsonl"
    if not reps_path.exists():
        print(json.dumps({"schema_version": 1, "command": "surface",
                          "error": "no reps.jsonl"}))
        sys.exit(2)
    by_corpus = defaultdict(list)
    for ln in open(reps_path):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        c = r.get("contract", {}) or {}
        key = c.get("project_id") or os.path.basename((c.get("path") or "?").rstrip("/"))
        by_corpus[key].append(r)
    lines = [f"# plumbline surface report",
             f"",
             f"Generated by `plumbline surface`. Total reps: {sum(len(v) for v in by_corpus.values())}. Corpora: {len(by_corpus)}.",
             f"",
             f"## Per-corpus aggregate (sorted by precision μ desc)",
             f"",
             f"| corpus | n | proposer kinds | precision μ±σ | recall μ±σ |",
             f"|---|---|---|---|---|"]
    rows = []
    for corpus, reps in sorted(by_corpus.items()):
        precs = [r["score"].get("precision") for r in reps if (r.get("score") or {}).get("precision") is not None]
        recs = [r["score"].get("recall") for r in reps if (r.get("score") or {}).get("recall") is not None]
        kinds = sorted({(r.get("proposer", {}) or {}).get("kind", "?") for r in reps})
        def _fmt(xs):
            if not xs:
                return "—"
            mu = statistics.mean(xs)
            if len(xs) == 1:
                return f"{mu:.2f}"
            return f"{mu:.2f}±{statistics.stdev(xs):.2f}"
        rows.append((statistics.mean(precs) if precs else -1, corpus, len(reps), kinds, _fmt(precs), _fmt(recs)))
    rows.sort(key=lambda r: -r[0])
    for _, corpus, n, kinds, ps, rs in rows:
        lines.append(f"| `{corpus}` | {n} | {', '.join(kinds)} | {ps} | {rs} |")
    out_path = Path(args.to)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "schema_version": 1,
        "command": "surface",
        "path": str(out_path),
        "n_corpora": len(by_corpus),
        "n_reps": sum(len(v) for v in by_corpus.values()),
        "bytes_written": out_path.stat().st_size,
    }, indent=2, default=str))


def main():
    p = argparse.ArgumentParser(
        prog="plumbline",
        description="audit-priority scanner for Solidity (agent-ergonomic: auto-JSON when stdout is piped)",
    )
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("scan", help="rank functions by audit priority")
    sp.add_argument("dir", help="directory containing Solidity sources")
    sp.add_argument("--top", type=int, default=20, help="how many to show (default 20)")
    sp.add_argument("--blame", help="explain a single function's ranking")
    sp.add_argument("--json", action="store_true", help="machine-readable output (auto-on when stdout is piped)")
    sp.add_argument("--no-color", action="store_true", help="disable ANSI color")
    sp.add_argument("--quiet", action="store_true", help="ranked list only, no header/footer")
    sp.add_argument("--force", action="store_true", help="bypass sha256_dir cache and re-scan")

    sb = sub.add_parser("blame", help="alias for `scan --blame <fn>`")
    sb.add_argument("fn", help="Contract.function to explain")
    sb.add_argument("--dir", default=".", help="directory to scan (default .)")
    sb.add_argument("--no-color", action="store_true")
    sb.add_argument("--json", action="store_true")

    sr = sub.add_parser("run", help="fetch + scan + Ricci + log rep for a scabench project_id")
    sr.add_argument("project_ids", nargs="+", help="one or more curated.json project_ids")
    sr.add_argument("--json", action="store_true", help="machine-readable output")

    sc = sub.add_parser("corpus", help="corpus operations (ls)")
    cs_sub = sc.add_subparsers(dest="corpus_cmd")
    csl = cs_sub.add_parser("ls", help="list scabench corpora with rep counts")
    csl.add_argument("--untouched", action="store_true", help="only show corpora with 0 reps")
    csl.add_argument("--json", action="store_true")
    csl.add_argument("--no-color", action="store_true")

    sq = sub.add_parser("reps", help="reps.jsonl operations (query)")
    sq_sub = sq.add_subparsers(dest="reps_cmd")
    sqq = sq_sub.add_parser("query", help="filter reps.jsonl with corpus/proposer/leads filters")
    sqq.add_argument("--corpus", default=None, help="substring match on corpus/project_id")
    sqq.add_argument("--proposer", default=None, help="substring match on proposer.kind")
    sqq.add_argument("--leads-contain", default=None, help="substring match in any lead string")
    sqq.add_argument("--limit", type=int, default=50, help="last N rows after filter (default 50)")
    sqq.add_argument("--fields", default=None,
                     help="comma-separated fields to project per rep (e.g. 'rep_id,contract.project_id,score.precision')")
    sqq.add_argument("--json", action="store_true")

    sd = sub.add_parser("diff", help="compare two scan outputs")
    sd.add_argument("baseline", help="path to baseline scan json or scan dir")
    sd.add_argument("target", help="path to target scan json or scan dir")
    sd.add_argument("--top", type=int, default=20, help="show top N moved (default 20)")
    sd.add_argument("--threshold", type=int, default=5, help="min rank delta to report (default 5)")
    sd.add_argument("--json", action="store_true")

    ss = sub.add_parser("surface", help="auto-generate a markdown report from reps + scans")
    ss.add_argument("--to", required=True, help="output markdown path")
    ss.add_argument("--json", action="store_true")

    args = p.parse_args()

    # Agent-ergonomic default: if stdout isn't a tty (piped / captured), the
    # caller is almost always a script or agent — emit JSON automatically so
    # they don't have to remember `--json` every time.
    if hasattr(args, "json") and not args.json and not sys.stdout.isatty():
        args.json = True

    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "blame":
        target = Path(args.dir).resolve()
        cache = target / ".plumbline" / "scan-latest.json"
        if cache.exists():
            data = json.loads(cache.read_text())
            items = data["ranking"]
            if args.json:
                match = [it for it in items if it["name"] == args.fn
                         or it["name"].endswith("." + args.fn)
                         or it["name"].startswith(args.fn + ".")]
                print(json.dumps({
                    "schema_version": 1,
                    "command": "blame",
                    "target": str(target),
                    "query": args.fn,
                    "matches": match,
                }, indent=2, default=str))
            else:
                c = C(enabled=_supports_color() and not args.no_color)
                print_blame(items, args.fn, c)
        else:
            args.blame = args.fn
            args.top = 20
            args.quiet = False
            cmd_scan(args)
    elif args.cmd == "run":
        cmd_run(args)
    elif args.cmd == "corpus":
        if args.corpus_cmd == "ls":
            cmd_corpus_ls(args)
        else:
            sc.print_help()
            sys.exit(1)
    elif args.cmd == "reps":
        if args.reps_cmd == "query":
            cmd_reps_query(args)
        else:
            sq.print_help()
            sys.exit(1)
    elif args.cmd == "diff":
        cmd_diff(args)
    elif args.cmd == "surface":
        cmd_surface(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
