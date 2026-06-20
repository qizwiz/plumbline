"""
tools/h14_lift_simulator.py — re-use existing scorer_v2 per-finding labels to
simulate top-K=10 macro F1 under four orderings without any new judge calls:

    1. baseline      — GPT-5 confidence order (corpus/scabench/baseline-results/)
    2. h14_old       — H14 eigenvector re-rank, pre-cleanup snapshot
    3. h14_new       — H14 with setdefault→max attribution fix
    4. h14_dedup     — h14_new + dedupe-at-K policy (skip a finding whose
                       attributed function has already appeared earlier in top-K)

A finding is counted TP if its id appears in `matched_findings[*].found_id`
of the per-project score file. This is the same definition scorer_v2 uses,
just applied at a top-K cutoff instead of over the full list.

Note: scorer_v2's matcher is 1-to-1 (each expected bug → one tool finding),
so this simulator slightly under-estimates the gain of any reordering that
surfaces a better-but-unmatched tool finding for an already-matched bug.
The bias is symmetric across the four conditions and doesn't change the
relative comparison.
"""
from __future__ import annotations
import json
import re
import statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent.parent
BASELINE_DIR = HERE / "corpus" / "scabench" / "baseline-results"
RERANK_OLD = HERE / "runs" / "scabench-rerank-pre-cleanup"
RERANK_NEW = HERE / "runs" / "scabench-rerank"
SCORES_DIR = HERE / "runs" / "scabench-scores"
H14_FEATURES_DIR = HERE / "runs" / "2026-06-10-h14-centralities-scabench-ast"

K = 10

# Marked H14-losers per scabench/h14_lift_2026-06-20.md (where Δ ≤ -0.05).
H14_LOSERS = {
    "code4rena_bakerfi-invitational_2025_02",
    "code4rena_kinetiq_2025_07",
    "cantina_smart-contract-audit-of-tn-contracts_2025_08",
    "sherlock_symmio_2025_03",
    "code4rena_blackhole_2025_07",
    "sherlock_idle-finance_2024_12",
}


def _extract_fn_names(text):
    """Same regex as scabench_rerank._extract_fn_names — needed to apply the
    dedupe-at-K policy from raw findings without re-running the re-ranker."""
    if not text:
        return []
    names = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]+)[:.]+([a-z_][A-Za-z0-9_]*)\b", text):
        names.add(f"{m.group(1)}.{m.group(2)}")
    for m in re.finditer(r"\b([a-z_][A-Za-z0-9_]*)\s*\(", text):
        names.add(m.group(1))
    return list(names)


def _dedup_key(finding):
    """The (file, primary_fn) key used to identify duplicate findings on the
    same function. Prefers `file` + first-extracted fn name; falls back to
    just the fn name; if no fn extractable, returns the finding id (so it's
    treated as unique)."""
    loc = finding.get("location", "") or ""
    if isinstance(loc, list):
        loc = " ".join(str(x) for x in loc)
    title = finding.get("title", "") or ""
    if isinstance(title, list):
        title = " ".join(str(x) for x in title)
    fns = _extract_fn_names(str(loc) + " " + str(title))
    file_ = finding.get("file") or ""
    if fns:
        return (file_, sorted(fns)[0])
    return ("_unmapped_", finding.get("id") or id(finding))


def topk_with_dedup(findings, k):
    out = []
    seen = set()
    for f in findings:
        key = _dedup_key(f)
        # Unmapped findings (key starts with _unmapped_) don't dedupe against
        # each other — they're unique by id.
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
        if len(out) >= k:
            break
    # If dedup removed too many to fill K, top up with any remaining findings
    if len(out) < k:
        chosen_ids = {f.get("id") or id(f) for f in out}
        for f in findings:
            fid = f.get("id") or id(f)
            if fid in chosen_ids:
                continue
            out.append(f)
            if len(out) >= k:
                break
    return out


def score_at_k(findings, tp_ids, expected, k=K):
    topk = findings[:k]
    tp_at_k = sum(1 for f in topk if (f.get("id") in tp_ids))
    n = len(topk) or 1
    P = tp_at_k / n
    R = (tp_at_k / expected) if expected else 0.0
    F1 = (2 * P * R / (P + R)) if (P + R) else 0.0
    return P, R, F1, tp_at_k


