#!/usr/bin/env bash
# bootstrap.sh — one-shot fresh-machine setup for plumbline.
#
# Creates a .venv in the repo root using Python 3.11+, installs pinned deps,
# verifies sol_graph parses a single file, and prints the next-step command.
#
# Idempotent: safe to re-run.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# --- find a usable Python ----------------------------------------------------
PY=""
for cand in python3.13 python3.12 python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [[ -z "$PY" ]]; then
  echo "ERROR: need python3.11+ on PATH. tried python3.13, python3.12, python3.11." >&2
  echo "  install via 'brew install python@3.12' (macOS) or apt (linux)." >&2
  exit 1
fi
echo "[bootstrap] using $($PY --version) from $(command -v $PY)"

# --- venv --------------------------------------------------------------------
if [[ ! -d .venv ]]; then
  echo "[bootstrap] creating .venv"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- deps --------------------------------------------------------------------
echo "[bootstrap] installing requirements.txt (quiet)"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --- smoke test: sol_graph parses one .sol file ------------------------------
echo "[bootstrap] smoke test: sol_graph parses 1 contract"
python -c "
import sys
sys.path.insert(0, '.')
import tree_sitter_solidity as tss
from tree_sitter import Language, Parser
L = Language(tss.language())
p = Parser(L)
t = p.parse(b'contract Foo { function bar() public {} }')
assert t.root_node.type == 'source_file', f'unexpected root: {t.root_node.type}'
print('  tree-sitter solidity: OK')

import networkx as nx
G = nx.DiGraph(); G.add_edge('a','b')
pr = nx.pagerank(G)  # exercises numpy+scipy path
print('  networkx pagerank: OK (numpy+scipy reachable)')
"

# --- install symlink so `plumbline` works from anywhere ----------------------
LOCAL_BIN="$HOME/.local/bin"
LINK="$LOCAL_BIN/plumbline"
mkdir -p "$LOCAL_BIN"
if [[ -L "$LINK" || ! -e "$LINK" ]]; then
  ln -sf "$HERE/bin/plumbline" "$LINK"
  echo "[bootstrap] linked $LINK -> $HERE/bin/plumbline"
else
  echo "[bootstrap] $LINK already exists and isn't a symlink — skipping install"
fi

# --- print next step ---------------------------------------------------------
PATH_HINT=""
case ":$PATH:" in
  *":$LOCAL_BIN:"*) ;;
  *) PATH_HINT="
  Add $LOCAL_BIN to your PATH if it isn't already:
    export PATH=\"\$HOME/.local/bin:\$PATH\"
";;
esac

cat <<EOF

[bootstrap] done.
$PATH_HINT
Try it on a Solidity directory:
  plumbline scan ~/some-audit-target/src
  plumbline blame Contract.fn --dir ~/some-audit-target/src

Local research surfaces (optional):
  python tools/web.py                  # dashboard at http://127.0.0.1:5050
  python scoreboard.py                 # aggregate stats from reps.jsonl

EOF
