"""
structural_cascade — compose tree-sitter, NetworkX, embedding NN, and
TLA+ shape match into one deterministic pipeline.

Closes the gap between sol_intent's 0.42 cold recall and the 0.94 corpus
ceiling measured in CALIBRATION_SHERLOCK_SWEEP.md. Each layer narrows
the search space, so expensive layers (TLA+ / halmos) only see
candidates that survived cheap filters.

Five layers, ordered cheap-to-expensive:

  Layer A: tree-sitter Solidity queries for known structural shapes
           (external-call-before-write, permit-without-nonce, etc.)
  Layer B: NetworkX call graph — reachable from public/external entry
  Layer C: embedding nearest-neighbor against the 1240-finding corpus
  Layer D: TLA+ shape heuristic match
  Layer E: halmos symbolic discharge (skipped if scope doesn't build)

Per prompts/goals/STRUCTURAL_CASCADE.goal.md.

Usage:
  python tools/structural_cascade.py examples/sequence/ --out cascade.jsonl

Cost: $0 (no LLM calls; all layers deterministic).
"""
from __future__ import annotations
import argparse, glob, json, os, pickle, re, sys
from pathlib import Path

import tree_sitter
import tree_sitter_solidity as tssol
import networkx as nx
import numpy as np

HERE = Path(__file__).resolve().parent.parent
INDEX_PATH = HERE / "tools" / "findings_index.pkl"
SHAPES = ["SignatureReplay", "ReentrancyDrain", "ERC4337StaticSigDoS",
          "Uint64FeeOverflow", "Create2NonIdempotent", "PartialSignatureReplay",
          "CrossWalletSigReplay", "FlagBypassesValidationChain", "MissingAwait"]

# ============================================================
# Layer A: tree-sitter Solidity structural queries
# ============================================================

LANG = tree_sitter.Language(tssol.language())
PARSER = tree_sitter.Parser(LANG)


def parse_file(path: Path) -> tuple[bytes, tree_sitter.Tree]:
    code = path.read_bytes()
    return code, PARSER.parse(code)


def extract_functions(code: bytes, tree: tree_sitter.Tree,
                      path: Path) -> list[dict]:
    """Walk AST → list of function records with text, line ranges, modifiers."""
    out = []
    def walk(node, contract_name=None):
        if node.type == "contract_declaration":
            # Find contract name
            name_node = next((c for c in node.named_children
                              if c.type == "identifier"), None)
            cname = code[name_node.start_byte:name_node.end_byte].decode() \
                    if name_node else None
            for c in node.named_children:
                walk(c, cname)
        elif node.type == "contract_body":
            for c in node.named_children:
                walk(c, contract_name)
        elif node.type == "function_definition":
            name_node = next((c for c in node.named_children
                              if c.type in ("identifier", "function_name")), None)
            fname = code[name_node.start_byte:name_node.end_byte].decode() \
                    if name_node else "<unknown>"
            body_text = code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            out.append({
                "file": str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path),
                "contract": contract_name,
                "function": fname,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "text": body_text,
                "ast_hits": [],
            })
        else:
            for c in node.named_children:
                walk(c, contract_name)
    walk(tree.root_node)
    return out


# Layer A queries — pattern is intentionally coarse (filter, not verdict)
A_QUERIES = {
    "external_call": re.compile(
        r"\.(call|delegatecall|staticcall|transfer|send)\s*\(", re.M),
    "low_level_call_unchecked": re.compile(
        r"^\s*[^=\s]*\.(call|delegatecall)\s*\(.*?\)\s*;\s*$", re.M),
    "state_write_after_call": re.compile(
        r"\.(call|transfer|send)\s*\(.*?\)\s*;.*?\b\w+\s*[+\-*/]?=", re.S),
    "permit_call": re.compile(r"\bpermit\s*\(", re.M),
    "create2": re.compile(r"\bcreate2\s*\(|\bnew\s+\w+\{salt:", re.M),
    "unbounded_for": re.compile(
        r"for\s*\(.*?;.*?\b(\w+\.length|\w+s)\b\s*[;)]", re.S),
    "msg_sender_in_validation": re.compile(r"msg\.sender", re.M),
    "ecrecover": re.compile(r"\becrecover\s*\(", re.M),
    "self_call": re.compile(r"\bthis\.\w+\(", re.M),
    "raw_assembly": re.compile(r"\bassembly\s*\{", re.M),
}


