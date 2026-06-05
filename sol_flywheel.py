"""
sol_flywheel — the curriculum. Climb a difficulty LADDER of targets, each with GROUND-TRUTH findings.
At each rung: generate leads → score recall against truth (measured, never confidence) → if mastered,
ESCALATE to a harder rung; if not, write the grounded miss-signal into lessons.md and retry. Hard, then
harder, then harder — the generator is always trained at the frontier of its ability.

The flywheel only turns on MEASURED truth: a rung is passed by recall vs real findings, and the lesson
fed back is derived from what it MISSED — so improvement tracks reality, not the model's self-regard.

  python sol_flywheel.py            # climb the whole ladder
  python sol_flywheel.py --rung 0   # run one rung (grounded smoke test)
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sol_score

PY = sys.executable
LESSONS = os.path.join(HERE, "prompts", "lessons.md")

# The ladder. gen = argv whose STDOUT is the leads; truth = ground-truth findings file; bar = recall to pass.
# difficulty climbs: a passed rung escalates; rungs 1+ need the corpus of past-contest judged findings.
RUNGS = [
    {"name": "twin-easy", "difficulty": 1, "bar": 0.80,
     "gen": [PY, "sol_intent.py", "examples/synthetic-dreusd"],
     "truth": "examples/synthetic-dreusd/.ANSWERS.md",
     "note": "planted decimals + JIT bugs — the sanity floor; if this misses, nothing downstream is trustworthy"},
    # rung 2+: drop in past Sherlock/Code4rena contests — source dir + its judged-findings file.
    # {"name":"<contest>-high","difficulty":2,"bar":0.6,"gen":[PY,"sol_intent.py","<src>"],"truth":"<judged_high.md>"},
]


def _leads(rung):
    r = subprocess.run(rung["gen"], cwd=HERE, capture_output=True, text=True, timeout=1200)
    return (r.stdout or "") + ("\n[stderr]\n" + r.stderr if r.returncode else "")


def _learn(rung, sc):
    """Write the GROUNDED miss-signal back as a durable lesson (the only thing that trains the generator)."""
    lesson = (f"\n## from {rung['name']} (recall {sc.get('recall')}, difficulty {rung['difficulty']})\n"
              f"MISSED: {'; '.join(sc.get('missed', []))[:600]}\n"
              f"LESSON: {sc.get('signal', '')}\n")
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write(lesson)
    return lesson


def flywheel(rungs, tries=2):
    if not os.path.exists(LESSONS):
        open(LESSONS, "w").write("# Grounded lessons — derived ONLY from findings the pipeline MISSED.\n"
                                 "# Generator prompts include this. Never edited by hand from intuition.\n")
    for rung in rungs:
        truth = open(os.path.join(HERE, rung["truth"]), encoding="utf-8", errors="replace").read()
        print(f"\n=== RUNG {rung['difficulty']}: {rung['name']} (bar recall {rung['bar']}) ===")
        print(f"    {rung['note']}")
        passed = False
        for attempt in range(1, tries + 1):
            sc = sol_score.score(_leads(rung), truth)
            if not sc:
                print(f"    attempt {attempt}: unscorable; stopping rung"); break
            rec = sc.get("recall") or 0
            print(f"    attempt {attempt}: RECALL {rec}  precision {sc.get('precision')}  "
                  f"({len(sc.get('missed', []))} missed, {len(sc.get('noise', []))} noise)")
            for m in sc.get("missed", []):
                print(f"        MISS: {m[:110]}")
            if rec >= rung["bar"]:
                print(f"    ✓ MASTERED — escalating to harder rung."); passed = True; break
            print(f"    ↻ below bar — writing grounded lesson, retrying."); _learn(rung, sc)
        if not passed:
            print(f"    ✗ stuck at difficulty {rung['difficulty']} — the frontier. This is where to work.")
            break


if __name__ == "__main__":
    rungs = RUNGS
    if "--rung" in sys.argv:
        i = int(sys.argv[sys.argv.index("--rung") + 1]); rungs = [RUNGS[i]]
    print("sol_flywheel: climb the difficulty ladder on MEASURED truth (hard → harder → harder)")
    flywheel(rungs)
