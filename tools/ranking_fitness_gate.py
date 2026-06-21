"""
tools/ranking_fitness_gate.py — sound-refutation gate for ranking-shaped
proposals. The structural analog of halmos for findings: a proposal that
changes how findings are ordered gets auto-tested against existing
scorer_v2 per-finding TP labels at top-K, and refused if it makes things
worse on data we already have.

The whole point (per notes/RANKING_FITNESS_GATE_SPEC_2026-06-20.md):
when a multi-agent synthesizer recommends "re-rank by X" or "dedupe by Y"
or "use signal Z instead of eigenvector," DON'T spend Modal/compute
testing it against new judgments. Apply it to the existing rerank-vs-
judgment data first — $0/call, ~2 seconds, hard verdict.

The 2026-06-20 session caught two such recommendations (dedupe-at-K +
centrality-inversion as dataflow-distance proxy) manually with the
predecessor of this primitive (tools/h14_lift_simulator.py). This file
is the extracted, reusable form.

Usage:

    from tools.ranking_fitness_gate import ranking_fitness_gate

    # A proposal is any callable: (findings, ctx) → reordered_findings.
    # ctx contains at least {"project_id": str}; callers can stash more via
    # closure.

    def dedup_at_k(findings, ctx):
        from tools.ranking_fitness_gate import topk_with_dedup
        return topk_with_dedup(findings, 10)

    verdict = ranking_fitness_gate(dedup_at_k, label="dedupe-at-K")
    if verdict["kill"]:
        print(f"REFUTED: {verdict['kill_reason']}")
    else:
        print(f"Approved: Δ={verdict['delta']:+.4f}")
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Callable, Iterable

# ── paths ───────────────────────────────────────────────────────────────────

HERE = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = HERE / "corpus" / "scabench" / "baseline-results"
DEFAULT_SCORES_DIR = HERE / "runs" / "scabench-scores"

K_DEFAULT = 10

# ── attribution helpers (shared with tools/scabench_rerank.py) ──────────────

def extract_fn_names(text: str) -> list[str]:
    """Pull camel/snake function-name candidates from free-text location/title.
    Same heuristic as tools/scabench_rerank.py:_extract_fn_names. Lives here
    so the dedupe-at-K proposal can attribute findings without re-running
    the re-ranker."""
    if not text:
        return []
    names: set[str] = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9]+)[:.]+([a-z_][A-Za-z0-9_]*)\b", text):
        names.add(f"{m.group(1)}.{m.group(2)}")
    for m in re.finditer(r"\b([a-z_][A-Za-z0-9_]*)\s*\(", text):
        names.add(m.group(1))
    return list(names)


def dedup_key(finding: dict) -> tuple:
    """(file, primary_fn) key for identifying duplicate findings on the same
    function. Unmapped findings keyed on their id so they don't collide."""
    loc = finding.get("location", "") or ""
    if isinstance(loc, list):
        loc = " ".join(str(x) for x in loc)
    title = finding.get("title", "") or ""
    if isinstance(title, list):
        title = " ".join(str(x) for x in title)
    fns = extract_fn_names(str(loc) + " " + str(title))
    file_ = finding.get("file") or ""
    if fns:
        return (file_, sorted(fns)[0])
    return ("_unmapped_", finding.get("id") or id(finding))


def topk_with_dedup(findings: list[dict], k: int) -> list[dict]:
    """Walk down `findings` in order, skip any whose dedup_key has already
    appeared, until k accepted (or input exhausted). Tops up with skipped
    findings if dedup leaves fewer than k."""
    out: list[dict] = []
    seen: set = set()
    for f in findings:
        key = dedup_key(f)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
        if len(out) >= k:
            break
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


# ── scoring ─────────────────────────────────────────────────────────────────

def score_at_k(findings: list[dict], tp_ids: set[str], expected: int,
               k: int = K_DEFAULT) -> tuple[float, float, float, int]:
    """Returns (precision, recall, F1, tp_count) for the top-k of `findings`
    given the set of finding-ids that are true positives and the count of
    expected ground-truth bugs."""
    topk = findings[:k]
    tp_at_k = sum(1 for f in topk if (f.get("id") in tp_ids))
    n = len(topk) or 1
    P = tp_at_k / n
    R = (tp_at_k / expected) if expected else 0.0
    F1 = (2.0 * P * R / (P + R)) if (P + R) else 0.0
    return P, R, F1, tp_at_k


# ── the gate ────────────────────────────────────────────────────────────────

Proposal = Callable[[list[dict], dict], list[dict]]


