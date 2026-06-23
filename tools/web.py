"""
tools/web.py — minimal frontend scout for plumbline.

One file, Flask, no DB, no auth. Routes:
  /            single-page dashboard (corpora, rep count, links)
  /scoreboard  runs scoreboard.py and dumps stdout in <pre>
  /reps        last 20 rows of reps.jsonl, pretty
  /fitness     serves docs/fitness.png if it exists

Run:
  python3 tools/web.py
  # -> http://127.0.0.1:5050

Surgical scout — sized to "is a web UI worth building"? Not a product.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys

from flask import Flask, Response, abort, request, send_file

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPS_PATH = os.path.join(ROOT, "reps.jsonl")
STATUS_PATH = os.path.join(ROOT, "STATUS.md")
SCOREBOARD_PY = os.path.join(ROOT, "scoreboard.py")
FITNESS_PNG = os.path.join(ROOT, "docs", "fitness.png")

app = Flask(__name__)


# ---------- helpers ----------------------------------------------------------
#
# (Removed _read_corpora_from_status — the dashboard now reads disk reality
# via _real_corpora() instead of parsing STATUS.md's '## Corpora curated'
# table. STATUS.md is human prose now; if you want a corpus to appear in
# the dashboard, add it to corpus/scabench/curated.json or examples/
# .ANSWERS.md or log a rep referencing it.)


def _rep_count() -> int:
    if not os.path.isfile(REPS_PATH):
        return 0
    return sum(1 for ln in open(REPS_PATH) if ln.strip())


# ---------- live corpora: read disk reality, not STATUS.md prose -------------

CURATED_SCABENCH = os.path.join(ROOT, "corpus", "scabench", "curated.json")
EXAMPLES_DIR = os.path.join(ROOT, "examples")


def _reps_per_corpus() -> dict[str, int]:
    """Count reps grouped by contract.project_id (preferred) or basename(path)."""
    counts: dict[str, int] = {}
    if not os.path.isfile(REPS_PATH):
        return counts
    for ln in open(REPS_PATH):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        contract = r.get("contract", {})
        key = contract.get("project_id") or os.path.basename(
            (contract.get("path") or "?").rstrip("/")
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _real_corpora() -> list[dict]:
    """Compute corpora list from disk reality: scabench + examples + reps."""
    rep_counts = _reps_per_corpus()
    rows: list[dict] = []
    seen: set[str] = set()

    # 1. ScaBench projects from curated.json
    if os.path.isfile(CURATED_SCABENCH):
        try:
            sb = json.loads(open(CURATED_SCABENCH).read())
            for p in sb:
                pid = p.get("project_id") or "?"
                rows.append({
                    "name": pid,
                    "findings": str(len(p.get("vulnerabilities", []))),
                    "source": "scabench/" + p.get("platform", "?"),
                    "reps": rep_counts.get(pid, 0),
                })
                seen.add(pid)
        except json.JSONDecodeError:
            pass

    # 2. Hand-curated examples/ corpora (presence of .ANSWERS.md = labeled)
    if os.path.isdir(EXAMPLES_DIR):
        for name in sorted(os.listdir(EXAMPLES_DIR)):
            ex_dir = os.path.join(EXAMPLES_DIR, name)
            if not os.path.isdir(ex_dir):
                continue
            ans = os.path.join(ex_dir, ".ANSWERS.md")
            findings = "—"
            if os.path.isfile(ans):
                # crude: count "## SEV-" headings
                txt = open(ans).read()
                findings = str(sum(1 for ln in txt.splitlines()
                                   if ln.startswith("## SEV-")))
            rows.append({
                "name": name,
                "findings": findings,
                "source": "examples/",
                "reps": rep_counts.get(name, 0),
            })
            seen.add(name)

    # 3. Any rep-only corpora (logged but not registered anywhere)
    for k, n in sorted(rep_counts.items()):
        if k in seen:
            continue
        rows.append({
            "name": k,
            "findings": "—",
            "source": "reps-only",
            "reps": n,
        })

    return rows


def _tail_reps(n: int = 20) -> list[dict]:
    if not os.path.isfile(REPS_PATH):
        return []
    rows: list[dict] = []
    with open(REPS_PATH) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return rows[-n:]


def _html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — plumbline</title>
<style>
  :root {{
    --bg:        #0f1115;
    --bg-2:      #161922;
    --bg-3:      #1c2030;
    --fg:        #d4d4dc;
    --fg-dim:    #8a8d99;
    --fg-dimmer: #5a5d68;
    --accent:    #d97757;
    --red:       #e06c75;
    --yel:       #e5c07b;
    --grn:       #98c379;
    --bdr:       #232735;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    background: var(--bg);
    color: var(--fg);
    font-family: 'Berkeley Mono', 'JetBrains Mono', 'Menlo', monospace;
    font-size: 13px;
    line-height: 1.55;
    margin: 0;
  }}
  body {{ padding: 2rem 2.4rem; max-width: 1100px; margin: 0 auto; }}
  h1 {{
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 0.4rem;
  }}
  h1 small {{ color: var(--fg-dimmer); font-weight: 400;
              letter-spacing: 0; text-transform: none; font-size: 0.78rem; margin-left: 0.6rem; }}
  h3 {{ font-size: 0.85rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
        color: var(--fg-dim); margin: 2.2rem 0 0.7rem; border-bottom: 1px solid var(--bdr); padding-bottom: 0.3rem; }}
  nav {{ margin: 0.8rem 0 1.6rem; }}
  nav a {{
    color: var(--fg-dim); text-decoration: none; margin-right: 1.2rem; font-size: 0.85rem;
    border-bottom: 1px solid transparent; padding-bottom: 2px;
  }}
  nav a:hover {{ color: var(--fg); border-bottom-color: var(--accent); }}
  pre {{ background: var(--bg-2); border: 1px solid var(--bdr); padding: 0.9rem 1.1rem;
         border-radius: 4px; overflow-x: auto; font-size: 12px; color: var(--fg); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ padding: 0.42rem 0.7rem; text-align: left; border-bottom: 1px solid var(--bdr); }}
  th {{ font-weight: 500; color: var(--fg-dim); text-transform: uppercase; letter-spacing: 0.05em;
        font-size: 0.72rem; border-bottom: 1px solid var(--bdr); }}
  tr:hover td {{ background: var(--bg-2); }}
  tr.has-reps td:first-child {{ border-left: 2px solid var(--accent); padding-left: calc(0.7rem - 2px); }}
  code {{ background: transparent; color: var(--fg); font-family: inherit; }}
  .meter {{ display: inline-block; height: 2px; background: var(--accent); vertical-align: middle; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; margin: 1.4rem 0 2.4rem; }}
  .stat {{ border: 1px solid var(--bdr); padding: 1rem 1.2rem; border-radius: 4px; }}
  .stat .label {{ color: var(--fg-dim); text-transform: uppercase; letter-spacing: 0.06em;
                  font-size: 0.7rem; }}
  .stat .value {{ font-size: 2rem; font-weight: 600; color: var(--accent); margin: 0.4rem 0 0.2rem; }}
  .stat .sub {{ color: var(--fg-dim); font-size: 0.78rem; }}
  .pill {{ font-size: 0.7rem; padding: 1px 6px; border-radius: 3px; color: var(--bg);
            background: var(--accent); font-weight: 600; vertical-align: middle; }}
  .muted {{ color: var(--fg-dim); }}
  .muted-er {{ color: var(--fg-dimmer); }}
</style>
</head>
<body>
  <h1>plumbline <small>{title}</small></h1>
  <nav>
    <a href="/">dashboard</a>
    <a href="/verification">verification</a>
    <a href="/scoreboard">scoreboard</a>
    <a href="/reps">reps</a>
    <a href="/fitness">fitness</a>
  </nav>
  {body}
</body>
</html>
"""


