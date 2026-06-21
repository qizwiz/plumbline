"""
tools/gate_explore.py — fire ranking_fitness_gate on a battery of no-cost
proposals, save verdicts as JSON + markdown report. Builds the gate's
track record and locks in any proposals that beat the current production
ranker (H14_new) at $0/proposal.

Run:
    python tools/gate_explore.py

Output:
    runs/scabench-scores/gate_explore_<ts>.json   (machine-readable)
    notes/gate_explore_results.md                  (human-readable)
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ranking_fitness_gate import (
    HERE,
    K_DEFAULT,
    Proposal,
    extract_fn_names,
    proposal_compose,
    proposal_dedup_at_k,
    proposal_h14_rerank_from_disk,
    proposal_identity,
    ranking_fitness_gate,
    topk_with_dedup,
)

H14_FEATURES_DIR = HERE / "runs" / "2026-06-10-h14-centralities-scabench-ast"

H14_LOSERS = [
    "code4rena_bakerfi-invitational_2025_02",
    "code4rena_kinetiq_2025_07",
    "cantina_smart-contract-audit-of-tn-contracts_2025_08",
    "sherlock_symmio_2025_03",
    "code4rena_blackhole_2025_07",
    "sherlock_idle-finance_2024_12",
]


def _load_features(pid: str) -> list[dict]:
    p = H14_FEATURES_DIR / f"{pid}.json"
    if not p.exists():
        return []
    return (json.loads(p.read_text()).get("features") or [])


def _score_map(features: list[dict], signal: str, invert: bool = False) -> dict[str, float]:
    """Build node→score map from H14 features for the given signal."""
    out: dict[str, float] = {}
    for f in features:
        node = f.get("node")
        if not node:
            continue
        v = f.get(signal) or 0
        score = (1.0 / (v + 1e-6)) if invert else float(v)
        out[node] = max(out.get(node, 0.0), score)
        if "." in node:
            short = node.split(".", 1)[1]
            out[short] = max(out.get(short, 0.0), score)
    return out


def _attribute(finding: dict, score_map: dict[str, float]) -> float:
    loc = finding.get("location", "") or ""
    if isinstance(loc, list):
        loc = " ".join(str(x) for x in loc)
    title = finding.get("title", "") or ""
    if isinstance(title, list):
        title = " ".join(str(x) for x in title)
    names = extract_fn_names(str(loc) + " " + str(title))
    best = 0.0
    for nm in names:
        s = score_map.get(nm)
        if s is not None and s > best:
            best = s
    return best


def proposal_by_h14_signal(signal: str, invert: bool = False) -> Proposal:
    """Reorder by a single H14 feature (eigenvector, katz, betweenness, closeness,
    degree, clustering). invert=True flips so low → high rank."""
    def _p(findings: list[dict], ctx: dict) -> list[dict]:
        feats = _load_features(ctx.get("project_id", ""))
        if not feats:
            return findings
        sm = _score_map(feats, signal, invert=invert)
        return sorted(findings, key=lambda f: -_attribute(f, sm))
    return _p


def _composite_score_map(features: list[dict], weights: dict[str, float]) -> dict[str, float]:
    """Build a node→score map as a weighted sum of feature columns."""
    out: dict[str, float] = {}
    for f in features:
        node = f.get("node")
        if not node:
            continue
        score = sum(w * (f.get(signal) or 0) for signal, w in weights.items())
        out[node] = max(out.get(node, 0.0), score)
        if "." in node:
            short = node.split(".", 1)[1]
            out[short] = max(out.get(short, 0.0), score)
    return out


def proposal_weighted_composite(weights: dict[str, float]) -> Proposal:
    """Reorder by an arbitrary weighted sum of H14 features."""
    def _p(findings: list[dict], ctx: dict) -> list[dict]:
        feats = _load_features(ctx.get("project_id", ""))
        if not feats:
            return findings
        sm = _composite_score_map(feats, weights)
        return sorted(findings, key=lambda f: -_attribute(f, sm))
    return _p


def proposal_reciprocal_rank_fusion(*proposals: Proposal, k_const: int = 60) -> Proposal:
    """Reciprocal rank fusion across multiple proposals — the standard rank
    aggregation method from IR. Each proposal's ordering contributes
    1/(k + rank) per finding; sum across proposals, sort descending.

    k_const=60 is the textbook default (Cormack et al. 2009). Lower k_const
    amplifies the top of each list; higher dampens it."""
    def _p(findings: list[dict], ctx: dict) -> list[dict]:
        scores: dict = {}
        for p in proposals:
            try:
                ordered = p(findings, ctx)
            except Exception:
                continue
            for rank, f in enumerate(ordered):
                fid = f.get("id") or id(f)
                scores[fid] = scores.get(fid, 0.0) + 1.0 / (k_const + rank)
        return sorted(findings, key=lambda f: -scores.get(f.get("id") or id(f), 0.0))
    return _p


def proposal_severity_tiebreak(reference: Proposal) -> Proposal:
    """Same as reference, but tiebreak by severity (high → low) when reference
    leaves equal score within a stable-sort window. Approximation: take top-50
    from reference, re-sort by severity descending, append the rest."""
    SEV = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    def _p(findings: list[dict], ctx: dict) -> list[dict]:
        ref = reference(findings, ctx)
        if len(ref) <= 1:
            return ref
        head = ref[:50]
        tail = ref[50:]
        head_sorted = sorted(
            head,
            key=lambda f: -SEV.get(str(f.get("severity", "")).lower(), 0),
        )
        return head_sorted + tail
    return _p


def proposal_h14_confidence_tiebreak(h14: Proposal) -> Proposal:
    """H14 ordering, but break ties using the finding's reported confidence
    (descending). Implementation: take H14 top-30, sort by GPT-5 confidence
    descending within that window, append the rest unchanged."""
    def _p(findings: list[dict], ctx: dict) -> list[dict]:
        ref = h14(findings, ctx)
        if len(ref) <= 1:
            return ref
        head = ref[:30]
        tail = ref[30:]
        head_sorted = sorted(head, key=lambda f: -(f.get("confidence") or 0))
        return head_sorted + tail
    return _p


def _row(verdict: dict, expected_sign: str | None = None) -> dict:
    """Compact a verdict for the markdown table."""
    return {
        "label": verdict["label"],
        "ref": verdict["reference_label"],
        "delta": verdict["delta"],
        "helped": verdict["n_helped"],
        "hurt": verdict["n_hurt"],
        "flat": verdict["n_flat"],
        "kill": verdict["kill"],
        "reason": verdict["kill_reason"],
        "expected": expected_sign,
    }


def run() -> None:
    h14 = proposal_h14_rerank_from_disk()
    closeness = proposal_by_h14_signal("closeness")
    katz = proposal_by_h14_signal("katz")
    betweenness = proposal_by_h14_signal("betweenness")
    inv_eig = proposal_by_h14_signal("eigenvector", invert=True)
    inv_deg = proposal_by_h14_signal("degree", invert=True)
    dedup = proposal_dedup_at_k(K=10)
    severity_tiebreak_h14 = proposal_severity_tiebreak(h14)
    confidence_tiebreak_h14 = proposal_h14_confidence_tiebreak(h14)

    # Battery: (label, proposal, reference_proposal, reference_label, expected_sign)
    battery: list[tuple[str, Proposal, Proposal, str, str | None]] = [
        # --- known regressions for sanity (must reproduce yesterday's kills) ---
        ("h14+dedup",                         proposal_compose(h14, dedup), h14, "h14",      "neg"),
        ("inv_eig",                           inv_eig,                       None, "baseline", "neg"),

        # --- known wins (must reproduce) ---
        ("h14",                               h14,                           None, "baseline", "pos"),
        ("baseline+dedup",                    dedup,                         None, "baseline", "flat"),

        # --- new exploration (no expectation set) ---
        ("closeness",                         closeness,                     None, "baseline", None),
        ("katz",                              katz,                          None, "baseline", None),
        ("betweenness",                       betweenness,                   None, "baseline", None),
        ("inv_deg",                           inv_deg,                       None, "baseline", None),

        # --- vs H14: anything beat the production ranker? ---
        ("closeness  vs h14",                 closeness,                     h14, "h14",       None),
        ("katz       vs h14",                 katz,                          h14, "h14",       None),
        ("betweenness vs h14",                betweenness,                   h14, "h14",       None),
        ("h14+severity-tiebreak vs h14",      severity_tiebreak_h14,         h14, "h14",       None),
        ("h14+confidence-tiebreak vs h14",    confidence_tiebreak_h14,       h14, "h14",       None),

        # --- loser-only: targeted improvement on the 6 H14-loss projects ---
        ("inv_eig (losers only)",             inv_eig,                       None, "baseline", "?"),
        ("closeness (losers only)",           closeness,                     None, "baseline", "?"),
        ("severity-tiebreak (losers only)",   severity_tiebreak_h14,         h14, "h14",       "?"),

        # --- weighted-composite sweep: alternatives to default 0.6/0.3/0.1 ---
        ("composite 0.4/0.4/0.2",             proposal_weighted_composite({"eigenvector":0.4,"katz":0.4,"betweenness":0.2}), h14, "h14", "?"),
        ("composite 0.5/0.3/0.2",             proposal_weighted_composite({"eigenvector":0.5,"katz":0.3,"betweenness":0.2}), h14, "h14", "?"),
        ("composite 0.7/0.2/0.1",             proposal_weighted_composite({"eigenvector":0.7,"katz":0.2,"betweenness":0.1}), h14, "h14", "?"),
        ("composite 0.5/0.25/0.25",           proposal_weighted_composite({"eigenvector":0.5,"katz":0.25,"betweenness":0.25}), h14, "h14", "?"),
        ("composite + closeness 0.5/0.2/0.1/0.2", proposal_weighted_composite({"eigenvector":0.5,"katz":0.2,"betweenness":0.1,"closeness":0.2}), h14, "h14", "?"),

        # --- rank-aggregation ensembles: can voting beat the best individual? ---
        ("RRF(h14, katz, closeness)",         proposal_reciprocal_rank_fusion(h14, katz, closeness), h14, "h14", "?"),
        ("RRF(h14, katz, closeness, bet)",    proposal_reciprocal_rank_fusion(h14, katz, closeness, betweenness), h14, "h14", "?"),
        ("RRF(katz, closeness, bet)",         proposal_reciprocal_rank_fusion(katz, closeness, betweenness), h14, "h14", "?"),
    ]

    results = []
    print(f"{'proposal':<40} {'ref':<10} {'Δ':>8}  {'helped':>3}/{'hurt':>3}/{'flat':>3}  kill?")
    print("-" * 90)
    for label, proposal, reference, ref_label, expected in battery:
        only = H14_LOSERS if "(losers only)" in label else None
        v = ranking_fitness_gate(
            proposal,
            label=label,
            reference=reference,
            reference_label=ref_label,
            only_projects=only,
        )
        row = _row(v, expected_sign=expected)
        results.append(row)
        kill_marker = "🛑" if row["kill"] else "  "
        print(f"{label:<40} {ref_label:<10} {row['delta']:+.4f}  "
              f"{row['helped']:>3}/{row['hurt']:>3}/{row['flat']:>3}  {kill_marker}")

    out_path = HERE / "notes" / "gate_explore_results.md"
    summary = _format_markdown(results)
    out_path.write_text(summary)
    print(f"\nWritten: {out_path.relative_to(HERE)}")

    json_path = HERE / "runs" / "scabench-scores" / "gate_explore.json"
    json_path.write_text(json.dumps(results, indent=2))
    print(f"Written: {json_path.relative_to(HERE)}")


def _format_markdown(rows: list[dict]) -> str:
    out = ["# Gate exploration battery — auto-generated by `tools/gate_explore.py`",
           "",
           "Verdict of `ranking_fitness_gate` on a battery of no-cost ranking proposals against the scabench scorer_v2 judgments. Each row is one A/B at top-K=10 over 24 (or 6 for loser-only) projects.",
           "",
           "| proposal | reference | Δ macro F1 | helped | hurt | flat | kill | expected | reason |",
           "|---|---|---:|---:|---:|---:|:---:|:---:|---|"]
    for r in rows:
        kill_str = "**🛑 YES**" if r["kill"] else "ok"
        exp = r.get("expected") or "—"
        reason_short = (r["reason"] or "")[:90]
        out.append(f"| `{r['label']}` | `{r['ref']}` | {r['delta']:+.4f} | "
                   f"{r['helped']} | {r['hurt']} | {r['flat']} | {kill_str} | {exp} | {reason_short} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    run()
