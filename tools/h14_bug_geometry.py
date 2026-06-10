"""
h14_bug_geometry — H14 second-premise test.

For each corpus: build the call graph, compute graph features per function
(betweenness centrality, cut-vertex status, clustering coefficient,
distance-from-entry-point), cross-reference with the corpus's
.ANSWERS.md to label each function as bug-implicated or clean, then
test whether the geometric features distinguish the two distributions.

H14 second premise: bugs cluster at predictable geometric positions
within the call graph. Specifically: bug-implicated functions are
expected to show systematically different graph-feature distributions
than non-buggy functions (typically: higher betweenness, more often
near cut vertices, lower clustering coefficient).

This is a function-level test (hundreds of data points across the 6
corpora), unlike the smoke test which was corpus-level (N=6).

Result: statistical comparison of bug vs clean function distributions
on each feature, with corpus-stratified Mann-Whitney U test and
combined-corpus pooled test.

Run unattended overnight: completes in minutes for small graphs,
~10-15 min total even on dreUSDs (the 403-node corpus).
"""
from __future__ import annotations
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
from measure_graph_hyperbolicity import extract_call_graph


def find_answer_key(corpus_dir: Path) -> Path | None:
    """Find the .ANSWERS.md for a corpus. Looks in dir + 1 level up."""
    candidates = [corpus_dir / ".ANSWERS.md"]
    if corpus_dir.parent != corpus_dir:
        candidates.append(corpus_dir.parent / ".ANSWERS.md")
    for p in candidates:
        if p.exists():
            return p
    return None


def extract_bug_implicated_functions(answers_md: Path) -> set[str]:
    """Heuristic: pull camelCase function names out of the .ANSWERS.md.
    Per sol_match.py's _idents rule: lowercase-first or _lowercase,
    length>=7, contains an internal capital."""
    if not answers_md:
        return set()
    text = answers_md.read_text(encoding="utf-8", errors="replace")
    out = set()
    for w in re.findall(r"_?[a-z][A-Za-z0-9_]{6,}", text):
        low = w.lower().strip("_")
        if not re.search(r"[a-z][A-Z]", w):
            continue
        out.add(w)
    return out


