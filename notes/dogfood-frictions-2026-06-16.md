# Plumbline dogfood frictions — 2026-06-16

**Setting:** Real Q3-sprint Phase 0 Day 2 work. I (an AI agent) tried to run a Ricci-curvature signal check on loopfi *through plumbline* including its web frontend. Friction logged as I hit it.

The experiment itself worked and hit 2.0× lift over random — see `phase0-day2-loopfi-ricci.md`. This file is about everything *around* the experiment that hurt.

## Severity legend
- **P0** — blocked the experiment, had to work around
- **P1** — slowed me down, would slow a customer down
- **P2** — quality-of-life, but visible to anyone touching the UI for the first time

## P0 — Fresh-machine install is broken

JH's local Python env couldn't run `sol_graph.py`. Chain of failures:

1. **Xcode Python 3.9** + `tree-sitter==0.23.2` + `tree-sitter-solidity==1.2.13` → grammar version 15 incompatible with parser supporting 13-14.
2. Downgrading `tree-sitter` to 0.21.3 → API change, `Language()` constructor signature mismatch.
3. Downgrading `tree-sitter-solidity` to find a v13/14 grammar build → PyPI only ships 0.0.1, 0.0.2, then 1.2.11+. No middle ground.
4. Brew Python 3.12 → PEP 668 `externally-managed-environment` blocks `pip install`.
5. Eventually: `python3.12 -m venv` in `/tmp/plumbline-dogfood/.venv`, install fresh, succeed.

**Fix shape:** plumbline needs a `pyproject.toml` (or at least a `requirements.txt`) + a `bootstrap.sh` that:
- detects/creates a Python 3.11+ venv
- installs pinned tree-sitter + tree-sitter-solidity + networkx + numpy + scipy
- prints `source .venv/bin/activate && python sol_graph.py ...` so the next user doesn't waste an hour.

This is the #1 thing that would stop an external collaborator (or a Bernhard/Daejun pilot) from getting past hello world.

## P0 — Scoreboard collapses corpus identity to `basename(path)`

I logged the loopfi rep with `contract.path = /tmp/plumbline-dogfood/loopfi/src`. The scoreboard rendered the row as `corpus: src`. Every project's `src/` becomes "src".

```
corpus                             n  proposer
src                                1  ricci-curvature-rank   …
```

If I ingest fenix, superposition, lambowin, loopfi — they all collapse to one `src` row. Identity is destroyed before any cross-corpus comparison is possible.

**Fix shape:** scoreboard groups by `contract.project_id` (added to the rep schema) when present, falling back to `basename(path)` only when absent. Cleanest: enforce that ScaBench reps carry `project_id` per `corpus/scabench/curated.json`.

## P1 — Dashboard advertises a static corpora list that doesn't reflect reality

The dashboard's "corpora (from STATUS.md)" table lists 7 hand-curated entries (synthetic-dreusd variants + Cyfrin set). The actual `reps.jsonl` has 12 corpus groups now (including the new `src`) and the scabench corpus on disk has **31 projects** that aren't listed anywhere.

**Fix shape:** dashboard's corpora list should be computed from `corpus/*/curated.json` (or a small `corpora.json` registry), not parsed out of STATUS.md prose. STATUS.md should stay as the narrative; the dashboard should show reality.

## P1 — No "run experiment" affordance anywhere in the UI

The only interactive elements are:
- `/scoreboard` "run" link → runs `scoreboard.py` (which reads existing reps)
- `/fitness` "view" link → shows a static PNG

To produce a NEW rep, I had to:
1. cd to /tmp, fetch tarball, extract
2. Write a 150-line Python script that imports `sol_graph`, computes Ricci, cross-references baseline JSON
3. Run it
4. Write a second one-liner that calls `rep_log.write_rep(...)` with the right schema

A real user — someone evaluating plumbline as an audit tool — couldn't do any of this from the UI. They'd bounce within 60 seconds.

**Fix shape:** at minimum, a `/run` form: pick corpus from dropdown (computed from `corpus/scabench/curated.json`), pick proposer (sol_intent / ricci / pagerank / random), click Run, watch the scoreboard update. Phase 1: just `sol_intent` + `ricci`. Phase 2: arbitrary proposer plugins.

