"""
sol_intent — the auditor's brain. Recover what the builders INTENDED (from README, ADRs, NatSpec, and
git history) and find where the Solidity code BETRAYS its own stated intent. The bug is the gap between
what they meant and what they made.

This is the eyes; plumbline (the verifier) is the organ. Run intent first to get the promised invariants
+ a struggle-prioritized list of where code contradicts them; verify the survivors with plumbline.

  python sol_intent.py <repo-or-dir>
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import invariant_agent as agent
import prompt_improve as pi

_SKIP = {"lib", "node_modules", "out", "cache", ".git", "test", "tests", "script", "scripts"}
_FIX = re.compile(r"\b(fix|bug|revert|reverts|again|broke|broken|wrong|incorrect|patch|hotfix|oops)\b", re.I)


def _read_first(root, names):
    for n in names:
        p = os.path.join(root, n)
        if os.path.isfile(p):
            return open(p, encoding="utf-8", errors="replace").read()
    return ""


def collect(root):
    """README + ADRs (highest-confidence intent) + the Solidity sources (excluding tests/libs)."""
    readme = _read_first(root, ["README.md", "README.rst", "README.txt", "README"])[:8000]
    adrs, sols = [], []
    for dp, dns, fs in os.walk(root):
        parts = set(dp.split(os.sep))
        dns[:] = [d for d in dns if d not in _SKIP and not d.endswith(".egg-info")]
        if parts & _SKIP:
            continue
        low = dp.lower()
        for f in sorted(fs):
            fl = f.lower()
            full = os.path.join(dp, f)
            if fl.endswith((".md", ".txt")) and ("adr" in low or "decision" in low or "adr" in fl or fl.startswith("adr")):
                adrs.append(open(full, encoding="utf-8", errors="replace").read())
            elif f.endswith(".sol") and not f.endswith(".t.sol"):
                rel = os.path.relpath(full, root)
                sols.append((rel, open(full, encoding="utf-8", errors="replace").read()))
    return readme, "\n\n---\n\n".join(adrs[:10])[:8000], sols


def git_struggle(root, sols):
    """Per-file struggle score from git history: more fixes/reverts = where they fought bugs = look
    here hardest. Language-agnostic (the distinctive pact-intent signal)."""
    rows = []
    for rel, _ in sols:
        try:
            log = subprocess.run(["git", "-C", root, "log", "--oneline", "--", rel],
                                 capture_output=True, text=True, timeout=20).stdout
        except Exception:
            log = ""
        lines = [l for l in log.splitlines() if l.strip()]
        churn = len(lines)
        struggle = sum(1 for l in lines if _FIX.search(l))
        if churn:
            rows.append((struggle * 3 + churn, churn, struggle, rel))
    rows.sort(reverse=True)
    if not rows:
        return "(no git history — prioritize by code complexity instead)"
    return "\n".join(f"  {rel}: {churn} commits, {struggle} fix/revert" for _, churn, struggle, rel in rows)


def analyze(root, model=None):
    readme, adrs, sols = collect(root)
    if not sols:
        return "(no Solidity sources found under " + root + ")"
    struggle = git_struggle(root, sols)
    src_blob = "\n\n".join(f"// ===== {rel} =====\n{src}" for rel, src in sols)[:60000]
    # The prompt is file-backed and SELF-IMPROVING: sol_flywheel scores this output on grounded
    # recall/precision and calls prompt_improve.improve_if_weak, which rewrites sol_intent.md when weak.
    prompt = pi.render(
        open(os.path.join(HERE, "prompts/sol_intent.md")).read(),
        struggle=struggle, readme=readme or "(no README)",
        adrs=adrs or "(no ADRs found)", sources=src_blob)
    return agent._ask(prompt, 3000)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"sol_intent: recovering builder intent + violations for {root}\n")
    print(analyze(root))
