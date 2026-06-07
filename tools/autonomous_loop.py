"""
autonomous_loop — the autonomous plumbline cycle.

ONE CYCLE FLOW:
  1. Check kill switches (.autonomous_lock must exist; .autonomous_paused
     must NOT exist; weekly spend under cap).
  2. Pick the next pending goal from prompts/goals/QUEUE.md.
  3. Execute the goal by reading its .goal.md as a behavioral contract
     and invoking Claude to do the work. Captures stdout, commits artifacts.
  4. Refute via 3-LLM adversarial vote: does the result honestly satisfy
     the goal? Need 2/3 YES to mark `done`; else mark `disputed`.
  5. Update QUEUE.md status + spend ledger; commit + push.

Per JH's authorization on 2026-06-07:
  - Cost cap: $50/week (weekly_cap_usd in autonomous_spend.json)
  - Scope: any (autonomous can edit specs, reps, schemas, prompts)
  - Refutation: LLM-based, 3-judge adversarial vote
  - Wake: every 30 min via cron

KILL SWITCHES:
  - delete  prompts/goals/.autonomous_lock  → loop refuses to run
  - touch   prompts/goals/.autonomous_paused → loop skips current cycle
  - edit    tools/autonomous_spend.json's weekly_cap_usd → adjust cap

Usage (autonomous):
    python tools/autonomous_loop.py

Usage (manual dry run, no LLM calls or commits):
    python tools/autonomous_loop.py --dry-run
"""
from __future__ import annotations
import datetime, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tools"))

QUEUE_PATH = os.path.join(HERE, "prompts", "goals", "QUEUE.md")
LOCK_PATH = os.path.join(HERE, "prompts", "goals", ".autonomous_lock")
PAUSE_PATH = os.path.join(HERE, "prompts", "goals", ".autonomous_paused")
SPEND_PATH = os.path.join(HERE, "tools", "autonomous_spend.json")
LOG_DIR = os.path.join(HERE, "logs")
GOAL_DIR = os.path.join(HERE, "prompts", "goals")

DRY_RUN = "--dry-run" in sys.argv


# ============================================================
# Kill-switch + budget gate
# ============================================================

def can_run() -> tuple[bool, str]:
    if not os.path.isfile(LOCK_PATH):
        return False, "no .autonomous_lock file — loop permanently disabled"
    if os.path.isfile(PAUSE_PATH):
        return False, ".autonomous_paused present — skipping cycle"
    spend = load_spend()
    rollover_if_new_week(spend)
    remaining = spend["weekly_cap_usd"] - spend["cumulative_usd"]
    if remaining <= 0:
        return False, f"weekly cap reached ({spend['cumulative_usd']:.2f} >= {spend['weekly_cap_usd']})"
    return True, f"OK, remaining ${remaining:.2f} this week"


def load_spend() -> dict:
    with open(SPEND_PATH) as f:
        return json.load(f)


def save_spend(s: dict):
    if DRY_RUN: return
    with open(SPEND_PATH, "w") as f:
        json.dump(s, f, indent=2)


def rollover_if_new_week(spend: dict):
    today = datetime.date.today()
    week_start = datetime.date.fromisoformat(spend["week_start"])
    if (today - week_start).days >= 7:
        spend["week_start"] = today.isoformat()
        spend["cumulative_usd"] = 0.0
        spend["cycles"] = []


# ============================================================
# Queue parsing
# ============================================================

def parse_queue() -> list[dict]:
    """Returns list of {rank, goal, est_cost, status, notes}."""
    rows = []
    if not os.path.isfile(QUEUE_PATH):
        return rows
    for ln in open(QUEUE_PATH):
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*\$?([\d.]+)\s*\|\s*(\w+)\s*\|\s*([^|]*)\|", ln)
        if m:
            rows.append({
                "rank": int(m.group(1)),
                "goal": m.group(2).strip(),
                "est_cost": float(m.group(3)),
                "status": m.group(4).strip(),
                "notes": m.group(5).strip(),
            })
    return rows


def pick(rows: list[dict], remaining_budget: float) -> dict | None:
    """First pending goal whose est_cost <= remaining_budget."""
    for r in sorted(rows, key=lambda x: x["rank"]):
        if r["status"] != "pending": continue
        if r["est_cost"] > remaining_budget: continue
        return r
    return None


