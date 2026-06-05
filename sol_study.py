"""
sol_study — make the AI do the studying. Digest a protocol's PRIOR AUDITS (+ docs) into a contest
HUNT BRIEF: architecture, findings catalog (with fixed/acknowledged status), the team's recurring
blind spots, and a prioritized map of where the *remaining* bugs likely live (variants of fixed
findings, acknowledged-unfixed, under-scoped areas, cross-component interactions).

This is the intent piece extended to the richest layer of the human record — prior audits are the
highest-confidence "what's known about this code." It maps the terrain; it does NOT find the unfound
bug (that's still the Jun-8 source + you + plumbline).

  python sol_study.py <audit-or-doc files/dirs ...>
  python sol_study.py /tmp/2026-02-spearbit-dreusd.txt /tmp/2026-03-quantstamp-dreusd.txt
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import invariant_agent as agent
import prompt_improve as pi

_PER_SRC = 70000   # cap per document so one huge report can't crowd out the others
_TOTAL = 150000    # total material cap (keeps the call within context)
_DOC_EXT = (".txt", ".md", ".rst")


def _files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fs in os.walk(p):
                for f in sorted(fs):
                    if f.lower().endswith(_DOC_EXT):
                        out.append(os.path.join(dp, f))
        elif os.path.isfile(p):
            out.append(p)
    return out


def study(paths, model=None):
    files = _files(paths)
    if not files:
        return "(no audit/doc files found — pass extracted .txt/.md audit reports)"
    blob, used = [], 0
    for f in files:
        txt = open(f, encoding="utf-8", errors="replace").read()[:_PER_SRC]
        if used + len(txt) > _TOTAL:
            txt = txt[: max(0, _TOTAL - used)]
        if not txt:
            break
        blob.append(f"// ===== {os.path.basename(f)} =====\n{txt}")
        used += len(txt)
    material = "\n\n".join(blob)
    prompt = pi.render(open(os.path.join(HERE, "prompts/sol_study.md")).read(), material=material)
    return agent._ask(prompt, 4000)


if __name__ == "__main__":
    paths = sys.argv[1:] or ["."]
    print("sol_study: digesting prior audits/docs into a contest hunt brief\n")
    print(study(paths))