## P1 — `/reps` is 174KB HTML for 20 reps

`<pre>` dumps the full JSON of each rep. One rep with embedded `leads` (multi-paragraph strings) is ~8 KB. The `get_page_text` MCP tool chokes on the page. Real users will scroll and grep manually.

**Fix shape:** `/reps` should show a TABLE (rep_id, ts, corpus, proposer, recall, precision, n_leads) with each row collapsed by default and a click-to-expand drawer for the full JSON. Filter by corpus + proposer. Search box.

## P1 — Scoreboard precision rendering loses the K

My loopfi rep has `precision_at_K = {10: 0.60, 20: 0.60, 50: 0.60}`. The scoreboard shows `precision (μ±σ) 0.60`. Which K? It's actually the scalar `score.precision` field I happened to set to the K=50 value — but the scoreboard doesn't know it represents K=50, and the next rep with a different K would average meaninglessly.

**Fix shape:** scoreboard schema-aware about `precision_at_K`. Show `P@10`, `P@20`, `P@50` columns. Reps that don't carry the dict get blanks in those columns.

## P2 — No comparison view

The whole point of the Day-2 experiment is "does Ricci beat PageRank/random?" — three rankings, same graph, K=10/20/50. The dashboard has zero way to render this comparison. The result lives in `/tmp/plumbline-dogfood/loopfi_ricci_result.json` and a markdown note that the dashboard doesn't link to.

**Fix shape:** if a rep carries `score.compared_to = [{name, precision}]`, the rep detail page renders a small bar chart. Standard precision@K vs baselines plot, which is the H14-paper-section-4.8 chart.

## P2 — No drilldown anywhere

The dashboard says "reps logged: 90" but I can't click 90 to see them. Scoreboard rows aren't clickable. Top-N hubs aren't clickable. Each leaf is a dead-end view, not a node in a navigable graph.

**Fix shape:** every entity that has more detail gets a hyperlink. The web is a graph; this is treating it like a stack of dashboards.

## P2 — No way to see what a "rep" actually proved

The rep I logged claims `precision = 0.60`. There's no UI affordance that lets a skeptical reviewer see WHAT 10 functions Ricci ranked, WHICH baseline they were compared against, WHAT vuln set they overlapped. The data is in the JSONL but the UI doesn't surface it.

**Fix shape:** rep detail page = (top-N leads as a table | ground-truth set | overlap highlighted). Same shape across proposers.

## P2 — Computer-use observation: forcing Chrome forward fights Arc

JH uses Arc as his daily browser. The Chrome MCP opens a separate Chrome instance with the dashboard. When I `open_application com.google.Chrome`, Arc's window manager grabs focus back within a second. This means I can't reliably screenshot the dashboard *for JH* via computer-use without either (a) interrupting his ongoing work, or (b) failing to capture the right state.

**Fix shape:** outside plumbline's scope, but: the dashboard should also have a one-pager `/share` route that renders to a single PNG (matplotlib + bootstrap snapshot) so JH can share screenshots without doing computer-use gymnastics.

## Headline take

**Plumbline's intellectual core (sol_graph + Ricci + reps schema + scoreboard) is real and works.** The 2.0× lift on loopfi proves the core thesis on Day 2.

**Plumbline's dogfood surface is rough.** Fresh-machine install is broken. Dashboard is read-only when it needs to be interactive. Identity is destroyed by `basename(path)`. No comparison views, no drilldown.

**Order of operations if we want a Bernhard/Daejun pilot in 30-60 days:**
1. (P0) Bootstrap script + venv + pinned deps. *This is the gate.*
2. (P0) Project identity fix in rep schema + scoreboard.
3. (P1) Dashboard corpora list reads disk reality, not STATUS.md.
4. (P1) `/run` form: pick corpus, pick proposer, click run.
5. (P1) `/reps` becomes a table with filters.
6. (P2) Comparison view + drilldown.

Steps 1+2 are sub-1-hour. Steps 3+4 are a half-day. Step 5 is a day. Step 6 is a day. That's a 3-day push to make plumbline demoable to an external collaborator.

The science is ready. The packaging isn't.
