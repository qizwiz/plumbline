"""
plumbline — public demo (self-contained).

Serves ONLY the /verification money-shot: a live-LLM audit run, gated by halmos,
with a model switcher. Reads PRE-COMPUTED runs from audit-runs/ — it never calls
an LLM or runs halmos at request time, so it's safe to deploy publicly: no keys,
no compute, no cost-per-click, no abuse surface. Regenerate the cache locally with
`plumbline audit <dir> --live --model <m>` and copy states/audit-runs/*.json here.
"""
import os, json, html
from flask import Flask, Response, request, redirect

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "audit-runs")
app = Flask(__name__)

CSS = """
:root{--bg:#0f1115;--bg-2:#161922;--bg-3:#1c2030;--fg:#d4d4dc;--fg-dim:#8a8d99;
--fg-dimmer:#5a5d68;--accent:#d97757;--red:#e06c75;--yel:#e5c07b;--grn:#98c379;--bdr:#232735;}
*{box-sizing:border-box}html,body{background:var(--bg);color:var(--fg);
font-family:'Berkeley Mono','JetBrains Mono','Menlo',monospace;font-size:13px;line-height:1.55;margin:0}
body{padding:2rem 2.4rem;max-width:1100px;margin:0 auto}
h1{font-size:1.05rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 .4rem}
h1 small{color:var(--fg-dimmer);font-weight:400;letter-spacing:0;text-transform:none;font-size:.78rem;margin-left:.6rem}
h3{font-size:.85rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--fg-dim);
margin:2.2rem 0 .7rem;border-bottom:1px solid var(--bdr);padding-bottom:.3rem}
code{font-family:inherit}.muted{color:var(--fg-dim)}.muted-er{color:var(--fg-dimmer)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:.42rem .7rem;text-align:left;border-bottom:1px solid var(--bdr)}
th{font-weight:500;color:var(--fg-dim);text-transform:uppercase;letter-spacing:.05em;font-size:.72rem}
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.2rem;margin:1.4rem 0 2.4rem}
.stat{border:1px solid var(--bdr);padding:1rem 1.2rem;border-radius:4px}
.stat .label{color:var(--fg-dim);text-transform:uppercase;letter-spacing:.06em;font-size:.7rem}
.stat .value{font-size:2rem;font-weight:600;color:var(--accent);margin:.4rem 0 .2rem}
.stat .sub{color:var(--fg-dim);font-size:.78rem}
.pill{font-size:.7rem;padding:1px 6px;border-radius:3px;color:var(--bg);background:var(--accent);font-weight:600}
"""

def page(body):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<title>plumbline — verification</title><style>{CSS}</style></head>"
            f"<body><h1>plumbline <small>verification</small></h1>{body}</body></html>")

def vstyle(v):
    v = str(v)
    if v == "CONFIRMED": return "var(--red)", "✗ CONFIRMED — counterexample"
    if v.startswith("CLEARED"): return "var(--grn)", "✓ proved safe"
    if v.startswith("ESCALATED"): return "var(--yel)", "⊘ ESCALATED — human review"
    return "var(--fg-dim)", html.escape(v)

@app.route("/")
def home():
    return redirect("/verification")

