"""
calibrate_against_sherlock — score plumbline's RAG corpus coverage
against ground-truth findings extracted from Sherlock past audit reports.

Sherlock publishes 259+ PDFs at
github.com/sherlock-protocol/sherlock-reports/audits. Each report contains
H/M findings graded by Sherlock judges. We use them as external ground truth.

Method (per CALIBRATION_NOTIONAL.md):
  1. Fetch + pdftotext each PDF (strip form-feed page breaks)
  2. Regex-parse "Issue [HM]-N: title" headings
  3. For each finding, embed title via bge-small-en-v1.5 with
     identifier-lifting, nearest-neighbor against tools/findings_index.pkl
  4. cos>0.7 = "semantically reachable prior in RAG corpus"

Per-contest output:
  {slug, date, h_count, m_count, h_covered, m_covered, h_avg_cos, m_avg_cos}

Aggregate report at end.

Usage:
  python tools/calibrate_against_sherlock.py --limit 10   # first 10 contests
  python tools/calibrate_against_sherlock.py --all        # all 259
  python tools/calibrate_against_sherlock.py --pdf-dir corpus/sherlock_pdfs

Output: corpus/calibration/sherlock_coverage.jsonl + summary stdout.

Note per docs/research/AUDIT_REPORT_TEMPLATE_RESEARCH.md: Sherlock reports
are not licensed. We process them privately for our own calibration. The
downloaded PDFs are gitignored (corpus/sherlock_pdfs/).
"""
from __future__ import annotations
import argparse, json, os, pickle, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PDF_DIR = HERE / "corpus" / "sherlock_pdfs"
OUT_PATH = HERE / "corpus" / "calibration" / "sherlock_coverage.jsonl"
INDEX_PATH = HERE / "tools" / "findings_index.pkl"
COS_THRESHOLD = 0.7

FINDING_PAT = re.compile(r"^Issue ([HM])-(\d+):\s*(.+?)$", re.M)


def list_sherlock_pdfs() -> list[dict]:
    cmd = ["gh", "api",
           "repos/sherlock-protocol/sherlock-reports/contents/audits"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"gh api failed: {p.stderr[:300]}")
    items = json.loads(p.stdout)
    out = []
    for it in items:
        if not it["name"].endswith(".pdf"): continue
        out.append({"name": it["name"], "download_url": it["download_url"]})
    return out