def ranking_fitness_gate(
    proposal: Proposal,
    *,
    label: str = "anonymous",
    reference: Proposal | None = None,
    reference_label: str = "baseline",
    scores_dir: str | Path = DEFAULT_SCORES_DIR,
    baseline_dir: str | Path = DEFAULT_BASELINE_DIR,
    K: int = K_DEFAULT,
    kill_threshold: float = -0.005,
    kill_min_loser_majority: float = 0.66,
    only_projects: Iterable[str] | None = None,
) -> dict:
    """Sound-refutation gate for ranking-shaped proposals.

    For each scored scabench project: applies `proposal(findings, ctx)` to
    the GPT-5 baseline finding list, simulates top-K macro F1 against the
    existing scorer_v2 per-finding TP labels, and compares to the baseline
    ordering (GPT-5 confidence).

    Args:
        proposal: callable (findings, ctx) → reordered_findings. ctx
            contains {"project_id": str} at minimum; callers can stash extra
            state via closure (e.g. precomputed H14 score maps).
        label: short identifier for this proposal (shows up in verdict).
        scores_dir: where scorer_v2 per-project score JSONs live. The
            score files supply matched_findings → TP id set, and
            total_expected → recall denominator.
        baseline_dir: where GPT-5's per-project baseline_<pid>.json files
            live. Supplies the finding list the proposal reorders.
        K: top-K truncation for F1.
        kill_threshold: macro F1 delta below this triggers a kill (default
            -0.005 = "lost half a percentage point").
        kill_min_loser_majority: of projects where |delta| > 0.005, this
            fraction must be NEGATIVE for kill=True. Prevents one bad
            outlier project from killing an otherwise-fine proposal.
        only_projects: optional iterable of project_ids to restrict the gate
            to a subset (e.g. just the 6 H14-losers for a targeted test).

    Returns:
        {
          "label": str,
          "K": int,
          "n_projects": int,
          "macro_F1_baseline": float,
          "macro_F1_proposal": float,
          "delta": float,                                   # proposal − baseline
          "n_helped": int, "n_hurt": int, "n_flat": int,
          "per_project_delta": {pid: float, ...},
          "kill": bool,
          "kill_reason": str,                               # "ok" if not killed
        }

    Sound-refutation property: kill=True means the proposal would have
    produced lower top-K macro F1 than baseline on the data we already
    have. It is NOT metaphysical certainty about future runs (judgments
    could change with a new judge model) but it IS hard ground truth for
    the question "is this proposal worse on what we've measured?"
    """
    scores_dir = Path(scores_dir)
    baseline_dir = Path(baseline_dir)
    only = set(only_projects) if only_projects is not None else None

    # Default reference = GPT-5 confidence ordering (identity-on-baseline).
    # When set, the gate compares proposal vs reference instead of vs baseline.
    # Use case: "does dedup improve on H14?" → reference = H14 proposal, not GPT-5.
    ref_fn: Proposal = reference if reference is not None else proposal_identity

    per_project_ref_F1: dict[str, float] = {}
    per_project_proposal_F1: dict[str, float] = {}

    for score_path in sorted(scores_dir.glob("score_*.json")):
        pid = score_path.stem[len("score_"):]
        if only is not None and pid not in only:
            continue
        bl_path = baseline_dir / f"baseline_{pid}.json"
        if not bl_path.exists():
            continue

        score = json.loads(score_path.read_text())
        bl = json.loads(bl_path.read_text())

        tp_ids = {m.get("found_id") for m in (score.get("matched_findings") or [])
                  if m.get("found_id")}
        expected = score.get("total_expected") or 0
        bl_findings = bl.get("findings") or []

        # Baseline = GPT-5 confidence order (descending, stable for ties)
        bl_sorted = sorted(bl_findings, key=lambda f: -(f.get("confidence") or 0))
        ctx = {"project_id": pid}

        try:
            ref_ordered = ref_fn(bl_sorted, ctx)
        except Exception:
            ref_ordered = bl_sorted
        try:
            prop_ordered = proposal(bl_sorted, ctx)
        except Exception:
            prop_ordered = bl_sorted

        _, _, F1_ref, _ = score_at_k(ref_ordered, tp_ids, expected, k=K)
        _, _, F1_pr, _ = score_at_k(prop_ordered, tp_ids, expected, k=K)
        per_project_ref_F1[pid] = F1_ref
        per_project_proposal_F1[pid] = F1_pr

    if not per_project_ref_F1:
        return {
            "label": label, "reference_label": reference_label, "K": K, "n_projects": 0,
            "macro_F1_reference": 0.0, "macro_F1_proposal": 0.0,
            "delta": 0.0, "n_helped": 0, "n_hurt": 0, "n_flat": 0,
            "per_project_delta": {},
            "kill": False, "kill_reason": "no_projects_to_evaluate",
        }

    deltas = {pid: per_project_proposal_F1[pid] - per_project_ref_F1[pid]
              for pid in per_project_ref_F1}
    macro_ref = statistics.mean(per_project_ref_F1.values())
    macro_pr = statistics.mean(per_project_proposal_F1.values())
    overall_delta = macro_pr - macro_ref

    flat_band = 0.005
    n_helped = sum(1 for d in deltas.values() if d > flat_band)
    n_hurt   = sum(1 for d in deltas.values() if d < -flat_band)
    n_flat   = sum(1 for d in deltas.values() if abs(d) <= flat_band)

    movers = n_helped + n_hurt
    loser_fraction = (n_hurt / movers) if movers else 0.0

    kill = (overall_delta < kill_threshold) and (loser_fraction >= kill_min_loser_majority)
    if kill:
        kill_reason = (
            f"Δmacro F1 {overall_delta:+.4f} < {kill_threshold:+.4f} threshold; "
            f"{n_hurt}/{movers} non-flat projects hurt "
            f"({loser_fraction:.0%} ≥ {kill_min_loser_majority:.0%} majority)"
        )
    else:
        if overall_delta < kill_threshold:
            kill_reason = (
                f"Δmacro F1 {overall_delta:+.4f} below threshold but only "
                f"{n_hurt}/{movers} non-flat projects hurt "
                f"({loser_fraction:.0%} < {kill_min_loser_majority:.0%} majority); "
                f"likely outlier-driven, not killed"
            )
        else:
            kill_reason = "ok"

    return {
        "label": label,
        "reference_label": reference_label,
        "K": K,
        "n_projects": len(deltas),
        "macro_F1_reference": macro_ref,
        "macro_F1_proposal": macro_pr,
        "delta": overall_delta,
        "n_helped": n_helped,
        "n_hurt": n_hurt,
        "n_flat": n_flat,
        "per_project_delta": deltas,
        "kill": kill,
        "kill_reason": kill_reason,
    }


