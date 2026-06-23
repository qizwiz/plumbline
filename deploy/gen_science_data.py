"""
Generate REAL graph + heat-diffusion data for deploy/science.html.

Everything here uses plumbline's OWN tooling on a REAL example protocol:
  - sol_graph.rich_graph(fns, files)  -> the actual function/state/modifier graph
  - personalized-PageRank / random-walk-with-restart heat field, computed with the
    IDENTICAL formula used in geom_dirichlet_probe.py:
        heat = (1-alpha) * (I - alpha * P^T)^-1 * s     (P row-stochastic adjacency)
    i.e. solve  (I - alpha*A_norm) u = (1-alpha) s   -- heat spreading from seeds.

No fabrication: nodes/edges come straight from tree-sitter parsing of the .sol source;
heat comes straight from numpy solving the diffusion linear system over that graph.

Run:  .venv/bin/python deploy/gen_science_data.py
"""
import json
import os
import sys

import networkx as nx
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import sol_graph as sg  # noqa: E402

# --- pick ONE real example protocol: boss-bridge (small, well-known public bugs) ---
EX = os.path.join(ROOT, "examples", "boss-bridge")
ALPHA = 0.85  # same restart strength as geom_dirichlet_probe.py


def parse_core(root):
    """Parse only the protocol's OWN .sol files (skip out/ artifacts & tests)."""
    from tree_sitter import Parser
    p = Parser(sg.LANG)
    files = {}
    for f in sorted(os.listdir(root)):
        if f.endswith(".sol") and not f.endswith(".t.sol"):
            full = os.path.join(root, f)
            src = open(full, "rb").read()
            files[f] = p.parse(src).root_node
    return files


def heat_field(G, fn_nodes, seed_id, alpha=ALPHA):
    """Random-walk-with-restart / personalized PageRank heat from a single seed.
    Identical math to geom_dirichlet_probe.py: (I - alpha P^T) u = (1-alpha) s."""
    nodes = list(G.nodes())
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    A = nx.to_numpy_array(G, nodelist=nodes)
    deg = A.sum(1)
    P = A / np.where(deg[:, None] == 0, 1, deg[:, None])  # row-stochastic
    s = np.zeros(N)
    s[idx[seed_id]] = 1.0
    heat = (1 - alpha) * np.linalg.solve(np.eye(N) - alpha * P.T, s)
    h = {n: float(heat[idx[n]]) for n in nodes}
    return h


def main():
    files = parse_core(EX)
    fns = sg.collect_functions(files)
    # call_graph mutates ids (overload suffixes); call it so rich_graph ids match what we report
    sg.call_graph(fns)
    G = sg.rich_graph(fns, files)

    fn_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "fn"]

    # honest seed: the famous boss-bridge bug — depositTokensToL2 takes an arbitrary
    # `from`, so anyone can move another user's approved tokens into the vault and mint
    # themselves L2 tokens (CodeHawks "First Flight" #1 high). It is a real fn node.
    seed_id = next((n for n in fn_nodes if n.endswith(".depositTokensToL2")), None)
    if seed_id is None:  # safety fallback to a present hub
        seed_id = max(fn_nodes, key=lambda n: G.degree(n))

    # precompute the converged heat field from that seed
    heat = heat_field(G, fn_nodes, seed_id)
    # also compute degree (the baseline heat-diffusion BEATS) for honest comparison
    deg = {n: G.degree(n) for n in G.nodes()}

    # Build a compact, fully self-describing JSON the front-end can animate.
    # Pre-solve heat from EVERY fn node so click-to-reseed stays offline (no server math).
    heat_by_seed = {n: heat_field(G, fn_nodes, n) for n in fn_nodes}

    def kind_of(n):
        return G.nodes[n].get("kind", "fn")

    def label_of(n):
        d = G.nodes[n]
        if d.get("kind") == "fn":
            return n.split(".")[-1]          # function name
        if d.get("kind") == "state":
            return n.split(".")[-1]          # state var name
        if d.get("kind") == "mod":
            return n.replace("mod::", "")    # modifier name
        return n

    nodes_out = []
    for n in G.nodes():
        d = G.nodes[n]
        nodes_out.append({
            "id": n,
            "label": label_of(n),
            "kind": kind_of(n),
            "contract": d.get("contract", ""),
            "vis": d.get("vis", ""),
            "mut": d.get("mut", ""),
            "line": d.get("line", None),
            "degree": deg[n],
            "is_fn": kind_of(n) == "fn",
            "heat": heat.get(n, 0.0),
        })

    edges_out = []
    for u, v, d in G.edges(data=True):
        edges_out.append({"source": u, "target": v, "etype": d.get("etype", "")})

    # call_graph (sparse) numbers for the honest "rich graph beats sparse" contrast
    CG = sg.call_graph(fns)

    data = {
        "meta": {
            "protocol": "boss-bridge",
            "source": "examples/boss-bridge (Cyfrin CodeHawks First Flight)",
            "generator": "plumbline sol_graph.rich_graph + numpy RWR heat solve",
            "files": sorted(files.keys()),
            "n_functions": len(fn_nodes),
            "n_nodes": G.number_of_nodes(),
            "n_edges": G.number_of_edges(),
            "call_graph_nodes": CG.number_of_nodes(),
            "call_graph_edges": CG.number_of_edges(),
            "alpha": ALPHA,
            "seed_id": seed_id,
            "seed_label": label_of(seed_id),
            "seed_why": ("depositTokensToL2 accepts an arbitrary `from` address — any "
                         "caller can pull another user's approved tokens into the vault "
                         "and mint themselves L2 tokens (boss-bridge High #1)."),
            "heat_formula": "(I - alpha*A_norm) u = (1-alpha) s",
            "heat_method": "personalized PageRank / random-walk-with-restart (numpy linalg.solve)",
            # headline numbers measured across the full corpus by geom_dirichlet_probe.py
            "corpus_auc_heat": 0.79,
            "corpus_auc_null": 0.48,
            "corpus_protocols": 16,
            "corpus_functions": 5030,
        },
        "nodes": nodes_out,
        "edges": edges_out,
        "heat_by_seed": heat_by_seed,
    }

    out = os.path.join(HERE, "science_data.json")
    with open(out, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"wrote {out}")
    print(f"  protocol=boss-bridge  rich_graph={G.number_of_nodes()}n/{G.number_of_edges()}e "
          f"(fn nodes={len(fn_nodes)})  call_graph={CG.number_of_nodes()}n/{CG.number_of_edges()}e")
    print(f"  seed={seed_id}")
    top = sorted(fn_nodes, key=lambda n: heat[n], reverse=True)[:6]
    print("  top heat fn nodes:", [(n.split('.')[-1], round(heat[n], 4)) for n in top])


if __name__ == "__main__":
    main()