def layer_a(functions: list[dict]) -> list[dict]:
    """Apply tree-sitter-extracted regex queries to function bodies.
    Function survives if it has ≥1 structural hit. ast_hits records which."""
    survivors = []
    for f in functions:
        hits = []
        for name, pat in A_QUERIES.items():
            if pat.search(f["text"]):
                hits.append(name)
        if hits:
            f["ast_hits"] = hits
            survivors.append(f)
    return survivors


# ============================================================
# Layer B: NetworkX call graph + public-reachability
# ============================================================

VISIBILITY_PAT = re.compile(r"\bfunction\s+\w+\s*\([^)]*\)\s*[^{]*?"
                             r"(external|public)\b", re.S)
CALL_PAT = re.compile(r"\b([a-z][a-zA-Z0-9_]*)\s*\(", re.M)


def build_call_graph(all_functions: list[dict]) -> nx.DiGraph:
    """Best-effort call graph from regex over function text. Slither would
    be more precise but adds build dependency; this is good enough for v1."""
    G = nx.DiGraph()
    by_name = {}
    for f in all_functions:
        node = f"{f['contract']}.{f['function']}" if f['contract'] else f['function']
        f["node"] = node
        G.add_node(node, **f)
        by_name.setdefault(f["function"], []).append(node)
    for f in all_functions:
        for call_name in set(CALL_PAT.findall(f["text"])):
            for callee in by_name.get(call_name, []):
                if callee != f["node"]:
                    G.add_edge(f["node"], callee)
    return G


def layer_b(layer_a_survivors: list[dict],
            all_functions: list[dict], G: nx.DiGraph) -> list[dict]:
    """Keep Layer A survivors reachable from a public/external entry point."""
    # Find public entry points
    entries = set()
    for f in all_functions:
        if VISIBILITY_PAT.search(f["text"]):
            entries.add(f["node"])
    if not entries:
        # Conservative: no visibility detected → treat all as entries
        entries = {f["node"] for f in all_functions}
    # Reverse BFS: which nodes are reachable from any entry?
    reachable = set(entries)
    for e in entries:
        if e in G:
            reachable.update(nx.descendants(G, e))
    survivors = []
    for f in layer_a_survivors:
        if f["node"] in reachable:
            f["cfg_reachable_from_public"] = True
            f["distance_from_entry"] = (
                0 if f["node"] in entries
                else min((nx.shortest_path_length(G, e, f["node"])
                          for e in entries if nx.has_path(G, e, f["node"])),
                         default=999))
            survivors.append(f)
    return survivors


# ============================================================
# Layer C: embedding nearest-neighbor in corpus
# ============================================================

def layer_c(survivors: list[dict], cos_threshold: float = 0.55) -> list[dict]:
    """For each surviving function, embed (signature + body[:1000]) and find
    nearest neighbor in tools/findings_index.pkl. Keep if cos > threshold."""
    sys.path.insert(0, str(HERE / "tools"))
    import spec_retrieval as sr
    from fastembed import TextEmbedding

    d = pickle.load(open(INDEX_PATH, "rb"))
    embs = d["embeddings"]
    findings_corpus = d["findings"]
    norms = np.linalg.norm(embs, axis=1)

    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    queries = []
    for f in survivors:
        # Use function signature + first few lines (the gist)
        body_head = "\n".join(f["text"].splitlines()[:15])
        q = (f"{f.get('contract','')}.{f['function']}: " +
             f"hits={','.join(f['ast_hits'])}. " + body_head)
        queries.append(sr._lift_idents(q))
    if not queries:
        return []
    q_embs = np.array(list(embedder.embed(queries)))
    q_norms = np.linalg.norm(q_embs, axis=1)
    sims = (q_embs @ embs.T) / (q_norms[:, None] * norms[None, :])

    out = []
    for i, f in enumerate(survivors):
        top_idx = np.argsort(-sims[i])[:3]
        top_match = findings_corpus[top_idx[0]]
        if sims[i][top_idx[0]] > cos_threshold:
            f["corpus_top1_cos"] = float(sims[i][top_idx[0]])
            f["corpus_top1"] = {
                "id": top_match.get("finding_id"),
                "title": top_match.get("title")[:80],
                "source": top_match.get("source"),
                "corpus": top_match.get("corpus"),
                "severity": top_match.get("severity"),
            }
            f["corpus_top3"] = [
                {"id": findings_corpus[j].get("finding_id"),
                 "title": findings_corpus[j].get("title")[:60],
                 "cos": float(sims[i][j])}
                for j in top_idx]
            out.append(f)
    return out


# ============================================================
# Layer D: TLA+ shape heuristic match
# ============================================================

