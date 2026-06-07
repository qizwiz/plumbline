"""
oracle_loop — second-pass forcing function. For each sol_intent lead,
if a TLA+ shape matches with cos > THRESHOLD, ask LLM to GROUND the
lead in spec mechanics (name variables, describe invariant violation,
give attack path). Unmatched leads pass through unchanged.

Per ORACLE_LOOP.goal.md (deep-research top-3 #3). v0: no TLC
execution — pure forcing function on the LLM.

Usage:
    cat leads.txt | python tools/oracle_loop.py - <exclude_corpus> [threshold=0.55]
    python tools/oracle_loop.py <leads.txt> <exclude_corpus> [threshold=0.55]
"""
from __future__ import annotations
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import spec_retrieval
import invariant_agent as agent
import prompt_improve as pi

PROMPT_PATH = os.path.join(HERE, "prompts", "oracle_loop.md")


def _split_leads(text: str) -> list[tuple[str, str]]:
    """Returns [(prefix, lead_line), ...]. Each lead_line is one '- [...]' bullet.
    Non-lead lines (headers, blank, prose) keep prefix empty."""
    out = []
    for ln in text.splitlines():
        m = re.match(r"^(\s*-\s*\[)", ln)
        if m or re.match(r"^\s*-\s*\*\*", ln):
            out.append(("LEAD", ln))
        else:
            out.append(("OTHER", ln))
    return out


def _revise_lead(lead: str, exclude_corpus: str, threshold: float,
                 tmpl: str) -> tuple[str, str]:
    """Returns (revised_lead, status) where status in {'revised', 'no-match',
    'shape-not-applicable', 'error'}."""
    # Skip very short leads — nothing to ground
    if len(lead.strip()) < 20:
        return lead, "no-match"
    try:
        results = spec_retrieval.query_top(lead, k=1)
    except Exception:
        return lead, "error"
    if not results or results[0]["cos"] < threshold:
        return lead, "no-match"
    # Skip imported (Python-domain) shapes
    if "/imported/" in results[0].get("path", ""):
        return lead, "no-match"
    shape = results[0]
    prompt = pi.render(tmpl, lead=lead,
                       shape_name=shape["name"],
                       shape_description=shape["description_head"])
    try:
        revised = agent._ask(prompt, 800)
    except Exception:
        return lead, "error"
    if "NOTE: shape" in revised and "does not apply" in revised:
        return lead, "shape-not-applicable"
    return revised, "revised"


def main():
    if len(sys.argv) < 3:
        print("usage: oracle_loop.py <leads.txt|-> <exclude_corpus> [threshold=0.55]",
              file=sys.stderr); sys.exit(1)
    src = sys.argv[1]
    exclude = sys.argv[2]
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55
    text = sys.stdin.read() if src == "-" else open(src).read()
    tmpl = open(PROMPT_PATH).read()
    items = _split_leads(text)
    stats = {"revised": 0, "no-match": 0, "shape-not-applicable": 0,
             "error": 0, "other-line": 0}
    out_lines = []
    for kind, ln in items:
        if kind != "LEAD":
            out_lines.append(ln); stats["other-line"] += 1; continue
        revised, status = _revise_lead(ln, exclude, threshold, tmpl)
        stats[status] += 1
        if status == "revised":
            out_lines.append("- [REVISED] " + revised.strip())
        else:
            out_lines.append(ln)
    print("\n".join(out_lines))
    sys.stderr.write(f"\noracle_loop stats: {stats}\n")


if __name__ == "__main__":
    main()
