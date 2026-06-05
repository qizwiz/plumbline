"""
sol_graph — the STRUCTURAL layer. Parse a Solidity codebase with tree-sitter (NO compile needed, works on
partial/huge repos), build a function/call/state graph in networkx, and run DETERMINISTIC syntactic
detectors (no LLM). This is the sound, ungameable FLOOR under the semantic LLM finder: a detector either
fires on the AST or it doesn't. It also exposes the call graph for cluster-based chunking + centrality
prioritization (audit the hubs/cut-vertices first).

Limit (honest): tree-sitter is SYNTACTIC — the call graph is name-approximate (no inheritance resolution),
and detectors are pattern-level (false hits possible). It's a floor, not a prover; the deep data-flow
detectors (reentrancy/taint) want Slither or a real IR. But it catches the structural classes the LLM
misses, deterministically, on code that won't even compile.

  python sol_graph.py <dir>            # detectors + graph summary
"""
from __future__ import annotations

import os
import re
import sys

import networkx as nx
import tree_sitter_solidity as tss
from tree_sitter import Language, Parser

LANG = Language(tss.language())
_SKIP = {"lib", "node_modules", "test", "tests", ".git", "mock", "mocks", "interfaces"}


def _walk(n, t, acc):
    if n.type == t:
        acc.append(n)
    for c in n.children:
        _walk(c, t, acc)


def _name(n):
    nm = n.child_by_field_name("name")
    return nm.text.decode() if nm else None


def _text(n):
    return n.text.decode("utf8", "replace")


def parse_dir(root):
    p = Parser(LANG)
    files = {}
    for dp, dns, fs in os.walk(root):
        dns[:] = [d for d in dns if d not in _SKIP]
        for f in sorted(fs):
            if f.endswith(".sol") and not f.endswith(".t.sol"):
                full = os.path.join(dp, f)
                src = open(full, "rb").read()
                files[os.path.relpath(full, root)] = p.parse(src).root_node
    return files


def fn_info(fn, rel, contract):
    """Pull a function's name, visibility, modifiers, body — from the AST, signature-text as fallback."""
    name = _name(fn) or "<anon>"
    body = fn.child_by_field_name("body")
    btext = _text(body) if body else ""
    sig = _text(fn).split("{", 1)[0]
    vis = ("external" if re.search(r"\bexternal\b", sig) else "public" if re.search(r"\bpublic\b", sig)
           else "private" if re.search(r"\bprivate\b", sig) else "internal")
    mods = []
    for c in fn.children:
        if c.type == "modifier_invocation":
            mods.append(_text(c.child_by_field_name("name") or c))
    # signature-level modifier fallback (names that aren't visibility/mutability keywords)
    for m in re.findall(r"\b([a-zA-Z_]\w*)\s*(?:\([^)]*\))?\s*(?=returns|\{|external|public|internal|private)", sig):
        if m not in {"function", "external", "public", "internal", "private", "view", "pure",
                     "payable", "virtual", "override", "returns", name} and m not in mods:
            mods.append(m)
    return {"name": name, "vis": vis, "mods": mods, "sig": sig.strip()[:160], "body": btext,
            "rel": rel, "contract": contract, "id": f"{contract}.{name}"}


def collect_functions(files):
    fns = []
    for rel, root in files.items():
        contracts = []
        _walk(root, "contract_declaration", contracts)
        for c in contracts:
            cname = _name(c) or rel
            fdefs = []
            _walk(c, "function_definition", fdefs)
            for fd in fdefs:
                fns.append(fn_info(fd, rel, cname))
    return fns


def call_graph(fns):
    """Approximate call graph: edge fn -> g when fn's body names g (any function of that name). Name-based,
    no inheritance resolution — a floor for centrality/clustering, not a sound dependency analysis."""
    by_name = {}
    for f in fns:
        by_name.setdefault(f["name"], []).append(f["id"])
    G = nx.DiGraph()
    for f in fns:
        G.add_node(f["id"], **{k: f[k] for k in ("vis", "rel", "contract")})
    for f in fns:
        called = set(re.findall(r"\b([a-zA-Z_]\w*)\s*\(", f["body"]))
        for cn in called:
            if cn != f["name"] and cn in by_name:
                for tgt in by_name[cn]:
                    G.add_edge(f["id"], tgt)
    return G


