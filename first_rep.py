"""
first_rep — the smallest viable rep. Plumbing test for Layer 1 of the bilayer IR.

This rep deliberately puts the PROPOSER role on a hand-crafted lead set (one real,
one bogus). That is NOT cheating — it is testing the scoring/log plumbing in
isolation, before plugging the model proposer (sol_intent) in for rep 2+. Per the
"smallest working thing" rule: prove the pipe carries water before connecting it
to the well.

Expected verdict on this rep:
  - real lead (decimals 6↔18 bug) matches finding via id-overlap on `redeem`/`dreAmount`
  - bogus lead (fake reentrancy in `transfer`) does NOT match anything
  - recall ≥ 0.5 (we caught at least one of two planted bugs)
  - precision ≤ 0.5 (one of two leads is noise)

If the numbers don't match expectation, the bug is in the scorer/log — fix that
before adding a model proposer on top.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sol_match
import rep_log

EX = os.path.join(HERE, "examples/synthetic-dreusd")
TRUTH = os.path.join(EX, ".ANSWERS.md")

# Hand-crafted leads for the plumbing test. One real (matches planted bug 2:
# decimals 6↔18 in redeem), one bogus (fake reentrancy claim with no real anchor).
LEADS = [
    "redeem pays out dreAmount of USDC without scaling back down by 1e12, "
    "so redeem(mint(x)) returns ~1e12x the USDC deposited and drains backing",
    "transfer is reentrant because external call happens before state update",
]

# Pull findings from the answer key. _lines() does the same line-clean sol_match.py's
# CLI does — keeps scorer behavior identical to the production path.
findings = sol_match._lines(TRUTH)

score = sol_match.match(LEADS, findings, threshold=0.80)

row = {
    "contract": {
        "path": EX,
        "sha256_dir": rep_log.sha256_dir(EX),
    },
    "proposer": {
        "kind": "manual",
        "version": "plumbing-test-v1",
        "model": None,
    },
    "leads": LEADS,
    "verifier": {
        "kind": "sol_match",
        "threshold": 0.80,
    },
    "score": {
        "recall": score["recall"],
        "precision": score["precision"],
        "matched": score["matched"],
        "missed": score["missed"],
        "n_findings": len(findings),
        "n_leads": len(LEADS),
    },
    "ground_truth_path": TRUTH,
}
written = rep_log.write_rep(row)

print(json.dumps({
    "rep_id": written["rep_id"],
    "recall": row["score"]["recall"],
    "precision": row["score"]["precision"],
    "matched": row["score"]["matched"],
    "missed": row["score"]["missed"],
}, indent=2))