def _build_alt_score_maps(features):
    """Build node->score maps for the alternative-signal conditions.
    Returns (inv_eig_map, inv_deg_map, closeness_map). Includes a short-name
    fallback per the same take-max policy as scabench_rerank.py."""
    inv_eig, inv_deg, clos = {}, {}, {}
    for f in features:
        node = f.get("node")
        if not node:
            continue
        eig = f.get("eigenvector") or 0
        deg = f.get("degree") or 0
        cl = f.get("closeness") or 0
        # Invert: lower eig/degree → higher rank. Add epsilon to avoid /0.
        inv_eig[node] = 1.0 / (eig + 1e-6)
        inv_deg[node] = 1.0 / (deg + 1)  # deg can be 0
        clos[node] = cl
        if "." in node:
            fn = node.split(".", 1)[1]
            for m, v in ((inv_eig, inv_eig[node]),
                         (inv_deg, inv_deg[node]),
                         (clos, clos[node])):
                if v > m.get(fn, 0.0):
                    m[fn] = v
    return inv_eig, inv_deg, clos


def _rerank_by_signal(baseline_findings, score_map):
    """Re-rank a copy of baseline_findings by max-attributed score in score_map."""
    annotated = []
    for i, f in enumerate(baseline_findings):
        loc = f.get("location", "") or ""
        if isinstance(loc, list):
            loc = " ".join(str(x) for x in loc)
        title = f.get("title", "") or ""
        if isinstance(title, list):
            title = " ".join(str(x) for x in title)
        names = _extract_fn_names(str(loc) + " " + str(title))
        best = 0.0
        for nm in names:
            s = score_map.get(nm)
            if s is None:
                continue
            if s > best:
                best = s
        annotated.append((-best, i, f))
    annotated.sort()
    return [a[2] for a in annotated]