# ───────────────────────── deterministic syntactic detectors ─────────────────────────
def detectors(fns):
    out = []
    for f in fns:
        b, name, vis, mods = f["body"], f["name"], f["vis"], f["mods"]
        guarded = any(m for m in mods if re.search(r"only|auth|admin|owner|role|govern|restrict", m, re.I)) \
            or re.search(r"\b_?(checkOwner|onlyOwner|require\s*\(\s*msg\.sender\s*==)", b)
        # 1) unprotected initializer → first-caller takeover
        if re.search(r"initiali|setup|__init", name, re.I) and vis in ("public", "external") and not guarded \
           and re.search(r"\b(owner|implementation|admin|_initialized|governor|manager|registr)\w*\s*=", b):
            out.append((f, "HIGH", "unprotected-initializer",
                        f"{f['id']} is {vis}, sets owner/impl/admin state, no access guard — first-caller takeover"))
        # 2) unchecked ERC20 transfer/approve (no require, no Safe*)
        for m in re.finditer(r"\b([A-Za-z_]\w*)\.(transfer|transferFrom|approve)\s*\(", b):
            seg = b[max(0, m.start() - 40):m.start()]
            if not re.search(r"require\s*\(|=\s*$|bool\s+\w+\s*=|Safe\w*\.", seg) and "Safe" not in b[:m.start()][-80:]:
                out.append((f, "MEDIUM", "unchecked-erc20",
                            f"{f['id']}: {m.group(0)} return value unchecked"))
                break
        # 3) narrowing cast → silent truncation
        mc = re.search(r"\b(uint(?:8|16|32|64|96|128)|int(?:8|16|32|64|96|128))\s*\(", b)
        if mc:
            out.append((f, "MEDIUM", "narrowing-cast", f"{f['id']}: {mc.group(1)}(...) may truncate silently"))
        # 4) tx.origin auth
        if "tx.origin" in b:
            out.append((f, "MEDIUM", "tx-origin", f"{f['id']}: uses tx.origin"))
        # 5) low-level call return unchecked
        for m in re.finditer(r"\.call\s*[{(]", b):
            seg = b[max(0, m.start() - 30):m.start()]
            if not re.search(r"\(\s*bool|require\s*\(|=\s*$", seg):
                out.append((f, "MEDIUM", "unchecked-call", f"{f['id']}: low-level .call return unchecked"))
                break
    return out


def analyze(root):
    files = parse_dir(root)
    fns = collect_functions(files)
    G = call_graph(fns)
    dets = detectors(fns)
    return files, fns, G, dets


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    files, fns, G, dets = analyze(root)
    print(f"=== sol_graph: {len(files)} files, {len(fns)} functions, "
          f"call graph {G.number_of_nodes()} nodes / {G.number_of_edges()} edges ===")
    # centrality: which functions are hubs (audit these first)
    if G.number_of_edges():
        pr = nx.pagerank(G)
        top = sorted(pr, key=pr.get, reverse=True)[:8]
        print("top call-graph hubs (audit-first):", [t for t in top])
    print(f"\n=== {len(dets)} hits, aggregated to CLASS-LEVEL leads (precision: 1 finding = 1 class, "
          f"not N instances) ===")
    import collections
    groups = collections.defaultdict(list)
    for f, sev, kind, msg in dets:
        groups[kind].append(f["id"])
    for kind, ids in groups.items():
        funcs = sorted(set(ids))
        print(f"  {kind} affecting {len(funcs)} functions: {', '.join(funcs[:12])}"
              + (" ..." if len(funcs) > 12 else ""))
    if "--instances" in sys.argv:
        print("\n--- per-instance ---")
        for f, sev, kind, msg in sorted(dets, key=lambda x: x[1]):
            print(f"  [{sev}] {kind}: {msg}")
