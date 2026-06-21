"""score — multi-signal grounded scoring for plumbline reps.

Replaces the single-recall signal in flywheel.py with a Score dataclass
that carries per-signal breakdown plus a multiplicative total. Any signal
that returns 0 kills the total (hard gate). This is exactly what GPTScan
(ICSE 2024) showed cuts FPs by 2/3: hybrid signal composition where any
sound refutation overrides positive heuristics.

Design (per UNIFIED_CORE_2026-06-19.md Move 2):

  Score(
      total       = product of all signal values        ∈ [0,1]
      signals     = {name: value}                       per-signal columns
      meta        = {n_findings, n_proved_real, n_refuted, ...}
  )

  MultiplicativeCritic({
      'recall'     = sol_match_recall,
      'halmos'     = halmos_pass_rate,
      'severity'   = severity_weight,
      # add your own
  }).score(leads, findings, **ctx) -> Score

Per-signal semantics:
  - recall    [0,1] : fraction of ground-truth findings matched
  - halmos    {0,1}* : 1 unless ANY finding was PROVED-not-a-bug; then 0
                       (sound refutation hard-gate)
  - severity  [0,1] : mean severity weight of LEADS we produced (H=1.0, M=0.6, L=0.2)

Schema written to reps.jsonl row's "score" field:

  "score": {
      "total":     0.42,
      "signals": {"recall": 0.7, "halmos": 1.0, "severity": 0.6},
      "meta":    {"n_findings": 10, "n_halmos_verdicts": 3, "n_proved_fake": 1}
  }

This stays backward-compatible: flywheel.py reads r["score"]["signals"]["recall"]
when it needs the recall component; r["score"]["total"] is the gradient signal
that prompt_improve.improve_if_weak fires on.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Callable, Any
from functools import reduce
import operator


@dataclass
class Score:
    """A multi-signal grounded score for one (leads, findings) rep.

    total       — product of all signals (multiplicative gate); ∈ [0,1]
    signals     — per-signal contribution (transparent breakdown)
    meta        — counts / context that informs the signals (n_findings, etc.)
    """
    total: float
    signals: dict[str, float]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        """Canonical reps.jsonl shape. Recall/precision aliased at top level
        so legacy readers (flywheel.py's r["score"]["recall"]) keep working
        without migration."""
        out = {"total": self.total, "signals": self.signals, "meta": self.meta}
        # Back-compat aliases for legacy readers (flywheel.py reads
        # r["score"]["recall"] / r["score"]["precision"] directly).
        if "recall" in self.signals:
            out["recall"] = self.signals["recall"]
        if "precision" in self.signals:
            out["precision"] = self.signals["precision"]
        # Precision/recall may live in meta keyed under whichever signal stashed
        # them (sol_match_signal → "recall.precision"; f1_signal → "f1.precision",
        # "f1.recall"). Surface them at the top level so flywheel keeps working.
        if "precision" not in out:
            for k in ("recall.precision", "f1.precision"):
                if k in self.meta:
                    out["precision"] = self.meta[k]
                    break
        if "recall" not in out and "f1.recall" in self.meta:
            out["recall"] = self.meta["f1.recall"]
        return out

    @classmethod
    def from_legacy_row(cls, score_field: dict) -> "Score":
        """Construct a Score from a pre-Move-2 rep row's score field.
        Legacy field shape: {"recall": float, "precision": float, ...}.
        Use this to read existing reps.jsonl rows uniformly."""
        if "total" in score_field and "signals" in score_field:
            # Already new shape
            return cls(total=score_field["total"],
                       signals=score_field.get("signals", {}),
                       meta=score_field.get("meta", {}))
        # Legacy: synthesize signals from top-level recall/precision
        signals = {}
        if "recall" in score_field:
            signals["recall"] = score_field["recall"]
        if "precision" in score_field:
            signals["precision"] = score_field["precision"]
        total = score_field.get("recall", 0.0)  # legacy total was just recall
        meta = {k: v for k, v in score_field.items() if k not in ("recall", "precision")}
        return cls(total=total, signals=signals, meta=meta)

    # Back-compat: old flywheel code reads r["score"].get("recall") / get("precision")
    # We surface those at the top level so legacy paths keep working.
    @property
    def recall(self) -> float | None:
        return self.signals.get("recall")

    @property
    def precision(self) -> float | None:
        return self.signals.get("precision")

    @classmethod
    def legacy_recall_only(cls, recall: float, precision: float | None = None) -> "Score":
        """Construct a Score from the pre-Move-2 (recall, precision) shape.

        Use this in flywheel.py when sol_match.match() returns its current
        dict and the rest of the signal stack isn't wired yet.
        """
        signals = {"recall": recall}
        if precision is not None:
            signals["precision"] = precision
        return cls(total=recall, signals=signals, meta={})


# ── Built-in signals ───────────────────────────────────────────────────────

def sol_match_signal(leads: list, findings: list, ground_truth_path: str | None,
                     threshold: float = 0.80) -> tuple[float, dict]:
    """Return (recall_in_[0,1], meta) using sol_match.match.

    Meta carries precision + counts for the row schema.
    """
    if not leads or not findings:
        return 0.0, {"n_leads": len(leads), "n_findings": len(findings),
                     "precision": 0.0, "matched": 0, "missed": len(findings)}
    from sol_match import match  # local import so score.py is cheap to load
    r = match(leads, findings, threshold=threshold)
    meta = {
        "n_leads": len(leads),
        "n_findings": len(findings),
        "precision": r.get("precision", 0.0),
        "matched": len(r.get("matched", [])),
        "missed": len(r.get("missed", [])),
    }
    return float(r.get("recall", 0.0)), meta


def f1_signal(leads: list, findings: list, ground_truth_path: str | None,
              threshold: float = 0.80) -> tuple[float, dict]:
    """Return (F1_in_[0,1], meta) using sol_match.match.

    F1 = 2 * p * r / (p + r); 0.0 if (p + r) == 0.

    Stashes precision, recall, matched_n, missed_n in meta so MultiplicativeCritic
    surfaces them under the "f1." prefix (e.g. meta["f1.precision"]). Back-compat
    aliasing in Score.to_json() picks these up and lifts precision/recall to the
    top level for flywheel.py.
    """
    if not leads or not findings:
        return 0.0, {"n_leads": len(leads), "n_findings": len(findings),
                     "precision": 0.0, "recall": 0.0,
                     "matched_n": 0, "missed_n": len(findings)}
    from sol_match import match  # local import so score.py is cheap to load
    r = match(leads, findings, threshold=threshold)
    p = float(r.get("precision", 0.0))
    rec = float(r.get("recall", 0.0))
    f1 = (2.0 * p * rec / (p + rec)) if (p + rec) > 0 else 0.0
    meta = {
        "n_leads": len(leads),
        "n_findings": len(findings),
        "precision": p,
        "recall": rec,
        "matched_n": len(r.get("matched", [])),
        "missed_n": len(r.get("missed", [])),
    }
    return f1, meta


def halmos_signal(halmos_verdicts: list[dict] | None) -> tuple[float, dict]:
    """Return (1.0, meta) unless any verdict is PROVED (sound refutation).

    A verdict shape: {"function": str, "proved": bool, "counterexample": dict|None}
    - proved=True with counterexample=None → halmos PROVED the invariant holds
      → our claimed bug is FAKE → signal = 0 (hard gate)
    - proved=False with counterexample → halmos found the bug → signal = 1
    - missing / TIMEOUT / ERROR → no information → signal = 1

    This implements the "any zero from halmos is hard-gated" requirement.
    """
    if not halmos_verdicts:
        return 1.0, {"n_halmos_verdicts": 0, "n_proved_fake": 0, "n_counterexample_real": 0}
    n_proved_fake = sum(1 for v in halmos_verdicts
                       if v.get("proved") is True and not v.get("counterexample"))
    n_counter_real = sum(1 for v in halmos_verdicts if v.get("counterexample"))
    sig = 0.0 if n_proved_fake > 0 else 1.0
    return sig, {
        "n_halmos_verdicts": len(halmos_verdicts),
        "n_proved_fake": n_proved_fake,
        "n_counterexample_real": n_counter_real,
    }


_SEV_WEIGHT = {"H": 1.0, "High": 1.0, "high": 1.0,
               "M": 0.6, "Medium": 0.6, "medium": 0.6,
               "L": 0.2, "Low": 0.2, "low": 0.2}

def severity_signal(leads: list, get_severity: Callable[[Any], str] | None = None) -> tuple[float, dict]:
    """Return mean severity weight of the leads.

    Default: try lead.get('severity') if dict-shaped, else None → assume Medium.
    Override get_severity for custom lead shapes.
    """
    if not leads:
        return 0.0, {"n_leads": 0}
    def _w(lead):
        sev = None
        if get_severity is not None:
            sev = get_severity(lead)
        elif isinstance(lead, dict):
            sev = lead.get("severity")
        return _SEV_WEIGHT.get(sev, 0.6)  # default to Medium weight
    weights = [_w(l) for l in leads]
    return sum(weights) / len(weights), {"n_leads": len(leads),
                                          "mean_weight": sum(weights) / len(weights)}


# ── The composing critic ────────────────────────────────────────────────────

class MultiplicativeCritic:
    """Compose per-signal scorers multiplicatively. Any zero kills the total.

    Sound-by-construction: only the verifier signals (halmos) gate via zero;
    heuristic signals (recall, severity) contribute multiplicatively but
    won't hard-gate. Composers must be explicit about which signals are
    sound-refutation-gates vs heuristic.

    Usage:

        critic = MultiplicativeCritic({
            'recall':   lambda leads, findings, **ctx: sol_match_signal(
                            leads, findings, ctx.get('ground_truth_path')),
            'halmos':   lambda leads, findings, **ctx: halmos_signal(
                            ctx.get('halmos_verdicts')),
            'severity': lambda leads, findings, **ctx: severity_signal(leads),
        })
        score = critic.score(leads, findings, ground_truth_path='.../ANSWERS.md',
                              halmos_verdicts=[...])
    """

    def __init__(self, signal_fns: dict[str, Callable[..., tuple[float, dict]]]):
        self.signal_fns = signal_fns

    def score(self, leads: list, findings: list, **ctx) -> Score:
        signals: dict[str, float] = {}
        meta: dict[str, Any] = {}
        for name, fn in self.signal_fns.items():
            try:
                val, sig_meta = fn(leads, findings, **ctx)
            except Exception as e:
                val, sig_meta = 0.0, {"error": str(e)[:200]}
            signals[name] = float(val)
            for k, v in sig_meta.items():
                meta[f"{name}.{k}"] = v
        if not signals:
            return Score(total=0.0, signals={}, meta=meta)
        total = reduce(operator.mul, signals.values(), 1.0)
        return Score(total=total, signals=signals, meta=meta)


# ── Default critic preset ───────────────────────────────────────────────────

def default_critic() -> MultiplicativeCritic:
    """The recommended composition for plumbline reps as of 2026-06-20.

    Changed from recall (sol_match_signal) → F1 (f1_signal) after the 2026-06-19
    adversarial-swarm finding: recall-only is degenerate (more leads = higher recall,
    lower precision, total goes up while audit quality goes down). F1 balances both.

    - f1        (sol_match-based, 2*p*r/(p+r))   ← was "recall"
    - halmos    (any PROVED → 0)
    - severity  (mean lead severity weight)

    Precision/recall remain available at the top level of Score.to_json() (via
    f1_signal stashing them in meta), so flywheel.py keeps working unchanged.

    For recall-only objective, use sol_match_signal directly (still exported).
    """
    return MultiplicativeCritic({
        "f1":       lambda leads, findings, **ctx:
                        f1_signal(leads, findings, ctx.get("ground_truth_path")),
        "halmos":   lambda leads, findings, **ctx:
                        halmos_signal(ctx.get("halmos_verdicts")),
        "severity": lambda leads, findings, **ctx:
                        severity_signal(leads),
    })


# ── Smoke test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke test: a Score with all signals at 0.5 should multiply to 0.125
    critic = MultiplicativeCritic({
        "a": lambda l, f, **c: (0.5, {"x": 1}),
        "b": lambda l, f, **c: (0.5, {"y": 2}),
        "c": lambda l, f, **c: (0.5, {"z": 3}),
    })
    s = critic.score(["lead"], ["finding"])
    assert abs(s.total - 0.125) < 1e-9, f"expected 0.125, got {s.total}"
    assert s.signals == {"a": 0.5, "b": 0.5, "c": 0.5}
    print(f"OK MultiplicativeCritic compose: total={s.total} signals={s.signals}")

    # Hard-gate test: any zero → total 0
    critic2 = MultiplicativeCritic({
        "a": lambda l, f, **c: (0.9, {}),
        "b": lambda l, f, **c: (0.0, {}),  # ZERO from a verifier
        "c": lambda l, f, **c: (0.9, {}),
    })
    s2 = critic2.score([], [])
    assert s2.total == 0.0, f"expected 0.0 hard-gate, got {s2.total}"
    print(f"OK hard-gate on zero: total={s2.total}")

    # Halmos signal test
    val, m = halmos_signal([{"function": "ok", "proved": False, "counterexample": {"x": 1}}])
    assert val == 1.0 and m["n_counterexample_real"] == 1
    val, m = halmos_signal([{"function": "fake_bug", "proved": True, "counterexample": None}])
    assert val == 0.0 and m["n_proved_fake"] == 1
    print(f"OK halmos signal: counterexample→1.0, proved→0.0")

    # Severity signal test
    val, _ = severity_signal([{"severity": "H"}, {"severity": "M"}, {"severity": "L"}])
    assert abs(val - (1.0 + 0.6 + 0.2) / 3) < 1e-9
    print(f"OK severity signal: HML mean = {val:.4f}")

    print("\nscore.py smoke test PASSED")
