# Society Synthesis — Honest Verdict

## 1. Headline
**Cloud-society-escape is feasible TODAY at $0/mo for a single off-Mac reviewer; CA-shaped society is the right LONG-term ambition but is premature THIS WEEK — the blinded-replication debt from the 0.3496 correction outranks it.**

## 2. Free-tier total capacity (combined, actual)
- **Compute**: GH Actions unlimited on public repos + 2000 min/mo private + Modal $30 credit (~228 vCPU-hr) + Codespaces 120 core-hr/mo (3 already idle, all authed). Realistic ceiling: ~300 vCPU-hr/mo of bursty agent work, $0 cash.
- **Storage**: HF public datasets (effectively unlimited) + 100 GB HF private + 10 GB R2 (zero egress) + 10 GB B2 + GitHub Releases (2 GB/file public). ~120 GB hot+warm free, ~$0.25/mo for 50 GB cold.
- **LLM**: OpenRouter (Sonnet), OpenAI, Groq keys all live — no free tier but Groq's free dev tier covers ~70% of mutation traffic if routed there.
- **Already authed**: gh (admin:org+workflow), Modal (`~/.modal.toml`), OpenRouter (`plumbline/.env`), OpenAI, Groq. HF CLI installed but NOT logged in.

**Honest reading**: free tier comfortably hosts ~3 always-on bursty agents + ~50 vCPU-hr/mo verifier work. It does NOT comfortably host the 64-cell CA at the rate the design assumes once Sonnet mutation calls dominate ($23/mo LLM even with caching).

## 3. Pilot recommendation (next 1–2 hours)
**Do the reviewer-Claude pilot. Do NOT start the CA society.** Concretely:
1. `gh repo create qizwiz/society-reviewer --public --clone` (15 min)
2. Copy `plumbline/.github/workflows/autonomous.yml` → `reviewer.yml`, strip to manual+daily cron, target `qizwiz/rule30` (20 min)
3. Write `tools/reviewer.py` (~80 LoC, read-only, output-only, $5/wk budget cap) (30 min)
4. `gh secret set PACT_LLM_API_KEY` (reuse, don't mint) (2 min)
5. `gh workflow run reviewer.yml`, watch one run, verify `findings/2026-06-21.md` lands (15 min)

**Total**: ~90 min. Cost: $0 infra, ~$0.10 LLM. Outcome: off-Mac pattern proven end-to-end with structurally-read-only permissions — directly aligned with today's "don't auto-ship" lesson.

## 4. CA-society verdict
**Premature. Defer 2–4 weeks.** Honest reasons:
- The CA topology is **theater until A/B-beaten against an island model** — the design itself flags this as Risk 1. We have no evidence spatial locality recovers a rule class islands miss.
- The 0.3496 correction TODAY says: when external review hasn't converged, building more upstream machinery is the bias-amplifier move. CA-society is 7 cell types of upstream machinery.
- The "ship one improvement per turn" trap: CA-society is 7 improvements stacked, justified by a coherent story. That's exactly the architecture-astronaut shape JH's own memory warns against.
- **However**: the lisp-ca + ski-soup + plumbline arc IS real, the blinded-concordance circuit-breaker IS the right structural invariant, and the pilot lays the exact substrate (public repo + Actions + Modal + git-as-sync) the CA design needs. Don't kill the idea — sequence it.

## 5. Sequenced plan
1. **TODAY (90 min, $0)**: Reviewer-Claude pilot ships. Smoke test passes. Off-Mac proven.
2. **Days 2–7 (~30 min/day, ~$3 total)**: Read the daily findings. Grade signal-to-noise. If <30% useful after 7 days, kill the workflow — one-line disable.
3. **Week 2 (2 hr, $0)**: Add the **blinded-replication harness** as its OWN repo (`society-blinded`) — separate Modal token, held-out corpus, runs against frozen 0.3496-pipeline outputs. This is the actual external-review debt. Does NOT require CA.
4. **Week 3 (2 hr, $0)**: Add external-perspective-Claude as a second public-repo workflow reading society-reviewer findings + blinded results, weekly cron. Now graph is `rule30 → reviewer → external → JH`.
5. **Week 4 (3 hr, ~$15)**: Migrate librarian to public HF dataset; rclone `~/src` archives to B2. Reclaim 30–50 GB on Mac. Structural fix to swap-spiral root cause.
6. **Week 5 decision gate**: IF blinded-replication has converged AND reviewer pilot has produced ≥3 catches JH agrees with, THEN scope auditor-cells island-model v0 (NOT CA — island first). ELSE iterate on review quality.
7. **Week 8+**: Only if island-model A/B is won, add CA topology as the LATER experiment.

## 6. Risks + kills
- **R1 — Reviewer hallucinates confident garbage**. KILL: <30% useful findings after 7 days.
- **R2 — Off-Mac pattern leaks API key or burns budget**. KILL: any secret in logs, OR week-1 spend >$5.
- **R3 — CA enthusiasm bypasses blinded-replication debt**. KILL: catching myself proposing CA work before week-3 blinded harness ships.
- **R4 — Scope creep on pilot (auto-PR, auto-fix)**. KILL: any PR enriching pilot before v0 graph closes.
- **R5 — Modal/Actions queue drift makes daily cron unreliable**. KILL: <5 successful runs in week 1 → switch to manual `gh workflow run` only.
- **R6 — Mac scheduled-tasks contaminate the experiment**. KILL: any society-critical signal still depending on `~/.claude/scheduled-tasks/` after week 2.

**Bottom line**: ship the 90-minute pilot, build the blinded harness next, defer CA. The asymmetric bet is proving off-Mac works end-to-end at $0, not designing the cathedral.