# ---------- routes -----------------------------------------------------------

@app.route("/")
def dashboard() -> Response:
    corpora = _real_corpora()
    n_reps = _rep_count()

    # Sort: corpora with reps first (sorted by rep count desc), then alphabetical
    corpora.sort(key=lambda c: (-c["reps"], c["name"]))
    n_with_reps = sum(1 for c in corpora if c["reps"] > 0)

    if corpora:
        # Render a tiny inline meter for each corpus's rep count
        max_reps = max((c["reps"] for c in corpora), default=1) or 1
        rows = []
        for c in corpora:
            cls = "has-reps" if c["reps"] > 0 else ""
            if c["reps"]:
                bar_w = max(2, int(48 * c["reps"] / max_reps))
                reps_cell = (
                    f"<span class='meter' style='width:{bar_w}px'></span>"
                    f"&nbsp;<code>{c['reps']}</code>"
                )
            else:
                reps_cell = "<span class='muted-er'>—</span>"
            # html.escape on every user/disk-derived string — corpus names
            # come from directory names, scabench project_id, reps.jsonl
            # basename(path); any `<` would otherwise render as HTML.
            rows.append(
                f"<tr class='{cls}'>"
                f"<td><code>{html.escape(str(c['name']))}</code></td>"
                f"<td>{html.escape(str(c['findings']))}</td>"
                f"<td><span class='muted'>{html.escape(str(c['source']))}</span></td>"
                f"<td>{reps_cell}</td>"
                f"</tr>"
            )
        corpora_html = (
            "<table>"
            "<thead><tr><th>corpus</th><th>findings</th>"
            "<th>source</th><th>reps</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    else:
        corpora_html = "<p class='muted'>no corpora on disk</p>"

    n_total = len(corpora)
    body = f"""
    <div class="stat-grid">
      <div class="stat">
        <div class="label">reps logged</div>
        <div class="value">{n_reps}</div>
        <div class="sub">across {n_with_reps} corpora · <a href='/reps' style='color:var(--fg-dim)'>view latest →</a></div>
      </div>
      <div class="stat">
        <div class="label">corpora on disk</div>
        <div class="value">{n_total}</div>
        <div class="sub">{n_with_reps} touched · {n_total - n_with_reps} unused</div>
      </div>
      <div class="stat">
        <div class="label">scoreboard</div>
        <div class="value">μ±σ</div>
        <div class="sub"><a href='/scoreboard' style='color:var(--fg-dim)'>per-corpus aggregate →</a></div>
      </div>
    </div>

    <h3>corpora <span class='muted' style='text-transform:none;letter-spacing:0;font-weight:400'>· {n_total} from disk · {n_with_reps} with reps</span></h3>
    {corpora_html}
    """
    return Response(_html_page("dashboard", body), mimetype="text/html")


@app.route("/scoreboard")
def scoreboard() -> Response:
    if not os.path.isfile(SCOREBOARD_PY):
        body = "<p class='text-danger'>scoreboard.py not found</p>"
        return Response(_html_page("scoreboard", body), mimetype="text/html")
    try:
        proc = subprocess.run(
            [sys.executable, SCOREBOARD_PY],
            cwd=ROOT,
            capture_output=True, text=True, timeout=30,
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
    except subprocess.TimeoutExpired:
        out, err = "", "(timed out after 30s)"
    # subprocess stdout includes reps.jsonl-derived strings (project_id,
    # proposer.kind) — escape before <pre> to prevent injected `<script>`
    body = (
        f"<h3>scoreboard.py output</h3>"
        f"<pre>{html.escape(out)}</pre>"
        + (f"<h5 class='text-danger'>stderr</h5><pre>{html.escape(err)}</pre>" if err.strip() else "")
    )
    return Response(_html_page("scoreboard", body), mimetype="text/html")


@app.route("/reps")
def reps() -> Response:
    rows = _tail_reps(20)
    if not rows:
        body = "<p class='muted'>reps.jsonl is empty or missing</p>"
        return Response(_html_page("reps", body), mimetype="text/html")
    # Compact table: rep_id, corpus, proposer, recall, precision
    table_rows = []
    for r in rows:
        rid = (r.get("rep_id") or "")[:8] or "—"
        contract = r.get("contract", {})
        corpus = contract.get("project_id") or os.path.basename(
            (contract.get("path") or "?").rstrip("/")
        )
        proposer = (r.get("proposer", {}) or {}).get("kind", "?")
        sc = r.get("score", {}) or {}
        rec = sc.get("recall")
        prec = sc.get("precision")
        rec_s = f"{rec:.2f}" if isinstance(rec, (int, float)) else "—"
        prec_s = f"{prec:.2f}" if isinstance(prec, (int, float)) else "—"
        n_leads = len(r.get("leads") or [])
        table_rows.append(
            "<tr>"
            f"<td><code class='muted'>{rid}</code></td>"
            f"<td><code>{corpus}</code></td>"
            f"<td><span class='muted'>{proposer}</span></td>"
            f"<td>{rec_s}</td>"
            f"<td>{prec_s}</td>"
            f"<td><span class='muted'>{n_leads}</span></td>"
            "</tr>"
        )
    body = (
        f"<h3>reps · last {len(rows)} of {_rep_count()}</h3>"
        "<table>"
        "<thead><tr><th>rep</th><th>corpus</th><th>proposer</th>"
        "<th>recall</th><th>precision</th><th>leads</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
        "<p class='muted' style='margin-top:1.2rem;font-size:0.78rem'>"
        f"raw jsonl: <code>{os.path.relpath(REPS_PATH, ROOT)}</code>"
        "</p>"
    )
    return Response(_html_page("reps", body), mimetype="text/html")


@app.route("/fitness")
def fitness() -> Response:
    if os.path.isfile(FITNESS_PNG):
        return send_file(FITNESS_PNG, mimetype="image/png")
    body = (
        "<p class='text-muted'>docs/fitness.png not present. "
        "Generate with <code>python3 tools/fitness_card.py</code>.</p>"
    )
    return Response(_html_page("fitness", body), mimetype="text/html")


@app.route("/verification")
def verification() -> Response:
    """The legible money-shot: AI proposes a finding, a sound gate proves or rejects it."""
    intro = (
        "<p class='muted' style='max-width:64ch; margin:0.2rem 0 1.6rem; line-height:1.7;'>"
        "An AI agent <b>proposes</b> findings on a smart contract, then <b>routes</b> each to the "
        "formal verifier that can settle it — <code>halmos</code> (symbolic EVM), <code>z3</code>, "
        "or <code>lean</code>. Only a real tool subprocess can mark a finding "
        "<b>confirmed</b> or <b>cleared</b>; the agent has no verdict to give. "
        "A finding survives only with a replayable counterexample or a machine-checked proof. "
        "<b>The agent never grades its own homework.</b> Each card below is a real recorded run "
        "(reproduce with <code>plumbline audit &lt;dir&gt; --agent</code>)."
        "</p>"
    )
    # cached per-model runs (the switcher toggles these; the deployed page never calls an LLM).
    # states/ is gitignored, so a fresh clone has no runs there — fall back to deploy/audit-runs/
    # (which IS committed), deduping by slug so local runs win over the shipped samples.
    runs = []
    seen = set()
    for runs_dir in (os.path.join(ROOT, "states", "audit-runs"),
                     os.path.join(ROOT, "deploy", "audit-runs")):
        if not os.path.isdir(runs_dir):
            continue
        for fn in sorted(os.listdir(runs_dir)):
            if not fn.endswith(".json") or fn[:-5] in seen:
                continue
            try:
                d = json.loads(open(os.path.join(runs_dir, fn)).read())
                runs.append({"slug": fn[:-5],
                             "target": str(d.get("target_name", "?")),
                             "model": str((d.get("proposer") or {}).get("model", fn[:-5])),
                             "data": d})
                seen.add(fn[:-5])
            except Exception:
                pass
    projects = []
    for r in runs:
        if r["target"] not in projects:
            projects.append(r["target"])
    sel_proj = request.args.get("project")
    if sel_proj not in projects:
        sel_proj = ("synthetic-dreusd" if "synthetic-dreusd" in projects
                    else (projects[0] if projects else None))
    proj_runs = [r for r in runs if r["target"] == sel_proj]
    chosen = (next((r for r in proj_runs if r["slug"] == request.args.get("model")), None)
              or (proj_runs[0] if proj_runs else None))
    if chosen:
        data = chosen["data"]
    else:
        latest = os.path.join(ROOT, "states", "audit-latest.json")
        if not os.path.isfile(latest):
            body = intro + (
                "<div class='stat'><div class='label'>no run yet</div>"
                "<p class='muted'>Run <code>bin/plumbline audit examples/synthetic-dreusd --live</code>, "
                "then refresh.</p></div>"
            )
            return Response(_html_page("verification", body), mimetype="text/html")
        data = json.loads(open(latest).read())

    def _sel(name, options, selected):
        opts = "".join(f"<option value='{html.escape(str(v))}'{' selected' if v == selected else ''}>"
                       f"{html.escape(str(lab))}</option>" for v, lab in options)
        return (f"<span class='muted' style='font-size:0.8rem;'>{name}&nbsp;</span>"
                f"<select name='{name}' onchange='this.form.submit()' "
                "style='background:var(--bg-3);color:var(--accent);border:1px solid var(--bdr);"
                "border-radius:4px;padding:0.35rem 0.7rem;font-family:inherit;font-size:0.85rem;"
                "margin-right:1.1rem;'>" + opts + "</select>")

    switcher = ""
    if runs:
        switcher = (
            "<form method='get' style='margin:-0.3rem 0 1.5rem;'>"
            + _sel("project", [(p, p) for p in projects], sel_proj)
            + _sel("model", [(r["slug"], r["model"].split("/")[-1]
                              + (" · agent" if r["data"].get("command") == "agent-audit" else ""))
                             for r in proj_runs],
                   chosen["slug"] if chosen else "")
            + "<span class='muted-er' style='font-size:0.75rem;'>"
            "same gate · swap the contract or the model</span></form>")
    intro = intro + switcher
    res = data.get("results", [])
    prop = data.get("proposer")
    tgt = html.escape(str(data.get("target_name", "?")))
    nc, ncl = data.get("n_confirmed", 0), data.get("n_cleared", 0)

    def _vstyle(v):
        v = str(v)
        if v == "CONFIRMED":
            return "var(--red)", "✗ CONFIRMED — counterexample"
        if v.startswith("CLEARED"):
            return "var(--grn)", "✓ proved safe"
        if v.startswith("ESCALATED"):
            return "var(--yel)", "⊘ ESCALATED — human review"
        return "var(--fg-dim)", html.escape(v)

    # ---- agent-orchestration view (schema v3): the visible reasoning trace ----
    # claim (proposer) → route (proposer) → tool subprocess (real) → verdict (tool, gated)
    if data.get("schema_version") == 3:
        model = html.escape(str((data.get("proposer") or {}).get("model", "")).split("/")[-1])
        nconf3 = data.get("n_confirmed", 0)
        nesc3 = data.get("n_escalated", 0)
        fired = data.get("tools_fired", [])
        chips = " ".join(
            "<code class='muted' style='background:var(--bg-3);padding:0.15rem 0.5rem;"
            f"border-radius:4px;'>{html.escape(str(t))}</code>" for t in fired
        ) or "<span class='muted'>none</span>"
        summary = (
            "<div class='stat-grid'>"
            f"<div class='stat'><div class='label'>target · recorded agent run</div>"
            f"<div class='value' style='font-size:1.15rem'>{tgt}</div><div class='sub'>{model}</div></div>"
            f"<div class='stat'><div class='label'>confirmed (target-bound)</div>"
            f"<div class='value' style='color:var(--red)'>{nconf3}</div><div class='sub'>replayable witness</div></div>"
            f"<div class='stat'><div class='label'>escalated</div>"
            f"<div class='value' style='color:var(--yel)'>{nesc3}</div><div class='sub'>to human review</div></div>"
            "</div>"
            f"<p class='muted' style='font-size:0.82rem;margin:0.2rem 0 0.5rem;'>"
            f"tools the agent actually invoked this run: {chips}</p>"
            f"<p class='muted-er' style='font-size:0.78rem;margin:0 0 1.4rem;line-height:1.6;"
            f"border-left:2px solid var(--bdr);padding-left:0.7rem;'>"
            f"<b>Recorded run.</b> The proposer and router are stochastic — <i>which</i> findings "
            f"appear and <i>which</i> tool each routes to vary run-to-run. The gate is not: each "
            f"verdict below is a deterministic function of a real subprocess's <code>(stdout, "
            f"exit_code)</code>, and a CONFIRMED requires the witness to appear verbatim in stdout. "
            f"Re-run any printed <code>$ halmos&nbsp;…</code> line for the same counterexample, bit "
            f"for bit.</p>"
        )

        def _fmt_argv(argv):
            out = []
            for a in argv:
                a = str(a)
                out.append(os.path.basename(a) if a.startswith("/") else a)
            return " ".join(out)

        cards = []
        for f in data.get("findings", []):
            v = f.get("verification", {})
            color, tag = _vstyle(v.get("verdict"))
            sev = html.escape(str(f.get("severity", "?")))
            fn = html.escape(str(f.get("function", "?")))
            claim = html.escape(str(f.get("claim", "")))
            route = f.get("route", {})
            tool = html.escape(str(route.get("chosen_tool", "none")))
            rationale = html.escape(str(route.get("rationale", "")))
            bug = html.escape(str(f.get("bug_class", "")))
            bound = v.get("bound")
            # ROW 3 — the real tool subprocess(es): argv + captured stdout + provenance hash
            term = ""
            for s in v.get("steps", []):
                argv = html.escape(_fmt_argv(s.get("argv", [])))
                ex = html.escape(str(s.get("stdout_excerpt", "")).strip())
                ec, wall = s.get("exit_code"), s.get("wall_s")
                sha = html.escape(str(s.get("stdout_sha256", "")))
                term += (
                    "<div style='background:#0b0e14;border:1px solid var(--bdr);border-radius:6px;"
                    "padding:0.6rem 0.8rem;margin:0.55rem 0;font-family:ui-monospace,monospace;"
                    "font-size:0.78rem;overflow-x:auto;'>"
                    f"<div style='color:var(--accent);'>$ {argv}</div>"
                    f"<pre style='margin:0.4rem 0 0;white-space:pre-wrap;color:var(--fg-dim);'>{ex}</pre>"
                    f"<div class='muted-er' style='font-size:0.7rem;margin-top:0.4rem;'>"
                    f"exit {ec} · {wall}s · sha256:{sha}</div></div>"
                )
            if not v.get("steps"):
                term = ("<div class='muted' style='font-size:0.8rem;margin:0.55rem 0;font-style:italic;'>"
                        "no formal tool dispatched — the agent found no verifier that could soundly "
                        "settle this claim</div>")
            # ROW 4 — the verdict, with provenance (only a bound tool subprocess can CONFIRM/CLEAR)
            vsource = html.escape(str(v.get("verdict_source", "none")))
            boundtxt = ("bound to this target's bytecode" if bound
                        else "representative obligation — not target-bound" if v.get("steps")
                        else "—")
            note = (f"<div class='muted' style='font-size:0.78rem;margin-top:0.4rem;'>"
                    f"{html.escape(str(v.get('note')))}</div>" if v.get("note") else "")
            cards.append(
                f"<div class='stat' style='border-left:3px solid {color}; margin-bottom:1.3rem; "
                f"padding:1rem 1.1rem;'>"
                # claim
                f"<div><span class='pill' style='background:{color}'>{sev}</span> "
                f"<code style='font-size:0.95rem'>{fn}</code> "
                f"<span class='muted-er' style='font-size:0.7rem;'>· claim by proposer</span></div>"
                f"<div style='margin:0.55rem 0 0.85rem; line-height:1.55;'>{claim}</div>"
                # route
                f"<div style='font-size:0.83rem;margin:0.2rem 0;'>"
                f"<span class='muted'>agent routed&nbsp;→&nbsp;</span>"
                f"<code style='color:var(--accent)'>{tool}</code>"
                + (f"&nbsp;<code class='muted' style='font-size:0.78rem'>"
                   f"{html.escape(str(route.get('invariant')))}</code>" if route.get("invariant") else "")
                + (f" <code class='muted' style='font-size:0.72rem'>{bug}</code>" if bug else "")
                + (f"<div class='muted' style='font-size:0.78rem;margin-top:0.25rem;font-style:italic;'>"
                   f"“{rationale}”</div>" if rationale else "")
                + "</div>"
                # tool
                + term
                # verdict
                + f"<div style='margin-top:0.5rem;font-size:0.86rem;'>"
                f"<b style='color:{color}'>{tag}</b>"
                f"<span class='muted-er' style='font-size:0.72rem;'> &nbsp;· verdict source: "
                f"{vsource} · {boundtxt}</span></div>"
                + note
                + "</div>"
            )
        body = (intro + summary
                + "<h3>reasoning trace · claim → route → tool → verdict</h3>" + "".join(cards))
        return Response(_html_page("verification", body), mimetype="text/html")

    # live-proposer view (schema v2): real agent findings + independent gate verdicts
    if prop and prop.get("ok") and prop.get("findings"):
        model = html.escape(str(prop.get("model", "")).split("/")[-1])
        finds = prop["findings"]
        n_conf = sum(1 for f in finds if f.get("status") == "CONFIRMED")
        n_esc = sum(1 for f in finds if str(f.get("status", "")).startswith("ESCALATED"))
        summary = (
            "<div class='stat-grid'>"
            f"<div class='stat'><div class='label'>target · recorded run</div>"
            f"<div class='value' style='font-size:1.2rem'>{tgt}</div><div class='sub'>{model}</div></div>"
            f"<div class='stat'><div class='label'>confirmed exploits</div>"
            f"<div class='value' style='color:var(--red)'>{n_conf}</div><div class='sub'>replayable witness</div></div>"
            f"<div class='stat'><div class='label'>escalated</div>"
            f"<div class='value' style='color:var(--yel)'>{n_esc}</div><div class='sub'>no sound invariant → human</div></div>"
            "</div>"
        )
        fcards = []
        for f in finds:
            color, tag = _vstyle(f.get("status"))
            sev = html.escape(str(f.get("severity", "?")))
            fn = html.escape(str(f.get("function", "?")))
            desc = html.escape(str(f.get("desc", "")))
            inv = (f" &nbsp;<code class='muted'>{html.escape(str(f.get('invariant')))}</code>"
                   if f.get("invariant") else "")
            cex = f.get("counterexample")
            witness = (f"<div style='margin-top:0.5rem;'><span class='muted'>counterexample&nbsp;</span>"
                       f"<code style='color:{color}'>{html.escape(str(cex))}</code></div>") if cex else ""
            fcards.append(
                f"<div class='stat' style='border-left:3px solid {color}; margin-bottom:0.8rem;'>"
                f"<div><span class='pill' style='background:{color}'>{sev}</span> "
                f"<code style='font-size:0.95rem'>{fn}</code></div>"
                f"<div style='margin:0.55rem 0;'>{desc}</div>"
                f"<div class='muted' style='font-size:0.8rem;'>gate&nbsp;→&nbsp;"
                f"<b style='color:{color}'>{tag}</b>{inv}</div>{witness}</div>"
            )
        grows = []
        for r in res:
            color, _ = _vstyle(r.get("verdict"))
            v = ("✗ FAIL — counterexample" if r.get("verdict") == "CONFIRMED"
                 else "✓ PASS — proved safe" if str(r.get("verdict", "")).startswith("CLEARED")
                 else html.escape(str(r.get("verdict", "?"))))
            grows.append(f"<tr><td><code>{html.escape(str(r.get('invariant','')))}</code></td>"
                         f"<td style='color:{color}'>{v}</td></tr>")
        gate_tbl = ("<table><tr><th>invariant</th><th>halmos verdict (independent)</th></tr>"
                    + "".join(grows) + "</table>")
        body = (intro + summary
                + "<h3>agent findings · recorded LLM run</h3>" + "".join(fcards)
                + "<h3>gate · independent formal verdicts</h3>" + gate_tbl)
        return Response(_html_page("verification", body), mimetype="text/html")

    cards = []
    for r in res:
        confirmed = r.get("verdict") == "CONFIRMED"
        cleared = str(r.get("verdict", "")).startswith("CLEARED")
        color = "var(--red)" if confirmed else ("var(--grn)" if cleared else "var(--yel)")
        tag = ("✗ CONFIRMED EXPLOIT" if confirmed
               else "✓ CLEARED — proved safe" if cleared
               else "⧗ " + html.escape(str(r.get("verdict", "?"))))
        fn = html.escape(str(r.get("function", "?")))
        finding = html.escape(str(r.get("finding", "")))
        inv = html.escape(str(r.get("invariant", "")))
        sev = html.escape(str(r.get("severity", "?")))
        cex = r.get("counterexample")
        witness = (f"<div style='margin-top:0.6rem;'><span class='muted'>counterexample&nbsp;</span>"
                   f"<code style='color:{color}'>{html.escape(str(cex))}</code></div>") if cex else ""
        cards.append(
            f"<div class='stat' style='border-left:3px solid {color}; margin-bottom:1rem;'>"
            f"<div><span class='pill' style='background:{color}'>{sev}</span> "
            f"<code style='font-size:0.95rem'>{fn}</code></div>"
            f"<div style='margin:0.7rem 0 0.5rem; color:var(--fg);'>{finding}</div>"
            f"<div class='muted' style='font-size:0.8rem;'>gate&nbsp; <code>{inv}</code> &nbsp;→&nbsp; "
            f"<b style='color:{color}'>{tag}</b></div>"
            f"{witness}"
            "</div>"
        )

    summary = (
        f"<div class='stat-grid'>"
        f"<div class='stat'><div class='label'>target</div><div class='value' style='font-size:1.3rem'>{tgt}</div>"
        f"<div class='sub'>foundry project</div></div>"
        f"<div class='stat'><div class='label'>confirmed exploits</div>"
        f"<div class='value' style='color:var(--red)'>{nc}</div><div class='sub'>with replayable witness</div></div>"
        f"<div class='stat'><div class='label'>cleared</div>"
        f"<div class='value' style='color:var(--grn)'>{ncl}</div><div class='sub'>proved safe, not guessed</div></div>"
        f"</div>"
    )
    body = intro + summary + "<h3>findings · proposed → gated</h3>" + "".join(cards)
    return Response(_html_page("verification", body), mimetype="text/html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
