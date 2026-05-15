#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/rank_captures.sh <capture-prefix>" >&2
  exit 1
fi

prefix="$1"

echo "Capture ranking for $prefix"
echo "- Scores registered images, registration ratio, sparse points, reprojection error, and point distribution proxy."

if [[ "${SPLAT_RANK_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if ! command -v colmap >/dev/null 2>&1; then
  echo "COLMAP is required for ranking. Install it with: brew install colmap" >&2
  exit 1
fi

python3 scripts/rank_captures.py "$prefix"
