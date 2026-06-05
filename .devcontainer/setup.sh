#!/usr/bin/env bash
# Plumbline Codespace setup — runs inside the container, builds the loop env
# entirely in the cloud so local disk never thrashes again.
#
# Pre-reqs (set as Codespaces Secrets via GH UI, NOT committed):
#   PACT_LLM_API_KEY       OpenRouter or Anthropic key for sol_intent
#   PACT_LLM_BASE_URL      (optional) e.g. https://openrouter.ai/api
#   PACT_LLM_MODEL         (optional) model id override
#   HF_TOKEN               (optional) for pushing reps.jsonl as a dataset
set -uo pipefail

echo ">>> [1/4] Foundry (forge/cast/anvil)..."
curl -L https://foundry.paradigm.xyz | bash || true
export PATH="$HOME/.foundry/bin:$PATH"
"$HOME/.foundry/bin/foundryup" || foundryup || true

echo ">>> [2/4] Python venv + requirements..."
python -m venv .venv
./.venv/bin/pip -q install --upgrade pip
./.venv/bin/pip -q install -r requirements.txt fastembed numpy huggingface_hub

echo ">>> [3a/4] Foundry libs for halmos verifier (examples/synthetic-dreusd)..."
if [ -f examples/synthetic-dreusd/foundry.toml ]; then
  (cd examples/synthetic-dreusd && \
    forge install --no-commit foundry-rs/forge-std transmissions11/solmate 2>&1 | tail -5 || true)
fi

echo ">>> [3a'/4] Foundry libs for examples/puppy-raffle (solc 0.7.6)..."
if [ -f examples/puppy-raffle/foundry.toml ]; then
  (cd examples/puppy-raffle && \
    forge install --no-commit foundry-rs/forge-std \
      OpenZeppelin/openzeppelin-contracts@v3.4.2 \
      Brechtpd/base64 2>&1 | tail -5 || true)
fi

echo ">>> [3b/4] Verifying the rep loop turns..."
./.venv/bin/python first_rep.py || true
./.venv/bin/python scoreboard.py || true

echo ">>> [3c/4] Halmos sanity (synthetic-dreusd Properties.t.sol)..."
if [ -f examples/synthetic-dreusd/test/Properties.t.sol ]; then
  (cd examples/synthetic-dreusd && \
    ../../.venv/bin/halmos --function check --solver-timeout-assertion 60000 2>&1 | tail -20 || true)
fi

echo ">>> [4/4] Done. To run model reps:"
echo "    ./.venv/bin/python model_rep.py examples/synthetic-dreusd"
echo ""
echo "    Secrets must be set in GH: Settings > Codespaces > Repository secrets"
echo "      - PACT_LLM_API_KEY      (required for sol_intent)"
echo "      - HF_TOKEN              (optional, for dataset mirror)"
