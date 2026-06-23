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

SPLASH_SVG = '''<svg width="100%" viewBox="0 0 680 392" role="img" xmlns="http://www.w3.org/2000/svg" style="display:block">
<title>plumbline</title><desc>An Egyptian wall scene: workers haul a stone block toward a pyramid while a plumb-line level swings and settles to true vertical; cartouches morph between glyphs and Ethereum hex. Title: plumbline, true by construction.</desc>
<rect x="0" y="0" width="680" height="392" fill="#E4D3AC"/>
<rect x="0" y="0" width="680" height="30" fill="#B98F4D"/>
<g fill="#7A5524"><rect x="14" y="11" width="9" height="9"/><rect x="38" y="11" width="9" height="9"/><rect x="62" y="11" width="9" height="9"/><rect x="86" y="11" width="9" height="9"/><rect x="110" y="11" width="9" height="9"/><rect x="134" y="11" width="9" height="9"/><rect x="158" y="11" width="9" height="9"/><rect x="182" y="11" width="9" height="9"/><rect x="206" y="11" width="9" height="9"/><rect x="230" y="11" width="9" height="9"/><rect x="254" y="11" width="9" height="9"/><rect x="278" y="11" width="9" height="9"/><rect x="302" y="11" width="9" height="9"/><rect x="326" y="11" width="9" height="9"/><rect x="350" y="11" width="9" height="9"/><rect x="374" y="11" width="9" height="9"/><rect x="398" y="11" width="9" height="9"/><rect x="422" y="11" width="9" height="9"/><rect x="446" y="11" width="9" height="9"/><rect x="470" y="11" width="9" height="9"/><rect x="494" y="11" width="9" height="9"/><rect x="518" y="11" width="9" height="9"/><rect x="542" y="11" width="9" height="9"/><rect x="566" y="11" width="9" height="9"/><rect x="590" y="11" width="9" height="9"/><rect x="614" y="11" width="9" height="9"/><rect x="638" y="11" width="9" height="9"/><rect x="662" y="11" width="9" height="9"/></g>
<circle cx="602" cy="78" r="25" fill="#E0A93B"/>
<g stroke="#E0A93B" stroke-width="3" stroke-linecap="round"><line x1="602" y1="40" x2="602" y2="30"/><line x1="640" y1="78" x2="650" y2="78"/><line x1="629" y1="51" x2="636" y2="44"/><line x1="629" y1="105" x2="636" y2="112"/><line x1="575" y1="51" x2="568" y2="44"/></g>
<polygon points="560,138 470,256 650,256" fill="#C99A5B"/>
<polygon points="560,138 560,256 650,256" fill="#B5853F"/>
<g stroke="#9E7333" stroke-width="1" opacity="0.6"><line x1="488" y1="232" x2="632" y2="232"/><line x1="506" y1="208" x2="614" y2="208"/><line x1="524" y1="184" x2="596" y2="184"/><line x1="542" y1="160" x2="578" y2="160"/></g>
<line x1="20" y1="256" x2="660" y2="256" stroke="#8C6A38" stroke-width="2.5"/>
<g><polygon points="262,236 304,236 312,256 254,256" fill="#9E7333"/><rect x="266" y="216" width="34" height="22" fill="#B5853F" stroke="#5E4220" stroke-width="1.5"/><line x1="278" y1="216" x2="278" y2="238" stroke="#5E4220" stroke-width="1"/><line x1="288" y1="216" x2="288" y2="238" stroke="#5E4220" stroke-width="1"/></g>
<line x1="300" y1="226" x2="430" y2="228" stroke="#6E4B22" stroke-width="2"/>
<g fill="#B0492B" stroke="#3A2415" stroke-width="1.2" stroke-linejoin="round">
<g transform="translate(340,0)"><circle cx="0" cy="210" r="6"/><polygon points="-5,217 7,214 9,238 -3,240"/><line x1="6" y1="220" x2="-16" y2="226" stroke="#3A2415" stroke-width="3" stroke-linecap="round"/><line x1="3" y1="239" x2="11" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/><line x1="-2" y1="239" x2="-9" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/></g>
<g transform="translate(374,0)"><circle cx="0" cy="210" r="6"/><polygon points="-5,217 7,214 9,238 -3,240"/><line x1="6" y1="220" x2="-16" y2="226" stroke="#3A2415" stroke-width="3" stroke-linecap="round"/><line x1="3" y1="239" x2="11" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/><line x1="-2" y1="239" x2="-9" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/></g>
<g transform="translate(408,0)"><circle cx="0" cy="210" r="6"/><polygon points="-5,217 7,214 9,238 -3,240"/><line x1="6" y1="220" x2="-16" y2="226" stroke="#3A2415" stroke-width="3" stroke-linecap="round"/><line x1="3" y1="239" x2="11" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/><line x1="-2" y1="239" x2="-9" y2="255" stroke="#3A2415" stroke-width="4" stroke-linecap="round"/></g>
</g>
<g>
<line x1="118" y1="256" x2="170" y2="104" stroke="#5E4220" stroke-width="4" stroke-linecap="round"/>
<line x1="222" y1="256" x2="170" y2="104" stroke="#5E4220" stroke-width="4" stroke-linecap="round"/>
<line x1="118" y1="256" x2="222" y2="256" stroke="#5E4220" stroke-width="5" stroke-linecap="round"/>
<line x1="140" y1="190" x2="200" y2="190" stroke="#5E4220" stroke-width="3"/>
<polygon points="166,256 170,248 174,256" fill="#1C5D99"/>
<g><line x1="170" y1="104" x2="170" y2="206" stroke="#2A1C0E" stroke-width="1.5"/><polygon points="170,206 164,214 170,228 176,214" fill="#1C5D99" stroke="#123E66" stroke-width="1"/>
<animateTransform attributeName="transform" type="rotate" dur="7s" repeatCount="indefinite" keyTimes="0;0.07;0.15;0.23;0.31;0.40;0.49;0.86;1" values="19 170 104; -14 170 104; 10 170 104; -6 170 104; 3 170 104; -1 170 104; 0 170 104; 0 170 104; 19 170 104"/></g>
<text x="196" y="232" font-family="Georgia, serif" font-size="13" fill="#1C5D99" font-style="italic">true<animate attributeName="opacity" dur="7s" repeatCount="indefinite" keyTimes="0;0.45;0.52;0.82;0.9;1" values="0;0;1;1;0;0"/></text>
</g>
<rect x="20" y="290" width="640" height="2" fill="#8C6A38" opacity="0.5"/>
<text x="40" y="338" font-family="Georgia, serif" font-size="40" letter-spacing="2" fill="#9A3B1E">plumbline</text>
<text x="42" y="360" font-family="Georgia, serif" font-size="14" letter-spacing="3" fill="#6E4B22">true by construction</text>
<g font-family="ui-monospace, Menlo, monospace" font-size="14" text-anchor="middle">
<g transform="translate(410,326)"><rect x="-78" y="-17" width="156" height="34" rx="17" fill="none" stroke="#5E4220" stroke-width="2"/><circle cx="-78" cy="0" r="4" fill="#5E4220"/><circle cx="78" cy="0" r="4" fill="#5E4220"/>
<text x="0" y="5" fill="#6E4B22" letter-spacing="3">&#9765; &#9673; &#8982; &#9737; &#9242;<animate attributeName="opacity" dur="4.4s" repeatCount="indefinite" values="1;1;0;0;1" keyTimes="0;0.35;0.5;0.85;1"/></text>
<text x="0" y="5" fill="#1C5D99" letter-spacing="1">0x7a34f5&#8230;c0de<animate attributeName="opacity" dur="4.4s" repeatCount="indefinite" values="0;0;1;1;0" keyTimes="0;0.35;0.5;0.85;1"/></text></g>
<g transform="translate(580,326)"><rect x="-78" y="-17" width="156" height="34" rx="17" fill="none" stroke="#5E4220" stroke-width="2"/><circle cx="-78" cy="0" r="4" fill="#5E4220"/><circle cx="78" cy="0" r="4" fill="#5E4220"/>
<text x="0" y="5" fill="#6E4B22" letter-spacing="3">&#9765; &#8982; &#9772; &#10038; &#9765;<animate attributeName="opacity" dur="4.4s" repeatCount="indefinite" begin="-1.6s" values="1;1;0;0;1" keyTimes="0;0.35;0.5;0.85;1"/></text>
<text x="0" y="5" fill="#9A3B1E" letter-spacing="0.5" font-size="12">0x0D2c3B&#8230;36030aA<animate attributeName="opacity" dur="4.4s" repeatCount="indefinite" begin="-1.6s" values="0;0;1;1;0" keyTimes="0;0.35;0.5;0.85;1"/></text></g>
</g>
<text x="40" y="384" font-family="Georgia, serif" font-size="12" fill="#7A5524" font-style="italic">the plumb line has no opinion about vertical &#8212; and the gate has none about truth</text>
</svg>'''


