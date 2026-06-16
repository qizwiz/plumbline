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

from flask import Flask, Response, abort, send_file

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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
