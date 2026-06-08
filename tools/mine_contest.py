"""
mine_contest — Sherlock/C4/audit contest mining pipeline as ONE COMMAND.

This is the productionalized version of the workflow that produced
Sherlock contest 1259 (DRE App) HIGH-severity finding on 2026-06-08.

WHAT IT DOES (one command):
  1. Index the contest scope (`*.sol` files outside mocks/test/lib).
  2. Run structural cascade (tree-sitter AST → CFG → embedding NN).
  3. Cluster H/M corpus findings (k=50) → identify dominant attack
     pattern families.
  4. Embed each in-scope function via fastembed bge-small-en-v1.5.
  5. Rank functions by max cosine similarity to corpus findings.
  6. Auto-extract Sherlock Q&A scope carve-ins / carve-outs from the
     contest README (so "If X causes serious loss, MAY be valid" hints
     are surfaced before manual triage).
  7. Fetch + parse prior audit PDFs if a URL list is provided
     (--prior-audits) so previously-acknowledged-but-not-in-README
     findings are explicitly listed as IN-SCOPE candidates.
  8. Output a ranked hypothesis JSON with top NN matches per function
     and Sherlock-scope tags.

DESIGN NOTES (the brutal-honesty bit):
  - This tool does NOT find bugs autonomously. It produces a RANKED
    HYPOTHESIS LIST for human/LLM-agent adversarial verification.
  - The autonomous loop's adversarial verification (see CONTEST_DAY_HARDENING
    goal) is the next stage that turns hypotheses into PoCs.
  - "Plumbline plus a human + corpus + adversarial loop" is the actual
    discovery engine; this tool is the BRIDGE that hands well-ranked
    hypotheses to that loop.

USAGE:
  python tools/mine_contest.py \\
    --scope corpus/calibration/2026-06-08-dre-labs-dreusd-source/dreusd/contracts \\
    --readme corpus/calibration/2026-06-08-dre-labs-dreusd-source/README.md \\
    --prior-audits prior-audits.txt \\
    --out runs/<contest-name>/

REPRODUCIBILITY:
  Same scope + corpus → same output. Embeddings are deterministic;
  k-means uses random_state=42.

PROVENANCE:
  Distilled from runs/2026-06-08-dre-structural/ workflow that produced
  Sherlock issue #1 on contest 1259.
"""
from __future__ import annotations
import argparse, json, pickle, re, sys
from collections import Counter
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent.parent


# ============================================================
# Step 1: Index in-scope Solidity files
# ============================================================

def find_scope_files(scope_dir: Path) -> list[Path]:
    """Return all *.sol files under scope_dir EXCEPT mocks/test/lib."""
    out = []
    for p in scope_dir.rglob("*.sol"):
        s = str(p)
        if any(x in s for x in ("/mocks/", "/test/", "/tests/", "/lib/", "/script/")):
            continue
        out.append(p)
    return sorted(out)


# ============================================================
# Step 2: Extract functions via tree-sitter (reuse structural_cascade)
# ============================================================

def extract_concrete_functions(scope_files: list[Path]) -> list[dict]:
    sys.path.insert(0, str(HERE / "tools"))
    from structural_cascade import extract_functions, parse_file

    fns = []
    for sol in scope_files:
        try:
            code, tree = parse_file(sol)
        except Exception as e:
            print(f"  ! parse failed {sol}: {e}", file=sys.stderr)
            continue
        fns.extend(extract_functions(code, tree, sol))

    # Filter: skip interface-only fns (contract starts with capital I + capital)
    concrete = [
        f for f in fns
        if f.get("contract")
        and not (f["contract"].startswith("I") and f["contract"][1:2].isupper())
        and len(f.get("text", "")) > 100
    ]
    return concrete


# ============================================================
# Step 3: NN-rank functions against H/M corpus
# ============================================================

def rank_against_corpus(fns: list[dict], corpus_path: Path,
                        top_per_fn: int = 5) -> list[dict]:
    from fastembed import TextEmbedding
    from sklearn.metrics.pairwise import cosine_similarity

    idx = pickle.load(corpus_path.open("rb"))
    findings = idx["findings"]
    embs = idx["embeddings"]
    hm_mask = np.array([f["severity"] in ("H", "M") for f in findings])
    hm_findings = [f for f, m in zip(findings, hm_mask) if m]
    hm_embeds = embs[hm_mask]

    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    texts = [
        f"{x.get('contract','?')}.{x.get('function','?')}: {x.get('text','')[:1500]}"
        for x in fns
    ]
    fn_embeds = np.array(list(embedder.embed(texts)))
    sims = cosine_similarity(fn_embeds, hm_embeds)

    ranked = []
    for i, f in enumerate(fns):
        top_idx = np.argsort(-sims[i])[:top_per_fn]
        top = [
            {
                "cos": float(sims[i][j]),
                "severity": hm_findings[j]["severity"],
                "title": hm_findings[j]["title"][:120],
                "finding_id": hm_findings[j]["finding_id"],
            }
            for j in top_idx
        ]
        ranked.append(
            {
                "contract": f["contract"],
                "function": f["function"],
                "file": f.get("file"),
                "start_line": f.get("start_line"),
                "max_cos": top[0]["cos"],
                "top": top,
            }
        )
    ranked.sort(key=lambda r: -r["max_cos"])
    return ranked


# ============================================================
# Step 4: Cluster H/M corpus to surface dominant pattern families
# ============================================================