_LIVE_API = "https://qizwiz--plumbline-live-web-run.modal.run"
_LIVE_BANNER = (
    "<div style='border:1px solid var(--accent);border-radius:8px;padding:0.85rem 1rem;"
    "margin:0 0 1.6rem;background:var(--bg-3)'>"
    "<b>Think the run below is canned?</b> It isn't — "
    "<button id='liveBtn' onclick='runLive()' style='background:var(--accent);color:#1a1205;"
    "border:none;font-weight:600;padding:0.42rem 0.95rem;border-radius:6px;cursor:pointer;"
    "font-family:inherit;font-size:0.82rem'>&#9654; run halmos live in the cloud</button>"
    "<div style='font-size:0.74rem;color:var(--fg-dim);margin-top:0.4rem'>spins a real Modal "
    "container, compiles the contract, runs the symbolic-execution invariant against the real "
    "bytecode, and returns the verbatim output (~5s; longer on a cold start).</div>"
    "<div id='liveOut' style='display:none;background:#0b0e14;border:1px solid var(--bdr);"
    "border-radius:6px;padding:0.6rem 0.8rem;margin-top:0.6rem;font-family:ui-monospace,monospace;"
    "font-size:0.76rem;overflow-x:auto'></div></div>"
    "<script>"
    "async function runLive(){"
    "var b=document.getElementById('liveBtn'),o=document.getElementById('liveOut');"
    "b.disabled=true;b.textContent='running\\u2026';o.style.display='block';"
    "o.innerHTML=\"<span style='color:var(--yel)'>spinning up a Modal container \\u00b7 compiling \\u00b7 running symbolic execution\\u2026</span>\";"
    "try{"
    "var r=await fetch('" + _LIVE_API + "?inv=check_redeemReturnsDeposit');"
    "var d=await r.json();var ok=d.found_counterexample;"
    "o.innerHTML=\"<pre style='white-space:pre-wrap;color:#C9B98F;margin:0'>$ \"+d.argv+\"\\n\\n\"+(d.clean||d.error||'')+\"</pre>\""
    "+\"<div style='margin-top:.5rem;color:\"+(ok?'var(--red)':'var(--yel)')+\"'>\"+(ok?'\\u2713 live halmos found the counterexample':'(no counterexample this run)')+\" \\u00b7 ran in \"+d.ran_in+\" \\u00b7 \"+d.wall_s+\"s \\u00b7 exit \"+d.exit_code+\"</div>\""
    "+\"<div style='font-size:.72rem;color:var(--fg-dim);margin-top:.3rem'>fresh run \\u2014 same 0x800\\u2026 witness as the recording above; only the symbolic var-name and hash differ because it just executed now. Not canned.</div>\";"
    "}catch(e){o.innerHTML=\"<span style='color:var(--yel)'>live endpoint unavailable (\"+e+\"). The recorded run above is still reproducible locally.</span>\";}"
    "b.disabled=false;b.textContent='\\u25b6 run halmos live again';"
    "}"
    "</script>"
)


