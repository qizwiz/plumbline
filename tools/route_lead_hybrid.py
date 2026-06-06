"""route_lead_hybrid — spec_retrieval pre-check + ML router fallback. ROUTER_CAVEATS Option 3."""
from __future__ import annotations
import os, pickle, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_retrieval, route_lead  # noqa

ANCHORS = {  # spec-name token → lead-text synonyms
    "sig": ["sig", "signature", "signed"], "replay": ["replay", "twice", "reuse"],
    "wallet": ["wallet", "self"], "cross": ["cross", "different"],
    "partial": ["partial", "per-element", "per-call", "batch"],
    "idempotent": ["idempot", "exist", "redeploy"],
    "create2": ["create2", "deploy", "factory"],
    "reentrancy": ["reentran", "callback", "cei"], "drain": ["drain", "withdraw"],
    "static": ["static"], "dos": ["dos", "revert", "unusable"],
    "erc4337": ["erc4337", "entrypoint", "useroperation"],
    "uint64": ["uint64", "uint128", "truncate", "cast"], "fee": ["fee"],
    "overflow": ["overflow", "wrap"], "nonce": ["nonce"],
}


def _has_anchor(lead: str, spec_name: str) -> bool:
    L = lead.lower()
    for tok in re.findall(r"[A-Z][a-z0-9]+|[a-z0-9]+", spec_name):
        for syn in ANCHORS.get(tok.lower(), [tok.lower()]):
            if re.search(rf"\b{re.escape(syn)}\b", L): return True
    return False


def route(lead: str, threshold: float = 0.55) -> list[tuple[str, float, str]]:
    top = spec_retrieval.query_top(lead, k=1)[0]
    with open(route_lead.MODEL_PATH, "rb") as f: b = pickle.load(f)
    proba = b["model"].predict_proba(route_lead.featurize([lead]))[0]
    ml = sorted(zip(b["classes"], proba), key=lambda kv: -kv[1])
    tlc_fires = top["cos"] > threshold and _has_anchor(lead, top["name"])
    out: list[tuple[str, float, str]] = []
    if tlc_fires:
        out.append(("tlc_will_decide", top["cos"], f"matched {top['name']}"))
    for c, p in ml[:2]:
        if c != "tlc_will_decide" or not tlc_fires:
            out.append((c, float(p), "ml-fallback" if tlc_fires else "ml"))
    if not any(c == "slither_will_catch" for c, _, _ in out):
        out.append(("slither_will_catch", 0.0, "free safety net"))
    return out


def main():
    threshold = 0.55
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])
    leads = [ln.strip() for ln in sys.stdin if ln.strip()]
    if not leads: sys.exit(1)
    for i, lead in enumerate(leads):
        rs = route(lead, threshold)
        parts = [f"{c.replace('_will_catch','').replace('_will_decide','').replace('_only','')} ({s:.2f}, {r})" for c, s, r in rs]
        print(f"[{i+1}] {lead[:60]}\n    {', '.join(parts)}" if len(leads) > 1 else ", ".join(parts))


if __name__ == "__main__": main()
