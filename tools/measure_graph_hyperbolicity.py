"""
measure_graph_hyperbolicity — preliminary H14 smoke test.

Extract function call graphs from plumbline's corpora, compute Gromov
δ-hyperbolicity (4-point condition), compare against Erdős-Rényi
random graphs of same |V| and |E|. If δ_real << δ_random, that's
preliminary evidence that smart-contract call graphs are negatively
curved (hyperbolic), supporting H14's first premise.

NOT a proof of H14. Five corpora is N=5. Call graph is one of many
possible graph representations. δ-hyperbolicity is one of several
curvature measures. This is a 30-min smoke test, not a paper-grade
experiment.

H14 first premise: Smart-contract dependency graphs are δ-hyperbolic
with measurable δ ≤ k.

H14 second premise (NOT tested here): Bugs cluster at predictable
geometric positions within these graphs.

Usage:
  python3 tools/measure_graph_hyperbolicity.py
"""
from __future__ import annotations
import json
import random
import statistics
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))

# Reuse plumbline's existing tree-sitter Solidity parser
from structural_cascade import LANG, PARSER, parse_file


def extract_call_graph(sol_dir: Path) -> tuple[set[str], set[tuple[str, str]]]:
    """For all .sol files under sol_dir (excluding test/lib), return
    (nodes, edges) where node = '<Contract>.<function>' and edge = caller→callee.
    """
    SKIP = {"lib", "node_modules", "out", "cache", ".git", "test", "tests",
            "script", "scripts"}
    sol_files = []
    for p in sol_dir.rglob("*.sol"):
        if any(part in SKIP for part in p.parts):
            continue
        sol_files.append(p)

    nodes = set()
    edges = set()
    # First pass: collect all function nodes
    fn_table = {}  # short name → full qualified name (best-effort)
    for sol in sol_files:
        try:
            code, tree = parse_file(sol)
        except Exception:
            continue

        def walk(node, contract=None):
            if node.type in ("contract_declaration", "library_declaration",
                             "interface_declaration",
                             "abstract_contract_declaration"):
                name_node = next((c for c in node.named_children
                                  if c.type == "identifier"), None)
                cname = code[name_node.start_byte:name_node.end_byte].decode() \
                        if name_node else "?"
                for c in node.named_children:
                    walk(c, cname)
            elif node.type == "contract_body":
                for c in node.named_children:
                    walk(c, contract)
            elif node.type == "function_definition":
                name_node = next((c for c in node.named_children
                                  if c.type in ("identifier", "function_name")), None)
                fname = code[name_node.start_byte:name_node.end_byte].decode() \
                        if name_node else "?"
                qname = f"{contract}.{fname}" if contract else fname
                nodes.add(qname)
                fn_table[fname] = qname
                # Walk body for call expressions
                body_text = code[node.start_byte:node.end_byte].decode(
                    "utf-8", errors="replace")
                import re
                for m in re.finditer(r"\b(\w+)\s*\(", body_text):
                    callee = m.group(1)
                    if callee == fname:
                        continue
                    if callee in fn_table:
                        edges.add((qname, fn_table[callee]))
            else:
                for c in node.named_children:
                    walk(c, contract)
        walk(tree.root_node)

    # Second pass: resolve unresolved short names
    for sol in sol_files:
        try:
            code, tree = parse_file(sol)
        except Exception:
            continue

        def walk2(node, contract=None):
            if node.type in ("contract_declaration", "library_declaration",
                             "interface_declaration",
                             "abstract_contract_declaration"):
                name_node = next((c for c in node.named_children
                                  if c.type == "identifier"), None)
                cname = code[name_node.start_byte:name_node.end_byte].decode() \
                        if name_node else "?"
                for c in node.named_children:
                    walk2(c, cname)
            elif node.type == "contract_body":
                for c in node.named_children:
                    walk2(c, contract)
            elif node.type == "function_definition":
                name_node = next((c for c in node.named_children
                                  if c.type in ("identifier", "function_name")), None)
                fname = code[name_node.start_byte:name_node.end_byte].decode() \
                        if name_node else "?"
                qname = f"{contract}.{fname}" if contract else fname
                body_text = code[node.start_byte:node.end_byte].decode(
                    "utf-8", errors="replace")
                import re
                for m in re.finditer(r"\b(\w+)\s*\(", body_text):
                    callee = m.group(1)
                    if callee == fname or callee == qname:
                        continue
                    if callee in fn_table and fn_table[callee] != qname:
                        edges.add((qname, fn_table[callee]))
            else:
                for c in node.named_children:
                    walk2(c, contract)
        walk2(tree.root_node)

    return nodes, edges


