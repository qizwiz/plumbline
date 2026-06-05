"""
rep_log — append-only JSONL of training reps. Layer 1 carrier of the bilayer IR:
the row is the rep, the file is the dataset, the schema is the contract that
future Layer 2 (hyperbolic embedding) attaches to.

Row schema (Lisp-shaped, JSON-encoded):
  (rep
    :rep_id            <uuid>
    :ts_ns             <int>
    :contract          {:path, :sha256_dir}      ; identity of the codebase under test
    :proposer          {:kind, :version, :model} ; what generated the leads/invariant
    :leads             [str, ...]                ; the proposal(s)
    :verifier          {:kind, :result}          ; halmos / sol_match / manual
    :score             {:recall, :precision, ...} ; from sol_match against truth
    :ground_truth_path <path>
    :prior             "random"                  ; Layer 2 init policy (locked = random per agreement)
    :embed_coords      null)                     ; filled later by Layer 2 pass

REP_LOG is append-only. Never rewrite past rows.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REP_LOG = os.path.join(HERE, "reps.jsonl")


def sha256_dir(path: str) -> str:
    """Stable hash over all source files under `path` (sorted by relative path).
    Identity for the contract-under-test — same files in, same hash out."""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(path)):
        for fn in sorted(files):
            if fn.startswith(".") or fn in {"reps.jsonl"}:
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, path).encode("utf-8")
            h.update(rel + b"\x00")
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
    return h.hexdigest()


def write_rep(row: dict) -> dict:
    """Append a rep row. Stamp rep_id, ts_ns, prior, embed_coords if absent."""
    row.setdefault("rep_id", str(uuid.uuid4()))
    row.setdefault("ts_ns", time.time_ns())
    row.setdefault("prior", "random")
    row.setdefault("embed_coords", None)
    with open(REP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return row


def read_reps() -> list[dict]:
    if not os.path.exists(REP_LOG):
        return []
    with open(REP_LOG, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


if __name__ == "__main__":
    rows = read_reps()
    print(f"{len(rows)} reps in {REP_LOG}")
    for r in rows[-5:]:
        print(f"  {r.get('ts_ns')}  {r.get('proposer',{}).get('kind')}  "
              f"recall={r.get('score',{}).get('recall'):.2f}  "
              f"precision={r.get('score',{}).get('precision'):.2f}  "
              f"contract={r.get('contract',{}).get('sha256_dir','')[:12]}")
