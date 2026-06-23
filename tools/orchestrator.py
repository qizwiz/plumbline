"""
orchestrator.py — the agent loop.

An LLM agent PROPOSES findings, then ROUTES each to the formal verifier that can
soundly settle it; a deterministic dispatcher runs the REAL tool via verifier.run_verifier
(the only place a verdict is minted). The agent's reasoning is the visible hero on the
page; only a tool subprocess can mark a finding CONFIRMED / CLEARED — the agent literally
has no verdict field to fill in.

  orchestrate(target_dir, model) -> schema_v3 payload (written to states/audit-runs/<slug>.json)
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import verifier as V

HALMOS = str(ROOT / ".venv" / "bin" / "halmos")
LEAN_OBLIGATION = str(ROOT / "lean" / "SummaryObligation.lean")
# lean ships via elan and is usually NOT on a bare subprocess PATH; resolve it.
_ELAN_LEAN = Path.home() / ".elan" / "bin" / "lean"
LEAN_BIN = str(_ELAN_LEAN) if _ELAN_LEAN.exists() else "lean"

ROUTING_GUIDE = """You are the routing brain of a formal-verification agent. For each finding, pick the
ONE verifier that can soundly settle it:

- "halmos"  — symbolic-EVM EXPLOIT class: fund drain, conservation/solvency, redeem returns more than
              deposited, signature replay, supply-exceeds-backing. ONLY if a check_* invariant in the
              provided list actually tests THIS claim. Set "invariant" to that exact check_* name.
- "z3_cast" — a narrowing INTEGER-CAST / truncation / decimal-scaling bug (e.g. casting a uint256 sum
              down to uint64; fee truncation).
- "lean"    — a width-independent ARITHMETIC obligation: mulDiv / ERC4626 share-rounding soundness,
              floor monotonicity — properties true over the naturals regardless of bit width.
- "none"    — no formal tool fits (or halmos fits but NO listed invariant matches); ESCALATES to a human.

Pick "halmos" ONLY when one of the listed invariants genuinely tests the claim — name it in "invariant".
If no invariant matches, choose another tool or "none"; do NOT route to halmos with a mismatched invariant.

