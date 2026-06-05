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

# IMPORTANT: forge 1.7+ removed --no-commit. Earlier versions silently no-op'd
# the install when it was passed, leaving lib/ empty and halmos with nothing
# to compile. Use bare `forge install` (the new default is no-commit) and
# pin versions where needed.
#
# ALSO: `forge install` in a git subdir installs to the GIT ROOT's lib/, not
# the subdir's lib/. We symlink each examples/<name>/lib → /workspaces/.../lib
# so the relative `libs = ["lib"]` in each example's foundry.toml resolves.

echo ">>> [3a/4] Foundry libs (installed to repo-root lib/)..."
forge install foundry-rs/forge-std 2>&1 | tail -3 || true
forge install transmissions11/solmate 2>&1 | tail -3 || true
forge install OpenZeppelin/openzeppelin-contracts 2>&1 | tail -3 || true
forge install OpenZeppelin/openzeppelin-contracts@v3.4.2 2>&1 | tail -3 || true
forge install Brechtpd/base64 2>&1 | tail -3 || true

# Solmate's own internal tests pin solc =0.8.15. If they sit in the build
# graph, forge fails to compile (synthetic-dreusd uses solc 0.8.20). Library
# tests aren't needed for our verifier — remove them.
if [ -d lib/solmate/src/test ]; then
  rm -rf lib/solmate/src/test
fi

echo ">>> [3b/4] Symlinking lib/ into each example dir..."
for ex in examples/synthetic-dreusd examples/puppy-raffle examples/t-swap examples/boss-bridge; do
  if [ -f "$ex/foundry.toml" ] && [ ! -e "$ex/lib" ]; then
    ln -sf "$(pwd)/lib" "$ex/lib"
  fi
done

echo ">>> [3c/4] Verifying the rep loop turns..."
./.venv/bin/python first_rep.py || true
./.venv/bin/python scoreboard.py || true

echo ">>> [3d/4] Halmos sanity (synthetic-dreusd Properties.t.sol)..."
if [ -f examples/synthetic-dreusd/test/Properties.t.sol ]; then
  (cd examples/synthetic-dreusd && \
    ../../.venv/bin/halmos --function check --solver-timeout-assertion 60000 2>&1 | tail -20 || true)
fi

echo ">>> [4/4] Done."
echo ""
echo "  HONEST NOTE: as of 2026-06-05 the halmos scaffolds in examples/ are"
echo "  UNVERIFIED — written by reading the bug then writing a check_*. Several"
echo "  scaffolds return vacuous PASS because the buggy path reverts BEFORE the"
echo "  assertion runs. See CLAUDE.md 'Scaffold honesty' for the repair plan."
echo ""
echo "  Secrets must be set in GH: Settings > Codespaces > Repository secrets"
echo "    - PACT_LLM_API_KEY      (required for sol_intent)"
echo "    - HF_TOKEN              (optional, for dataset mirror)"
