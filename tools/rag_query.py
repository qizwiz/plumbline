"""
rag_query — retrieve top-K past findings for a Solidity chunk, with
mandatory corpus-exclusion for leakage control.

Returns a formatted markdown block suitable for injection into a
prompt slot. Hard-fails if exclude_corpus is None (forces explicit
leakage decision).

Usage:
    from rag_query import retrieve_block
    block = retrieve_block(chunk_text, exclude_corpus="sequence", k=3)
"""
from __future__ import annotations
import os, pickle, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import spec_retrieval

INDEX_PATH = os.path.join(HERE, "tools", "findings_index.pkl")


def retrieve(chunk_text: str, exclude_corpus: str, k: int = 3) -> list[dict]:
    """Returns top-K findings, EXCLUDING any from exclude_corpus.
    Raises ValueError if exclude_corpus is empty (leakage prevention)."""
    if not exclude_corpus:
        raise ValueError("exclude_corpus required for leakage control. "
                         "Pass '' explicitly only if you mean 'no exclusion'.")
    if not os.path.isfile(INDEX_PATH):
        raise FileNotFoundError(
            f"no index at {INDEX_PATH} — run: "
            f"python tools/build_findings_index.py")
    import numpy as np
    sys.path.insert(0, HERE); import sol_match
    payload = pickle.load(open(INDEX_PATH, "rb"))
    findings = payload["findings"]
    embs = payload["embeddings"]
    q_lifted = spec_retrieval._lift_idents(chunk_text)
    q = sol_match._embed([q_lifted])[0]
    sims = embs @ q  # cosine since fastembed unit-norms
    # Mask out exclude_corpus rows
    mask = np.array([f["corpus"] != exclude_corpus for f in findings])
    masked_sims = np.where(mask, sims, -1.0)
    order = np.argsort(-masked_sims)[:k]
    return [
        {**findings[i], "cos": float(sims[i])}
        for i in order
    ]


def format_block(results: list[dict]) -> str:
    """Format retrieved findings as a markdown few-shot block."""
    if not results:
        return ""
    lines = ["## SIMILAR PAST FINDINGS",
             "",
             "Below are similar bugs from past audits. Use as inspiration; "
             "the target corpus may have ENTIRELY different bug shapes.",
             ""]
    for r in results:
        lines.append(f"- **[{r['severity']}] {r['title']}** "
                     f"(from {r['corpus']}, cos={r['cos']:.2f})")
        body = r['body'].replace("\n", " ").strip()
        if len(body) > 280: body = body[:280] + "..."
        lines.append(f"  Mechanism: {body}")
        lines.append("")
    return "\n".join(lines)


def retrieve_block(chunk_text: str, exclude_corpus: str, k: int = 3) -> str:
    return format_block(retrieve(chunk_text, exclude_corpus, k))


def main():
    """CLI: stdin chunk text → top-K block to stdout."""
    if len(sys.argv) < 2:
        print("usage: python tools/rag_query.py <exclude_corpus> [k=3]",
              file=sys.stderr); sys.exit(1)
    exclude = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    chunk = sys.stdin.read()
    print(retrieve_block(chunk, exclude, k))


if __name__ == "__main__":
    main()
