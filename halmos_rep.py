"""
halmos_rep — wire halmos as a SECOND verifier column alongside sol_match.

A `model_rep` row scores leads vs an answer key (deductive lower bound on
which findings are real). A `halmos_rep` row asks halmos to PROVE a stated
invariant — answer is one of {PROVED, COUNTEREXAMPLE, TIMEOUT, ERROR}. Both
rows live in the same reps.jsonl. Layer 1's two halves, side-by-side.

Usage:
  python halmos_rep.py examples/synthetic-dreusd
  python halmos_rep.py examples/synthetic-dreusd --function check_redeemReturnsDeposit

Requires Foundry + halmos installed; the codespace's setup.sh ensures both.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rep_log

HALMOS = os.path.join(HERE, ".venv/bin/halmos")
FOUNDRY_BIN = os.path.expanduser("~/.foundry/bin")


def run_halmos(root: str, function_prefix: str = "check", timeout_ms: int = 120000) -> dict:
    env = dict(os.environ, PATH=f"{FOUNDRY_BIN}:{os.environ.get('PATH','')}")
    cmd = [HALMOS, "--root", root, "--function", function_prefix,
           "--solver-timeout-assertion", str(timeout_ms)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_ms // 1000 + 60, env=env, cwd=root)
    return _parse(proc.stdout + proc.stderr, proc.returncode)


def _parse(out: str, returncode: int) -> dict:
    # halmos prints per-function lines like:
    #   [PASS] check_foo (paths: …)        ← PROVED
    #   [FAIL] check_bar — counterexample…  ← COUNTEREXAMPLE
    verdicts = []
    for m in re.finditer(r"\[(PASS|FAIL|TIMEOUT|ERROR)\]\s+(\w+)", out):
        kind, fname = m.group(1), m.group(2)
        verdict = {
            "PASS": "PROVED",
            "FAIL": "COUNTEREXAMPLE",
            "TIMEOUT": "TIMEOUT",
            "ERROR": "ERROR",
        }[kind]
        verdicts.append({"function": fname, "verdict": verdict})
    return {"returncode": returncode, "verdicts": verdicts, "raw_tail": out[-2000:]}


def run_one(ex_path: str, function_prefix: str = "check") -> dict:
    ex_abs = os.path.join(HERE, ex_path) if not os.path.isabs(ex_path) else ex_path
    foundry_toml = os.path.join(ex_abs, "foundry.toml")
    if not os.path.isfile(foundry_toml):
        raise FileNotFoundError(f"no foundry.toml at {ex_abs} — halmos requires Foundry layout")

    result = run_halmos(ex_abs, function_prefix=function_prefix)

    proved = sum(1 for v in result["verdicts"] if v["verdict"] == "PROVED")
    refuted = sum(1 for v in result["verdicts"] if v["verdict"] == "COUNTEREXAMPLE")
    n = len(result["verdicts"])

    row = {
        "contract": {
            "path": ex_abs,
            "sha256_dir": rep_log.sha256_dir(ex_abs),
        },
        "proposer": {
            "kind": "halmos",
            "version": "v1",
            "function_prefix": function_prefix,
        },
        "leads": [v["function"] for v in result["verdicts"]],
        "verifier": {
            "kind": "halmos",
            "returncode": result["returncode"],
        },
        "score": {
            "n_checks": n,
            "proved": proved,
            "refuted": refuted,
            "timeout_or_error": n - proved - refuted,
            "verdicts": result["verdicts"],
        },
        "ground_truth_path": None,
    }
    written = rep_log.write_rep(row)
    return written


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ex = sys.argv[1]
    function_prefix = "check"
    if "--function" in sys.argv:
        function_prefix = sys.argv[sys.argv.index("--function") + 1]
    try:
        r = run_one(ex, function_prefix=function_prefix)
        print(json.dumps({
            "ex": ex,
            "rep_id": r["rep_id"],
            "n_checks": r["score"]["n_checks"],
            "proved": r["score"]["proved"],
            "refuted": r["score"]["refuted"],
            "timeout_or_error": r["score"]["timeout_or_error"],
            "verdicts": r["score"]["verdicts"],
        }, indent=2))
    except Exception as e:
        print(json.dumps({"ex": ex, "error": str(e)}))


if __name__ == "__main__":
    main()
