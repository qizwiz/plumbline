# Plumbline as a Society — architecture spec

**Date:** 2026-06-22
**Triggered by:** JH observation that the "loop runs without you as conductor" goal is structurally the same goal as "build a society of specialized members that compose into capability no single member has." Today's autonomous-loop primitives (3 scheduled tasks + workflow agents + external CLI calls) are the first-generation members.

## The structural argument

A single Claude session is bounded by:
- Context window (~1M tokens, but real working set smaller)
- Claude desktop process memory (~6-8 hr lifetime on JH's 16 GB Mac before swap-thrash forces restart — see `[[project_claude_desktop_memory_leak]]`)
- Single-perspective bias (Claude can't catch what Claude can't see)
- Sequential execution within turn (parallel only via Workflow tool's bounded fan-out)
- Permission scope (whatever the session's settings.json / Run-now state allows)
- No persistent identity across restarts (except via files + memory dir)

A SOCIETY of agents transcends every one of these:
- Each member carries one role's working set; society carries the union
- Members run on Codespaces / Modal / GitHub Actions / JH's Mac — no single-machine ceiling
- Members include non-Anthropic species (gemini, codex, qwen, ollama, halmos, slither, scorer_v2) — perspective diversity is structural
- Members work in parallel; coordinate via shared state (files, memory, commits, scheduled-task triggers)
- Each member has narrow permission scope (settings.json profiles per-role)
- Society's identity IS the file/memory/SKILL.md substrate — survives any single Claude restart

The current "Claude as conductor" pattern IS the bottleneck. Building society IS the path past it.

## Current state — mapped to society roles

| Existing | Role | Status |
|---|---|---|
| `plumbline-hourly-self-improve` (scheduled task) | Generalist | OVERLOADED — does everything; needs decomposition |
| `disk-pressure-watchdog` (scheduled task) | Health-monitor-Claude | Specialized ✓ |
| `nightly-priors-reindex` (scheduled task) | Librarian-Claude (partial) | Specialized to one task ✓ |
| Workflow agents (Workflow tool, transient) | Task force | Not persistent |
| External CLIs (gemini, codex, qwen, ollama, gh-copilot) | Outside species | Underused — only one query so far (w2jo8n8mh) |
| Halmos, scorer_v2, slither, foundry-fuzz | Verifier species | Well-integrated |
| `ranking_fitness_gate` primitive | Self-falsifier | Operational, but called by humans not loop |
| Me (this session, JH-conducted) | Conductor + everything-else | The bottleneck |

## Proposed society members (initial 6)

Each is a scheduled task with a narrow role + tightly-scoped settings.json permissions + clear coordination protocol.

### 1. auditor-Claude
- **Role**: scan new Solidity contracts (e.g. new scabench rows, new Sherlock contests), produce Sonnet-default audits, file findings as JSONs.
- **Fires**: every 2 hr, OR triggered by new contract appearing in `~/src/plumbline/corpus/incoming/`.
- **Outputs**: `runs/auditor/<project_id>/findings.json`.
- **Permissions**: Bash (audit-prep commands), Read (corpus), Write (runs/auditor/).
- **Cross-validation**: every output triggers reviewer-Claude.

### 2. paper-Claude
- **Role**: given new empirical results in `notes/`, draft/revise paper sections in `docs/arxiv/`.
- **Fires**: on git commit affecting `notes/PROPOSER_BET*` or `notes/H14*` or `notes/GATE*`.
- **Outputs**: `docs/arxiv/h14-empirical-paper-vN.md` updates.
- **Permissions**: Read (notes, runs), Write (docs/arxiv/), git commit.
- **Cross-validation**: every commit triggers reviewer-Claude.

### 3. gate-Claude
- **Role**: on any proposed change to `tools/scabench_rerank.py` or new ranker proposal in `tools/`, run `ranking_fitness_gate.py` and refuse-or-approve.
- **Fires**: on git diff in `tools/` matching ranker-related files.
- **Outputs**: gate verdict appended to `notes/gate-verdicts-log.md`.
- **Permissions**: Read (tools, runs/scabench-scores), Write (verdict log).
- **Cross-validation**: rejected proposals get explained; approved proposals get committed only after a second member confirms.

### 4. librarian-Claude
- **Role**: maintain memory hygiene (MEMORY.md index, RESOURCES.md catalog, cross-links). Prune stale entries, update freshness markers, run priors reindex weekly.
- **Fires**: daily 03:30 (current `nightly-priors-reindex` expanded).
- **Outputs**: memory/RESOURCES.md edits + priors reindex.
- **Permissions**: Read (all), Edit (memory/, RESOURCES.md), Bash (~/.priors/.venv/bin/python ingest.py).
- **Cross-validation**: edits committed only if a sanity-check passes (MEMORY.md still parses, no duplicate slugs, etc.).

### 5. reviewer-Claude
- **Role**: adversarial review of any new commit by any society member. Tries 3+ falsifications per claim. Posts review as comment in `notes/reviewer/<commit-sha>.md`.
- **Fires**: on every git commit to plumbline master.
- **Outputs**: review markdown in `notes/reviewer/`.
- **Permissions**: Read (all), Write (notes/reviewer/), PushNotification (if review surfaces a hard objection).
- **Cross-validation**: this IS the cross-validation layer. Plus: external-perspective-Claude periodically asks if reviewer-Claude is being too soft.

### 6. external-perspective-Claude
- **Role**: weekly, query gemini + codex + qwen + ollama with current state + recent commits. Aggregate divergent-view findings.
- **Fires**: weekly Sunday 02:00 CDT.
- **Outputs**: `notes/external-review-<date>.md`.
- **Permissions**: Bash (CLI invocations), Read (transcript chunks, recent notes), Write (external-review log).
- **Cross-validation**: synthesizer agent ensures external CLIs actually ran (raw_response_excerpt grounding per today's w2jo8n8mh design).

## Coordination protocol

Communication channels (passive, file-based):
- **Memory dir**: persistent semantic state; cross-linked via `[[slug]]`
- **RESOURCES.md**: living catalog; every new member registers here on creation
- **notes/**: outputs by member type (auditor/, reviewer/, external-review/, etc.)
- **plumbline git log**: timeline of society actions
- **`notes/society-log-YYYY-MM.md`**: chronological inbox of cross-member messages ("librarian-Claude noted MEMORY.md drift; please run consolidation")

Triggering protocol (active):
- Cron schedules (per-member)
- File-change triggers (auditor on new contracts; paper on new notes/ commits; reviewer on every git commit; gate on tools/ commits)
- Manual via "ask the society" — JH or me-as-conductor names a question; the right specialist picks it up

## Cloud member roadmap (post-MVP)

Move heavy work off JH's Mac (per `[[feedback_remote_first_for_heavy_work]]`):
- **Codespaces auditor**: runs Sonnet on full corpus weekly, posts results to GitHub
- **Modal workflow runner**: deep-research / proposer-bet / CA-audit-rule prototypes
- **GitHub Actions reviewer**: every PR gets reviewer-Claude verdict as PR comment

This is what unblocks "society runs even when JH's Mac is off."

## Membership for AI species (not just Anthropic)

Today's society is Claude-monoculture. External species available via CLI:
- `claude` (Anthropic) — multiple sub-species: Sonnet, Opus, Haiku, Fable
- `gemini` (Google)
- `codex` (OpenAI)
- `qwen` (Alibaba)
- `ollama` (any local model: llama3.2:3b for now, more available)
- `gh copilot` (GitHub)
- `llm` (Simon Willison's, multi-provider)

Each can be a member when their perspective is differential. Examples:
- **codex** as second-opinion auditor (different model = different bug-finding style)
- **gemini** as paper-reviewer (independent of Claude's writing habits)
- **qwen** as external sanity-check on novel claims
- **ollama-3b** as cheap continuous sanity-check (always-on, no API cost)

## Cross-validation discipline

EVERY member output gets reviewed before being treated as canonical:
- auditor-Claude finding → reviewer-Claude verifies → gate-Claude scores → committed only if passes
- paper-Claude draft section → reviewer-Claude critiques → external-perspective-Claude sanity-checks → revised
- librarian-Claude edit → another member (e.g. reviewer-Claude in this role) confirms no info lost

This bakes adversarial-verify-before-banking into the society structurally, not just as my standing rule.

## Memory + disk constraints (CRITICAL — added after JH flagged the omission)

The very constraints we discovered today MAKE society-on-JH's-Mac unworkable beyond a small membership. The naive "add 6 more scheduled tasks" path makes everything WORSE, not better.

**The honest accounting**:
- Each scheduled-task fire = a fresh Claude desktop session = +memory to the process tree
- The Claude desktop memory leak (~2.8 GB/hr per `[[project_claude_desktop_memory_leak]]`) IS PROPORTIONAL to session count
- More members firing more often → 39 GB ceiling hit faster (currently 6-8 hr; with 6 members firing 4x/day → maybe 3-4 hr)
- Disk: each session jsonl is ~50 KB. 6 members × 24 fires/day = 144 jsonls/day = 7 MB/day in `~/.claude/projects/<project>/` alone. Plus workflow transcripts in `/private/tmp/claude-501/` at 100-500 KB each. Plus member outputs in `runs/` and `notes/`. Steady-state ~50-200 MB/day on a constrained 16 GB / 250 GB Mac.

**Mitigation strategies (mandatory before building society)**:

1. **CLOUD-FIRST members, not local-first**. Reverse the priority from the original spec:
   - auditor-Claude, paper-Claude, gate-Claude, external-perspective-Claude → CLOUD (Codespaces / Modal / GitHub Actions)
   - Only local: librarian-Claude, disk-pressure-watchdog (which itself manages the constraint)
   - reviewer-Claude: per-commit, so can run as a GitHub Action triggered by pushes
   - This breaks the dependence on Claude desktop's process tree for the bulk of society work

2. **Session jsonl cleanup** as part of librarian-Claude's daily duties:
   - Old session jsonls (> 7 days) get gzipped and moved to `~/.priors/archive/jsonl/` for priors-RAG (already a pending task per `[[project_priors_jsonl_subsumption]]`)
   - Active session jsonls untouched
   - Net: keeps `~/.claude/projects/` flat-state rather than monotonically growing

3. **Workflow transcripts auto-delete** after a successful synthesis run:
   - `/private/tmp/claude-501/*/tasks/<id>.output` files >24 hr old get deleted
   - Workflow durability is in committed artifacts (per `[[workflow-outputs-in-repo-not-tmp]]`), transcripts are ephemeral
   - Disk-watchdog already cleans these; just need to ensure pattern holds

4. **Memory-aware fire scheduling**:
   - Disk-watchdog continuously checks Claude tree RSS (already wired post-2026-06-22)
   - If RSS > 25 GB, PAUSE non-critical members (paper-Claude, external-perspective-Claude) until next Claude restart
   - librarian-Claude periodically push-notifies JH: "Claude tree at <RSS> GB, X hours since last restart — recommend restart for society to continue firing"

5. **Stagger schedules** so peak member-overlap is minimized:
   - Current: all 3 active tasks fire near :20-:30 of each hour → memory spike
   - Future: spread fires across the hour with minimum 5-min gap between members → smoother memory profile

6. **Cap simultaneous workflow agents**:
   - Today's session ran 157 workflow agents total (wsbt086zx 106 + wnllzi6r0 14 + w9xfplwvz 9 + wk0lfc30t 28). Each agent = ~30-100 MB peak.
   - Society spec should EXPLICITLY budget agent counts. Member-fired workflows cap at 20 agents; conductor-fired (this session) can go higher but each turn checks memory first.

7. **Output dedup discipline**:
   - Members write to specialized paths (`runs/auditor/<pid>/...`) not generic `runs/`
   - Old runs auto-archive after N days
   - Audit findings dedupe by content hash, not re-saved

**The structural fix** (post-2026 hardware refresh): JH gets a 32+ GB RAM machine. Memory ceiling rises. All this mitigation overhead becomes unnecessary. Until then: cloud-first society + aggressive cleanup + memory-aware scheduling.

**The honest tension**: a society of N specialized members is only better than 1 generalist Claude if the per-member cost is LOWER than the conductor cost. On a constrained Mac, that math goes negative quickly. The right move may be to keep society membership SMALL on the local Mac (2-3 members + watchdog) and put the bulk of society in the cloud where memory is unbounded.

## Build order (incremental, post-MVP today)

**REVISED PRIORITY** (cloud-first, post the memory/disk constraint analysis above):

1. **Reviewer-Claude as a GitHub Action** (not local scheduled task) — fires on every push to main, posts review as PR comment / commit comment. ~2 hr. Memory cost: ZERO on JH's Mac (runs on GitHub's infra). Highest-leverage single addition + doesn't compound the local memory problem.
2. **External-perspective-Claude as a weekly Modal cron** — ~2 hr. Runs in cloud, posts results to git, no local memory cost.
3. **gate-Claude as a GitHub Action** triggered by `tools/*.py` changes — uses the existing `ranking_fitness_gate.py`. Modal alternative if PR-trigger isn't ideal.
4. **librarian-Claude** stays LOCAL (it manages local file state) but expanded scope: weekly memory consolidation + daily jsonl archive + priors reindex. Replaces current `nightly-priors-reindex`.
5. **auditor-Claude as Codespaces cron** — when a new scabench contest appears, auditor runs Sonnet audit on Codespaces, posts findings to plumbline as a PR. NO local fire required.
6. **Decompose `plumbline-hourly-self-improve`** LAST or NEVER. If reviewer + external + gate + librarian are all cloud or specialized-local, the local hourly generalist may not be needed anymore — society members handle their own triggers.

Net local-Mac membership after this build: librarian-Claude + disk-pressure-watchdog (= the meta-watchdog). Everything else cloud. Local memory pressure stays flat.

## Open questions

- **How do members handle disagreement?** Reviewer-Claude says "kill" but auditor-Claude says "ship" — who wins? Proposed: reviewer's veto is absolute on safety/correctness; on aesthetic disagreements, JH arbitrates.
- **Identity persistence**: when Claude desktop restarts mid-fire, does the member's identity survive? Today: yes via SKILL.md but no via in-flight session. Needs explicit "resume from checkpoint" pattern.
- **How does the society discover new members it needs?** Today: I propose them based on observed gaps. In a mature society: librarian-Claude proposes new members when it sees patterns of "this kind of work keeps getting done ad-hoc."
- **Permission scope per role**: each member should have minimal settings.json permissions. Today all members share one global settings.json. Future: per-role permission profiles.

## Connection to bigger arc

This isn't a new project — it's the natural endpoint of:
- Plumbline's flywheel (already a primitive society: proposer + critic + memory)
- The ranking_fitness_gate primitive (self-falsifier as society member)
- The H14 paper (society's output, written by paper-Claude rather than me directly in future)
- The CA-audit-rule build per `notes/CA_AUDIT_RULE_EVOLUTION_FEASIBILITY_2026-06-20.md` (society of audit-rule programs evolving under halmos fitness — recursively meta)
- JH's cross-project synthesis (`notes/UNIFIED_CORE_2026-06-19.md`) — unified Substrate abstraction across plumbline + lisp-ca + ski-soup + cf-library is the FORMAL definition of a society

Plumbline-as-society is the beachhead. The pattern transfers to every other JH project. The same library, the same primitives, the same coordination protocol.

## What this means for the immediate next move

Today JH should pick:
- (a) Ship the H14 paper at current state (Sonnet+H14=0.3496) — banks the empirical win
- (b) Build reviewer-Claude as the first specialized society member — highest-leverage single addition; replaces me-as-adversarial-verifier with a persistent member
- (c) Decompose hourly-loop into 3 specialized members — restructures current primitive into proper society
- (d) Wait for external-review workflow (w2jo8n8mh) to land — it'll inform whether the society framing is sound

My recommendation: **(d) → (b) → (a)** in sequence. The external review (in flight now) is checking whether my self-assessment of the bigger picture matches what outsiders see. Once that lands, (b) ships the highest-leverage society piece and frees me from being the only adversarial verifier. Then (a) is a clean ship.

Per `[[project_h14_ceiling_at_0_22]]`: the empirical win is already DONE. The society move converts that one-time win into the substrate that produces future wins without me as bottleneck.
