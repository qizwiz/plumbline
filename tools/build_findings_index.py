"""
build_findings_index — embed confirmed audit findings from
examples/<corpus>/.ANSWERS.md into a corpus-tagged retrieval index.

Each entry: {finding_id, severity, title, body, corpus, mechanism}.
Embedded via fastembed bge-small-en-v1.5 (same as spec_retrieval).
Identifiers lifted to <ident> placeholders for cross-corpus geometry.

Usage: python tools/build_findings_index.py
Output: tools/findings_index.pkl
"""
from __future__ import annotations
import os, pickle, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import spec_retrieval  # reuses _lift_idents + embedder

INDEX_PATH = os.path.join(HERE, "tools", "findings_index.pkl")
CORPORA = ["boss-bridge", "puppy-raffle", "sequence", "t-swap", "thunder-loan"]


def parse_findings(corpus: str) -> list[dict]:
    """Each ## H-NN / M-NN / L-NN heading starts a finding; body is
    everything until next ## or EOF."""
    path = os.path.join(HERE, "examples", corpus, ".ANSWERS.md")
    if not os.path.isfile(path):
        return []
    text = open(path).read()
    findings = []
    pat = re.compile(r"^## ([HML]-\d+)\s+(.+?)$(.*?)(?=^## [HML]-|\Z)",
                     re.M | re.S)
    for m in pat.finditer(text):
        fid, title, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        severity = fid[0]  # H, M, L
        findings.append({
            "finding_id": fid,
            "severity": severity,
            "title": title,
            "body": body,
            "corpus": corpus,
            "search_text": f"{title}. {body}",
        })
    return findings


def main():
    all_findings = []
    for corpus in CORPORA:
        fs = parse_findings(corpus)
        print(f"  {corpus}: {len(fs)} findings")
        all_findings.extend(fs)
    print(f"total: {len(all_findings)} findings across {len(CORPORA)} corpora")

    # Lift identifiers per LTLGuard / spec_retrieval precedent
    texts = [spec_retrieval._lift_idents(f["search_text"]) for f in all_findings]

    # Embed
    from fastembed import TextEmbedding
    import numpy as np
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    embeddings = np.array(list(embedder.embed(texts)))

    # Save
    payload = {
        "findings": all_findings,
        "embeddings": embeddings,
        "embedding_dim": embeddings.shape[1],
    }
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(payload, f)
    print(f"saved → {INDEX_PATH}")
    print(f"  corpus size: {len(all_findings)}")
    print(f"  embedding dim: {embeddings.shape[1]}")


if __name__ == "__main__":
    main()
