"""
manual_rep — log YOUR (human) audit findings as a rep, scored against the
same ground truth the model gets. The missing piece for JH-vs-model
calibration on identical corpora.

Workflow:
  1. cd to plumbline root
  2. Open the corpus source cold (no peeking at .ANSWERS.md)
  3. Write your findings to examples/<corpus>/MY_FINDINGS.md — one per
     ## section, free-form prose, anything that helps you remember the
     mechanism (mirroring how sol_match expects findings)
  4. python tools/manual_rep.py examples/<corpus>
  5. Your recall + precision land in reps.jsonl with proposer.kind="manual"
     proposer.author="<your name from $USER>"

Then:
  python scoreboard.py --corpus <name>
will show your reps alongside the model's, on identical ground truth. That's
the calibration number JH has been asking for: does the model add to you,
replace part of you, or just make triage noisier on novel code.

The honest framing: this isn't a number that says "human better" or
"model better" — it's the diff. If your recall is higher than the model's
on a corpus, the model is checking you. If lower, you're leaning on the
model. Both are useful; both inform contest workflow.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import sol_match
import rep_log


def run_one(ex_path: str, findings_file: str = "MY_FINDINGS.md") -> dict:
    ex_abs = os.path.join(HERE, ex_path) if not os.path.isabs(ex_path) else ex_path
    truth = os.path.join(ex_abs, ".ANSWERS.md")
    if not os.path.isfile(truth):
        raise FileNotFoundError(f"no .ANSWERS.md at {truth}")

    my = os.path.join(ex_abs, findings_file)
    if not os.path.isfile(my):
        raise FileNotFoundError(
            f"no {findings_file} at {my}\n"
            f"Write your findings there first — one per `## ` section."
        )

    leads = sol_match._lines(my)
    findings = sol_match._lines(truth)
    if not leads:
        raise ValueError(f"{my} has no parseable findings — at least one `## ` section?")
    score = sol_match.match(leads, findings, threshold=0.80)

    row = {
        "contract": {
            "path": ex_abs,
            "sha256_dir": rep_log.sha256_dir(ex_abs),
        },
        "proposer": {
            "kind": "manual",
            "version": "human-cold-read",
            "author": os.environ.get("USER", "unknown"),
            "findings_file": findings_file,
        },
        "leads": leads,
        "verifier": {
            "kind": "sol_match",
            "threshold": 0.80,
        },
        "score": {
            "recall": score["recall"],
            "precision": score["precision"],
            "matched_n": len(score["matched"]),
            "missed_n": len(score["missed"]),
            "n_findings": len(findings),
            "n_leads": len(leads),
        },
        "ground_truth_path": truth,
    }
    return rep_log.write_rep(row)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ex = sys.argv[1]
    findings_file = sys.argv[2] if len(sys.argv) > 2 else "MY_FINDINGS.md"
    try:
        r = run_one(ex, findings_file=findings_file)
        s = r["score"]
        print(f"manual rep logged:")
        print(f"  rep_id    {r['rep_id'][:12]}")
        print(f"  corpus    {os.path.basename(r['contract']['path'])}")
        print(f"  author    {r['proposer']['author']}")
        print(f"  recall    {s['recall']:.3f}  ({s['matched_n']}/{s['n_findings']})")
        print(f"  precision {s['precision']:.3f}  ({s['matched_n']}/{s['n_leads']})")
        print(f"  vs model: python scoreboard.py --corpus {os.path.basename(r['contract']['path'])}")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
