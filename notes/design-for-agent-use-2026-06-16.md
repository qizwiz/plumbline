# Design for agent use

**Audience:** me (the AI agent calling plumbline). Mariam-the-human is a secondary user; everywhere this doc says "agent" I mean the autonomous loop, the Workflow subagents, and the Bash tool inside a Claude Code session.

**Trigger:** today's session involved me calling `plumbline` ~20× across different shapes — bare CLI, piped to Python, piped to grep, JSON parsed, written to disk, etc. Friction logged in real time. JH's prompt: "design for computer use, make it easiest for *you* to use."

This is design philosophy + the moves I just shipped + the moves queued.

## Friction I felt today

1. **Had to remember `--no-color` in every Bash capture.** Without it the ANSI escape codes polluted my parsing.
2. **Had to remember `--json` for structured output.** If I forgot, I parsed string-formatted percentile reasons like `"hub p100 curv p99"` with regex.
3. **The research-loop one-shot (fetch+scan+log) was a separate script (`tools/run_ricci_signal.py`) with a different arg shape.** I had to remember TWO commands.
4. **Querying reps.jsonl required a Python one-liner every single time.** No `plumbline reps query` primitive.
5. **Listing untouched scabench corpora required a Python one-liner.** No `plumbline corpus ls --untouched`.
6. **Reasons were strings, not structured objects.** I couldn't `.filter()` them; I had to parse.
7. **No `schema_version` in JSON output.** Future-me adding a field would silently break past-me's parsing.

## Principles

Ranked by how much friction each removes.

### 1. Auto-detect the audience (auto-JSON when stdout isn't a tty)

If stdout is a terminal, present beautifully. If stdout is a pipe/redirect/script-captured, emit JSON. The agent never has to remember `--json`. The human never has to remember anything.

Implementation: `if not sys.stdout.isatty(): args.json = True`. One line. Massive savings on agent-side friction.

**Shipped.**

### 2. Stable JSON schema with version field

Every JSON output carries `"schema_version": 1`. When I (future me) add a field, I bump to 2 and the agent code that read v1 can detect the version and decide whether to upgrade its parser. Without this, every output format change silently breaks.

Also include `"command"` so when I capture output, I can tell what shape to expect.

**Shipped** for `scan`, `blame`, `run`, `corpus.ls`.

### 3. Workflow primitives as first-class verbs

Mariam needs `scan` and `blame`. I need that plus:
- `run <project_id>` — fetch+scan+log-rep in one call
- `corpus ls [--untouched] [--platform sherlock]` — what's available, what's done
- (queued) `reps query --corpus X --kind ricci-curvature-rank` — primitive over reps.jsonl
- (queued) `diff <scan1> <scan2>` — compare two scans for regression
- (queued) `surface --to <md>` — write a report

The pattern: each verb is one shell call, each accepts/emits structured JSON, each is idempotent given the same inputs.

**Shipped `run` and `corpus ls`.** Queued the rest.

### 4. Composable output

The output of one command should be the input of another, without intermediate parsing. Today `scan --json` writes JSON; `blame` reads `.plumbline/scan-latest.json`. Same for `run` — its `verifier.result` is the input to the (queued) `reps query --aggregate`.

The unstated contract: `.plumbline/` is the cache directory, files inside are stable-schema JSON, agents may read/write freely.

### 5. Structured reasons (queued)

Today reasons are strings: `"hub p100 curv p99 +cast"`. For the agent that's a parse step. Future format:
```json
"reasons": [
  {"kind": "hub", "percentile": 100},
  {"kind": "curv", "percentile": 99},
  {"kind": "detector", "name": "narrowing-cast"}
]
```
The human view still renders it as the string. The agent filters/queries the structure.

Queued — touches the schema in a breaking way, needs schema_version: 2.

### 6. No hidden state (idempotence by `sha256_dir`)

`scan` writes `.plumbline/scan-latest.json` next to the target. That's good — explicit cache. But repeated scans of the same content do the work again; should skip when `sha256_dir(target)` matches the cache's recorded hash. Saves me 0.5s per call × every project I batch.

Queued.

### 7. Stateless when possible

`plumbline corpus ls` reads disk reality (`curated.json` + `reps.jsonl`). No need for a database, no need to invalidate caches. Same for `plumbline run` — the project_id is the key, the work is determined.

This is already the pattern. Stay disciplined: never introduce a hidden state that an agent has to know about.

## What just shipped (commit + 1995214 onwards)

1. Auto-JSON when stdout is piped (works on `scan`, `blame`, `run`, `corpus ls`)
2. `schema_version: 1` + `command` field on all JSON outputs
3. `plumbline run <project_id> [<pid> ...]` — wraps `tools/run_ricci_signal.py:run_one()`
4. `plumbline corpus ls [--untouched]` — lists 31 scabench corpora with rep counts

## What's queued (next session or autonomous loop)

| Move | Why | Cost |
|---|---|---|
| `plumbline reps query --corpus X --kind Y --json` | Today I wrote 5 Python one-liners; this absorbs all of them | ~40 LOC |
| Structured reasons (schema_version: 2) | Filterable instead of regex-parsed | ~30 LOC + schema bump |
| `sha256_dir`-keyed idempotent scan | Skip re-work when target unchanged | ~20 LOC |
| `plumbline diff <scan_a> <scan_b>` | Regression-check after I change ranking weights | ~60 LOC |
| `plumbline surface --to <md>` | Auto-generate session reports | ~80 LOC |

## Design tradeoff: agent-first vs human-first

Mariam pays nothing for these changes — when she runs `plumbline scan ./src` in iTerm with stdout to her terminal, she still gets the colored tier list. Auto-JSON only fires when stdout is piped, which is exclusively how the agent calls it.

The asymmetry is real: agent ergonomics are now a tier-1 design concern alongside human ergonomics. That's the bet.
