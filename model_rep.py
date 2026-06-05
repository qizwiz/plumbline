"""
model_rep — rep with the MODEL in the proposer slot. Replaces hand-crafted leads
(first_rep) with whatever sol_intent.py emits when pointed at a contract.

This is where the loop stops being predictable: I can no longer guess the recall
number. The scoreboard becomes informative — every row is a real data point about
what sol_intent does on a given corpus shape.

Usage:
  python model_rep.py examples/synthetic-dreusd
  python model_rep.py examples/synthetic-dreusd examples/synthetic-dreusd-2 ...
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sol_match
import rep_log

PY = os.path.join(HERE, ".venv/bin/python")


def run_one(ex_path: str, truth_override: str | None = None) -> dict:
    ex_abs = os.path.join(HERE, ex_path) if not os.path.isabs(ex_path) else ex_path
    if truth_override:
        truth = (os.path.join(HERE, truth_override)
                 if not os.path.isabs(truth_override) else truth_override)
    else:
        # Probe several conventions: synthetic twins use .ANSWERS.md, real-corpus
        # repos use FINDINGS.md, audit projects sometimes use audit-data/report.md.
        for cand in (".ANSWERS.md", "FINDINGS.md", "audit-data/report.md",
                     "audit-data/findings.md"):
            p = os.path.join(ex_abs, cand)
            if os.path.isfile(p):
                truth = p
                break
        else:
            truth = None  # rep still logs; score is null

    # Call sol_intent the same way sol_flywheel does — subprocess, capture stdout.
    proc = subprocess.run(
        [PY, "sol_intent.py", ex_abs],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    leads_text = proc.stdout or ""
    if proc.returncode != 0:
        leads_text += "\n[stderr]\n" + (proc.stderr or "")

    # Tokenize both sides through the same scorer (Layer 1 contract).
    leads_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    leads_tmp.write(leads_text)
    leads_tmp.close()
    leads = sol_match._lines(leads_tmp.name)

    if truth is not None:
        findings = sol_match._lines(truth)
        score = sol_match.match(leads, findings, threshold=0.80)
        score_row = {
            "recall": score["recall"],
            "precision": score["precision"],
            "matched_n": len(score["matched"]),
            "missed_n": len(score["missed"]),
            "n_findings": len(findings),
            "n_leads": len(leads),
        }
    else:
        # No ground truth available — still log the rep so the proposer's
        # behavior on this corpus is on record.
        score_row = {"recall": None, "precision": None, "n_leads": len(leads),
                     "note": "no ground truth"}

    row = {
        "contract": {
            "path": ex_abs,
            "sha256_dir": rep_log.sha256_dir(ex_abs),
        },
        "proposer": {
            "kind": "sol_intent",
            "version": "v1",
            "model": os.environ.get("ANTHROPIC_MODEL", "default"),
            "exit": proc.returncode,
        },
        "leads": leads,
        "verifier": {
            "kind": "sol_match",
            "threshold": 0.80,
        },
        "score": score_row,
        "ground_truth_path": truth,
    }
    written = rep_log.write_rep(row)
    return written


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for ex in sys.argv[1:]:
        try:
            r = run_one(ex)
            print(json.dumps({
                "ex": ex,
                "rep_id": r["rep_id"],
                "recall": r["score"].get("recall"),
                "precision": r["score"].get("precision"),
                "n_findings": r["score"].get("n_findings"),
                "n_leads": r["score"].get("n_leads"),
                "exit": r["proposer"]["exit"],
                "note": r["score"].get("note"),
            }))
        except Exception as e:
            print(json.dumps({"ex": ex, "error": str(e)}))


if __name__ == "__main__":
    main()
