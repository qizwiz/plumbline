"""
route_lead_hybrid — composes spec_retrieval ahead of the ML router
to fix the tlc-routing gap from ROUTER_TRAIN. Per ROUTER_CAVEATS.md
Option 3. Usage: echo "lead" | python tools/route_lead_hybrid.py
"""
from __future__ import annotations
import os, pickle, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import spec_retrieval
import route_lead  # noqa: reuses featurize() + MODEL_PATH


def route(lead: str, threshold: float = 0.55) -> list[tuple[str, float, str]]:
    """Top-1 TLA+ shape pre-check; if cos > threshold prepend tlc."""
    top = spec_retrieval.query_top(lead, k=1)[0]
    with open(route_lead.MODEL_PATH, "rb") as f:
        b = pickle.load(f)
    proba = b["model"].predict_proba(route_lead.featurize([lead]))[0]
    ml = sorted(zip(b["classes"], proba), key=lambda kv: -kv[1])

    out: list[tuple[str, float, str]] = []
    if top["cos"] > threshold:
        out.append(("tlc_will_decide", top["cos"], f"matched {top['name']}"))
    for c, p in ml[:2]:
        if c != "tlc_will_decide" or not out:
            out.append((c, float(p), "ml-fallback" if out else "ml"))
    if not any(c == "slither_will_catch" for c, _, _ in out):
        out.append(("slither_will_catch", 0.0, "free safety net"))
    return out


def _fmt(c: str) -> str:
    return c.replace("_will_catch", "").replace("_will_decide", "").replace("_only", "")


def main():
    threshold = 0.55
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])
    leads = [ln.strip() for ln in sys.stdin if ln.strip()]
    if not leads:
        print("(no leads on stdin)", file=sys.stderr); sys.exit(1)
    for i, lead in enumerate(leads):
        routes = route(lead, threshold)
        parts = [f"{_fmt(c)} ({s:.2f}, {r})" for c, s, r in routes]
        if len(leads) > 1:
            print(f"[{i+1}] {lead[:60]}\n    {', '.join(parts)}")
        else:
            print(", ".join(parts))


if __name__ == "__main__":
    main()