def run():
    rows = []
    for score_path in sorted(SCORES_DIR.glob("score_*.json")):
        pid = score_path.stem[len("score_"):]
        bl_path = BASELINE_DIR / f"baseline_{pid}.json"
        rr_old_path = RERANK_OLD / f"{pid}.json"
        rr_new_path = RERANK_NEW / f"{pid}.json"
        feat_path = H14_FEATURES_DIR / f"{pid}.json"
        if not all(p.exists() for p in (bl_path, rr_old_path, rr_new_path)):
            continue
        score = json.loads(score_path.read_text())
        bl = json.loads(bl_path.read_text())
        rr_old = json.loads(rr_old_path.read_text())
        rr_new = json.loads(rr_new_path.read_text())
        feats = json.loads(feat_path.read_text()) if feat_path.exists() else None

        tp_ids = {m.get("found_id") for m in (score.get("matched_findings") or [])
                  if m.get("found_id")}
        expected = score.get("total_expected") or 0
        bl_findings = bl.get("findings") or []

        # baseline = GPT-5's order (sort by confidence descending, stable)
        bl_sorted = sorted(bl_findings, key=lambda f: -(f.get("confidence") or 0))

        P_bl, R_bl, F1_bl, tp_bl = score_at_k(bl_sorted, tp_ids, expected)
        P_old, R_old, F1_old, tp_old = score_at_k(rr_old["findings"], tp_ids, expected)
        P_new, R_new, F1_new, tp_new = score_at_k(rr_new["findings"], tp_ids, expected)
        rr_new_dedup = topk_with_dedup(rr_new["findings"], K)
        P_dd, R_dd, F1_dd, tp_dd = score_at_k(rr_new_dedup, tp_ids, expected, k=K)

        # Synthesis-memo's actual claim: dedupe BEFORE ranking, applied to
        # BOTH conditions. Tests whether collapsing the leaf-leak helps the
        # baseline more than it hurts H14's hub-stacking.
        bl_prededuped = topk_with_dedup(bl_sorted, K)
        h14_new_prededuped = topk_with_dedup(rr_new["findings"], K)
        P_bdd, R_bdd, F1_bdd, tp_bdd = score_at_k(bl_prededuped, tp_ids, expected, k=K)
        # (h14_prededuped is the same as h14_dedup above; included for symmetry)

        # Alternative-signal re-rankings: invert-eig (memo's anti-symmetric
        # claim test), invert-degree (leaf-bias test), closeness (alt-hub).
        F1_inveig = F1_invdeg = F1_clos = 0.0
        tp_inveig = tp_invdeg = tp_clos = 0
        if feats:
            inv_eig_map, inv_deg_map, clos_map = _build_alt_score_maps(
                feats.get("features") or [])
            ie = _rerank_by_signal(bl_findings, inv_eig_map)
            id_ = _rerank_by_signal(bl_findings, inv_deg_map)
            cl = _rerank_by_signal(bl_findings, clos_map)
            _, _, F1_inveig, tp_inveig = score_at_k(ie, tp_ids, expected)
            _, _, F1_invdeg, tp_invdeg = score_at_k(id_, tp_ids, expected)
            _, _, F1_clos, tp_clos = score_at_k(cl, tp_ids, expected)

        rows.append({
            "project": pid,
            "expected": expected,
            "is_h14_loser": pid in H14_LOSERS,
            "total_TP_available": len(tp_ids),
            "tp@10_baseline": tp_bl, "F1_baseline": F1_bl,
            "tp@10_baseline_dedup": tp_bdd, "F1_baseline_dedup": F1_bdd,
            "tp@10_h14_old": tp_old, "F1_h14_old": F1_old,
            "tp@10_h14_new": tp_new, "F1_h14_new": F1_new,
            "tp@10_h14_dedup": tp_dd, "F1_h14_dedup": F1_dd,
            "tp@10_inv_eig": tp_inveig, "F1_inv_eig": F1_inveig,
            "tp@10_inv_deg": tp_invdeg, "F1_inv_deg": F1_invdeg,
            "tp@10_closeness": tp_clos, "F1_closeness": F1_clos,
        })

    def macro(key):
        return statistics.mean(r[key] for r in rows) if rows else 0.0

    print(f"K = {K}, N = {len(rows)} projects\n")
    print(f"{'condition':<20} {'macro F1 ALL':>13} {'macro F1 LOSERS':>17}")
    print("-" * 55)
    losers = [r for r in rows if r["is_h14_loser"]]
    print(f"  ({len(losers)} of {len(rows)} projects are H14-losers)\n")
    for cond in ("baseline", "baseline_dedup", "h14_old", "h14_new", "h14_dedup",
                 "inv_eig", "inv_deg", "closeness"):
        mf_all = macro(f"F1_{cond}")
        mf_losers = (statistics.mean(r[f"F1_{cond}"] for r in losers)
                     if losers else 0.0)
        print(f"{cond:<20} {mf_all:>13.4f} {mf_losers:>17.4f}")

    print(f"\nDelta vs baseline (macro F1):")
    base = macro("F1_baseline")
    for cond in ("h14_old", "h14_new", "h14_dedup"):
        d = macro(f"F1_{cond}") - base
        print(f"  {cond:<15} {d:+.4f}")

    print(f"\nDelta of new vs old (macro F1):  "
          f"{macro('F1_h14_new') - macro('F1_h14_old'):+.4f}")
    print(f"Delta of dedup vs new (macro F1): "
          f"{macro('F1_h14_dedup') - macro('F1_h14_new'):+.4f}")

    print(f"\nPer-project F1 (top losses + wins of dedup vs baseline):")
    rows.sort(key=lambda r: r["F1_h14_dedup"] - r["F1_baseline"])
    for r in rows[:6] + [None] + rows[-6:]:
        if r is None:
            print("  ...")
            continue
        d = r["F1_h14_dedup"] - r["F1_baseline"]
        print(f"  {d:+.3f}  base={r['F1_baseline']:.3f}  "
              f"old={r['F1_h14_old']:.3f}  new={r['F1_h14_new']:.3f}  "
              f"dedup={r['F1_h14_dedup']:.3f}  {r['project']}")

    # JSON dump
    out = {
        "K": K,
        "n_projects": len(rows),
        "macro_F1": {cond: macro(f"F1_{cond}") for cond in
                     ("baseline", "h14_old", "h14_new", "h14_dedup")},
        "per_project": rows,
    }
    (HERE / "runs" / "scabench-scores" / "lift_simulation.json").write_text(
        json.dumps(out, indent=2))
    print(f"\nWritten: runs/scabench-scores/lift_simulation.json")


if __name__ == "__main__":
    run()
