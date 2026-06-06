"""
validate_reps — schema audit for reps.jsonl. Append-only datasets only stay
useful if every row honors the contract; this validator is the guard.

Checks (each row):
  - parseable JSON
  - has all expected top-level keys
  - contract.path + contract.sha256_dir present
  - proposer.kind in {manual, sol_intent, halmos}
  - prior == "random"  (Layer 2 init policy locked per CLAUDE.md)
  - rep_id is a UUID-shape string (8-4-4-4-12 hex)
  - ts_ns is an int

Cross-row:
  - rep_id uniqueness
  - ts_ns monotonic non-decreasing in file order (append-only honesty)

Exits non-zero on any failure — drop-in for CI.

  python tools/validate_reps.py
  python tools/validate_reps.py --path other/reps.jsonl
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOG = os.path.join(HERE, "reps.jsonl")

EXPECTED_TOP_KEYS = (
    "rep_id", "ts_ns", "contract", "proposer", "leads",
    "verifier", "score", "prior", "embed_coords",
)
ALLOWED_PROPOSERS = {"manual", "sol_intent", "halmos", "ensemble"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def validate(path: str) -> tuple[int, list[str]]:
    errors: list[str] = []
    rows: list[dict] = []
    if not os.path.isfile(path):
        return 1, [f"no reps file at {path}"]

    for ln_no, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {ln_no}: unparseable JSON ({e})")
            continue

        for k in EXPECTED_TOP_KEYS:
            if k not in row:
                errors.append(f"line {ln_no}: missing top-level key '{k}'")

        c = row.get("contract", {})
        if not c.get("path"):
            errors.append(f"line {ln_no}: contract.path missing")
        if not c.get("sha256_dir"):
            errors.append(f"line {ln_no}: contract.sha256_dir missing")

        kind = row.get("proposer", {}).get("kind")
        if kind not in ALLOWED_PROPOSERS:
            errors.append(f"line {ln_no}: proposer.kind={kind!r} not in {sorted(ALLOWED_PROPOSERS)}")

        if row.get("prior") != "random":
            errors.append(f"line {ln_no}: prior={row.get('prior')!r} (must be 'random' per Layer 2 lock)")

        rid = row.get("rep_id", "")
        if not UUID_RE.match(rid):
            errors.append(f"line {ln_no}: rep_id={rid!r} is not UUID-shaped")

        if not isinstance(row.get("ts_ns"), int):
            errors.append(f"line {ln_no}: ts_ns must be int, got {type(row.get('ts_ns')).__name__}")

        rows.append(row)

    # cross-row checks
    ids = [r.get("rep_id") for r in rows]
    if len(ids) != len(set(ids)):
        from collections import Counter
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        errors.append(f"duplicate rep_id(s): {dupes[:5]}")

    last_ts = -1
    for i, r in enumerate(rows):
        ts = r.get("ts_ns")
        if isinstance(ts, int) and ts < last_ts:
            errors.append(f"row {i}: ts_ns={ts} not monotonic (prev={last_ts})")
        if isinstance(ts, int):
            last_ts = ts

    return (0 if not errors else 1), errors


def main():
    path = DEFAULT_LOG
    if "--path" in sys.argv:
        path = sys.argv[sys.argv.index("--path") + 1]

    code, errs = validate(path)
    if errs:
        print(f"FAIL  {path}  ({len(errs)} error{'s' if len(errs)!=1 else ''})")
        for e in errs[:25]:
            print(f"  - {e}")
        if len(errs) > 25:
            print(f"  ... and {len(errs)-25} more")
    else:
        # count rows
        n = sum(1 for _ in open(path) if _.strip())
        print(f"OK    {path}  ({n} rows; all schema checks pass)")
    sys.exit(code)


if __name__ == "__main__":
    main()
