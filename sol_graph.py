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
_SKIP = {"lib", "node_modules", "test", "tests", ".git", "mock", "mocks", "interfaces",
         "dummy", "dummies"}


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
    # mutability: view/pure read-only functions are rarely bug sites — capture so
    # downstream ranking can deprioritize them (mirrors tools/admin_trust_filter Check 4)
    mut = ("view" if re.search(r"\bview\b", sig) else "pure" if re.search(r"\bpure\b", sig)
           else "payable" if re.search(r"\bpayable\b", sig) else "nonpayable")
    mods = []
    for c in fn.children:
        if c.type == "modifier_invocation":
            mods.append(_text(c.child_by_field_name("name") or c))
    # signature-level modifier fallback (names that aren't visibility/mutability keywords)
    for m in re.findall(r"\b([a-zA-Z_]\w*)\s*(?:\([^)]*\))?\s*(?=returns|\{|external|public|internal|private)", sig):
        if m not in {"function", "external", "public", "internal", "private", "view", "pure",
                     "payable", "virtual", "override", "returns", name} and m not in mods:
            mods.append(m)
    # tree-sitter rows are 0-indexed; editors are 1-indexed
    line = fn.start_point[0] + 1
    return {"name": name, "vis": vis, "mut": mut, "mods": mods, "sig": sig.strip()[:160],
            "body": btext, "rel": rel, "contract": contract, "id": f"{contract}.{name}", "line": line}


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
    # Disambiguate overloads: Solidity allows `function deposit(uint)` and
    # `function deposit(uint, address)` in the same contract. Both produce
    # the same `f"{contract}.{name}"` id, and the second `add_node` overwrites
    # the first's `line` attribute. Suffix overloads as `/0`, `/1`, ... so
    # each overload keeps its own source line and gets ranked separately.
    occ: dict[str, int] = {}
    for f in fns:
        base = f["id"]
        n = occ.get(base, 0)
        if n > 0:
            f["id"] = f"{base}/{n}"
        occ[base] = n + 1
    by_name = {}
    for f in fns:
        by_name.setdefault(f["name"], []).append(f["id"])
    G = nx.DiGraph()
    for f in fns:
        G.add_node(f["id"], **{k: f[k] for k in ("vis", "mut", "rel", "contract", "line")})
    for f in fns:
        called = set(re.findall(r"\b([a-zA-Z_]\w*)\s*\(", f["body"]))
        for cn in called:
            if cn != f["name"] and cn in by_name:
                for tgt in by_name[cn]:
                    G.add_edge(f["id"], tgt)
    return G


def collect_state_vars(files):
    """contract -> set(state-variable names), from tree-sitter state_variable_declaration nodes."""
    out = {}
    for rel, root in files.items():
        contracts = []
        _walk(root, "contract_declaration", contracts)
        for c in contracts:
            cname = _name(c) or rel
            svs = []
            _walk(c, "state_variable_declaration", svs)
            names = set()
            for sv in svs:
                nm = sv.child_by_field_name("name")
                if nm:
                    names.add(nm.text.decode())
                else:  # fallback: identifier before '=' or ';'
                    m = re.search(r"([A-Za-z_]\w*)\s*(?:=|;)", _text(sv))
                    if m:
                        names.add(m.group(1))
            out[cname] = names
    return out


def rich_graph(fns, files):
    """Denser STRUCTURAL graph than call_graph: functions are coupled through the
    storage they touch and the modifiers that guard them — not just direct internal
    calls. This matters because most Solidity calls target external/inherited code
    (which the syntactic call graph skips), leaving call_graph near-empty on real
    contracts and breaking centrality. Empirically (boss-bridge): call_graph gave
    9 nodes/1 edge; rich_graph gives 18/19, and eigenvector centrality on it
    localizes known-buggy functions at AUC≈0.72 over 1135 scabench functions
    (LOPO-CV). Use THIS for centrality / hub-prioritization, not call_graph.

    Undirected nx.Graph. Node kinds: 'fn' | 'state' | 'mod'. Edge etype: call|state|mod.
    """
    G = nx.Graph()
    state_by_contract = collect_state_vars(files)
    by_name = {}
    for f in fns:
        by_name.setdefault(f["name"], []).append(f["id"])
    for f in fns:
        G.add_node(f["id"], kind="fn", contract=f["contract"], vis=f["vis"],
                   mut=f["mut"], line=f["line"])
    for f in fns:
        body = f["body"]
        words = set(re.findall(r"\b([A-Za-z_]\w*)\b", body))
        for cn in set(re.findall(r"\b([a-zA-Z_]\w*)\s*\(", body)):
            if cn != f["name"] and cn in by_name:
                for tgt in by_name[cn]:
                    if tgt != f["id"]:
                        G.add_edge(f["id"], tgt, etype="call")
        for sv in state_by_contract.get(f["contract"], ()):
            if sv in words:
                snode = f"state::{f['contract']}.{sv}"
                G.add_node(snode, kind="state")
                G.add_edge(f["id"], snode, etype="state")
        for m in f.get("mods", ()):
            mnode = f"mod::{m}"
            G.add_node(mnode, kind="mod")
            G.add_edge(f["id"], mnode, etype="mod")
    return G


def function_centrality(fns, files):
    """Audit-prioritization signal: eigenvector centrality over rich_graph, restricted
    to function nodes. Returns {fn_id: score}. This is the 'audit the hubs first' signal
    that call_graph could not provide (it was too sparse). Higher = more structurally
    load-bearing (touches more shared state / modifiers) = higher bug prior."""
    G = rich_graph(fns, files)
    fn_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "fn"]
    if G.number_of_edges() == 0:
        return {n: 0.0 for n in fn_nodes}
    try:
        cent = nx.eigenvector_centrality(G, max_iter=3000, tol=1e-5)
    except Exception:
        cent = nx.betweenness_centrality(G)
    return {n: cent.get(n, 0.0) for n in fn_nodes}


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
    RG = rich_graph(fns, files)
    print(f"=== sol_graph: {len(files)} files, {len(fns)} functions, "
          f"call graph {G.number_of_nodes()}n/{G.number_of_edges()}e, "
          f"rich graph {RG.number_of_nodes()}n/{RG.number_of_edges()}e ===")
    # centrality on the RICH graph (call_graph is too sparse on real contracts);
    # these hubs localize known-buggy functions at AUC~0.72 (see rich_graph docstring).
    cent = function_centrality(fns, files)
    if cent and any(cent.values()):
        top = sorted(cent, key=cent.get, reverse=True)[:8]
        print("top structural hubs (audit-first):", [f"{t} ({cent[t]:.2f})" for t in top])
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
