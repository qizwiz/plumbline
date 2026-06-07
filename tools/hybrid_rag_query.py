"""
hybrid_rag_query — combines past .ANSWERS findings (rag_query) with
matched TLA+ FailureMode shapes (spec_retrieval) into one unified
few-shot block. Per IS_RAG_THE_BEST.md top-1 recommendation.

Usage:
    from hybrid_rag_query import retrieve_block
    block = retrieve_block(chunk_text, exclude_corpus="sequence", k=3)

CLI:
    echo "chunk text" | python tools/hybrid_rag_query.py <exclude_corpus> [k=3]
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import rag_query, spec_retrieval


def retrieve(chunk_text: str, exclude_corpus: str, k: int = 3) -> dict:
    """Returns {'findings': [...], 'shapes': [...]}."""
    findings = rag_query.retrieve(chunk_text, exclude_corpus, k=k)
    shapes = spec_retrieval.query_top(chunk_text, k=k)
    # Filter out imported (Python-domain) shapes — focus on Solidity-relevant
    shapes = [s for s in shapes if "/imported/" not in s.get("path", "")]
    return {"findings": findings, "shapes": shapes}


def format_block(results: dict) -> str:
    """Two-section markdown block."""
    findings = results.get("findings") or []
    shapes = results.get("shapes") or []
    if not findings and not shapes:
        return ""
    lines = ["## RELEVANT PAST EVIDENCE",
             "",
             "Below are TWO sources of inspiration. Use both. The target "
             "corpus may have ENTIRELY different bug shapes; don't pattern-"
             "match too literally — the STRUCTURE of the bug matters.",
             ""]
    if findings:
        lines += ["### Confirmed past audit findings (from other corpora)", ""]
        for r in findings:
            lines.append(f"- **[{r['severity']}] {r['title']}** "
                         f"(from {r['corpus']}, cos={r['cos']:.2f})")
            body = r['body'].replace("\n", " ").strip()
            if len(body) > 240: body = body[:240] + "..."
            lines.append(f"  Mechanism: {body}")
            lines.append("")
    if shapes:
        lines += ["### Matched bug-class shapes (TLA+ FailureMode corpus)", ""]
        for s in shapes:
            lines.append(f"- **{s['name']}** (cos={s['cos']:.2f})")
            desc = s.get('description_head', '').replace("\n", " ").strip()
            if len(desc) > 280: desc = desc[:280] + "..."
            lines.append(f"  Shape: {desc}")
            lines.append("")
    return "\n".join(lines)


def retrieve_block(chunk_text: str, exclude_corpus: str, k: int = 3) -> str:
    return format_block(retrieve(chunk_text, exclude_corpus, k))


def main():
    if len(sys.argv) < 2:
        print("usage: hybrid_rag_query.py <exclude_corpus> [k=3]",
              file=sys.stderr); sys.exit(1)
    exclude = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    chunk = sys.stdin.read()
    print(retrieve_block(chunk, exclude, k))


if __name__ == "__main__":
    main()