def all_pairs_shortest_paths(nodes: list[str],
                             undirected_edges: set[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """BFS from every node. Returns dict (u,v) → distance, ∞ if disconnected
    (represented by -1)."""
    from collections import defaultdict, deque
    adj = defaultdict(set)
    for u, v in undirected_edges:
        adj[u].add(v); adj[v].add(u)
    dist = {}
    for src in nodes:
        seen = {src: 0}
        q = deque([src])
        while q:
            u = q.popleft()
            for w in adj[u]:
                if w not in seen:
                    seen[w] = seen[u] + 1
                    q.append(w)
        for w in nodes:
            dist[(src, w)] = seen.get(w, -1)
    return dist


def gromov_delta_4point(nodes: list[str],
                        dist: dict[tuple[str, str], int],
                        sample_cap: int = 50000) -> float | None:
    """4-point condition: for any 4 nodes a,b,c,d, sort the three sums
       S1=d(a,b)+d(c,d), S2=d(a,c)+d(b,d), S3=d(a,d)+d(b,c) descending.
       δ for this 4-tuple = (S1 - S2) / 2 (or 0 if (S1-S2) ≤ 0).
       Graph δ = max over all 4-tuples. Tree → 0. More hyperbolic → smaller δ.

       For |V| > 30 the full O(n^4) computation is impractical, so we
       SAMPLE up to sample_cap random 4-tuples. The max over a sample is a
       LOWER BOUND on the true δ — we may underestimate, never overestimate.
       Returns None if too few connected 4-tuples.

       Time bound: at most sample_cap iterations of constant-time work."""
    import math
    n = len(nodes)
    if n < 4:
        return None
    total_4tuples = math.comb(n, 4)
    rng = random.Random(0)
    max_delta = 0.0
    n_sampled = 0
    if total_4tuples <= sample_cap:
        # exact computation
        for a, b, c, d in combinations(nodes, 4):
            dab, dcd = dist[(a, b)], dist[(c, d)]
            dac, dbd = dist[(a, c)], dist[(b, d)]
            dad, dbc = dist[(a, d)], dist[(b, c)]
            if -1 in (dab, dcd, dac, dbd, dad, dbc):
                continue
            sums = sorted([dab + dcd, dac + dbd, dad + dbc], reverse=True)
            delta = (sums[0] - sums[1]) / 2.0
            if delta > max_delta:
                max_delta = delta
            n_sampled += 1
    else:
        # sampled computation
        seen = set()
        attempts = 0
        while n_sampled < sample_cap and attempts < sample_cap * 4:
            attempts += 1
            idx = tuple(sorted(rng.sample(range(n), 4)))
            if idx in seen:
                continue
            seen.add(idx)
            a, b, c, d = nodes[idx[0]], nodes[idx[1]], nodes[idx[2]], nodes[idx[3]]
            dab, dcd = dist[(a, b)], dist[(c, d)]
            dac, dbd = dist[(a, c)], dist[(b, d)]
            dad, dbc = dist[(a, d)], dist[(b, c)]
            if -1 in (dab, dcd, dac, dbd, dad, dbc):
                continue
            sums = sorted([dab + dcd, dac + dbd, dad + dbc], reverse=True)
            delta = (sums[0] - sums[1]) / 2.0
            if delta > max_delta:
                max_delta = delta
            n_sampled += 1
    if n_sampled == 0:
        return None
    return max_delta


def erdos_renyi_baseline(num_nodes: int, num_edges: int, rng: random.Random) -> set[tuple[int, int]]:
    """Generate a random graph with same |V|, |E|."""
    edges = set()
    if num_nodes < 2:
        return edges
    max_edges = num_nodes * (num_nodes - 1) // 2
    target = min(num_edges, max_edges)
    while len(edges) < target:
        u = rng.randrange(num_nodes)
        v = rng.randrange(num_nodes)
        if u == v:
            continue
        edges.add((min(u, v), max(u, v)))
    return edges


def measure_corpus(name: str, sol_dir: Path, trials: int = 5) -> dict:
    nodes_set, edges_dir = extract_call_graph(sol_dir)
    nodes = sorted(nodes_set)
    # Undirected edge set
    edges_undir = {(min(u, v), max(u, v)) for u, v in edges_dir if u != v}
    n_v = len(nodes)
    n_e = len(edges_undir)
    if n_v < 4:
        return {"name": name, "n_v": n_v, "n_e": n_e, "delta_real": None,
                "delta_random_mean": None, "ratio": None,
                "reason": "too few nodes for 4-point δ"}

    dist = all_pairs_shortest_paths(nodes, edges_undir)
    delta_real = gromov_delta_4point(nodes, dist)
    if delta_real is None:
        return {"name": name, "n_v": n_v, "n_e": n_e, "delta_real": None,
                "delta_random_mean": None, "ratio": None,
                "reason": "no connected 4-tuples"}

    rng = random.Random(42)
    randoms = []
    for _ in range(trials):
        random_edges_idx = erdos_renyi_baseline(n_v, n_e, rng)
        random_edges = {(nodes[u], nodes[v]) for u, v in random_edges_idx}
        rd = all_pairs_shortest_paths(nodes, random_edges)
        delta_r = gromov_delta_4point(nodes, rd)
        if delta_r is not None:
            randoms.append(delta_r)
    delta_random_mean = statistics.mean(randoms) if randoms else None
    ratio = (delta_real / delta_random_mean
             if delta_random_mean and delta_random_mean > 0 else None)
    return {"name": name, "n_v": n_v, "n_e": n_e,
            "delta_real": delta_real,
            "delta_random_mean": delta_random_mean,
            "delta_random_samples": randoms,
            "ratio": ratio,
            "reason": "OK"}


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
    for name, p in candidates:
        if not p.exists():
            print(f"skip {name}: {p} not found")
            continue
        print(f"measuring {name}...")
        r = measure_corpus(name, p)
        results.append(r)
        print(f"  |V|={r['n_v']:>3}  |E|={r['n_e']:>3}  "
              f"δ_real={str(r['delta_real']):>6}  "
              f"δ_random={str(round(r['delta_random_mean'],2) if r['delta_random_mean'] else '?'):>6}  "
              f"ratio={str(round(r['ratio'],3) if r['ratio'] else '?')}  "
              f"({r['reason']})")

    # Write a markdown summary
    out = HERE / "runs" / "2026-06-09-h14-graph-hyperbolicity"
    out.mkdir(parents=True, exist_ok=True)
    md = out / "results.md"
    with md.open("w") as f:
        f.write("# H14 smoke test — Gromov δ-hyperbolicity of plumbline call graphs\n\n")
        f.write("Generated 2026-06-09 by tools/measure_graph_hyperbolicity.py.\n\n")
        f.write("Compares Gromov δ-hyperbolicity (4-point condition) of each "
                "corpus's function call graph against Erdős-Rényi random graphs "
                "with same |V| and |E| (5 trials each).\n\n")
        f.write("**Interpretation:** δ=0 means tree-like (maximally hyperbolic). "
                "Higher δ means less hyperbolic. ratio < 1 means the real graph "
                "is MORE hyperbolic than random.\n\n")
        f.write("| Corpus | |V| | |E| | δ_real | δ_random (mean) | ratio | note |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            dr = r['delta_real']; dm = r['delta_random_mean']; rt = r['ratio']
            f.write(f"| {r['name']} | {r['n_v']} | {r['n_e']} | "
                    f"{dr if dr is not None else '—'} | "
                    f"{round(dm,2) if dm else '—'} | "
                    f"{round(rt,3) if rt else '—'} | {r['reason']} |\n")
        f.write("\n## Honest interpretation\n\n")
        ratios = [r['ratio'] for r in results
                  if r['ratio'] is not None]
        if ratios:
            mean_ratio = statistics.mean(ratios)
            f.write(f"Mean ratio across corpora with measurable δ: **{mean_ratio:.3f}**.\n\n")
            if mean_ratio < 0.7:
                f.write("**Preliminary signal: smart-contract call graphs in this "
                        "corpus ARE more hyperbolic than Erdős-Rényi baseline.** "
                        f"Mean δ_real is {mean_ratio:.1%} of random. This is consistent "
                        f"with H14's first premise. NOT proof — N={len(ratios)} corpora, "
                        f"single graph type (call graph), single curvature measure.\n")
            elif mean_ratio > 1.3:
                f.write("**Real call graphs are LESS hyperbolic than random.** This "
                        "REFUTES H14's first premise on this corpus.\n")
            else:
                f.write("**Inconclusive.** Call graphs and random graphs have similar "
                        "δ. Either premise is wrong or this measure is the wrong test.\n")
        else:
            f.write("No corpora had enough connected 4-tuples to measure δ. "
                    "Inconclusive.\n")
        f.write("\n## Caveats (in print before any claim)\n\n")
        f.write("- N=5 corpora is small; would need 30+ for statistical claim\n")
        f.write("- Call graph is one of many possible representations; "
                "data-flow / control-flow / inheritance / library-dependency graphs "
                "could give different curvature\n")
        f.write("- Tree-sitter-based call extraction is heuristic; misses dynamic "
                "dispatch, library functions, modifiers\n")
        f.write("- 4-point δ is one curvature measure; others (graph thickness, "
                "spectral gap, persistent homology) might disagree\n")
        f.write("- Even if call graphs are hyperbolic, this doesn't prove bugs "
                "cluster at predictable positions (H14's second premise)\n")
        f.write("- Erdős-Rényi is the most generous baseline; tree baseline would "
                "be harder to beat\n")
    print(f"\nWrote {md}")
    # Also save raw JSON
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
