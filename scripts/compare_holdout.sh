#!/usr/bin/env zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "Usage: scripts/compare_holdout.sh <reference-image> <render-image> [metrics-json]" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffmpeg and ffprobe are required for holdout metrics." >&2
  exit 1
fi

python3 scripts/compare_holdout.py "$@"
