"""
build_findings_index — embed confirmed audit findings from
examples/<corpus>/.ANSWERS.md AND corpus/c4/<slug>/.ANSWERS.md
into a corpus-tagged retrieval index.

Each entry: {finding_id, severity, title, body, corpus, mechanism, source}.
  source = "examples" | "c4"
Embedded via fastembed bge-small-en-v1.5 (same as spec_retrieval).
Identifiers lifted to <ident> placeholders for cross-corpus geometry.

Usage: python tools/build_findings_index.py
Output: tools/findings_index.pkl

NOTE per docs/research/C4_INGEST_OPPORTUNITY.md: corpus/c4 entries are
sourced from code-423n4/*-findings repos which have NO LICENSE FILE.
The index is for PRIVATE RAG use only — do NOT publish.
"""
from __future__ import annotations
import glob, os, pickle, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import spec_retrieval  # reuses _lift_idents + embedder

INDEX_PATH = os.path.join(HERE, "tools", "findings_index.pkl")
CORPORA = ["boss-bridge", "puppy-raffle", "sequence", "t-swap", "thunder-loan"]
C4_GLOB = os.path.join(HERE, "corpus", "c4", "*", ".ANSWERS.md")


def parse_answers_md(path: str, corpus: str, source: str) -> list[dict]:
    """Each ## H-NN / M-NN / L-NN heading starts a finding; body is
    everything until next ## or EOF. Format is identical between
    examples/*/.ANSWERS.md (hand-built) and corpus/c4/*/.ANSWERS.md
    (auto-ingested by tools/c4_ingest.py) — both use `## <sev>-<num> <title>`."""
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
            "source": source,
            "search_text": f"{title}. {body}",
        })
    return findings


def parse_findings(corpus: str) -> list[dict]:
    """Back-compat shim: hand-built examples/ corpora."""
    return parse_answers_md(
        os.path.join(HERE, "examples", corpus, ".ANSWERS.md"),
        corpus, "examples")


def main():
    all_findings = []
    for corpus in CORPORA:
        fs = parse_findings(corpus)
        print(f"  examples/{corpus}: {len(fs)} findings")
        all_findings.extend(fs)
    examples_total = len(all_findings)
    # Extension: corpus/c4/*/.ANSWERS.md (auto-ingested Code4rena, gitignored)
    c4_paths = sorted(glob.glob(C4_GLOB))
    for path in c4_paths:
        slug = os.path.basename(os.path.dirname(path))
        fs = parse_answers_md(path, slug, "c4")
        all_findings.extend(fs)
    c4_total = len(all_findings) - examples_total
    print(f"  corpus/c4/*: {c4_total} findings across {len(c4_paths)} contests")
    print(f"total: {len(all_findings)} findings "
          f"({examples_total} examples + {c4_total} c4 ingested)")

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
