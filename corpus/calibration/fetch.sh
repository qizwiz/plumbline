#!/usr/bin/env bash
# Re-clone the third-party calibration corpora from their canonical sources.
# They are intentionally NOT vendored here (no redistribution; ~1.6 GB). Run from
# anywhere:  corpus/calibration/fetch.sh   (the Sherlock fork needs `gh auth login`).
set -uo pipefail
cd "$(dirname "$0")"
clone() {  # path url commit
  local path="$1" url="$2" commit="$3"
  if [ -e "$path/.git" ]; then echo "✓ $path present"; return; fi
  echo "→ cloning $path"
  mkdir -p "$(dirname "$path")"
  if git clone --quiet "$url" "$path"; then
    git -C "$path" checkout --quiet "$commit" 2>/dev/null || echo "  (commit $commit not found — using default branch)"
  else
    echo "  ✗ clone failed: $url  (private? run: gh auth login)"
  fi
}
clone "2026-06-08-cantina-morpho-midnight/midnight" "https://github.com/morpho-org/midnight.git"                         "7538c438513622721e23a94676b93a335b83dace"
clone "2026-06-08-dre-labs-dreusd-source"           "https://github.com/sherlock-audit/2026-04-dre-labs-audits-qizwiz.git" "bc8dcd0b5deb7da5caaa7e632b31e13d2ed7cb5d"
echo "done."
