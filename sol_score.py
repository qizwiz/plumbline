"""
sol_score — the GROUNDED training signal. Given the pipeline's LEADS (from sol_study_loop / sol_intent)
and a target's GROUND-TRUTH findings (a past contest's judged findings, a synthetic twin's planted bugs,
or Jun-8 plumbline verdicts), measure RECALL (which real findings did we pre-find?) and PRECISION (how
much of what we surfaced was noise?). That score — and ONLY that score — is what trains the lead
generator. Never train on the leads' own confidence; train on measured truth.

  recall    = real findings matched by a lead / total real findings   (did we catch the bug?)
  precision = leads that matched a real finding / total leads          (signal vs noise)
  signal    = a grounded feedback string for prompt_improve (what to recall harder, what noise to drop)

  python sol_score.py <leads.txt> <ground_truth.txt>
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import invariant_agent as agent

_PROMPT = """You are scoring an automated auditor's LEADS against the GROUND TRUTH (the real, confirmed
findings for this target). Be a strict, literal judge — a lead only "matches" a ground-truth finding if
it identifies the SAME root cause / mechanism, not merely the same area or a vague overlap.

Return ONE JSON object, no fences:
{
  "matches": [ {"finding": "<ground-truth finding>", "lead": "<the lead that matched, or null>"} ],
  "missed":  [ "<ground-truth finding with NO matching lead>" ],
  "noise":   [ "<lead that matched NO ground-truth finding>" ],
  "recall":  <matched findings / total findings, 0..1>,
  "precision": <leads-that-matched / total leads, 0..1>,
  "signal":  "<2-3 sentences of GROUNDED feedback for improving the lead generator: which real findings
              it MISSED and what kind of reasoning would have caught them; which noise patterns to drop.
              Concrete, derived from the misses/noise above — not generic advice.>"
}

=== LEADS (what the pipeline pre-found) ===
{leads}

=== GROUND TRUTH (the real findings) ===
{truth}
"""


def score(leads: str, truth: str):
    out = agent._ask(_PROMPT.format(leads=leads[:30000], truth=truth[:20000]), 2500)
    m = re.search(r"\{.*\}", out.strip().strip("`"), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(0)
    leads = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    truth = open(sys.argv[2], encoding="utf-8", errors="replace").read()
    r = score(leads, truth)
    if not r:
        print("score: unparseable"); sys.exit(1)
    print(f"RECALL    {r.get('recall')}   ({len(r.get('matches', []))} matched, {len(r.get('missed', []))} missed)")
    print(f"PRECISION {r.get('precision')}   ({len(r.get('noise', []))} noise leads)")
    print("\nMISSED (the grounded gap — train to catch these):")
    for x in r.get("missed", []):
        print("  -", x)
    print("\nGROUNDED SIGNAL (feeds prompt_improve):\n  " + str(r.get("signal", "")))
