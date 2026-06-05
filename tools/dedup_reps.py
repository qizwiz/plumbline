"""
dedup_reps — detect duplicate rep_id rows in reps.jsonl. Should NEVER find
one; if it does, append-only honesty broke somewhere and we want to know
loudly.

  python tools/dedup_reps.py             # checks ../reps.jsonl, exits non-zero on dupes
  python tools/dedup_reps.py --path X    # custom path

The schema validator (tools/validate_reps.py) also catches this as a
side-check, but having a dedicated tool means CI can isolate the failure
class and STATUS.md can show "0 duplicates, ever" as a standing fact.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG = os.path.join(HERE, "reps.jsonl")


def main():
    path = DEFAULT_LOG
    if "--path" in sys.argv:
        path = sys.argv[sys.argv.index("--path") + 1]

    if not os.path.isfile(path):
        print(f"no reps at {path}")
        sys.exit(1)

    ids = []
    by_id: dict[str, list[int]] = {}
    for ln_no, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            print(f"line {ln_no}: unparseable JSON — skipped")
            continue
        rid = r.get("rep_id")
        if not rid:
            print(f"line {ln_no}: missing rep_id")
            continue
        ids.append(rid)
        by_id.setdefault(rid, []).append(ln_no)

    counts = Counter(ids)
    dupes = [(rid, lns) for rid, lns in by_id.items() if len(lns) > 1]

    if not dupes:
        print(f"OK    {path}  ({len(ids)} reps; 0 duplicates)")
        sys.exit(0)

    print(f"FAIL  {path}  ({len(dupes)} duplicate rep_id{'s' if len(dupes)!=1 else ''})")
    for rid, lns in dupes[:10]:
        print(f"  - {rid}  appears at lines: {lns}")
    if len(dupes) > 10:
        print(f"  ... and {len(dupes) - 10} more")
    sys.exit(1)


if __name__ == "__main__":
    main()