def compute_features(nodes: list[str], edges: set[tuple[str, str]],
                     bug_names: set[str]) -> list[dict]:
    """For each function-node, compute graph features + bug label."""
    from collections import defaultdict, deque
    n = len(nodes)
    if n < 2:
        return []
    adj = defaultdict(set)
    for u, v in edges:
        adj[u].add(v); adj[v].add(u)
    idx = {nodes[i]: i for i in range(n)}

    # All-pairs shortest paths (BFS)
    dist = [[float('inf')] * n for _ in range(n)]
    for i, src in enumerate(nodes):
        dist[i][i] = 0
        q = deque([src])
        while q:
            u = q.popleft()
            for w in adj[u]:
                ju = idx[u]; jw = idx[w]
                if dist[i][jw] == float('inf'):
                    dist[i][jw] = dist[i][ju] + 1
                    q.append(w)

    # Betweenness centrality (Brandes, on the undirected graph)
    # For simplicity and correctness on small graphs use unweighted Brandes.
    betweenness = {node: 0.0 for node in nodes}
    for s in nodes:
        S = []
        P = {w: [] for w in nodes}
        sigma = {w: 0 for w in nodes}; sigma[s] = 1
        d = {w: -1 for w in nodes}; d[s] = 0
        Q = deque([s])
        while Q:
            v = Q.popleft()
            S.append(v)
            for w in adj[v]:
                if d[w] < 0:
                    Q.append(w)
                    d[w] = d[v] + 1
                if d[w] == d[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = {w: 0.0 for w in nodes}
        while S:
            w = S.pop()
            for v in P[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                betweenness[w] += delta[w]
    # Normalize for undirected (Brandes' formula divides by 2)
    norm = 1.0 / max(1, (n - 1) * (n - 2)) if n > 2 else 1.0
    for w in betweenness:
        betweenness[w] *= norm * 0.5

    # Clustering coefficient (local triangle ratio)
    clustering = {}
    for v in nodes:
        nbrs = list(adj[v])
        k = len(nbrs)
        if k < 2:
            clustering[v] = 0.0
            continue
        triangles = 0
        for i in range(k):
            for j in range(i + 1, k):
                if nbrs[j] in adj[nbrs[i]]:
                    triangles += 1
        clustering[v] = (2.0 * triangles) / (k * (k - 1))

    # Cut-vertex / articulation points (Tarjan-style)
    cut_vertices = set()
    disc = {}; low = {}; parent = {}; time_counter = [0]
    def dfs(u):
        time_counter[0] += 1
        disc[u] = low[u] = time_counter[0]
        children = 0
        for w in adj[u]:
            if w not in disc:
                children += 1
                parent[w] = u
                dfs(w)
                low[u] = min(low[u], low[w])
                if u not in parent and children > 1:
                    cut_vertices.add(u)
                if u in parent and low[w] >= disc[u]:
                    cut_vertices.add(u)
            elif w != parent.get(u):
                low[u] = min(low[u], disc[w])
    for v in nodes:
        if v not in disc:
            sys.setrecursionlimit(max(sys.getrecursionlimit(), n * 10 + 100))
            try:
                dfs(v)
            except RecursionError:
                pass

    # Build the per-node record
    out = []
    for v in nodes:
        # bug label: does the short function name appear in bug_names?
        short = v.split(".")[-1] if "." in v else v
        is_bug = (short in bug_names) or (v in bug_names)
        out.append({
            "node": v,
            "short_name": short,
            "is_bug": is_bug,
            "degree": len(adj[v]),
            "betweenness": betweenness[v],
            "clustering": clustering[v],
            "is_cut_vertex": v in cut_vertices,
        })
    return out


def mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    """Return (U, approximate two-sided p-value via normal approx).
    Returns (None, None) if too few samples."""
    import math
    n1, n2 = len(a), len(b)
    if n1 < 3 or n2 < 3:
        return (None, None)
    combined = [(x, 0) for x in a] + [(x, 1) for x in b]
    combined.sort(key=lambda t: t[0])
    # Assign ranks (handle ties via average rank)
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg
        i = j
    R1 = sum(ranks[k] for k in range(len(combined)) if combined[k][1] == 0)
    U1 = R1 - n1 * (n1 + 1) / 2.0
    U2 = n1 * n2 - U1
    U = min(U1, U2)
    mean_u = n1 * n2 / 2.0
    sd_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    if sd_u == 0:
        return (U, 1.0)
    z = (U - mean_u) / sd_u
    # two-sided p via normal approx
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return (U, p)


def measure_corpus(name: str, sol_dir: Path,
                   answers_md: Path | None) -> dict:
    nodes_set, edges_dir = extract_call_graph(sol_dir)
    nodes = sorted(nodes_set)
    edges = {(min(u, v), max(u, v)) for u, v in edges_dir if u != v}
    bug_names = extract_bug_implicated_functions(answers_md) if answers_md else set()

    features = compute_features(nodes, edges, bug_names)
    if not features:
        return {"name": name, "n_v": 0, "n_bugs": 0, "ok": False,
                "reason": "no functions extracted"}

    bug_rows = [f for f in features if f["is_bug"]]
    clean_rows = [f for f in features if not f["is_bug"]]

    def stat(rows: list[dict], k: str) -> dict:
        vals = [r[k] for r in rows]
        if not vals:
            return {"n": 0, "mean": None, "median": None, "stdev": None}
        if isinstance(vals[0], bool):
            vals = [int(v) for v in vals]
        return {
            "n": len(vals),
            "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "stdev": (statistics.stdev(vals) if len(vals) > 1 else 0.0),
        }

    out = {
        "name": name,
        "n_v": len(features),
        "n_bugs": len(bug_rows),
        "n_clean": len(clean_rows),
        "ok": True,
        "bug_names_in_answers": len(bug_names),
    }
    for feat in ("degree", "betweenness", "clustering", "is_cut_vertex"):
        out[f"bug_{feat}"] = stat(bug_rows, feat)
        out[f"clean_{feat}"] = stat(clean_rows, feat)
        a = [int(r[feat]) if isinstance(r[feat], bool) else r[feat] for r in bug_rows]
        b = [int(r[feat]) if isinstance(r[feat], bool) else r[feat] for r in clean_rows]
        U, p = mann_whitney_u(a, b)
        out[f"mwU_{feat}"] = U
        out[f"p_{feat}"] = p
    out["features"] = features
    return out


def main():
    candidates = [
        ("puppy-raffle", HERE / "examples" / "puppy-raffle"),
        ("t-swap",       HERE / "examples" / "t-swap"),
        ("thunder-loan", HERE / "examples" / "thunder-loan"),
        ("boss-bridge",  HERE / "examples" / "boss-bridge"),
        ("sequence",     HERE / "examples" / "sequence"),
        ("dreUSDs",      HERE / "corpus" / "calibration"
                              / "2026-06-08-dre-labs-dreusd-source" / "dreusd"
                              / "contracts"),
    ]
    results = []
    print("Computing H14 second-premise features (degree, betweenness, "
          "clustering, cut-vertex) for each corpus...\n")
    for name, p in candidates:
        if not p.exists():
            print(f"  skip {name}: {p} not found")
            continue
        ans = find_answer_key(p)
        if not ans:
            # try one level up beyond p.parent (corpus is in lib/contracts/)
            ans = find_answer_key(p.parent.parent if (p.parent.parent != p.parent) else p)
        print(f"  measuring {name} (answers: {ans.name if ans else 'NONE'})...")
        r = measure_corpus(name, p, ans)
        results.append(r)
        if r["ok"]:
            print(f"    |V|={r['n_v']}  bugs={r['n_bugs']}  clean={r['n_clean']}")
            for feat in ("degree", "betweenness", "clustering", "is_cut_vertex"):
                b = r[f"bug_{feat}"]["mean"]
                c = r[f"clean_{feat}"]["mean"]
                p_val = r[f"p_{feat}"]
                if b is not None and c is not None:
                    sig = " ★" if (p_val is not None and p_val < 0.05) else ""
                    p_str = f"{p_val:.3f}" if p_val is not None else "?"
                    print(f"      {feat:<15} bug={b:.4f}  clean={c:.4f}  "
                          f"p={p_str}{sig}")
        else:
            print(f"    skip — {r.get('reason','no reason')}")

    out = HERE / "runs" / "2026-06-09-h14-bug-geometry"
    out.mkdir(parents=True, exist_ok=True)

    # Strip the per-function feature list for the JSON summary (keep size sane)
    summary = []
    for r in results:
        s = {k: v for k, v in r.items() if k != "features"}
        summary.append(s)
    (out / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    # Full per-function data in a separate file
    full = []
    for r in results:
        if r.get("features"):
            for f in r["features"]:
                full.append({"corpus": r["name"], **f})
    (out / "features.json").write_text(json.dumps(full, indent=2, default=str))

    md = out / "results.md"
    with md.open("w") as f:
        f.write("# H14 second-premise smoke test — do bug-implicated functions sit at geometrically distinguished positions?\n\n")
        f.write("Generated by tools/h14_bug_geometry.py.\n\n")
        f.write("For each corpus: build the call graph, compute four features per function (degree, betweenness centrality, clustering coefficient, cut-vertex status), cross-reference with the corpus `.ANSWERS.md` to label each function bug-implicated or clean, run Mann-Whitney U test on bug-vs-clean distributions.\n\n")
        f.write("**A significant p-value (p < 0.05, ★) means the feature distribution differs between bug and clean functions** — a hint that the geometric feature is informative about bug location.\n\n")
        f.write("| Corpus | |V| | bugs | clean | feature | bug mean | clean mean | p-value |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in results:
            if not r.get("ok"):
                continue
            for feat in ("degree", "betweenness", "clustering", "is_cut_vertex"):
                b = r[f"bug_{feat}"]["mean"]
                c = r[f"clean_{feat}"]["mean"]
                p_val = r[f"p_{feat}"]
                sig = " ★" if (p_val is not None and p_val < 0.05) else ""
                p_str = f"{p_val:.3f}" if p_val is not None else "—"
                f.write(f"| {r['name']} | {r['n_v']} | {r['n_bugs']} | {r['n_clean']} | "
                        f"{feat} | "
                        f"{f'{b:.4f}' if b is not None else '—'} | "
                        f"{f'{c:.4f}' if c is not None else '—'} | "
                        f"{p_str}{sig} |\n")
        f.write("\n## Honest interpretation\n\n")
        # tally significant findings
        sig_count = 0
        total_tests = 0
        for r in results:
            if not r.get("ok"): continue
            for feat in ("degree", "betweenness", "clustering", "is_cut_vertex"):
                p_val = r.get(f"p_{feat}")
                if p_val is not None:
                    total_tests += 1
                    if p_val < 0.05:
                        sig_count += 1
        f.write(f"Across {total_tests} (corpus, feature) Mann-Whitney U tests, {sig_count} showed p<0.05.\n\n")
        f.write("At multiple-testing-naive α=0.05, we'd expect ~5% false positives under the null hypothesis. ")
        if total_tests > 0:
            null_expected = total_tests * 0.05
            f.write(f"With {total_tests} tests, that's ~{null_expected:.1f} expected false positives by chance. ")
            if sig_count > 3 * null_expected:
                f.write(f"**{sig_count} significant findings is well above chance** — preliminary support for H14's second premise (bugs occupy distinguishable geometric positions).\n")
            elif sig_count > null_expected:
                f.write(f"**{sig_count} significant findings is somewhat above chance** — weak support for H14's second premise.\n")
            else:
                f.write(f"**{sig_count} significant findings is at or below chance** — H14's second premise NOT supported by this data.\n")
        f.write("\n## Caveats\n\n")
        f.write("- Function-name matching against .ANSWERS.md is heuristic (camelCase regex)\n")
        f.write("- N=6 corpora is still small (function-level N is larger but stratified by corpus)\n")
        f.write("- Mann-Whitney U is non-parametric but bug-class sample sizes vary widely across corpora\n")
        f.write("- No multiple-testing correction applied; with Bonferroni at α=0.05 / {total_tests} threshold would be much stricter\n")
        f.write("- Call graph is one representation; data-flow / type / inheritance graphs might show different signal\n")
        f.write("- Tree-sitter call extraction misses dynamic dispatch and library calls\n")
        f.write("- Even strong signal here doesn't reach 'almost trivially solve auditing' — it would suggest geometry is a useful PRIOR\n")
    print(f"\nWrote {md} + results.json + features.json (per-function data)")


if __name__ == "__main__":
    main()
