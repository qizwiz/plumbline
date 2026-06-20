"""
tools/scabench_rerank.py — write per-project tool-result JSONs in scorer_v2's
expected shape, with GPT-5's baseline findings re-ordered by plumbline's
eigenvector centrality.

Input:
  corpus/scabench/baseline-results/baseline_<project>.json   GPT-5 findings
  runs/2026-06-10-h14-centralities-scabench-ast/<project>.json   per-fn features

Output:
  runs/scabench-rerank/<project>.json   findings list reordered

Then run:
  python /tmp/scabench-eval/scoring/scorer_v2.py \\
    --benchmark corpus/scabench/curated.json \\
    --results-dir runs/scabench-rerank/ \\
    --output runs/scabench-scores/ \\
    --model gpt-4o-mini

Function-name extraction from GPT-5's `location` field is best-effort
regex; unmappable findings keep their original order (sorted last by stable
sort). Same matching rule as H14 §4.8.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent.parent
CURATED = HERE / "corpus" / "scabench" / "curated.json"
BASELINE_DIR = HERE / "corpus" / "scabench" / "baseline-results"
H14_DIR = HERE / "runs" / "2026-06-10-h14-centralities-scabench-ast"
OUT_DIR = HERE / "runs" / "scabench-rerank"


def _extract_fn_names(text: str) -> list[str]:
    """Pull camel/snake function-name candidates from free-text location/title."""
    if not text:
        return []
    names = set()
    # `Contract.functionName` or `Contract::functionName`
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]+)[:.]+([a-z_][A-Za-z0-9_]*)\b", text):
        names.add(f"{m.group(1)}.{m.group(2)}")
    # `functionName()` bare
    for m in re.finditer(r"\b([a-z_][A-Za-z0-9_]*)\s*\(", text):
        names.add(m.group(1))
    return list(names)


def _build_node_score_map(h14_features: list) -> dict[str, float]:
    """Map node name -> composite plumbline score (eigenvector + katz + betweenness)."""
    out = {}
    for f in h14_features:
        node = f.get("node")
        if not node:
            continue
        # Composite: heaviest weight on eigenvector (paper's lead),
        # bit of katz + betweenness for robustness on disconnected graphs.
        eig = f.get("eigenvector") or 0
        katz = f.get("katz") or 0
        bet = f.get("betweenness") or 0
        score = 0.6 * eig + 0.3 * katz + 0.1 * bet
        # Also store the function-only suffix for fuzzy match
        out[node] = score
        if "." in node:
            fn = node.split(".", 1)[1]
            # Take max across contracts: when GPT-5's finding mentions a bare
            # function name (e.g. "permitWrap") that exists on several
            # contracts, we want it attributed to the highest-centrality
            # version, not whichever one happened to be enumerated first.
            # Fixed 2026-06-20 — old `setdefault` lost permitWrap on tn-contracts.
            if score > out.get(fn, 0.0):
                out[fn] = score
    return out


def rerank_one(project_id: str) -> tuple[Path, dict]:
    """Write reordered findings JSON. Returns (output_path, stats)."""
    baseline_path = BASELINE_DIR / f"baseline_{project_id}.json"
    h14_path = H14_DIR / f"{project_id}.json"
    if not baseline_path.exists():
        return None, {"error": f"no baseline at {baseline_path}"}
    if not h14_path.exists():
        return None, {"error": f"no H14 features at {h14_path}"}
    baseline = json.loads(baseline_path.read_text())
    h14 = json.loads(h14_path.read_text())

    score_map = _build_node_score_map(h14.get("features") or [])
    findings = baseline.get("findings") or []

    annotated = []
    n_mapped = 0
    for i, f in enumerate(findings):
        # Some baselines have list-typed location; flatten to string
        loc = f.get("location", "") or ""
        if isinstance(loc, list):
            loc = " ".join(str(x) for x in loc)
        title = f.get("title", "") or ""
        if isinstance(title, list):
            title = " ".join(str(x) for x in title)
        text = str(loc) + " " + str(title)
        names = _extract_fn_names(text)
        best = 0.0
        matched_via = None
        for nm in names:
            s = score_map.get(nm)
            if s is None:
                continue
            if s > best:
                best = s
                matched_via = nm
        if matched_via:
            n_mapped += 1
        annotated.append((-best, i, f, matched_via))

    # Stable sort: higher score first, original order for ties
    annotated.sort()
    reordered = [a[2] for a in annotated]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{project_id}.json"
    # Preserve the baseline's top-level keys so scorer_v2 can find them
    out = dict(baseline)
    out["findings"] = reordered
    out["plumbline_rerank"] = {
        "n_findings": len(findings),
        "n_mapped": n_mapped,
        "h14_source": str(h14_path.relative_to(HERE)),
        "ranker": "eigenvector*0.6 + katz*0.3 + betweenness*0.1",
    }
    out_path.write_text(json.dumps(out, indent=2, default=str))
    return out_path, {"n_findings": len(findings), "n_mapped": n_mapped}


def main():
    project_ids = sys.argv[1:]
    if not project_ids:
        # Default: all projects with both a baseline and an H14 feature file
        project_ids = sorted({p.stem.replace("baseline_", "")
                              for p in BASELINE_DIR.glob("baseline_*.json")
                              if (H14_DIR / f"{p.stem.replace('baseline_', '')}.json").exists()})
    print(f"reranking {len(project_ids)} projects -> {OUT_DIR.relative_to(HERE)}")
    print()
    results = []
    for pid in project_ids:
        path, stats = rerank_one(pid)
        if path:
            print(f"  ✓ {pid:50s}  {stats['n_mapped']}/{stats['n_findings']} mapped")
            results.append({"project_id": pid, **stats, "path": str(path.relative_to(HERE))})
        else:
            print(f"  ✗ {pid:50s}  {stats.get('error')}")
    print()
    total_mapped = sum(r["n_mapped"] for r in results)
    total_findings = sum(r["n_findings"] for r in results)
    print(f"summary: {len(results)} projects, {total_mapped}/{total_findings} findings mapped "
          f"({100*total_mapped/max(total_findings,1):.1f}%)")
    print()
    print(f"next: export OPENAI_API_KEY=sk-... && python /tmp/scabench-eval/scoring/scorer_v2.py \\")
    print(f"        --benchmark {CURATED.relative_to(HERE)} \\")
    print(f"        --results-dir {OUT_DIR.relative_to(HERE)} \\")
    print(f"        --output runs/scabench-scores/ \\")
    print(f"        --model gpt-4o")


if __name__ == "__main__":
    main()
