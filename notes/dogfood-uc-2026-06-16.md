# Plumbline-user-persona dogfood — 9 use cases, 2026-06-16

I AM the plumbline user. I ran 9 different things I'd actually want to do, and noted what hurt.

## What worked end-to-end

| UC | Task | Result | Time |
|---|---|---|---|
| 1 | Audit a fresh ScaBench project (blackhole) | 1.80× lift @ K=10 | 6s |
| 2 | Ricci vs PageRank bake-off on loopfi | PR wins K=10 (2.33×), Ricci wins K=50 (1.93×) | <1s |
| 3 | Corpus health: 5/31 ScaBench touched | mantra-dex top untouched (55 findings) | <1s |
| 4 | Drill into rep `4cb90287` | 6/10 leads confirmed against ground truth | <1s |
| 5 | Regression: PoolV3._updateBaseInterest still in top-10? | YES, at #4 (was #6) | 1s |
| 6 | Aggregate sniff via scoreboard | loopfi dropped 0.600→0.580 (within σ) | <1s |
| 7 | Pilot evaluator runs sol_graph on puppy-raffle | Found real `uint64` cast bug in `selectWinner` | 0.58s |
| 8 | Search reps for "reentrancy" mentions | 58 reps, dominated by sol_intent on Cyfrin | <1s |
| 9 | Proposer head-to-head on puppy-raffle | Couldn't — only sol_intent reps exist | n/a |

**8 of 9 produced real data. Use cases work.** Plumbline's actual capabilities are stronger than the surface suggests.

## What hurt — every single use case

Every single UC required me dropping to a CLI Python one-liner. Not one of the 9 could be done from the web frontend.

### The unified missing pattern: every UC is a query

UC2: "compute avg P@K across reps of corpus X, proposer P"
UC3: "list scabench projects sorted by findings, marked by rep count"
UC4: "show me rep R with leads cross-referenced against ground truth"
UC5: "is function F still in top-K of latest run on corpus C?"
UC6: "show me corpus-level precision delta between earliest and latest rep"
UC8: "find reps where leads contain text T"
UC9: "compare proposers P1 and P2 on corpus C, return precision/recall tables"

These are all queries over `reps.jsonl + curated.json + scoreboard aggregates`. **There is no query layer.** Each one is a fresh Python `json.load + filter + math`.

### The unified missing affordance: trigger an experiment

UC1, UC5, UC7, UC9 all needed me to RUN something to produce a new rep. I had two paths:
- `python tools/run_ricci_signal.py <project_id>` (for ricci)
- `python sol_graph.py <dir>` (for structural)

Neither is discoverable from the dashboard. A pilot evaluator would never find these.

## What should ship next — ranked by how often it would have helped today

1. **`/run` form (helps 4/9 UCs)** — pick corpus from dropdown (computed from real-corpora list), pick proposer, click Run, watch the scoreboard update. Wires up the only path to "I want a result on this thing."

2. **`/q` query interface (helps 5/9 UCs)** — a tiny declarative query layer over `reps.jsonl`. Think:
   ```
   GET /q?corpus=loopfi&proposer=ricci-curvature-rank
   GET /q?leads=reentran
   GET /q?rep_id=4cb90287
   ```
   Returns JSON or a small HTML table.

3. **Rep detail page (helps 2/9 UCs)** — `/rep/<rep_id>` shows: lead list, ground-truth overlay, score breakdown, and a "rerun this" button. Anchor for sanity-check workflows.

4. **Comparison view (helps 2/9 UCs)** — `/compare?corpus=puppy-raffle&proposers=sol_intent,ricci-curvature-rank` → side-by-side precision/recall + significance test (or at least sample sizes).

5. **"What's untouched" prompt (helps 1/9 UC, but it's the highest-value UC: planning the next experiment)** — a card on the dashboard: "5 of 31 ScaBench projects touched. Top 3 untouched by findings count: mantra-dex (55), virtuals-protocol (43), coded-estate (33). Click to start a ricci run."

Items 1-3 are ~1-1.5 hours of work each. Total ~4 hours to make plumbline a usable tool for the 9 use cases I just ran. The next dogfood loop would have basically zero CLI fall-throughs.

## What this says about the project

The intellectual core (sol_graph + Ricci + reps + scoreboard) is solid — it handled 8 of 9 use cases and produced real research data (UC2's "PR wins K=10, Ricci wins K=50" is a real finding worth ~2 paragraphs of paper).

The frontend lags way behind. It's a status display, not a tool. The 4-hour fix above turns it into a tool.

**Where I'd bet the next 4 hours:** UC1+UC5+UC7's needs are essentially the same — "run proposer P on target T, give me result + log a rep." That's the /run form. After that, /q gives me 5 more UCs for cheap. Two surgical pieces unlock everything.
