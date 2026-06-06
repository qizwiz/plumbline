#!/bin/bash
# Extracts just the goal body (post-preamble) for piping to /goal.
#
# Usage:
#   ./prompts/goals/load.sh CONTEST           # echo to stdout
#   ./prompts/goals/load.sh CONTEST | pbcopy  # copy to clipboard
#
# Then in Claude Code:
#   /goal <paste from clipboard>

set -e

name="$1"
if [ -z "$name" ]; then
  echo "usage: $0 <goal-name>"
  echo "available:"
  ls "$(dirname "$0")"/*.goal.md 2>/dev/null | xargs -n1 basename | sed 's/\.goal\.md$//' | sed 's/^/  /'
  exit 1
fi

file="$(dirname "$0")/${name}.goal.md"
if [ ! -f "$file" ]; then
  echo "no such goal: $name"
  echo "available:"
  ls "$(dirname "$0")"/*.goal.md 2>/dev/null | xargs -n1 basename | sed 's/\.goal\.md$//' | sed 's/^/  /'
  exit 1
fi

# Body is everything after the first --- line
awk '/^---$/{flag=1; next} flag' "$file"
