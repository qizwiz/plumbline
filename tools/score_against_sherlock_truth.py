"""
score_against_sherlock_truth — match sol_intent leads to graded Sherlock findings.

Two scorers (report both):
  MECHANICAL: lead text mentions contract/file/function name from ground truth title
  THEMATIC:   lead embeds within cos>0.65 of ground truth title (using
              the same bge-small-en-v1.5 + identifier-lifting as the RAG index)

Usage:
  python tools/score_against_sherlock_truth.py \\
    --leads corpus/calibration/notional-sol-intent.txt \\
    --truth corpus/calibration/notional-ground-truth.jsonl \\
    --out  corpus/calibration/notional-score.json
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LEAD_PAT = re.compile(r"^(?:- )?\[?LEAD\]?:?\s*(.+?)$|^- \*?\*?(.+?)$", re.M)


def parse_leads(text: str) -> list[str]:
    """sol_intent emits leads as bulleted lines, often `- [LEAD] ...` or
    `- **bold**...` Be permissive: any non-empty `-` bullet under 500 chars."""
    leads = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and 20 < len(line) < 500:
            leads.append(line[2:].strip())
    return leads


def mechanical_hits(leads: list[str], gt: dict) -> list[str]:
    """Lead contains an identifier from ground truth title."""
    title = gt["title"]
    # Extract candidate identifiers: CamelCase words, snake_case, function() refs
    idents = set(re.findall(r"\b[A-Z][a-zA-Z0-9_]{3,}\b|\b\w+\(\)|\b[a-z_]{4,}_[a-z_]+\b",
                            title))
    # Exclude very common words
    stop = {"This", "Function", "When", "Where", "Some", "Each", "Will", "Must",
            "Vault", "Address", "Token", "Update", "Reward", "Strategy"}
    idents = {i for i in idents if i not in stop}
    hits = []
    for L in leads:
        if any(i in L for i in idents):
            hits.append(L)
    return hits


def thematic_hits(leads: list[str], gt: dict, embedder, lift_fn,
                  threshold: float = 0.65) -> tuple[list[str], list[float]]:
    """Lead embeds within cos>threshold of ground truth title."""
    import numpy as np
    if not leads:
        return [], []
    q = lift_fn(gt["title"])
    q_emb = np.array(list(embedder.embed([q])))[0]
    q_norm = np.linalg.norm(q_emb)
    lead_embs = np.array(list(embedder.embed([lift_fn(L) for L in leads])))
    norms = np.linalg.norm(lead_embs, axis=1)
    sims = lead_embs @ q_emb / (norms * q_norm)
    hits = [(L, float(s)) for L, s in zip(leads, sims) if s > threshold]
    hits.sort(key=lambda x: -x[1])
    return [h[0] for h in hits], [h[1] for h in hits]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    text = open(args.leads).read()
    leads = parse_leads(text)
    truth = [json.loads(l) for l in open(args.truth) if l.strip()]
    print(f"leads parsed: {len(leads)}", file=sys.stderr)
    print(f"ground truth: {len(truth)} ({sum(1 for t in truth if t['severity']=='High')} H, "
          f"{sum(1 for t in truth if t['severity']=='Medium')} M)", file=sys.stderr)

    # Lazy-load embedder for thematic
    sys.path.insert(0, str(HERE / "tools"))
    import spec_retrieval as sr
    from fastembed import TextEmbedding
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    per_finding = []
    mech_caught = thematic_caught = 0
    mech_caught_h = thematic_caught_h = 0
    h_count = sum(1 for t in truth if t["severity"] == "High")
    m_count = sum(1 for t in truth if t["severity"] == "Medium")

    for gt in truth:
        m_hits = mechanical_hits(leads, gt)
        t_hits, t_sims = thematic_hits(leads, gt, embedder, sr._lift_idents)
        mech_caught_flag = bool(m_hits)
        them_caught_flag = bool(t_hits)
        per_finding.append({
            "id": gt["id"], "severity": gt["severity"], "title": gt["title"],
            "mechanical_caught": mech_caught_flag,
            "mech_hits": m_hits[:2],
            "thematic_caught": them_caught_flag,
            "thematic_best_cos": (max(t_sims) if t_sims else 0.0),
            "thematic_best_lead": t_hits[0][:200] if t_hits else "",
        })
        if mech_caught_flag:
            mech_caught += 1
            if gt["severity"] == "High":
                mech_caught_h += 1
        if them_caught_flag:
            thematic_caught += 1
            if gt["severity"] == "High":
                thematic_caught_h += 1

    summary = {
        "leads_parsed": len(leads),
        "ground_truth_total": len(truth),
        "h_total": h_count, "m_total": m_count,
        "mechanical_recall_total": mech_caught / len(truth) if truth else 0,
        "mechanical_recall_h": mech_caught_h / h_count if h_count else 0,
        "thematic_recall_total": thematic_caught / len(truth) if truth else 0,
        "thematic_recall_h": thematic_caught_h / h_count if h_count else 0,
        "per_finding": per_finding,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    open(args.out, "w").write(json.dumps(summary, indent=2))

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"  leads parsed:           {summary['leads_parsed']}")
    print(f"  ground truth:           {summary['ground_truth_total']} ({h_count} H, {m_count} M)")
    print(f"  MECHANICAL recall:      {summary['mechanical_recall_total']*100:.1f}% all  "
          f"{summary['mechanical_recall_h']*100:.1f}% H-only")
    print(f"  THEMATIC recall:        {summary['thematic_recall_total']*100:.1f}% all  "
          f"{summary['thematic_recall_h']*100:.1f}% H-only")
    print()
    print("CAUGHT (either scorer):")
    for f in per_finding:
        if f["mechanical_caught"] or f["thematic_caught"]:
            mark = "MECH+THEM" if (f["mechanical_caught"] and f["thematic_caught"]) \
                else "MECH" if f["mechanical_caught"] else "THEM"
            print(f"  [{mark:<10}] {f['severity'][:1]} {f['id']:<6} {f['title'][:60]}")
    print()
    print("MISSED:")
    for f in per_finding:
        if not (f["mechanical_caught"] or f["thematic_caught"]):
            print(f"  {f['severity'][:1]} {f['id']:<6} {f['title'][:65]}  (best them cos={f['thematic_best_cos']:.3f})")
    print()
    print(f"full output → {args.out}")


if __name__ == "__main__":
    main()
