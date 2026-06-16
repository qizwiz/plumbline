"""
tools/run_ricci_signal.py — Phase 0/1 Ricci-signal-check runner.

Pipeline per project:
  1. Look up project in corpus/scabench/curated.json by project_id
  2. Fetch + extract source tarball into /tmp/plumbline-ricci/<project_id>/
  3. Run sol_graph -> NetworkX call graph
  4. Compute Ollivier-Ricci curvature (greedy 1-Wasserstein on shortest-path metric)
  5. Cross-reference against ground-truth vuln-bearing contracts (from curated.json)
  6. Compute precision@K (K=10, 20, 50) for: ricci-low, pagerank-high, random
  7. Log a plumbline rep with project_id + score dict
  8. Print headline lift numbers

Usage:
  python tools/run_ricci_signal.py code4rena_loopfi_2025_02 [code4rena_iq-ai_2025_03 ...]

Each project_id is one rep written to reps.jsonl.
"""
from __future__ import annotations
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import networkx as nx
from sol_graph import analyze
from rep_log import write_rep, sha256_dir

CURATED = ROOT / 'corpus' / 'scabench' / 'curated.json'
CACHE_DIR = Path('/tmp/plumbline-ricci')


def fetch_project(project_id: str) -> Path:
    """Download + extract the project's source tarball. Returns the src/ dir.

    Prefers 'src/' subdirectory if present; falls back to project root.
    Cached: skips download if directory already exists.
    """
    curated = json.loads(CURATED.read_text())
    matches = [p for p in curated if p['project_id'] == project_id]
    if not matches:
        raise SystemExit(f"unknown project_id: {project_id}")
    proj = matches[0]
    cb = proj['codebases'][0]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    proj_dir = CACHE_DIR / project_id
    tarball = CACHE_DIR / f"{project_id}.tar.gz"

    if not proj_dir.exists():
        if not tarball.exists():
            print(f"  [fetch] {cb['tarball_url']}")
            subprocess.run(
                ['curl', '-sL', cb['tarball_url'], '-o', str(tarball)],
                check=True,
            )
        print(f"  [extract] -> {proj_dir}")
        proj_dir.mkdir()
        subprocess.run(
            ['tar', 'xzf', str(tarball), '-C', str(proj_dir), '--strip-components=1'],
            check=True,
        )

    # Find Solidity source root: prefer src/, contracts/, or first dir with many .sol
    candidates = [proj_dir / 'src', proj_dir / 'contracts', proj_dir]
    for c in candidates:
        if c.exists():
            n_sol = sum(1 for p in c.rglob('*.sol')
                        if 'node_modules' not in p.parts and 'test' not in p.parts)
            if n_sol >= 3:
                return c
    raise SystemExit(f"no Solidity src found in {proj_dir}")


def extract_vuln_targets(project_id: str) -> dict:
    """Pull ground-truth function/contract mentions from curated.json findings."""
    curated = json.loads(CURATED.read_text())
    proj = [p for p in curated if p['project_id'] == project_id][0]
    contract_mentions = set()
    fn_mentions = set()
    precise_locs = set()
    for v in proj['vulnerabilities']:
        text = (v.get('title', '') + ' ' + v.get('description', ''))
        for m in re.finditer(r'([A-Z][A-Za-z0-9]+)\.sol#?(\w+)?\b', text):
            contract_mentions.add(m.group(1))
            if m.group(2):
                precise_locs.add((m.group(1), m.group(2)))
                fn_mentions.add(m.group(2))
        for m in re.finditer(r'([A-Z][A-Za-z0-9]+)::(\w+)', text):
            contract_mentions.add(m.group(1))
            precise_locs.add((m.group(1), m.group(2)))
            fn_mentions.add(m.group(2))
    return {
        'n_findings': len(proj['vulnerabilities']),
        'contract_mentions': contract_mentions,
        'fn_mentions': fn_mentions,
        'precise_locs': precise_locs,
    }


def ollivier_ricci_node_avg(G):
    """OR curvature per edge via greedy 1-Wasserstein, aggregated to nodes (mean)."""
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

    def neighbors_mass(u, alpha=0.5):
        nbrs = list(UG.neighbors(u))
        if not nbrs:
            return {u: 1.0}
        m = {u: alpha}
        share = (1 - alpha) / len(nbrs)
        for n in nbrs:
            m[n] = share
        return m

    def wasserstein_greedy(m1, m2):
        items1 = list(m1.items())
        demand = dict(m2)
        total = 0.0
        for u, s_u in items1:
            if s_u <= 0:
                continue
            sorted_v = sorted(demand.keys(), key=lambda v: sp(u, v))
            remaining = s_u
            for v in sorted_v:
                if remaining <= 1e-9:
                    break
                d_v = demand.get(v, 0)
                if d_v <= 0:
                    continue
                take = min(remaining, d_v)
                total += take * sp(u, v)
                demand[v] -= take
                remaining -= take
        return total

    edge_curvs = {}
    for u, v in UG.edges():
        d = sp(u, v)
        if d == 0:
            edge_curvs[(u, v)] = 0.0
            continue
        w = wasserstein_greedy(neighbors_mass(u), neighbors_mass(v))
        edge_curvs[(u, v)] = 1 - (w / d)

    node_curvs = {}
    for n in UG.nodes():
        incident = [k for (u, v), k in edge_curvs.items() if u == n or v == n]
        node_curvs[n] = sum(incident) / len(incident) if incident else 0.0
    return node_curvs


