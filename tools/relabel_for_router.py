"""
relabel_for_router — apply ADR-006 §"Label rules" deterministically over
reps.jsonl, producing reps_routed.jsonl as a derived (non-destructive) view.

The original reps.jsonl is APPEND-ONLY and unchanged.
The derived file augments each row with verifier_route: [label, ...]
(empty list means ambiguous; needs manual labeling).

Usage:
    python tools/relabel_for_router.py [--in reps.jsonl] [--out reps_routed.jsonl]

Prints: "N rows routed, M rows ambiguous (need manual)".
"""
from __future__ import annotations
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ADR-006 Label rules table → keyword patterns (case-insensitive).
# Most specific first; first-match wins per rule class.
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(reentran|cei|external\s*call.*before|check.*effect|withdraw.*before)\b", re.I), "slither_will_catch"),
    (re.compile(r"\b(tx\.origin|delegatecall|selfdestruct)\b", re.I), "slither_will_catch"),
    (re.compile(r"\b(uint(\d+)?\s*overflow|integer\s*overflow|arithmetic\s*overflow)\b", re.I), "slither_will_catch"),
    (re.compile(r"\b(conservation|total\s*supply|total\s*fees|sum\s*equals|invariant.*account)\b", re.I), "halmos_will_decide"),
    (re.compile(r"\b(balance.*equal|address\(this\)\.balance)\b", re.I), "halmos_will_decide"),
    (re.compile(r"\b(replay|signature.*reuse|signature.*twice|no\s*nonce|nonce.*missing|one.\s*shot|state\s*machine)\b", re.I), "tlc_will_decide"),
    (re.compile(r"\b(msg\.sender.*misread|caller.\s*bound|caller.*identity|msg\.sender.*=.*entry)\b", re.I), "tlc_will_decide"),
    (re.compile(r"\b(idempot|deterministic\s*dispatch|deploy.*twice|create2.*exists)\b", re.I), "tlc_will_decide"),
    (re.compile(r"\b(narrow\s*accumulator|uint64.*fee|truncation|cast\s*to\s*uint)\b", re.I), "tlc_will_decide"),
    (re.compile(r"\b(domain\s*separat|cross.\s*wallet|missing.*wallet.*binding|chain.\s*id)\b", re.I), "tlc_will_decide"),
    (re.compile(r"\b(oracle\s*stale|staleness|freshness|round.\s*id)\b", re.I), "human_only"),
    (re.compile(r"\b(game.\s*theor|incentive|mev|griefing|frontrun.*incentive)\b", re.I), "human_only"),
    (re.compile(r"\b(unclear|ambiguous|spec.*assumes|out\s*of\s*scope)\b", re.I), "human_only"),
]


def route_one(leads_text: str) -> list[str]:
    """Apply rules in order, returning a deduped list of matched routes."""
    routes: list[str] = []
    for pat, label in RULES:
        if pat.search(leads_text) and label not in routes:
            routes.append(label)
    return routes


def main():
    in_path = os.path.join(HERE, "reps.jsonl")
    out_path = os.path.join(HERE, "reps_routed.jsonl")
    if "--in" in sys.argv:
        in_path = sys.argv[sys.argv.index("--in") + 1]
    if "--out" in sys.argv:
        out_path = sys.argv[sys.argv.index("--out") + 1]

    routed = 0
    ambiguous = 0
    with open(in_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            if not line.strip():
                continue
            row = json.loads(line)
            leads = row.get("leads") or []
            leads_text = " ".join(str(x) for x in leads)
            routes = route_one(leads_text)
            if routes:
                row["verifier_route"] = routes
                routed += 1
            else:
                row["verifier_route"] = []
                ambiguous += 1
            fout.write(json.dumps(row) + "\n")

    print(f"{routed} rows routed, {ambiguous} rows ambiguous (need manual)")
    print(f"output: {out_path}")


if __name__ == "__main__":
    main()