# ── built-in proposals for sanity testing ────────────────────────────────────

def proposal_identity(findings: list[dict], ctx: dict) -> list[dict]:
    """Returns findings unchanged — proposal Δ should be exactly 0."""
    return findings


def proposal_dedup_at_k(K: int = K_DEFAULT) -> Proposal:
    """Returns a proposal that dedupes findings by attributed function before
    K-truncation. Applied to baseline (GPT-5 confidence) order: Δ≈+0.001."""
    def _proposal(findings: list[dict], ctx: dict) -> list[dict]:
        return topk_with_dedup(findings, K)
    return _proposal


def proposal_h14_rerank_from_disk(
    rerank_dir: str | Path = HERE / "runs" / "scabench-rerank",
) -> Proposal:
    """Returns a proposal that swaps in the pre-computed H14 re-ranked
    ordering for each project (from `tools/scabench_rerank.py`'s output).
    Falls back to baseline order if no rerank file exists for that project."""
    rerank_dir = Path(rerank_dir)
    def _proposal(findings: list[dict], ctx: dict) -> list[dict]:
        pid = ctx.get("project_id", "")
        rr_path = rerank_dir / f"{pid}.json"
        if not rr_path.exists():
            return findings
        rr = json.loads(rr_path.read_text())
        return rr.get("findings") or findings
    return _proposal


def proposal_compose(*proposals: Proposal) -> Proposal:
    """Compose proposals left-to-right: compose(A, B)(findings, ctx) = B(A(findings, ctx), ctx).
    Use to test "H14 reorder THEN dedup at K" as a single proposal — the
    composition that yielded the -0.0210 kill on 2026-06-20."""
    def _proposal(findings: list[dict], ctx: dict) -> list[dict]:
        out = findings
        for p in proposals:
            out = p(out, ctx)
        return out
    return _proposal


# ── CLI smoke ────────────────────────────────────────────────────────────────

def _print(v: dict) -> None:
    print(f"\n=== {v['label']} (K={v['K']}, N={v['n_projects']}, ref={v['reference_label']}) ===")
    print(f"macro F1 reference: {v['macro_F1_reference']:.4f}")
    print(f"macro F1 proposal:  {v['macro_F1_proposal']:.4f}")
    print(f"Δ:                  {v['delta']:+.4f}")
    print(f"helped: {v['n_helped']}, hurt: {v['n_hurt']}, flat: {v['n_flat']}")
    print(f"kill:               {v['kill']}")
    print(f"reason:             {v['kill_reason']}")


if __name__ == "__main__":
    # 1: identity proposal should be Δ=0, kill=False.
    print("Smoke 1 — identity proposal (expect Δ=0):")
    _print(ranking_fitness_gate(proposal_identity, label="identity"))

    # 2: dedup applied to baseline is approximately a no-op (matches yesterday's
    #    baseline_dedup measurement of +0.0012).
    print("\nSmoke 2 — dedup-at-K on baseline (expect Δ≈+0.001, kill=False):")
    _print(ranking_fitness_gate(proposal_dedup_at_k(K=10), label="dedup-at-K-on-baseline"))

    # 3: H14-rerank applied alone — should be the +0.0276 win we measured.
    print("\nSmoke 3 — H14 rerank from disk (expect Δ≈+0.028, kill=False):")
    _print(ranking_fitness_gate(proposal_h14_rerank_from_disk(), label="h14-rerank"))

    # 4: dedup-on-top-of-H14 with H14 as the REFERENCE — the question that
    #    came up yesterday. Should REPRODUCE yesterday's -0.0210 kill.
    print("\nSmoke 4 — dedup on top of H14 (ref=H14) (expect Δ≈-0.02, kill=True):")
    h14 = proposal_h14_rerank_from_disk()
    h14_plus_dedup = proposal_compose(h14, proposal_dedup_at_k(K=10))
    _print(ranking_fitness_gate(
        h14_plus_dedup,
        label="h14+dedup",
        reference=h14,
        reference_label="h14",
    ))
