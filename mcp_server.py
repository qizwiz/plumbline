"""
mcp_server — plumbline functions as MCP tools.

Per JH's user rule: "If you CAN mcp it, mcp it." This wraps the deterministic
parts of the rep loop so any Claude session (CLI, IDE, Codespace) can call
them without learning the file layout.

Tools exposed:
  plumbline_match        — sol_match leads vs findings; returns recall/precision
  plumbline_scoreboard   — per-corpus μ±σ aggregator over reps.jsonl
  plumbline_validate     — schema-audit reps.jsonl
  plumbline_halmos_rep   — run halmos on an examples/<name> with Foundry layout
                           (requires forge + halmos in PATH)

DOES NOT expose sol_intent (LLM proposer) — that costs money and the cron
rule forbids unauthorized spend. Anything that wants the proposer must call
it explicitly via shell, not via MCP.

Install:
  pip install fastmcp
  # then point your MCP host (claude_desktop_config.json or .mcp.json) at:
  #   { "command": "python", "args": ["/path/to/plumbline/mcp_server.py"] }
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    from fastmcp import FastMCP
except ImportError:
    sys.stderr.write("fastmcp not installed; run: pip install fastmcp\n")
    sys.exit(1)

import sol_match
import rep_log

mcp = FastMCP("plumbline")


@mcp.tool()
def plumbline_match(leads: list[str], findings: list[str], threshold: float = 0.80) -> dict:
    """Score a list of audit leads against a list of ground-truth findings.

    Deterministic: identifier-overlap first (argmax), embedding fallback
    (BAAI/bge-small-en-v1.5, cosine, fixed threshold). Returns the same
    schema sol_match.match() does — recall/precision/matched/missed/pairs.

    Use for evaluating audit-tool output (slither, semgrep, sol_intent, etc.)
    against a known answer key.
    """
    return sol_match.match(leads, findings, threshold=threshold)


@mcp.tool()
def plumbline_scoreboard(reps_path: str | None = None) -> str:
    """Return the per-corpus μ±σ aggregate table for the rep dataset.

    Mirrors `python scoreboard.py` output but returns it as a string so an
    MCP host can render it inline. If reps_path is None, uses ~/src/plumbline/
    reps.jsonl.
    """
    log = reps_path or os.path.join(HERE, "reps.jsonl")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "scoreboard.py")],
        env={**os.environ, "REP_LOG": log},
        capture_output=True, text=True, timeout=30,
    )
    return (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.returncode else "")


@mcp.tool()
def plumbline_validate(reps_path: str | None = None) -> dict:
    """Schema audit of reps.jsonl. Returns {ok: bool, errors: [str], n_rows: int}.

    Same checks as the GH Actions sanity workflow. Use this from a Claude
    session before/after appending rows to confirm the dataset hasn't drifted.
    """
    sys.path.insert(0, os.path.join(HERE, "tools"))
    from validate_reps import validate
    path = reps_path or os.path.join(HERE, "reps.jsonl")
    code, errs = validate(path)
    n_rows = sum(1 for ln in open(path) if ln.strip()) if os.path.isfile(path) else 0
    return {"ok": code == 0, "errors": errs, "n_rows": n_rows, "path": path}


@mcp.tool()
def plumbline_halmos_rep(example: str, function_prefix: str = "check") -> dict:
    """Run halmos on examples/<example> (must have foundry.toml + test/) and
    log the verdict as a new row in reps.jsonl. Returns the full rep_row.

    Requires forge + halmos in PATH. From a Codespace this is automatic;
    locally, see .devcontainer/setup.sh for the install dance.

    Verdicts: PROVED / COUNTEREXAMPLE / TIMEOUT / ERROR (per check_* function).
    """
    sys.path.insert(0, HERE)
    import halmos_rep
    ex_path = example if os.path.isabs(example) else os.path.join(HERE, "examples", example)
    return halmos_rep.run_one(ex_path, function_prefix=function_prefix)


@mcp.tool()
def plumbline_status() -> dict:
    """Quick top-level state. Returns repo HEAD, rep count, scoreboard summary,
    and the count of unchecked TODO items. Use as a one-shot "where are we."
    """
    head = subprocess.run(["git", "-C", HERE, "log", "-1", "--format=%h %s"],
                          capture_output=True, text=True).stdout.strip()
    n_reps = sum(1 for ln in open(os.path.join(HERE, "reps.jsonl"))) \
        if os.path.isfile(os.path.join(HERE, "reps.jsonl")) else 0
    todo = open(os.path.join(HERE, "TODO.md")).read() \
        if os.path.isfile(os.path.join(HERE, "TODO.md")) else ""
    n_open = todo.count("\n- [ ]")
    return {
        "head": head,
        "n_reps": n_reps,
        "todo_open": n_open,
        "repo": HERE,
    }


if __name__ == "__main__":
    mcp.run()
