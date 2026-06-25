"""One-shot driver: generate a schema-v3 agent-audit run for (target, model).
Usage: .venv/bin/python tools/_gen_run.py <target_dir> <model_id>
Writes states/audit-runs/<slug>.json (orchestrate's normal output path)."""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import orchestrator

target, model = sys.argv[1], sys.argv[2]
t0 = time.time()
print(f"[gen] orchestrate({target}, {model}) …", flush=True)
payload = orchestrator.orchestrate(target, model)
dt = time.time() - t0
print(f"[gen] done in {dt:.1f}s — confirmed={payload['n_confirmed']} "
      f"escalated={payload.get('n_escalated')} cleared={payload.get('n_cleared')} "
      f"tools={payload['tools_fired']} n_findings={len(payload['findings'])}", flush=True)
for f in payload["findings"]:
    v = f["verification"]
    print(f"    [{f['severity']:4s}] {str(f['function'])[:30]:30s} "
          f"tool={f['route'].get('chosen_tool'):6s} inv={str(f['route'].get('invariant'))[:26]:26s} "
          f"-> {v['verdict']} (bound={v.get('bound')})", flush=True)