def fetch_pdf(item: dict) -> Path | None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    out = PDF_DIR / item["name"]
    if not out.exists():
        p = subprocess.run(["curl", "-fsSL", "-o", str(out), item["download_url"]],
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0 or not out.exists():
            return None
    return out


def extract_text(pdf: Path) -> str | None:
    txt = pdf.with_suffix(".txt")
    if not txt.exists():
        p = subprocess.run(["pdftotext", str(pdf), str(txt)],
                           capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return None
    return txt.read_text().replace("\f", "")


def parse_findings(text: str) -> list[dict]:
    out = []
    for sev, num, title in FINDING_PAT.findall(text):
        # Trim trailing [RESOLVED]/[ACKNOWLEDGED] tags; lossless cleanup
        title = re.sub(r"\s*\[(RESOLVED|ACKNOWLEDGED|FIXED|REPORTED)\]\s*$",
                       "", title.strip())
        out.append({"id": f"{sev}-{int(num):02d}",
                    "severity": "High" if sev == "H" else "Medium",
                    "title": title})
    return out


def slug_of(name: str) -> str:
    """Derive a slug for the contest from the PDF filename."""
    # 2026.05.14 - Final - Aave Labs Collaborative Audit Report 1778767107.pdf
    # → aave-labs (best-effort)
    n = re.sub(r"\.pdf$", "", name)
    n = re.sub(r"^\d{4}[.\-_]\d{2}[.\-_]\d{2}[\s\-_]+", "", n)
    n = re.sub(r"^Final\s*-\s*", "", n)
    n = re.sub(r"\s*-\s*Final.*$", "", n)
    n = re.sub(r"\s*Collaborative\s+Audit\s+Report.*$", "", n, flags=re.I)
    n = re.sub(r"\s*Audit\s+Report.*$", "", n, flags=re.I)
    n = re.sub(r"\s+", "-", n.strip()).lower()
    return n[:80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10,
                    help="Process only the most-recent N PDFs.")
    ap.add_argument("--all", action="store_true",
                    help="Process all PDFs (overrides --limit).")
    args = ap.parse_args()

    # Load RAG index
    print(f"loading index: {INDEX_PATH}", file=sys.stderr)
    sys.path.insert(0, str(HERE / "tools"))
    import spec_retrieval as sr
    from fastembed import TextEmbedding
    import numpy as np

    d = pickle.load(open(INDEX_PATH, "rb"))
    embs = d["embeddings"]
    findings_corpus = d["findings"]
    norms = np.linalg.norm(embs, axis=1)
    print(f"  corpus: {len(findings_corpus)} findings, dim {embs.shape[1]}",
          file=sys.stderr)

    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # List and pick PDFs
    print("listing Sherlock past reports...", file=sys.stderr)
    pdfs = list_sherlock_pdfs()
    print(f"  found {len(pdfs)} PDFs", file=sys.stderr)
    if not args.all:
        # Most-recent first (sort by name; the YYYY.MM.DD prefix sorts correctly)
        pdfs = sorted(pdfs, key=lambda x: x["name"], reverse=True)[:args.limit]
    print(f"  processing {len(pdfs)}", file=sys.stderr)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_file = open(OUT_PATH, "w")
    aggregate = {"contests": 0, "skipped_no_findings": 0, "skipped_fetch_fail": 0,
                 "total_h": 0, "total_m": 0, "covered_h": 0, "covered_m": 0}

    for item in pdfs:
        slug = slug_of(item["name"])
        sys.stderr.write(f"  {slug:<60} ")
        pdf = fetch_pdf(item)
        if not pdf:
            sys.stderr.write("FETCH FAIL\n")
            aggregate["skipped_fetch_fail"] += 1
            continue
        text = extract_text(pdf)
        if not text:
            sys.stderr.write("EXTRACT FAIL\n")
            aggregate["skipped_fetch_fail"] += 1
            continue
        gt = parse_findings(text)
        h_gt = [f for f in gt if f["severity"] == "High"]
        m_gt = [f for f in gt if f["severity"] == "Medium"]
        if not gt:
            sys.stderr.write("0 H+M\n")
            aggregate["skipped_no_findings"] += 1
            continue

        # Score coverage
        titles = [sr._lift_idents(f["title"]) for f in gt]
        q_embs = np.array(list(embedder.embed(titles)))
        q_norms = np.linalg.norm(q_embs, axis=1)
        # cosine sim matrix: gt × corpus → top1 per gt
        sims = (q_embs @ embs.T) / (q_norms[:, None] * norms[None, :])
        top1_sims = sims.max(axis=1)
        top1_idx = sims.argmax(axis=1)

        h_covered = sum(1 for i, f in enumerate(gt)
                        if f["severity"] == "High" and top1_sims[i] > COS_THRESHOLD)
        m_covered = sum(1 for i, f in enumerate(gt)
                        if f["severity"] == "Medium" and top1_sims[i] > COS_THRESHOLD)

        rec = {
            "slug": slug,
            "pdf": item["name"],
            "h_count": len(h_gt),
            "m_count": len(m_gt),
            "h_covered": h_covered,
            "m_covered": m_covered,
            "h_avg_cos": (float(np.mean([top1_sims[i] for i, f in enumerate(gt)
                          if f["severity"] == "High"])) if h_gt else None),
            "m_avg_cos": (float(np.mean([top1_sims[i] for i, f in enumerate(gt)
                          if f["severity"] == "Medium"])) if m_gt else None),
            "findings": [{
                **gt[i],
                "top1_cos": float(top1_sims[i]),
                "top1_match": {
                    "source": findings_corpus[top1_idx[i]].get("source"),
                    "corpus": findings_corpus[top1_idx[i]].get("corpus"),
                    "id": findings_corpus[top1_idx[i]].get("finding_id"),
                    "title": findings_corpus[top1_idx[i]].get("title")[:80],
                },
            } for i in range(len(gt))],
        }
        out_file.write(json.dumps(rec) + "\n"); out_file.flush()
        aggregate["contests"] += 1
        aggregate["total_h"] += len(h_gt)
        aggregate["total_m"] += len(m_gt)
        aggregate["covered_h"] += h_covered
        aggregate["covered_m"] += m_covered
        sys.stderr.write(f"H={h_covered}/{len(h_gt)}  M={m_covered}/{len(m_gt)}\n")

    out_file.close()

    print("\n" + "=" * 70)
    print("AGGREGATE")
    print("=" * 70)
    print(f"  contests processed:       {aggregate['contests']}")
    print(f"  skipped (no findings):    {aggregate['skipped_no_findings']}")
    print(f"  skipped (fetch/extract):  {aggregate['skipped_fetch_fail']}")
    print(f"  total H findings:         {aggregate['total_h']}")
    print(f"  total M findings:         {aggregate['total_m']}")
    if aggregate["total_h"]:
        print(f"  H coverage (cos>{COS_THRESHOLD}):     "
              f"{aggregate['covered_h']}/{aggregate['total_h']} "
              f"({100*aggregate['covered_h']/aggregate['total_h']:.1f}%)")
    if aggregate["total_m"]:
        print(f"  M coverage (cos>{COS_THRESHOLD}):     "
              f"{aggregate['covered_m']}/{aggregate['total_m']} "
              f"({100*aggregate['covered_m']/aggregate['total_m']:.1f}%)")
    total = aggregate["total_h"] + aggregate["total_m"]
    if total:
        cov = aggregate["covered_h"] + aggregate["covered_m"]
        print(f"  TOTAL coverage:           {cov}/{total} ({100*cov/total:.1f}%)")
    print(f"  per-contest jsonl:        {OUT_PATH.relative_to(HERE)}")


if __name__ == "__main__":
    main()
