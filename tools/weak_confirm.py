"""
weak_confirm — vocabulary-match post-filter for TLC oracle's CONFIRMED hits.

Per tlc-oracle-ab.md: v1 oracle produces 76 CONFIRMED on sequence, most
of which are noise because the spec's BuggyAction fires regardless of
cfg_generator's parameterization. This filter downgrades CONFIRMED to
WEAK-CONFIRM unless the lead text shares ≥2 anchor-keyword synonyms
with the matched spec's name.

Reuses ANCHORS from tools/route_lead_hybrid.py — same curated dictionary.

Usage as library:
    from weak_confirm import classify
    strength = classify(lead_text, spec_name)  # "STRONG" or "WEAK"

CLI for reclassifying existing CONFIRMED output:
    python tools/weak_confirm.py < examples/<corpus>/sol-intent-tlc-oracle.txt
"""
from __future__ import annotations
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import route_lead_hybrid as rlh  # for ANCHORS


def anchor_hits(lead: str, spec_name: str) -> int:
    """Count distinct anchor-keyword synonyms the lead shares with the
    spec name's tokens. Higher count = stronger vocabulary match."""
    L = lead.lower()
    hits = set()
    for tok in re.findall(r"[A-Z][a-z0-9]+|[a-z0-9]+", spec_name):
        synonyms = rlh.ANCHORS.get(tok.lower(), [tok.lower()])
        for syn in synonyms:
            if re.search(rf"\b{re.escape(syn)}\b", L):
                hits.add(syn)
    return len(hits)


def classify(lead: str, spec_name: str, min_hits: int = 2) -> str:
    """Returns 'STRONG' if anchor_hits >= min_hits, else 'WEAK'."""
    return "STRONG" if anchor_hits(lead, spec_name) >= min_hits else "WEAK"


def reclassify_line(line: str) -> tuple[str, str | None, int]:
    """Parse a CONFIRMED line, return (new_line, status, hits).
    status: 'kept-strong' | 'downgraded' | None (not a CONFIRMED line)."""
    m = re.match(r"^(\s*-\s*)\[CONFIRMED via TLC on (\w+)\]\s*(.*)$", line)
    if not m:
        return line, None, 0
    prefix, spec_name, rest = m.group(1), m.group(2), m.group(3)
    hits = anchor_hits(rest, spec_name)
    if hits >= 2:
        return line, "kept-strong", hits
    new_line = f"{prefix}[WEAK-CONFIRM via TLC on {spec_name}, only {hits} anchor(s)] {rest}"
    return new_line, "downgraded", hits


def main():
    text = sys.stdin.read()
    out_lines = []
    stats = {"kept-strong": 0, "downgraded": 0, "passthrough": 0}
    for line in text.splitlines():
        new_line, status, _ = reclassify_line(line)
        if status:
            stats[status] += 1
        else:
            stats["passthrough"] += 1
        out_lines.append(new_line)
    print("\n".join(out_lines))
    confirmed_total = stats["kept-strong"] + stats["downgraded"]
    sys.stderr.write(
        f"\nweak_confirm stats:\n"
        f"  total CONFIRMED reclassified: {confirmed_total}\n"
        f"  STRONG (kept): {stats['kept-strong']}\n"
        f"  WEAK (downgraded): {stats['downgraded']}\n"
        f"  passthrough (non-CONFIRMED lines): {stats['passthrough']}\n")


if __name__ == "__main__":
    main()