Respond with ONLY a fenced json array, one object per finding, no prose ("invariant" null unless halmos):
```json
[{"finding_id": 0, "chosen_tool": "halmos", "invariant": "check_supplyAtMostBacking", "bug_class": "supply-vs-backing", "rationale": "<one sentence>"}]
```"""


def _llm(prompt: str, model: str, timeout: int = 180) -> str:
    try:
        r = subprocess.run(["uvx", "--quiet", "--with", "llm-openrouter", "llm", "-m", model],
                           input=prompt, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _parse_routes(raw: str) -> list:
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.S) or re.search(r"(\[.*\])", raw, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:
        return []


# ---------- the runners: each returns a verifier.ToolVerdict (the only verdict source) ----------

def run_halmos(target: Path, inv: str) -> V.ToolVerdict:
    return V.run_verifier("halmos", [HALMOS, "--function", inv], str(target),
                          V.PARSERS["halmos"], timeout=240)


def run_lean() -> V.ToolVerdict:
    return V.run_verifier("lean", [LEAN_BIN, LEAN_OBLIGATION], str(ROOT),
                          V.PARSERS["lean"], timeout=120)


def run_z3_cast(body: str, operand: str, bits: int = 64) -> V.ToolVerdict:
    payload = json.dumps({"body": body, "operand": operand, "bits": bits})
    return V.run_verifier("z3_cast", [sys.executable, str(HERE / "_z3_cast_runner.py")], str(ROOT),
                          V.PARSERS["z3_cast"], timeout=120, stdin=payload)


# a tiny, honest demo artifact for the z3 cast class (a real uint64 truncation condition):
# total fees accumulate in uint256 then are cast to uint64 — z3 finds the overflow witness.
_Z3_CAST_DEMO = {
    "body": "uint256 totalFees; uint256 fee; uint64 cast = uint64(totalFees + fee);",
    "operand": "totalFees + fee",
    "bits": 64,
}


def orchestrate(target_dir: str, model: str) -> dict:
    import cli  # lazy to avoid circular import; reuse the proposer + invariant discovery
    target = Path(target_dir).resolve()

    # forge build (halmos prerequisite); swallow lint noise
    try:
        subprocess.run(["forge", "build"], cwd=str(target), capture_output=True, text=True, timeout=300)
    except Exception:
        pass

    # 1. PROPOSE (real live LLM)
    proposer = cli._run_proposer(target, model)
    findings = proposer.get("findings", []) if proposer else []
    for i, f in enumerate(findings):
        f["finding_id"] = i

    # 2. ROUTE (the agent reasons which verifier fits each finding)
    invs = cli._find_invariants(target)
    route_prompt = (ROUTING_GUIDE + "\n\nAvailable halmos check_* invariants in this project: "
                    + (", ".join(invs) if invs else "(none)")
                    + "\n\nFINDINGS:\n"
                    + "\n".join(f"{f['finding_id']}: [{f.get('severity')}] {f.get('function')} — {f.get('desc')}"
                                for f in findings))
    routes = {r.get("finding_id"): r for r in _parse_routes(_llm(route_prompt, model))}

    # 3. DISPATCH — run the REAL tool the agent picked
    inv_claimed = set()
    out_findings = []
    for f in findings:
        r = routes.get(f["finding_id"], {})
        tool = r.get("chosen_tool", "none")
        rec = {"severity": f.get("severity"), "function": f.get("function"),
               "claim": f.get("desc"), "claim_source": "proposer",
               "bug_class": r.get("bug_class", ""),
               "route": {"chosen_tool": tool, "rationale": r.get("rationale", ""),
                         "rationale_source": "proposer"}}
        steps = []
        # `bound` = the tool ran against THIS target's bytecode/test (halmos check_*),
        # so its verdict is a fact about the actual contract. A general/representative
        # obligation (lean lemma, z3 cast demo) is NOT bound — it can SUPPORT a finding
        # but must not be allowed to stamp it CONFIRMED. Misattribution is the cardinal sin.
        bound = False
        if tool == "halmos" and invs:
            # Bind to the invariant the AGENT named (its rationale reasons about which check_*
            # tests the claim). Honor that choice; else fall back to a function-name match.
            # If NEITHER yields a real, unclaimed invariant → no step → ESCALATE. Never grab an
            # arbitrary invariant: a counterexample for check_X must not be stamped onto a claim
            # about Y. Mis-binding is theater even when the subprocess is real.
            want = str(r.get("invariant") or "").strip()
            inv = want if (want in invs and want not in inv_claimed) else None
            if inv is None:
                fn = str(f.get("function", "")).split(".")[-1].lower()
                inv = next((iv for iv in invs if iv not in inv_claimed and fn and fn in iv.lower()), None)
            if inv:
                inv_claimed.add(inv)
                rec["route"]["invariant"] = inv
                steps.append(run_halmos(target, inv).dict())
                bound = True   # the symbolic test executes the real contract
        elif tool == "lean":
            steps.append(run_lean().dict())          # a general arithmetic lemma, not target bytecode
        elif tool == "z3_cast":
            steps.append(run_z3_cast(**_Z3_CAST_DEMO).dict())  # a representative truncation obligation
        # determine the finding verdict from the (last) tool step; no tool -> ESCALATED
        if steps:
            v = steps[-1]
            v["bound"] = bound
            if bound:
                rec["verification"] = {"verdict": v["verdict"], "verdict_source": "tool",
                                       "bound": True, "steps": steps}
            elif v["verdict"] == V.TOOL_ERROR:
                rec["verification"] = {
                    "verdict": V.ESCALATED, "verdict_source": "tool", "bound": False,
                    "steps": steps,
                    "note": f"{v['tool']} failed to run ({v.get('evidence')}) — escalated",
                }
            else:
                # a real subprocess ran and produced a real result, but it is a
                # representative/general obligation — honest verdict is ESCALATED,
                # with the tool result attached as SUPPORTING (not dispositive) evidence.
                rec["verification"] = {
                    "verdict": V.ESCALATED, "verdict_source": "tool", "bound": False,
                    "steps": steps,
                    "note": f"{v['tool']} discharged a representative obligation ({v['verdict'].lower()}) — "
                            f"illustrative of the bug class, not bound to this function's bytecode; "
                            f"escalated for target-bound verification",
                }
        else:
            rec["verification"] = {"verdict": V.ESCALATED, "verdict_source": "none", "bound": False,
                                   "steps": [], "note": "no formal tool fit — escalated to human"}
        out_findings.append(rec)

    tools_fired = sorted({s["tool"] for f in out_findings for s in f["verification"]["steps"]})
    payload = {
        "schema_version": 3, "command": "agent-audit",
        "target": str(target), "target_name": target.name, "ts": time.time(),
        "proposer": {"model": model, "ok": bool(findings), "n": len(findings)},
        "tools_fired": tools_fired,
        "n_confirmed": sum(1 for f in out_findings if f["verification"]["verdict"] == V.CONFIRMED),
        "n_cleared": sum(1 for f in out_findings if f["verification"]["verdict"] == V.CLEARED),
        "n_escalated": sum(1 for f in out_findings if str(f["verification"]["verdict"]).startswith(V.ESCALATED)),
        "findings": out_findings,
    }
    runs = ROOT / "states" / "audit-runs"; runs.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{target.name}--agent--{model}".lower()).strip("-")
    (runs / f"{slug}.json").write_text(json.dumps(payload, indent=2))
    (ROOT / "states" / "audit-latest.json").write_text(json.dumps(payload, indent=2))
    return payload