# Heuristic: each FailureMode shape has a signature of (ast_hits + corpus_match
# semantics) that fits it. This is a coarse routing — TLC actually proves.
SHAPE_HEURISTICS = {
    "SignatureReplay": lambda f: (
        "ecrecover" in f["ast_hits"] or "permit_call" in f["ast_hits"]),
    "ReentrancyDrain": lambda f: (
        "external_call" in f["ast_hits"] and
        "state_write_after_call" in f["ast_hits"]),
    "ERC4337StaticSigDoS": lambda f: (
        f["function"].lower() in ("validateuserop", "validatesignature") or
        "msg_sender_in_validation" in f["ast_hits"]),
    "Uint64FeeOverflow": lambda f: (
        "uint64" in f["text"].lower() and re.search(r"\b\w+\s*[+\-*/]?=", f["text"])),
    "Create2NonIdempotent": lambda f: (
        "create2" in f["ast_hits"]),
    "MissingAwait": lambda f: ("await" in f["text"].lower()),  # JS-shaped
}


def layer_d(survivors: list[dict]) -> list[dict]:
    """Heuristic-match each survivor to one or more TLA+ FailureMode shapes."""
    for f in survivors:
        f["tla_shape_matches"] = [
            s for s, h in SHAPE_HEURISTICS.items() if h(f)]
    # Survive if ≥1 shape matches OR if Layer C cos was very high (>0.75 = trust corpus)
    return [f for f in survivors
            if f["tla_shape_matches"] or f.get("corpus_top1_cos", 0) > 0.75]


# ============================================================
# Layer E: halmos (optional — skip if scope doesn't build)
# ============================================================

def layer_e(survivors: list[dict], scope_dir: Path) -> list[dict]:
    """Skip for v1 — halmos requires forge build which often fails on
    cold contest source. Mark each survivor halmos_status=skip with reason."""
    for f in survivors:
        f["halmos_status"] = "skip-v1"
    return survivors


# ============================================================
# Pipeline runner
# ============================================================

def run_cascade(scope_dir: Path, out_path: Path,
                cos_threshold: float = 0.55) -> dict:
    sol_files = sorted(scope_dir.rglob("*.sol"))
    # Skip test/mock/script files for cleaner signal
    sol_files = [p for p in sol_files
                 if not any(x in str(p).lower()
                            for x in ("test", "mock", "script", ".t.sol"))]

    all_functions = []
    for p in sol_files:
        try:
            code, tree = parse_file(p)
            all_functions.extend(extract_functions(code, tree, p))
        except Exception as e:
            print(f"  PARSE ERROR {p}: {e}", file=sys.stderr)

    print(f"Scope: {len(sol_files)} .sol files → {len(all_functions)} functions",
          file=sys.stderr)

    a = layer_a(all_functions)
    print(f"  Layer A (tree-sitter AST query):  {len(a):4d} candidates",
          file=sys.stderr)

    G = build_call_graph(all_functions)
    b = layer_b(a, all_functions, G)
    print(f"  Layer B (CFG reach from public):  {len(b):4d} candidates",
          file=sys.stderr)

    c = layer_c(b, cos_threshold=cos_threshold)
    print(f"  Layer C (corpus NN cos>{cos_threshold}):  {len(c):4d} candidates",
          file=sys.stderr)

    d = layer_d(c)
    print(f"  Layer D (TLA+ shape heuristic):   {len(d):4d} candidates",
          file=sys.stderr)

    e = layer_e(d, scope_dir)
    print(f"  Layer E (halmos):                 {len(e):4d} (skipped in v1)",
          file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        for f in e:
            # strip text to keep jsonl readable
            rec = {k: v for k, v in f.items() if k != "text"}
            rec["text_head"] = f["text"][:300]
            fh.write(json.dumps(rec) + "\n")

    summary = {
        "scope_files": len(sol_files),
        "functions_total": len(all_functions),
        "layer_a": len(a),
        "layer_b": len(b),
        "layer_c": len(c),
        "layer_d": len(d),
        "layer_e": len(e),
        "out_path": str(out_path),
    }
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scope_dir", help="Directory containing .sol files")
    ap.add_argument("--out", default="cascade.jsonl",
                    help="Output jsonl path")
    ap.add_argument("--cos-threshold", type=float, default=0.55,
                    help="Layer C cosine threshold (default 0.55)")
    args = ap.parse_args()
    s = run_cascade(Path(args.scope_dir).resolve(),
                    Path(args.out).resolve(),
                    cos_threshold=args.cos_threshold)
    print()
    print("CASCADE SUMMARY")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
