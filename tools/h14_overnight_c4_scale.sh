#!/usr/bin/env bash
# h14_overnight_c4_scale.sh — overnight scale-up of the H14 second-premise
# test across all 85 c4 contests with answer keys on disk.
#
# Step 1: for each corpus/c4/<contest>/ dir that has .ANSWERS.md, clone
#         code-423n4/<contest> into /tmp/c4_repos/<contest>.
# Step 2: build a path table mapping contest_name → (source_dir, answers_md).
# Step 3: invoke a Python aggregator that runs h14_bug_geometry on each
#         and pools the per-function bug/clean labels for a single big
#         statistical test (Mann-Whitney + Bonferroni multiple-testing
#         correction across all features).
#
# Total wall-clock estimate: 30-60 min (network-bound on git clones),
# then 5-10 min compute. Completely unattended.

set -u

PLUMBLINE="/Users/jonathanhill/src/plumbline"
CACHE="/tmp/c4_repos"
LOG="/tmp/h14_overnight.log"

echo "=== h14 overnight scale-up started $(date) ===" | tee "$LOG"
mkdir -p "$CACHE"

cd "$PLUMBLINE"
CONTESTS=()
for d in corpus/c4/*/; do
  name=$(basename "$d")
  if [ -f "${d}/.ANSWERS.md" ]; then
    CONTESTS+=("$name")
  fi
done
echo "found ${#CONTESTS[@]} contests with .ANSWERS.md" | tee -a "$LOG"

# Step 1: clone in parallel batches of 5 to avoid rate limits
CLONED=0
FAILED=0
for name in "${CONTESTS[@]}"; do
  if [ -d "$CACHE/$name/.git" ]; then
    echo "  cached $name" | tee -a "$LOG"
    CLONED=$((CLONED+1))
    continue
  fi
  if gh repo clone "code-423n4/$name" "$CACHE/$name" -- --depth 1 >> "$LOG" 2>&1; then
    CLONED=$((CLONED+1))
    echo "  cloned $name" | tee -a "$LOG"
  else
    FAILED=$((FAILED+1))
    echo "  FAILED $name" | tee -a "$LOG"
  fi
done
echo "cloning done: $CLONED ok, $FAILED failed" | tee -a "$LOG"

# Step 2 + 3: invoke the Python aggregator
cd "$PLUMBLINE"
echo "=== running aggregator $(date) ===" | tee -a "$LOG"
python3 tools/h14_c4_aggregate.py >> "$LOG" 2>&1
echo "=== done $(date) ===" | tee -a "$LOG"
