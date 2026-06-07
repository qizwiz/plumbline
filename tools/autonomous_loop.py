"""
autonomous_loop — plumbline autonomous cycle (v2, API-direct).

REFACTORED 2026-06-07: ditched nested `claude -p` subprocess pattern
(which produced no real work — see weak_confirm-style honest write-up
in the prior 3 cycles). Now uses Anthropic SDK directly with tool-use,
matching the pattern of every other LLM-using tool in plumbline.

Reads ANTHROPIC_API_KEY from .env (local) or env (GitHub Actions secret).

ONE CYCLE FLOW:
  1. Gate check (lock exists, paused absent, budget remaining).
  2. Pick next pending goal from QUEUE.md whose est_cost ≤ remaining.
  3. Execute: API call with goal body + tool definitions (Read/Write/
     Edit/Bash). Multi-turn tool-use loop until model emits final text.
     Cost from response.usage (real, not heuristic).
  4. Refute: 3 API calls with judge prompt. 2/3 PASS → done. 2/3
     NULL → done. Else disputed.
  5. Update QUEUE + spend ledger + commit + push.

KILL SWITCHES:
  - delete  prompts/goals/.autonomous_lock  → permanent stop
  - touch   prompts/goals/.autonomous_paused → temporary pause
  - edit    autonomous_spend.json weekly_cap_usd → adjust cap

Usage (autonomous, in GH Actions):
    python tools/autonomous_loop.py

Usage (manual dry-run, no API calls or commits):
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

# Sonnet 4.5 pricing per Anthropic billing (input/output per MTok)
PRICE_INPUT_PER_MTOK = 3.0
PRICE_OUTPUT_PER_MTOK = 15.0


# ============================================================
# Anthropic SDK client (lazy)
# ============================================================

def _get_client_and_model():
    sys.path.insert(0, HERE)
    from llm import make_client, resolve_model
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
    return make_client(), resolve_model()


# ============================================================
# Kill-switch + budget gate
# ============================================================

def can_run() -> tuple[bool, str]:
    if not os.path.isfile(LOCK_PATH):
        return False, "no .autonomous_lock — loop permanently disabled"
    if os.path.isfile(PAUSE_PATH):
        return False, ".autonomous_paused present — skipping cycle"
    spend = load_spend()
    rollover_if_new_week(spend)
    remaining = spend["weekly_cap_usd"] - spend["cumulative_usd"]
    if remaining <= 0:
        return False, f"weekly cap reached (${spend['cumulative_usd']:.2f} >= ${spend['weekly_cap_usd']})"
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
    rows = []
    if not os.path.isfile(QUEUE_PATH):
        return rows
    for ln in open(QUEUE_PATH):
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*\$?([\d.]+)\s*\|\s*([\w-]+)\s*\|\s*([^|]*)\|", ln)
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
    for r in sorted(rows, key=lambda x: x["rank"]):
        if r["status"] != "pending": continue
        if r["est_cost"] > remaining_budget: continue
        return r
    return None


def update_status(goal_name: str, new_status: str):
    """Edit QUEUE.md in place to update status. Hyphen-aware regex."""
    if DRY_RUN: return
    text = open(QUEUE_PATH).read()
    # Match: | rank | goal | $cost | OLD_STATUS | ...
    pat = re.compile(
        rf"(\|\s*\d+\s*\|\s*{re.escape(goal_name)}\s*\|\s*\$?[\d.]+\s*\|\s*)[\w-]+(\s*\|)")
    new_text = pat.sub(rf"\g<1>{new_status}\g<2>", text, count=1)
    open(QUEUE_PATH, "w").write(new_text)


# ============================================================
# Goal file loading
# ============================================================

def goal_body(goal_name: str) -> str | None:
    """Return the post-preamble body of the goal file."""
    candidates = [
        os.path.join(GOAL_DIR, f"{goal_name}.goal.md"),
        os.path.join(GOAL_DIR, f"{goal_name.upper()}.goal.md"),
        os.path.join(GOAL_DIR, f"{goal_name.replace(' ', '_')}.goal.md"),
    ]
    # Also try mapping "CORPUS_GROWTH for S-3" → CORPUS_GROWTH.goal.md
    # since CORPUS_GROWTH is the goal template; S-3 selects the shape
    if goal_name.startswith("CORPUS_GROWTH"):
        candidates.append(os.path.join(GOAL_DIR, "CORPUS_GROWTH.goal.md"))
    for c in candidates:
        if os.path.isfile(c):
            text = open(c).read()
            parts = text.split("\n---\n", 1)
            return parts[1] if len(parts) > 1 else text
    return None


# ============================================================
# Executor with tool-use (Anthropic SDK direct)
# ============================================================

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file's contents. Path relative to repo root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write contents to a file (overwrites). Path relative to repo root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_bash",
        "description": "Run a bash command in the repo root. Returns stdout+stderr. Timeout 120s.",
        "input_schema": {
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files in a directory. Path relative to repo root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]


def _safe_path(path: str) -> str | None:
    """Confine to HERE. Return absolute path or None if escape attempt."""
    abs_p = os.path.abspath(os.path.join(HERE, path))
    if not abs_p.startswith(HERE):
        return None
    return abs_p


def _exec_tool(name: str, args: dict) -> str:
    if name == "read_file":
        p = _safe_path(args.get("path", ""))
        if not p: return "ERROR: path escapes repo"
        if not os.path.isfile(p): return f"ERROR: not a file: {args.get('path')}"
        try:
            return open(p).read()[:50000]
        except Exception as e:
            return f"ERROR: {e}"
    if name == "write_file":
        p = _safe_path(args.get("path", ""))
        if not p: return "ERROR: path escapes repo"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            open(p, "w").write(args.get("content", ""))
            return f"OK wrote {args.get('path')}"
        except Exception as e:
            return f"ERROR: {e}"
    if name == "list_dir":
        p = _safe_path(args.get("path", "."))
        if not p: return "ERROR: path escapes repo"
        if not os.path.isdir(p): return f"ERROR: not a dir: {args.get('path')}"
        return "\n".join(sorted(os.listdir(p))[:200])
    if name == "run_bash":
        cmd = args.get("cmd", "")
        # Refuse dangerous patterns
        if any(x in cmd for x in ["rm -rf /", "git push --force",
                                  ":(){:|:&};:", "dd if=", "mkfs"]):
            return "ERROR: refused dangerous command"
        try:
            p = subprocess.run(["bash", "-c", cmd], cwd=HERE,
                               capture_output=True, text=True, timeout=120)
            return (p.stdout + p.stderr)[:8000]
        except subprocess.TimeoutExpired:
            return "ERROR: bash timeout (120s)"
        except Exception as e:
            return f"ERROR: {e}"
    return f"ERROR: unknown tool {name}"


def execute_goal(goal_name: str) -> tuple[str, float]:
    """Use Anthropic SDK with tool-use to actually DO the goal.
    Returns (final_text, real_cost_usd computed from token usage)."""
    body = goal_body(goal_name)
    if body is None:
        return f"GOAL FILE NOT FOUND: {goal_name}", 0.0
    if DRY_RUN:
        return f"[DRY RUN] would execute: {goal_name[:60]}", 0.0

    client, model = _get_client_and_model()
    system = (
        "You are operating plumbline autonomously. The repo is checked out "
        "in the working directory. Follow the goal contract literally. "
        "Use the tools to read files, edit files, and run bash commands. "
        "When the goal's DONE-WHEN criteria are met, commit your work with "
        "`run_bash` (use git add, git commit, git push). Use the message "
        f"prefix 'autonomous: true' on your commit. If you cannot meet the "
        "criteria, respond honestly with a null result — DO NOT FAKE WORK."
    )
    user = f"GOAL CONTRACT:\n\n{body}\n\nBegin work."
    messages = [{"role": "user", "content": user}]

    total_in_tokens = 0
    total_out_tokens = 0
    max_turns = 25  # bound the tool-use loop
    final_text = ""

    for turn in range(max_turns):
        try:
            resp = client.messages.create(
                model=model, max_tokens=4000, system=system,
                tools=TOOLS, messages=messages)
        except Exception as e:
            return f"EXECUTOR API ERROR: {e}", _tokens_to_cost(
                total_in_tokens, total_out_tokens)
        total_in_tokens += resp.usage.input_tokens
        total_out_tokens += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            # Final response
            text_blocks = [b.text for b in resp.content
                           if getattr(b, "type", None) == "text"]
            final_text = "\n".join(text_blocks)
            break
        # Execute tools, add tool_result to next message
        tool_results = []
        for tu in tool_uses:
            result = _exec_tool(tu.name, dict(tu.input))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result[:8000],
            })
        messages.append({"role": "user", "content": tool_results})
        if resp.stop_reason == "end_turn":
            break

    cost = _tokens_to_cost(total_in_tokens, total_out_tokens)
    return final_text or "(no final text)", cost


def _tokens_to_cost(in_tokens: int, out_tokens: int) -> float:
    return (in_tokens * PRICE_INPUT_PER_MTOK / 1_000_000 +
            out_tokens * PRICE_OUTPUT_PER_MTOK / 1_000_000)


# ============================================================
# Refuter: 3-LLM adversarial vote via SDK
# ============================================================

def refute(goal_name: str, execution_output: str) -> tuple[str, float]:
    if DRY_RUN:
        return "PASS (dry-run)", 0.0

    body = goal_body(goal_name) or "(goal body not found)"
    judge_prompt = (
        "You are adversarially evaluating an autonomous agent's claim. "
        "The agent says it completed this goal:\n\n"
        f"GOAL CONTRACT:\n{body[:2500]}\n\n"
        f"AGENT'S EXECUTION OUTPUT:\n{execution_output[:3500]}\n\n"
        "Judge ONE verdict:\n"
        "  PASS: output honestly demonstrates the goal's DONE-WHEN conditions\n"
        "  DISPUTED: agent claims success but evidence is missing or contradicts\n"
        "  NULL-HONEST: agent reports a null/negative result correctly (acceptable)\n\n"
        "Respond with ONLY the verdict word followed by ONE sentence of reasoning. "
        "Be strict — overclaim costs more than honest null."
    )
    client, model = _get_client_and_model()
    votes = []
    total_cost = 0.0
    for _ in range(3):
        try:
            r = client.messages.create(
                model=model, max_tokens=200,
                messages=[{"role": "user", "content": judge_prompt}])
            text = r.content[0].text if r.content else ""
            votes.append(text.strip())
            total_cost += _tokens_to_cost(r.usage.input_tokens,
                                          r.usage.output_tokens)
        except Exception as e:
            votes.append(f"DISPUTED: judge call failed ({e})")
    pass_count = sum(1 for v in votes if v.upper().startswith("PASS"))
    null_count = sum(1 for v in votes if v.upper().startswith("NULL"))
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
    print(f"[cycle] executor cost: ${exec_cost:.3f}")
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
        "exec_cost_usd": round(exec_cost, 4),
        "refute_cost_usd": round(refute_cost, 4),
    })
    save_spend(spend)

    log_cycle({
        "ts": spend["last_cycle_ts"], "goal": g["goal"],
        "verdict": verdict, "cost_usd": round(total_cost, 4),
        "remaining_after": round(
            spend["weekly_cap_usd"] - spend["cumulative_usd"], 2),
    })

    if not DRY_RUN:
        try:
            subprocess.run(["git", "add", "-A"], cwd=HERE, check=False)
            msg = (f"autonomous: true — cycle on goal '{g['goal']}' → "
                   f"verdict={verdict}, cost=${total_cost:.3f}, "
                   f"remaining=${spend['weekly_cap_usd'] - spend['cumulative_usd']:.2f}")
            subprocess.run(["git", "commit", "-m", msg], cwd=HERE, check=False)
            subprocess.run(["git", "push", "origin", "main"], cwd=HERE, check=False)
        except Exception as e:
            print(f"[cycle] commit/push failed: {e}")

    print(f"[cycle] done: verdict={verdict} total_cost=${total_cost:.3f}")


if __name__ == "__main__":
    cycle()
