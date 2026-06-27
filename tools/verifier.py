"""
verifier.py — the soundness CHOKEPOINT. The ONLY place a tool verdict is minted.

A verdict is a pure function of a real subprocess's captured (stdout, exit_code).
The LLM agent may ROUTE a finding to a tool, but it can NEVER author a verdict:
this module spawns the subprocess, sha256-hashes the output, calls a registered
PURE parser, and ASSERTS that any CONFIRMED carries an `evidence` string that is a
literal substring of the captured stdout — otherwise it downgrades to ESCALATED.
Theater is structurally impossible here: a verdict with no real subprocess cannot
be constructed, and a CONFIRMED with no in-band witness cannot survive.
"""
from __future__ import annotations
import hashlib
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

# ---- verdicts ----
CONFIRMED = "CONFIRMED"    # tool produced a real violation witness (counterexample / sat model)
CLEARED = "CLEARED"        # tool produced a POSITIVE proof of safety (unsat / [PASS] / lean exit-0)
ESCALATED = "ESCALATED"    # tool could not soundly settle it -> human review
TOOL_ERROR = "TOOL_ERROR"  # the tool failed to run / timed out

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class ToolVerdict:
    tool: str
    argv: list
    cwd: str
    exit_code: int
    wall_s: float
    stdout_sha256: str
    stdout_excerpt: str
    verdict: str
    evidence: Optional[str] = None     # the literal stdout substring proving CONFIRMED
    verdict_source: str = "tool"       # the structural firewall flag the renderer trusts

    def dict(self) -> dict:
        return asdict(self)


# parser signature: (stdout_plus_stderr: str, exit_code: int) -> (verdict, evidence_or_None)
Parser = Callable[[str, int], tuple]


def run_verifier(tool: str, argv: list, cwd: str, parser: Parser, timeout: int = 240,
                 stdin: Optional[str] = None, excerpt_len: int = 700) -> ToolVerdict:
    """Spawn the real tool, capture output, mint a verdict through the firewall."""
    t0 = time.monotonic()
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, input=stdin)
        out = (r.stdout or "") + (r.stderr or "")
        code = r.returncode
    except subprocess.TimeoutExpired:
        return ToolVerdict(tool, argv, cwd, -1, round(time.monotonic() - t0, 2),
                           "", f"[timeout after {timeout}s]", TOOL_ERROR, evidence="timeout")
    except Exception as e:
        return ToolVerdict(tool, argv, cwd, -1, round(time.monotonic() - t0, 2),
                           "", str(e)[:200], TOOL_ERROR, evidence=str(e)[:120])

    out = _strip_noise(_ANSI.sub("", out))   # drop benign forge/halmos build warnings before hashing/excerpting
    wall = round(time.monotonic() - t0, 2)
    sha = hashlib.sha256(out.encode("utf-8", "replace")).hexdigest()[:16]
    verdict, evidence = parser(out, code)

    # SOUNDNESS FIREWALL: a CONFIRMED must carry a witness that LITERALLY appears in
    # the captured stdout. If the parser can't point at real output, it's hallucinating.
    if verdict == CONFIRMED and (not evidence or evidence not in out):
        verdict, evidence = ESCALATED, None

    return ToolVerdict(tool, argv, cwd, code, wall, sha,
                       _excerpt(out, evidence, excerpt_len), verdict, evidence)


_NOISE = re.compile(r"No files changed|^\s*Warning:|AST source not found|Found unknown|"
                    r"Compiler run successful|^\s*Warning \(\d|Unused (function parameter|local variable)|"
                    r"forge-lint|unsafe-typecast")


def _strip_noise(out: str) -> str:
    """Drop benign forge/halmos build warnings so the stored excerpt + sha are the RESULT, not noise.
    Never touches result/witness lines (Counterexample, [FAIL]/[PASS], `= 0x…`), so the soundness
    firewall (`evidence in out`) still holds."""
    return "\n".join(ln for ln in out.splitlines() if not _NOISE.search(ln))


def _excerpt(out: str, evidence: Optional[str], n: int) -> str:
    """A window around the witness if we have one, else the head — for the UI terminal block."""
    out = out.strip()
    if evidence and evidence in out:
        i = out.index(evidence)
        return out[max(0, i - 160): i + len(evidence) + 160].strip()[:n]
    return out[:n]


# ---------- registered PURE parsers ----------

def parse_halmos(out: str, code: int):
    m = re.search(r"Counterexample:\s*([^\n]+)", out)
    if m and re.search(r"[0-9A-Za-z]", m.group(1)):       # a real model, not ∅ / empty
        return CONFIRMED, m.group(1).strip()[:90]
    if re.search(r"\b[1-9][0-9]* passed; 0 failed\b", out) or "[PASS]" in out:
        return CLEARED, None
    return ESCALATED, None                                 # FAIL w/o concrete model -> escalate, never confirm


def parse_z3_cast(out: str, code: int):
    """sol_z3-style: prints 'unsat' (proved safe) or 'sat' + a model (truncatable)."""
    low = out.lower()
    if re.search(r"\bunsat\b", low):
        return CLEARED, None
    m = re.search(r"\bsat\b.*", out, re.S)
    if re.search(r"\bsat\b", low) and m:
        return CONFIRMED, m.group(0).strip()[:120]
    return ESCALATED, None


def parse_lean(out: str, code: int):
    """Lean admits ONLY on a live exit-0 with no error/sorry. (`sorry` is a WARNING at
    exit 0, so we MUST scan stdout, not just the return code — that's the teeth.)"""
    low = out.lower()
    if code == 0 and not re.search(r"\berror\b|\bsorry\b|hassorry|uses 'sorry'|declaration uses", low):
        return CLEARED, "lean: exit 0, no sorry/error"   # evidence is synthetic-but-true; not CONFIRMED so firewall N/A
    return ESCALATED, None


PARSERS = {"halmos": parse_halmos, "z3_cast": parse_z3_cast, "lean": parse_lean}
