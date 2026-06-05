"""
replay — re-print a single rep row from reps.jsonl by rep_id (full or prefix).

  python tools/replay.py 5b2138d3                       # prefix match (recommended)
  python tools/replay.py 5b2138d3-b162-4bd0-9c59-...    # full uuid

Useful for sanity-checking historical reps without scrolling raw JSONL or
re-running `model_rep` / `halmos_rep`. Idempotent, read-only.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG = os.path.join(HERE, "reps.jsonl")


def find(path: str, needle: str) -> list[dict]:
    out = []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("rep_id") or "").startswith(needle):
            out.append(r)
    return out


def render(r: dict) -> str:
    contract = r.get("contract", {})
    proposer = r.get("proposer", {})
    score = r.get("score", {})
    verifier = r.get("verifier", {})
    lines = [
        f"rep_id      {r.get('rep_id')}",
        f"ts_ns       {r.get('ts_ns')}",
        f"contract    {os.path.basename(contract.get('path','').rstrip('/')):<24s}  sha256_dir={contract.get('sha256_dir','')[:12]}",
        f"proposer    {proposer.get('kind','?'):<14s} version={proposer.get('version','?')}  model={proposer.get('model','—')}",
        f"verifier    {verifier.get('kind','?'):<14s} " +
            (f"threshold={verifier.get('threshold')}" if 'threshold' in verifier
             else f"returncode={verifier.get('returncode','—')}"),
    ]
    if score.get("recall") is not None:
        lines.append(f"score       recall={score.get('recall'):.3f}  precision={score.get('precision'):.3f}  "
                     f"n_findings={score.get('n_findings','?')}  n_leads={score.get('n_leads','?')}")
        if score.get("matched_n") is not None:
            lines.append(f"            matched_n={score.get('matched_n')}  missed_n={score.get('missed_n')}")
    elif "verdicts" in score:
        lines.append(f"score       n_checks={score.get('n_checks',0)}  proved={score.get('proved',0)}  "
                     f"refuted={score.get('refuted',0)}  timeout_or_error={score.get('timeout_or_error',0)}")
        for v in score.get("verdicts", []):
            lines.append(f"              - {v.get('verdict','?'):<14s} {v.get('function','?')}")
    else:
        lines.append(f"score       (no recall/verdicts; raw={json.dumps(score)[:80]})")
    leads = r.get("leads") or []
    lines.append(f"leads       {len(leads)} entries")
    for i, l in enumerate(leads[:5]):
        lines.append(f"  L{i+1}: {l[:100]}")
    if len(leads) > 5:
        lines.append(f"  ... and {len(leads)-5} more")
    truth = r.get("ground_truth_path")
    if truth:
        lines.append(f"truth       {truth}")
    lines.append(f"prior       {r.get('prior','?')}  embed_coords={r.get('embed_coords')}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    needle = sys.argv[1]
    path = DEFAULT_LOG
    if "--path" in sys.argv:
        path = sys.argv[sys.argv.index("--path") + 1]
    if not os.path.isfile(path):
        print(f"no reps at {path}")
        sys.exit(1)

    hits = find(path, needle)
    if not hits:
        print(f"no rep matching prefix {needle!r}")
        sys.exit(1)
    if len(hits) > 1:
        print(f"prefix {needle!r} matched {len(hits)} rows — narrow it:")
        for h in hits:
            print(f"  {h.get('rep_id')}  {os.path.basename(h.get('contract',{}).get('path','').rstrip('/'))}")
        sys.exit(1)
    print(render(hits[0]))


if __name__ == "__main__":
    main()