@app.route("/verification")
def verification():
    intro = ("<p class='muted' style='max-width:64ch;margin:.2rem 0 1.4rem;line-height:1.7'>"
             "An AI agent <b>proposes</b> findings on a smart contract, then <b>routes</b> each to the "
             "formal verifier that can settle it — <code>halmos</code> (symbolic EVM), <code>z3</code>, "
             "or <code>lean</code>. Only a real tool subprocess can mark a finding <b>confirmed</b> or "
             "<b>cleared</b>; the agent has no verdict to give. A finding survives only with a "
             "replayable counterexample or a machine-checked proof. "
             "<b>The agent never grades its own homework.</b> Each card is a real recorded run "
             "(reproduce with <code>plumbline audit &lt;dir&gt; --agent</code>).</p>")
    runs = []
    if os.path.isdir(RUNS):
        for fn in sorted(os.listdir(RUNS)):
            if not fn.endswith(".json"): continue
            try:
                d = json.load(open(os.path.join(RUNS, fn)))
                runs.append({"slug": fn[:-5], "target": str(d.get("target_name", "?")),
                             "model": str((d.get("proposer") or {}).get("model", fn[:-5])), "data": d})
            except Exception: pass
    if not runs:
        return Response(page(intro + "<p class='muted'>no cached runs</p>"), mimetype="text/html")
    projects = []
    for r in runs:
        if r["target"] not in projects: projects.append(r["target"])
    sel_proj = request.args.get("project")
    if sel_proj not in projects:
        sel_proj = "synthetic-dreusd" if "synthetic-dreusd" in projects else projects[0]
    proj_runs = [r for r in runs if r["target"] == sel_proj]
    chosen = next((r for r in proj_runs if r["slug"] == request.args.get("model")), None) or proj_runs[0]
    data = chosen["data"]

    def sel(name, options, selected):
        opts = "".join(f"<option value='{html.escape(str(v))}'{' selected' if v==selected else ''}>"
                       f"{html.escape(str(lab))}</option>" for v, lab in options)
        return (f"<span class='muted' style='font-size:.8rem'>{name}&nbsp;</span>"
                f"<select name={name} onchange='this.form.submit()' style='background:var(--bg-3);"
                "color:var(--accent);border:1px solid var(--bdr);border-radius:4px;padding:.35rem .7rem;"
                f"font-family:inherit;font-size:.85rem;margin-right:1.1rem'>{opts}</select>")

    sw = ("<form method=get style='margin:-.2rem 0 1.5rem'>"
          + sel("project", [(p, p) for p in projects], sel_proj)
          + sel("model", [(r["slug"], r["model"].split("/")[-1]
                           + (" · agent" if r["data"].get("command") == "agent-audit" else ""))
                          for r in proj_runs], chosen["slug"])
          + "<span class='muted-er' style='font-size:.75rem'>"
          "same gate · swap the contract or the model</span></form>")

    # ---- agent-orchestration view (schema v3): the visible reasoning trace ----
    if data.get("schema_version") == 3:
        tgt = html.escape(str(data.get("target_name", "?")))
        model = html.escape(str((data.get("proposer") or {}).get("model", "")).split("/")[-1])
        nconf3, nesc3 = data.get("n_confirmed", 0), data.get("n_escalated", 0)
        chips = " ".join("<code class='muted' style='background:var(--bg-3);padding:.15rem .5rem;"
                         f"border-radius:4px'>{html.escape(str(t))}</code>"
                         for t in data.get("tools_fired", [])) or "<span class='muted'>none</span>"
        summary = ("<div class='stat-grid'>"
                   f"<div class='stat'><div class='label'>target · recorded agent run</div>"
                   f"<div class='value' style='font-size:1.15rem'>{tgt}</div><div class='sub'>{model}</div></div>"
                   f"<div class='stat'><div class='label'>confirmed (target-bound)</div>"
                   f"<div class='value' style='color:var(--red)'>{nconf3}</div><div class='sub'>replayable witness</div></div>"
                   f"<div class='stat'><div class='label'>escalated</div>"
                   f"<div class='value' style='color:var(--yel)'>{nesc3}</div><div class='sub'>to human review</div></div></div>"
                   f"<p class='muted' style='font-size:.82rem;margin:.2rem 0 1.4rem'>"
                   f"tools the agent actually invoked this run: {chips}</p>")

        def fmt_argv(argv):
            return " ".join(os.path.basename(a) if str(a).startswith("/") else str(a) for a in argv)

        cards = ""
        for f in data.get("findings", []):
            v = f.get("verification", {})
            color, tag = vstyle(v.get("verdict"))
            route = f.get("route", {})
            tool = html.escape(str(route.get("chosen_tool", "none")))
            bug = html.escape(str(f.get("bug_class", "")))
            term = ""
            for s in v.get("steps", []):
                ex = html.escape(str(s.get("stdout_excerpt", "")).strip())
                term += ("<div style='background:#0b0e14;border:1px solid var(--bdr);border-radius:6px;"
                         "padding:.6rem .8rem;margin:.55rem 0;font-family:ui-monospace,monospace;"
                         "font-size:.78rem;overflow-x:auto'>"
                         f"<div style='color:var(--accent)'>$ {html.escape(fmt_argv(s.get('argv', [])))}</div>"
                         f"<pre style='margin:.4rem 0 0;white-space:pre-wrap;color:var(--fg-dim)'>{ex}</pre>"
                         f"<div class='muted-er' style='font-size:.7rem;margin-top:.4rem'>"
                         f"exit {s.get('exit_code')} · {s.get('wall_s')}s · sha256:{html.escape(str(s.get('stdout_sha256','')))}</div></div>")
            if not v.get("steps"):
                term = ("<div class='muted' style='font-size:.8rem;margin:.55rem 0;font-style:italic'>"
                        "no formal tool dispatched — the agent found no verifier that could soundly "
                        "settle this claim</div>")
            bound = v.get("bound")
            boundtxt = ("bound to this target's bytecode" if bound
                        else "representative obligation — not target-bound" if v.get("steps") else "—")
            note = (f"<div class='muted' style='font-size:.78rem;margin-top:.4rem'>{html.escape(str(v.get('note')))}</div>"
                    if v.get("note") else "")
            cards += (f"<div class='stat' style='border-left:3px solid {color};margin-bottom:1.3rem;padding:1rem 1.1rem'>"
                      f"<div><span class='pill' style='background:{color}'>{html.escape(str(f.get('severity','?')))}</span> "
                      f"<code style='font-size:.95rem'>{html.escape(str(f.get('function','?')))}</code> "
                      f"<span class='muted-er' style='font-size:.7rem'>· claim by proposer</span></div>"
                      f"<div style='margin:.55rem 0 .85rem;line-height:1.55'>{html.escape(str(f.get('claim','')))}</div>"
                      f"<div style='font-size:.83rem;margin:.2rem 0'>"
                      f"<span class='muted'>agent routed&nbsp;→&nbsp;</span><code style='color:var(--accent)'>{tool}</code>"
                      + (f"&nbsp;<code class='muted' style='font-size:.78rem'>{html.escape(str(route.get('invariant')))}</code>"
                         if route.get("invariant") else "")
                      + (f" <code class='muted' style='font-size:.72rem'>{bug}</code>" if bug else "")
                      + (f"<div class='muted' style='font-size:.78rem;margin-top:.25rem;font-style:italic'>"
                         f"“{html.escape(str(route.get('rationale','')))}”</div>" if route.get("rationale") else "")
                      + "</div>" + term
                      + f"<div style='margin-top:.5rem;font-size:.86rem'><b style='color:{color}'>{tag}</b>"
                      f"<span class='muted-er' style='font-size:.72rem'> &nbsp;· verdict source: "
                      f"{html.escape(str(v.get('verdict_source','none')))} · {boundtxt}</span></div>" + note + "</div>")
        body = (intro + sw + summary
                + "<h3>reasoning trace · claim → route → tool → verdict</h3>" + cards)
        return Response(page(body), mimetype="text/html")

    prop = data.get("proposer") or {}
    finds = prop.get("findings", [])
    tgt = html.escape(str(data.get("target_name", "?")))
    model = html.escape(str(prop.get("model", "")).split("/")[-1])
    n_conf = sum(1 for f in finds if f.get("status") == "CONFIRMED")
    n_esc = sum(1 for f in finds if str(f.get("status", "")).startswith("ESCALATED"))
    summary = ("<div class='stat-grid'>"
               f"<div class='stat'><div class='label'>target · recorded run</div>"
               f"<div class='value' style='font-size:1.2rem'>{tgt}</div><div class='sub'>{model}</div></div>"
               f"<div class='stat'><div class='label'>confirmed exploits</div>"
               f"<div class='value' style='color:var(--red)'>{n_conf}</div><div class='sub'>replayable witness</div></div>"
               f"<div class='stat'><div class='label'>escalated</div>"
               f"<div class='value' style='color:var(--yel)'>{n_esc}</div><div class='sub'>no sound invariant → human</div></div></div>")
    cards = ""
    for f in finds:
        color, tag = vstyle(f.get("status"))
        inv = (f" &nbsp;<code class='muted'>{html.escape(str(f.get('invariant')))}</code>" if f.get("invariant") else "")
        cex = f.get("counterexample")
        wit = (f"<div style='margin-top:.5rem'><span class='muted'>counterexample&nbsp;</span>"
               f"<code style='color:{color}'>{html.escape(str(cex))}</code></div>") if cex else ""
        cards += (f"<div class='stat' style='border-left:3px solid {color};margin-bottom:.8rem'>"
                  f"<div><span class='pill' style='background:{color}'>{html.escape(str(f.get('severity','?')))}</span> "
                  f"<code style='font-size:.95rem'>{html.escape(str(f.get('function','?')))}</code></div>"
                  f"<div style='margin:.55rem 0'>{html.escape(str(f.get('desc','')))}</div>"
                  f"<div class='muted' style='font-size:.8rem'>gate&nbsp;→&nbsp;<b style='color:{color}'>{tag}</b>{inv}</div>{wit}</div>")
    grows = ""
    for r in data.get("results", []):
        color, _ = vstyle(r.get("verdict"))
        v = ("✗ FAIL — counterexample" if r.get("verdict") == "CONFIRMED"
             else "✓ PASS — proved safe" if str(r.get("verdict", "")).startswith("CLEARED")
             else html.escape(str(r.get("verdict", "?"))))
        grows += (f"<tr><td><code>{html.escape(str(r.get('invariant','')))}</code></td>"
                  f"<td style='color:{color}'>{v}</td></tr>")
    gate = f"<table><tr><th>invariant</th><th>halmos verdict (independent)</th></tr>{grows}</table>"
    body = (intro + sw + summary + "<h3>agent findings · recorded LLM run</h3>" + cards
            + "<h3>gate · independent formal verdicts</h3>" + gate)
    return Response(page(body), mimetype="text/html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
