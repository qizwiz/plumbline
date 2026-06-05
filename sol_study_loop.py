"""
sol_study_loop — study, and KEEP studying. A journal-based loop that deepens its world-model and
hypothesis set each round, until it stops surfacing anything new (loop-until-dry). The auditor who
keeps a notebook and keeps filling it.

The grounding discipline (the whole point): a hypothesis is NEVER a finding until verified against
source. Pre-source, testable hypotheses stay status:"open" (speculation, labeled). Once the contract
source exists, the testable ones route to plumbline to be confirmed/refuted — that's where "keep
studying" becomes "keep finding." The journal prevents re-spiraling; dry-detection forces convergence.

  python sol_study_loop.py <audit/doc/source files or dirs ...>
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import invariant_agent as agent
import prompt_improve as pi

JOURNAL = os.path.join(HERE, "states", "study_journal.json")
_PER_SRC, _TOTAL = 70000, 140000
_DOC_EXT = (".txt", ".md", ".rst", ".sol")


def _material(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fs in os.walk(p):
                files += [os.path.join(dp, f) for f in sorted(fs) if f.lower().endswith(_DOC_EXT)]
        elif os.path.isfile(p):
            files.append(p)
    blob, used = [], 0
    for f in files:
        t = open(f, encoding="utf-8", errors="replace").read()[:_PER_SRC]
        if used + len(t) > _TOTAL:
            t = t[: max(0, _TOTAL - used)]
        if not t:
            break
        blob.append(f"// ===== {os.path.basename(f)} =====\n{t}")
        used += len(t)
    return "\n\n".join(blob)


def _ids(j):
    return {(h.get("id") or h.get("claim", "")[:60]) for h in j.get("hypotheses", [])}


def _parse_delta(out):
    out = re.sub(r"^```[a-zA-Z]*\n?|```$", "", out.strip())
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def loop(paths, rounds=5, dry_limit=2, fresh=False):
    """Each round the LLM emits a small DELTA (new hypotheses + resolutions); we merge into the journal
    in code. Robust to the truncation/malformation that re-emitting the whole journal caused."""
    material = _material(paths)
    journal = ({} if fresh or not os.path.exists(JOURNAL)
               else json.load(open(JOURNAL))) or {"model": "", "hypotheses": [], "resolved": [],
                                                   "open_questions": [], "next": ""}
    dry = 0
    for r in range(1, rounds + 1):
        have = _ids(journal)
        hyp_list = "\n".join(f"- {h.get('id', '?')}: {str(h.get('claim', ''))[:120]}"
                             for h in journal.get("hypotheses", [])) or "(none yet)"
        prompt = pi.render(open(os.path.join(HERE, "prompts/sol_study_loop.md")).read(),
                           model=str(journal.get("model", ""))[:8000], hyp_list=hyp_list[:20000],
                           material=material)
        delta = _parse_delta(agent._ask(prompt, 2500))
        if delta is None:
            print(f"  round {r}: unparseable delta; stopping"); break
        # merge delta into journal (deterministic — the macro half)
        if delta.get("model_update"):
            journal["model"] = (str(journal.get("model", "")) + "\n" + delta["model_update"]).strip()[:12000]
        added = [h for h in delta.get("new_hypotheses", [])
                 if (h.get("id") or h.get("claim", "")[:60]) not in have]
        journal.setdefault("hypotheses", []).extend(added)
        for rs in delta.get("resolve", []):
            for h in journal["hypotheses"]:
                if h.get("id") == rs.get("id"):
                    h["status"] = rs.get("status", "refuted"); h["resolution"] = rs.get("why", "")
        journal["open_questions"] = delta.get("open_questions", journal.get("open_questions", []))
        journal["next"] = delta.get("next", journal.get("next", ""))
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        json.dump(journal, open(JOURNAL, "w"), indent=1)
        print(f"  round {r}: {len(journal.get('hypotheses', []))} hypotheses (+{len(added)} new) | "
              f"next: {str(journal.get('next', ''))[:90]}", flush=True)
        dry = dry + 1 if not added else 0
        if dry >= dry_limit:
            print(f"  DRY ({dry_limit} rounds, no new hypotheses) — converged."); break
    return journal


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if not a.startswith("--")] or ["."]
    print("sol_study_loop: study and KEEP studying (journal-based, until dry)\n")
    j = loop(paths, fresh="--fresh" in sys.argv)
    print("\n=== TESTABLE HYPOTHESES (unverified until plumbline checks them on the source) ===")
    for h in j.get("hypotheses", []):
        if h.get("testable"):
            print(f"- [{h.get('status', '?')}] {str(h.get('claim', ''))[:130]}  «{h.get('area', '')}»")
