"""
spec_retrieval — the retrieval corpus that conditions TLA+ generation.

Per ARCHITECTURE.md §3b (NCA-as-fluency-teacher curriculum step 1):
    "Every successful (bug-shape, TLC-verified TLA+ spec) triple goes
    into a vector index. Next generation retrieves nearest neighbors as
    few-shot context. Weekend-tractable."

This file IS that index, in the smallest viable form. No training,
no fine-tuning — pure embedding lookup over a hand-authored corpus.
Compounds with every verified spec added.

Per RESEARCH-NOTES-2026-06-06.md (LTLGuard arxiv 2603.05728): this
retrieval-augmented few-shot approach is what lifts a 14B open model
from 10% syntactic validity to 92.8%, and to 75-78% semantic accuracy
on the nl2spec hard benchmark — without fine-tuning. The lift is in
the retrieval, not the model.

USAGE
  # Build/refresh the index (run on every commit that adds a TLA+ module)
  python tools/spec_retrieval.py build

  # Query: get nearest TLA+ specs by description
  python tools/spec_retrieval.py query "signature replay nonce missing"
  python tools/spec_retrieval.py query "function default mutable list"
  python tools/spec_retrieval.py query "ERC-4337 entrypoint scheduler DoS"

  # Show all indexed specs
  python tools/spec_retrieval.py list
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TLA_DIRS = [
    os.path.join(HERE, "docs/tla"),
    os.path.join(HERE, "docs/tla/imported"),
]
INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "spec_retrieval_index.pkl")


def _read_header(path: str) -> tuple[str, str]:
    """Return (module_name, header_description). The header is everything
    between the `(* ... *)` directly after the MODULE line."""
    text = open(path, encoding="utf-8", errors="replace").read()
    name_match = re.search(r"MODULE\s+(\w+)", text)
    name = name_match.group(1) if name_match else os.path.basename(path)
    # Everything between the first `(*` and the matching `*)` is the
    # spec's natural-language description.
    body_match = re.search(r"\(\*(.*?)\*\)", text, re.DOTALL)
    if body_match:
        desc = body_match.group(1).strip()
        # Drop the asterisk-marker lines used as visual borders
        desc = "\n".join(ln.lstrip(" *") for ln in desc.splitlines())
    else:
        desc = text[:1000]
    # CRITICAL FIX (2026-06-06 03:48): focus the embedding on the bug-class
    # signal. All modules share boilerplate ("Formal specification of...",
    # section markers, fix history, TLC commands) and that boilerplate
    # dominates cosine similarity, collapsing all 13 specs into a 0.030
    # range regardless of bug content. Extract only the paragraph after
    # "The bug class:" / "bug class:" as the focused description.
    bug_class_match = re.search(
        r"(?:^|\n)\s*(?:The )?[Bb]ug class:\s*(.+?)(?=\n\s*\n|\n\s*[A-Z][a-z]+:|\Z)",
        desc, re.DOTALL
    )
    if bug_class_match:
        focused = bug_class_match.group(1).strip()
        # Keep the focused description; full original still available in path
        desc = focused
    return name, desc


# Conceptual vocabulary kept as-is during atomic-proposition lifting.
# These tokens describe BUG-SHAPE STRUCTURE that should match across
# domains (Solidity, Python, etc.). Everything outside this set that
# looks like a domain-specific identifier (camelCase, snake_case with
# multiple parts, contains a dot) gets lifted to a generic placeholder
# per LTLGuard's atomic-proposition lifting (arxiv 2603.05728).
_KEEP_VOCAB = {
    # TLA+ keywords
    "module", "extends", "constants", "constant", "variables", "variable",
    "assume", "init", "next", "spec", "vars", "type", "invariant",
    "invariants", "property", "properties", "fairness", "domain", "range",
    "subset", "union", "except", "such", "that", "where", "let", "in",
    "if", "then", "else", "true", "false", "boolean", "integer", "nat",
    "natural", "naturals", "integers", "finitesets", "sequences", "tlc",
    "checkdeadlock", "specification",
    # Bug-shape concepts (kept across domains)
    "reentrancy", "reentry", "replay", "nonce", "expiry", "consumed",
    "signature", "authorize", "authorized", "auth", "deposit", "withdraw",
    "transfer", "mint", "burn", "balance", "overflow", "underflow",
    "truncation", "cast", "rounding", "round", "decimals", "precision",
    "mutable", "default", "arg", "argument", "parameter", "param",
    "missing", "await", "coroutine", "consumer", "consume", "violation",
    "violated", "bug", "exploit", "attack", "attacker", "drain", "lose",
    "loss", "lost", "stolen", "broken", "breaks", "incorrect", "wrong",
    "promise", "intent", "guarantee", "invariant", "predicate", "fairness",
    "liveness", "safety", "monotonic", "monotonically", "eventually",
    "always", "trace", "counterexample", "witness", "spec", "model",
    "checker", "verify", "verified", "discharge", "discharged",
    "function", "method", "call", "callback", "external", "internal",
    "public", "private", "modifier", "require", "revert", "reverts",
    "submission", "submit", "submitted", "submissions",
    "scheduler", "scheduling", "scheduled", "schedule",
    "msgsender", "sender", "caller", "msgvalue", "value", "amount",
    "lifecycle", "lifetime", "state", "states", "stateful", "stateless",
    "session", "sessions", "wallet", "wallets", "bridge", "vault",
    "factory", "deploy", "deployed", "deployment", "deterministic",
    "idempotent", "idempotence", "race", "concurrent", "concurrency",
    "validation", "validated", "unvalidated", "check", "checked",
    "unchecked", "guard", "guarded", "unguarded",
}
# Regex for identifiers that LOOK domain-specific:
#   camelCase (has internal capital) OR snake_case with ≥1 underscore
#   AND length ≥ 4 (filter out short noise like 'foo' or 'bar' or 'i')
_DOMAIN_IDENT_RE = re.compile(r"\b([a-zA-Z_]\w{3,})\b")
# Detect domain-specific identifiers:
#   [a-z][A-Z]    — camelCase (lowercase to uppercase boundary)
#   [a-z]_[a-z]   — snake_case (lowercase, underscore, lowercase)
#   [A-Z]_[A-Z]   — SCREAMING_SNAKE_CASE (e.g. _CORO_CONSUMERS, MAX_DEPTH)
#   [A-Z][a-z].*[A-Z][a-z]  — PascalCase with ≥2 words
_CAMEL_RE = re.compile(r"[a-z][A-Z]|[a-z]_[a-z]|[A-Z]_[A-Z]|[A-Z][a-z]+[A-Z][a-z]+")


def _lift_idents(text: str) -> str:
    """Per LTLGuard atomic-proposition lifting (arxiv 2603.05728): replace
    domain-specific identifiers (contract names, function names, etc.)
    with generic placeholders so retrieval matches BUG-SHAPE STRUCTURE,
    not surface tokens.

    Without this, embedding a Solidity description rich in identifiers
    like `L1BossBridge::withdrawTokensToL1` and `s_flashLoanFee` cannot
    match a Python pact module rich in `_CORO_CONSUMERS` and
    `_scan_file_save_without_update_fields`, even if both encode the
    same temporal-replay bug shape. Lifting strips the surface noise.
    """
    counter = [0]
    seen: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        ident = m.group(1)
        ident_lc = ident.lower()
        # Keep conceptual vocabulary as-is
        if ident_lc in _KEEP_VOCAB:
            return ident
        # Only lift things that look domain-specific (camelCase or snake_case)
        if not _CAMEL_RE.search(ident):
            return ident
        # Stable placeholder per identifier within this text
        if ident not in seen:
            counter[0] += 1
            seen[ident] = f"<id_{counter[0]}>"
        return seen[ident]

    return _DOMAIN_IDENT_RE.sub(repl, text)


def _iter_specs():
    for tla_dir in TLA_DIRS:
        if not os.path.isdir(tla_dir):
            continue
        for fn in sorted(os.listdir(tla_dir)):
            if not fn.endswith(".tla"):
                continue
            yield os.path.join(tla_dir, fn)


def build():
    sys.path.insert(0, HERE)
    import sol_match  # for the same embedder sol_match uses

    specs = []
    for path in _iter_specs():
        name, desc = _read_header(path)
        lifted = _lift_idents(desc)
        specs.append({
            "name": name,
            "path": os.path.relpath(path, HERE),
            "description": desc,
            "description_lifted": lifted,    # atomic-proposition-lifted; used for embedding
            "description_head": desc[:200].replace("\n", " "),
        })

    if not specs:
        print("no TLA+ specs found under", TLA_DIRS)
        sys.exit(1)

    print(f"indexing {len(specs)} specs (atomic-proposition-lifted)...")
    # Embed the LIFTED descriptions so cross-domain retrieval (Solidity ↔
    # Python) matches structure rather than surface tokens. Per LTLGuard.
    descriptions = [s["description_lifted"] for s in specs]
    embeddings = sol_match._embed(descriptions)

    payload = {
        "specs": specs,
        "embeddings": embeddings,
        "embed_model": "BAAI/bge-small-en-v1.5",
    }
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(payload, f)

    print(f"saved → {INDEX_PATH}")
    print(f"  corpus size: {len(specs)}")
    print(f"  embedding dim: {embeddings.shape[1]}")
    for s in specs:
        print(f"  {s['name']:36s} ({s['path']})")


def query(query_text: str, k: int = 3):
    if not os.path.isfile(INDEX_PATH):
        print(f"no index at {INDEX_PATH} — run: python tools/spec_retrieval.py build")
        sys.exit(1)
    sys.path.insert(0, HERE)
    import sol_match
    import numpy as np

    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    specs = payload["specs"]
    embs = payload["embeddings"]

    # Lift the query too — its identifiers should map to the same
    # generic placeholders so geometry aligns with the indexed specs.
    q_lifted = _lift_idents(query_text)
    q = sol_match._embed([q_lifted])[0]
    sims = embs @ q  # cosine, since fastembed already unit-norms
    order = np.argsort(-sims)[:k]

    print(f"query: {query_text}")
    print(f"top {k}:\n")
    for rank, i in enumerate(order, 1):
        s = specs[i]
        print(f"  {rank}. {s['name']:36s}  cos={sims[i]:.3f}  ({s['path']})")
        print(f"     {s['description_head']}")
        print()


def list_specs():
    if not os.path.isfile(INDEX_PATH):
        print(f"no index at {INDEX_PATH} — run: python tools/spec_retrieval.py build")
        sys.exit(1)
    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    for s in payload["specs"]:
        print(f"  {s['name']:36s} ({s['path']})")
        print(f"    {s['description_head']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("usage: python tools/spec_retrieval.py query <text> [k]"); sys.exit(1)
        text = sys.argv[2]
        k = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        query(text, k=k)
    elif cmd == "list":
        list_specs()
    else:
        print(f"unknown: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