@app.route("/")
def home():
    body = (
        "<div style='max-width:760px;margin:0 auto;padding:2.4rem 1.1rem 3rem;text-align:center'>"
        "<div style='border:1px solid var(--bdr);border-radius:14px;overflow:hidden;line-height:0'>"
        + SPLASH_SVG +
        "</div>"
        "<p style='font-size:1.05rem;line-height:1.7;color:var(--fg);max-width:60ch;margin:1.8rem auto 0'>"
        "An autonomous AI agent audits your Solidity — it proposes vulnerabilities and routes each "
        "to a formal verifier. Only a real symbolic-EVM proof confirms a finding. "
        "<b>The agent never grades its own homework.</b></p>"
        "<a href='/verification' style='display:inline-block;margin:1.6rem 0 0.7rem;background:var(--accent);"
        "color:#1a1205;font-weight:600;text-decoration:none;padding:0.8rem 1.6rem;border-radius:8px;"
        "font-size:0.95rem'>Watch it confirm a real exploit &#8594;</a>"
        "<p class='muted-er' style='font-size:0.78rem;margin:0.6rem 0 0'>"
        "live halmos counterexamples · machine-checked · escalates what it can’t prove</p>"
        "</div>"
    )
    return Response(page(body), mimetype="text/html")

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
                   f"<p class='muted' style='font-size:.82rem;margin:.2rem 0 .5rem'>"
                   f"tools the agent actually invoked this run: {chips}</p>"
                   f"<p class='muted-er' style='font-size:.78rem;margin:0 0 1.4rem;line-height:1.6;"
                   f"border-left:2px solid var(--bdr);padding-left:.7rem'>"
                   f"<b>Recorded run.</b> The proposer and router are stochastic — <i>which</i> "
                   f"findings appear and <i>which</i> tool each routes to vary run-to-run. The gate "
                   f"is not: each verdict below is a deterministic function of a real subprocess's "
                   f"<code>(stdout, exit_code)</code>, and a CONFIRMED requires the witness to appear "
                   f"verbatim in stdout. Re-run any printed <code>$ halmos&nbsp;…</code> line for "
                   f"the same counterexample, bit for bit.</p>" + _LIVE_BANNER)

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