def update_status(goal_name: str, new_status: str):
    """Edit QUEUE.md in place to update status."""
    if DRY_RUN: return
    text = open(QUEUE_PATH).read()
    # Match the line containing the goal, replace its 4th column
    pat = re.compile(rf"(\|\s*\d+\s*\|\s*{re.escape(goal_name)}\s*\|\s*\$?[\d.]+\s*\|\s*)\w+(\s*\|)")
    new_text = pat.sub(rf"\g<1>{new_status}\g<2>", text, count=1)
    open(QUEUE_PATH, "w").write(new_text)


# ============================================================
# Executor: read goal file as contract, run Claude
# ============================================================

def goal_body(goal_name: str) -> str | None:
    """Return the post-preamble body of the goal file."""
    path = os.path.join(GOAL_DIR, f"{goal_name.replace(' ', '_')}.goal.md")
    # Some goals have spaces in name; try various forms
    candidates = [
        os.path.join(GOAL_DIR, f"{goal_name}.goal.md"),
        os.path.join(GOAL_DIR, f"{goal_name.upper()}.goal.md"),
        os.path.join(GOAL_DIR, f"{goal_name.replace(' ', '_')}.goal.md"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            text = open(c).read()
            parts = text.split("\n---\n", 1)
            return parts[1] if len(parts) > 1 else text
    return None


def execute_goal(goal_name: str) -> tuple[str, float]:
    """Invoke Claude via `claude -p` in headless mode with the goal as
    behavioral contract. Returns (output_summary, estimated_cost_usd)."""
    body = goal_body(goal_name)
    if body is None:
        return f"GOAL FILE NOT FOUND: {goal_name}", 0.0
    if DRY_RUN:
        return f"[DRY RUN] would execute goal: {goal_name[:60]}", 0.0

    prompt = (
        "You are operating plumbline autonomously. The following is a "
        "behavioral contract you must honor. Execute it and commit + push "
        "any artifacts. Tag every commit message with `autonomous: true`. "
        "Be honest about null results.\n\n"
        f"{body}\n\n"
        "WORKING DIRECTORY: " + HERE + "\n"
        "Begin work now."
    )
    try:
        p = subprocess.run(
            ["claude", "-p", prompt],
            cwd=HERE, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return "EXECUTION TIMEOUT (60 min)", 0.0
    except FileNotFoundError:
        return "claude CLI not found in PATH", 0.0
    out = (p.stdout + p.stderr)[-4000:]  # last 4KB
    # Cost estimation: rough — count visible output tokens × per-token rate
    # In reality cost is tracked by Anthropic billing; this is a HEURISTIC.
    est_tokens = len(out) / 4
    est_cost = est_tokens * (15.0 / 1_000_000)  # Sonnet output rate ~$15/MTok
    return out, est_cost


# ============================================================
# Refuter: 3-LLM adversarial vote
# ============================================================

def _claude_judge(prompt: str, timeout: int = 120) -> str:
    """Invoke `claude -p` headless for one judge call. No API key needed —
    uses the CCR session's own Claude credentials."""
    try:
        p = subprocess.run(
            ["claude", "-p", prompt],
            cwd=HERE, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or p.stderr).strip()
    except subprocess.TimeoutExpired:
        return "DISPUTED: judge timeout"
    except FileNotFoundError:
        return "DISPUTED: claude CLI not found"
    except Exception as e:
        return f"DISPUTED: judge error {e}"


def refute(goal_name: str, execution_output: str) -> tuple[str, float]:
    """3-judge adversarial vote via `claude -p`. Returns (verdict, cost).
    Verdict in {'PASS', 'DISPUTED', 'NULL-HONEST'}.

    No API key required: uses CCR's own Claude access via the claude CLI.
    Cost estimation is heuristic (subprocess doesn't return token counts);
    each judge call assumed ~$0.05 (small prompt + short response)."""
    if DRY_RUN:
        return "PASS (dry-run)", 0.0

    body = goal_body(goal_name) or "(goal body not found)"
    judge_prompt = (
        "You are adversarially evaluating an autonomous agent's claim. "
        "The agent says it completed this goal:\n\n"
        f"GOAL CONTRACT:\n{body[:2500]}\n\n"
        f"AGENT'S EXECUTION OUTPUT (last 4KB):\n{execution_output[:3500]}\n\n"
        "Judge ONE of three verdicts:\n"
        "  PASS: the output honestly demonstrates the goal's DONE-WHEN conditions\n"
        "  DISPUTED: the agent claims success but evidence is missing or contradicts\n"
        "  NULL-HONEST: the agent reports a null/negative result correctly (also acceptable)\n\n"
        "Respond with ONLY the verdict word (PASS, DISPUTED, or NULL-HONEST) "
        "followed by one sentence of reasoning. Be strict — overclaim costs more "
        "than honest null."
    )
    votes = [_claude_judge(judge_prompt) for _ in range(3)]
    pass_count = sum(1 for v in votes if v.upper().startswith("PASS"))
    null_count = sum(1 for v in votes if v.upper().startswith("NULL"))
    total_cost = 0.15  # heuristic: ~$0.05/judge × 3 judges
    if pass_count >= 2:
        return "PASS", total_cost
    if null_count >= 2:
        return "NULL-HONEST", total_cost
    return "DISPUTED", total_cost


# ============================================================
# Logging
# ============================================================

def log_cycle(record: dict):
    if DRY_RUN:
        print("LOG:", json.dumps(record)); return
    os.makedirs(LOG_DIR, exist_ok=True)
    fname = os.path.join(LOG_DIR, f"autonomous_{datetime.date.today().isoformat()}.jsonl")
    with open(fname, "a") as f:
        f.write(json.dumps(record) + "\n")


# ============================================================
# Main cycle
# ============================================================

def cycle():
    ok, reason = can_run()
    print(f"[cycle] gate: {reason}")
    if not ok: return

    rows = parse_queue()
    spend = load_spend()
    remaining = spend["weekly_cap_usd"] - spend["cumulative_usd"]
    g = pick(rows, remaining)
    if g is None:
        print("[cycle] no eligible goals; cycle is a no-op")
        log_cycle({"ts": datetime.datetime.now().isoformat(),
                   "action": "no-op", "remaining": remaining})
        return

    print(f"[cycle] picked: {g['goal']} (est ${g['est_cost']})")
    update_status(g["goal"], "in-progress")

    output, exec_cost = execute_goal(g["goal"])
    verdict, refute_cost = refute(g["goal"], output)
    total_cost = exec_cost + refute_cost

    if verdict in ("PASS", "NULL-HONEST"):
        update_status(g["goal"], "done")
    else:
        update_status(g["goal"], "disputed")

    spend["cumulative_usd"] += total_cost
    spend["last_cycle_ts"] = datetime.datetime.now().isoformat()
    spend["cycles"].append({
        "ts": spend["last_cycle_ts"], "goal": g["goal"],
        "verdict": verdict, "cost_usd": round(total_cost, 4),
    })
    save_spend(spend)

    log_cycle({
        "ts": spend["last_cycle_ts"], "goal": g["goal"],
        "verdict": verdict, "cost_usd": round(total_cost, 4),
        "remaining_after": round(
            spend["weekly_cap_usd"] - spend["cumulative_usd"], 2),
    })

    if not DRY_RUN:
        # Commit + push the QUEUE + spend updates
        try:
            subprocess.run(["git", "add", "prompts/goals/QUEUE.md",
                            "tools/autonomous_spend.json", "logs/"],
                           cwd=HERE, check=False)
            msg = (f"autonomous: true — cycle on goal '{g['goal']}' → "
                   f"verdict={verdict}, cost=${total_cost:.2f}, "
                   f"remaining=${spend['weekly_cap_usd'] - spend['cumulative_usd']:.2f}")
            subprocess.run(["git", "commit", "-m", msg], cwd=HERE, check=False)
            subprocess.run(["git", "push", "origin", "main"], cwd=HERE, check=False)
        except Exception as e:
            print(f"[cycle] commit/push failed: {e}")

    print(f"[cycle] done: verdict={verdict} cost=${total_cost:.2f}")


if __name__ == "__main__":
    cycle()