def precision_at_k(ranking, vuln_set, K):
    top_k = ranking[:K]
    hits = sum(1 for n in top_k if n in vuln_set)
    return hits / K


def run_one(project_id: str) -> dict:
    print(f"\n=== {project_id} ===")
    src_dir = fetch_project(project_id)
    print(f"  src: {src_dir}")

    files, fns, G, dets = analyze(str(src_dir))
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    print(f"  graph: {len(files)} files, {len(fns)} fns, {n_nodes} nodes / {n_edges} edges")

    gt = extract_vuln_targets(project_id)
    print(f"  findings: {gt['n_findings']}  contracts: {len(gt['contract_mentions'])}")

    vuln_nodes = set()
    for n in G.nodes():
        if '.' in n:
            c = n.split('.', 1)[0]
            if c in gt['contract_mentions']:
                vuln_nodes.add(n)
    base_rate = len(vuln_nodes) / max(1, n_nodes)
    print(f"  vuln-bearing nodes: {len(vuln_nodes)}/{n_nodes} (base rate {base_rate:.3f})")

    if len(vuln_nodes) == 0:
        print("  SKIP: no ground-truth contract matches in graph (regex miss)")
        return {'project_id': project_id, 'status': 'no_gt_match'}

    pr = nx.pagerank(G)
    UG = G.to_undirected()
    if not nx.is_connected(UG):
        largest = max(nx.connected_components(UG), key=len)
        G_sub = G.subgraph(largest).copy()
        print(f"  ricci-on largest component: {len(largest)}/{n_nodes} nodes")
    else:
        G_sub = G
    node_curvs = ollivier_ricci_node_avg(G_sub)

    ricci_low = sorted(node_curvs, key=lambda n: node_curvs[n])
    pr_high = sorted(pr, key=lambda n: pr[n], reverse=True)
    random.seed(0)
    rand_order = random.sample(list(G.nodes()), n_nodes)

    p_at_K = {}
    for K in [10, 20, 50]:
        p_at_K[K] = {
            'ricci_low': precision_at_k(ricci_low, vuln_nodes, K),
            'pagerank': precision_at_k(pr_high, vuln_nodes, K),
            'random': precision_at_k(rand_order, vuln_nodes, K),
            'base_rate': base_rate,
        }
        lift = p_at_K[K]['ricci_low'] / max(p_at_K[K]['random'], 1e-9)
        print(f"  K={K:3d}  ricci={p_at_K[K]['ricci_low']:.3f}  "
              f"pagerank={p_at_K[K]['pagerank']:.3f}  "
              f"random={p_at_K[K]['random']:.3f}  "
              f"lift={lift:.2f}x")

    # Log rep
    row = {
        'contract': {
            'path': str(src_dir),
            'sha256_dir': sha256_dir(str(src_dir)),
            'project_id': project_id,
        },
        'proposer': {
            'kind': 'ricci-curvature-rank',
            'version': 'phase0-day2-v2',
            'model': None,
        },
        'leads': [n for n in ricci_low[:10]],
        'verifier': {
            'kind': 'precision-at-k-vs-baseline',
            'result': {str(K): v for K, v in p_at_K.items()},
        },
        'score': {
            'recall': None,
            'precision': p_at_K[50]['ricci_low'],
            'k': 50,
            'lift_over_random': p_at_K[50]['ricci_low'] / max(p_at_K[50]['random'], 1e-9),
            'lift_over_pagerank': p_at_K[50]['ricci_low'] / max(p_at_K[50]['pagerank'], 1e-9),
            'base_rate': base_rate,
        },
        'ground_truth_path': str(CURATED),
        'notes': f'Phase 0 Day 2 multi-project. Greedy Wasserstein OR. {n_nodes}n/{n_edges}e graph.',
    }
    written = write_rep(row)
    print(f"  -> rep {written['rep_id']}")
    return {
        'project_id': project_id,
        'status': 'ok',
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'base_rate': base_rate,
        'p_at_K': p_at_K,
    }


def main():
    project_ids = sys.argv[1:]
    if not project_ids:
        print("usage: run_ricci_signal.py <project_id> [<project_id> ...]")
        sys.exit(1)

    results = []
    for pid in project_ids:
        try:
            results.append(run_one(pid))
        except Exception as e:
            print(f"  FAIL: {e}")
            results.append({'project_id': pid, 'status': 'error', 'error': str(e)})

    print("\n=== SUMMARY: Ricci lift over random by K ===")
    print(f"  {'project':50s}  {'K=10':>8s}  {'K=20':>8s}  {'K=50':>8s}")
    for r in results:
        if r['status'] != 'ok':
            print(f"  {r['project_id']:50s}  -- {r['status']}")
            continue
        lift10 = r['p_at_K'][10]['ricci_low'] / max(r['p_at_K'][10]['random'], 1e-9)
        lift20 = r['p_at_K'][20]['ricci_low'] / max(r['p_at_K'][20]['random'], 1e-9)
        lift50 = r['p_at_K'][50]['ricci_low'] / max(r['p_at_K'][50]['random'], 1e-9)
        print(f"  {r['project_id']:50s}  {lift10:>6.2f}x  {lift20:>6.2f}x  {lift50:>6.2f}x")


if __name__ == '__main__':
    main()