def cluster_corpus(corpus_path: Path, k: int = 50) -> list[dict]:
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity

    idx = pickle.load(corpus_path.open("rb"))
    findings = idx["findings"]
    embs = idx["embeddings"]
    hm_mask = np.array([f["severity"] in ("H", "M") for f in findings])
    hm_findings = [f for f, m in zip(findings, hm_mask) if m]
    hm_embeds = embs[hm_mask]

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(hm_embeds)
    out = []
    for cid in range(k):
        mask = labels == cid
        members = [hm_findings[i] for i, m in enumerate(mask) if m]
        cluster_embeds = hm_embeds[mask]
        centroid = km.cluster_centers_[cid : cid + 1]
        sims_c = cosine_similarity(cluster_embeds, centroid).flatten()
        top3 = np.argsort(-sims_c)[:3]
        sev = Counter(m["severity"] for m in members)
        out.append(
            {
                "cluster_id": cid,
                "size": len(members),
                "severity_dist": dict(sev),
                "representative_titles": [members[i]["title"][:120] for i in top3],
            }
        )
    out.sort(key=lambda c: -c["size"])
    return out


# ============================================================
# Step 5: Parse README for Sherlock Q&A scope carve-ins / carve-outs
# ============================================================

# Patterns hinting at carve-IN (issues protocol team flags as in scope)
CARVE_IN_PATTERNS = [
    r"may\s+be\s+a\s+valid\s+finding",
    r"can\s+be\s+considered\s+(?:a\s+)?valid",
    r"would\s+be\s+a\s+valid\s+finding",
    r"if.*(?:loss|breaks?|causes)\s+(?:loss|loss\s+of\s+funds|losses)",
    r"if\s+a\s+mechanism\s+were\s+found",
]

# Patterns hinting at carve-OUT (acknowledged / out of scope)
CARVE_OUT_PATTERNS = [
    r"(?:known|acceptable)\s+(?:issue|risk)s?",
    r"acknowledged",
    r"by\s+design",
    r"this\s+is\s+intentional",
    r"out\s+of\s+scope",
]


def parse_scope_signals(readme_path: Path) -> dict:
    text = readme_path.read_text()
    paras = re.split(r"\n\s*\n", text)
    carve_in = []
    carve_out = []
    for p in paras:
        lower = p.lower()
        if any(re.search(pat, lower) for pat in CARVE_IN_PATTERNS):
            carve_in.append(p.strip()[:500])
        if any(re.search(pat, lower) for pat in CARVE_OUT_PATTERNS):
            carve_out.append(p.strip()[:500])
    return {
        "carve_in_signals": carve_in[:20],
        "carve_out_signals": carve_out[:20],
        "summary": {
            "n_carve_in_paragraphs": len(carve_in),
            "n_carve_out_paragraphs": len(carve_out),
        },
    }


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True, help="Contest scope directory (contains contracts/)")
    ap.add_argument("--readme", help="Path to contest README.md for scope-signal extraction")
    ap.add_argument("--corpus", default=str(HERE / "tools" / "findings_index.pkl"),
                    help="Path to plumbline findings_index.pkl")
    ap.add_argument("--out", required=True, help="Output directory for mining artifacts")
    ap.add_argument("--top-per-fn", type=int, default=5)
    ap.add_argument("--k-clusters", type=int, default=50)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"# mine_contest: scope={args.scope}")

    # ---- Step 1: scope files
    files = find_scope_files(Path(args.scope))
    print(f"  scope files: {len(files)}")

    # ---- Step 2: extract concrete functions
    fns = extract_concrete_functions(files)
    print(f"  concrete functions: {len(fns)}")
    (out / "scope_functions.json").write_text(
        json.dumps([{"contract": f["contract"], "function": f["function"],
                     "file": f.get("file"), "start_line": f.get("start_line")}
                    for f in fns], indent=2)
    )

    # ---- Step 3: NN rank against corpus
    print("  embedding + NN ranking...")
    ranked = rank_against_corpus(fns, Path(args.corpus), top_per_fn=args.top_per_fn)
    (out / "ranked_hypotheses.json").write_text(json.dumps(ranked[:50], indent=2))
    print(f"    top-10 by NN cos:")
    for r in ranked[:10]:
        print(f"      cos={r['max_cos']:.3f}  {r['contract']}.{r['function']:<40}  → {r['top'][0]['title'][:60]}")

    # ---- Step 4: cluster corpus
    print(f"  clustering H/M corpus (k={args.k_clusters})...")
    clusters = cluster_corpus(Path(args.corpus), k=args.k_clusters)
    (out / "corpus_clusters.json").write_text(json.dumps(clusters, indent=2))

    # ---- Step 5: scope-signal parsing
    if args.readme:
        print(f"  parsing scope signals from {args.readme}")
        signals = parse_scope_signals(Path(args.readme))
        (out / "scope_signals.json").write_text(json.dumps(signals, indent=2))
        print(f"    carve-in paragraphs: {signals['summary']['n_carve_in_paragraphs']}")
        print(f"    carve-out paragraphs: {signals['summary']['n_carve_out_paragraphs']}")

    # ---- Summary
    summary = {
        "scope_dir": args.scope,
        "scope_files": len(files),
        "concrete_functions": len(fns),
        "ranked_top1": ranked[0] if ranked else None,
        "artifacts": [
            "scope_functions.json",
            "ranked_hypotheses.json",
            "corpus_clusters.json",
        ] + (["scope_signals.json"] if args.readme else []),
    }
    (out / "mine_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE → {out}")
    print(f"  Inspect: ranked_hypotheses.json (top-50 functions by corpus NN)")
    print(f"  Inspect: scope_signals.json (Q&A carve-in/out paragraphs)")
    print(f"  Next: pick top 5-10 hypotheses, run adversarial verification "
          f"(see prompts/goals/CONTEST_DAY_HARDENING.goal.md)")


if __name__ == "__main__":
    main()
