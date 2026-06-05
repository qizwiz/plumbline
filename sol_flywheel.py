"""
sol_flywheel — the curriculum, driven by PACT'S OWN LOOP. Score the finder (sol_intent) on RECALL +
PRECISION against PLANTED ground truth across a ladder of contracts, then let prompt_improve.improve_if_weak
REWRITE the finder prompt on the demonstrated weakness — repeat. The only thing that moves the prompt is
measured truth (recall/precision vs real bugs), never the model's self-regard. Improving over the whole
curriculum (not one twin) keeps the rewrite from overfitting.

  python sol_flywheel.py            # run pact's grounded loop over the curriculum
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sol_score
import prompt_improve as pi
import invariant_agent as agent

PY = sys.executable

# The ladder. gen = argv whose STDOUT is the leads; truth = ground-truth findings file; bar = recall to pass.
# difficulty climbs: a passed rung escalates; rungs 1+ need the corpus of past-contest judged findings.
RUNGS = [
    {"name": "twin-easy", "difficulty": 1, "bar": 0.80,
     "gen": [PY, "sol_intent.py", "examples/synthetic-dreusd"],
     "truth": "examples/synthetic-dreusd/.ANSWERS.md",
     "note": "planted decimals + JIT bugs — the sanity floor; if this misses, nothing downstream is trustworthy"},
    {"name": "twin-reserve-inflation", "difficulty": 2, "bar": 0.5,
     "gen": [PY, "sol_intent.py", "examples/synthetic-dreusd-2"],
     "truth": "examples/synthetic-dreusd-2/.ANSWERS.md",
     "note": "cross-function timing bug: totalAssets double-counts reserved withdrawals (burn-now/pay-later "
             "pps inflation). No wrong constant — needs reasoning about state between calls."},
    {"name": "twin-staking-multi", "difficulty": 3, "bar": 0.66,
     "gen": [PY, "sol_intent.py", "examples/synthetic-dreusd-3"],
     "truth": "examples/synthetic-dreusd-3/.ANSWERS.md",
     "note": "MULTI-finding (3 classes: ungated setRewardRate, fundRewards drops leftover, earned() rounds "
             "up) — measures precision HONESTLY and breadth across reasoning modes. bar = catch >=2 of 3."},
    # rung 4+: subtler self-play twins (adversary aims at lessons.md blind spots) + real past-contest findings.
]


def _leads(rung):
    r = subprocess.run(rung["gen"], cwd=HERE, capture_output=True, text=True, timeout=1200)
    return (r.stdout or "") + ("\n[stderr]\n" + r.stderr if r.returncode else "")


def _score_rung(rung):
    """Run sol_intent on the rung and score it on MEASURED truth. Returns (recall, precision, sc)."""
    truth = open(os.path.join(HERE, rung["truth"]), encoding="utf-8", errors="replace").read()
    sc = sol_score.score(_leads(rung), truth) or {}
    return (sc.get("recall") or 0.0), (sc.get("precision") or 0.0), sc


def flywheel(rungs, iters=3):
    """PACT'S LOOP. Run the whole curriculum → grounded score (recall+precision vs planted truth) →
    if the weakest rung is below THRESHOLD, prompt_improve.improve_if_weak REWRITES sol_intent.md to fix
    the demonstrated weakness → re-run → repeat. Improving over the FULL curriculum (not one twin) keeps
    the rewrite from overfitting. The only thing that moves the prompt is measured truth."""
    for it in range(1, iters + 1):
        print(f"\n=== curriculum pass {it} ===")
        weakest, weak_rung, transcript = 1.0, None, []
        for rung in rungs:
            rec, prec, sc = _score_rung(rung)
            g = min(rec, prec)  # weakest link; with recall solved, PRECISION is the binding axis
            print(f"  rung {rung['difficulty']} {rung['name']:24s}  recall {rec:.2f}  precision {prec:.2f}"
                  f"  -> grounded {g:.2f}", flush=True)
            if g < weakest:
                weakest, weak_rung = g, rung["name"]
            if sc.get("missed"):
                transcript.append(f"[{rung['name']}] MISSED real bugs (a class you failed to see): "
                                  f"{'; '.join(sc['missed'])[:500]}")
            if sc.get("noise"):
                transcript.append(f"[{rung['name']}] OVER-FLAGGED — reported with NO concrete traced "
                                  f"mechanism. Fix toward RIGOR not silence: only call it a finding when you "
                                  f"can name the exact mechanism + exploit. Noise: {'; '.join(sc['noise'])[:400]}")
        print(f"  weakest grounded score across curriculum: {weakest:.2f}  (rung: {weak_rung})")
        if weakest >= pi.THRESHOLD:
            print(f"  ✓ curriculum mastered (>= {pi.THRESHOLD}). The loop has nothing to fix — escalate "
                  f"difficulty by adding a harder rung."); return weakest
        # the grounded weakness drives pact's prompt rewrite
        tx = ("The smart-contract finder (sol_intent) was scored on RECALL + PRECISION against PLANTED "
              "ground truth across a curriculum of contracts. Recall is strong; PRECISION is the weak axis — "
              "it over-reports plausible concerns it cannot mechanistically prove. Rewrite the prompt to "
              "raise precision (demand a concrete traced mechanism + exploit before calling something a "
              "finding) WITHOUT losing recall.\n\n" + "\n".join(transcript)[:4500])
        required_ph = ["{{struggle}}", "{{readme}}", "{{adrs}}", "{{sources}}"]
        before = pi.load_prompt("sol_intent")
        rewrote = pi.improve_if_weak("sol_intent", weakest, tx, agent._ask)
        if not rewrote:
            print("  improve_if_weak did NOT rewrite (score above threshold or rewrite rejected) — stop.")
            return weakest
        if not all(ph in pi.load_prompt("sol_intent") for ph in required_ph):
            pi.save_prompt("sol_intent", before)
            print("  [guard] rewrite dropped a required {{placeholder}} — REVERTED; stopping."); return weakest
    print("  reached iteration cap.")
    return weakest


if __name__ == "__main__":
    print("sol_flywheel: PACT'S grounded loop — measure recall+precision on planted truth, "
          "improve_if_weak rewrites the finder on the weakness, repeat.")
    flywheel(RUNGS)
