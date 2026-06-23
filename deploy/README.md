# plumbline — verification demo

A self-contained public demo of plumbline's `/verification` page: a live-LLM smart-contract
audit, gated by halmos, with a model switcher. **Serves pre-computed runs only** — no LLM
calls, no halmos, no keys at request time. Safe to deploy publicly.

## Run locally
    pip install -r requirements.txt && python app.py    # → http://localhost:8000

## Deploy (pick one — all free-tier)
- **Render**: New Web Service → connect repo → it auto-detects the Dockerfile. Done.
- **Fly.io**: `fly launch` (uses the Dockerfile) → `fly deploy`.
- **HF Spaces**: new Space (Docker SDK) → push these files.
- **Railway**: new project from repo → auto-builds the Dockerfile.

## Refresh the cache (local, needs OpenRouter key + foundry/halmos)
    plumbline audit examples/synthetic-dreusd --live --model openrouter/anthropic/claude-opus-4.8
    cp ../states/audit-runs/*.json audit-runs/
