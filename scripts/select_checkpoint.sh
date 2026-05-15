#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/select_checkpoint.sh <ply-prefix-or-file>" >&2
  exit 1
fi

prefix="$1"

echo "Checkpoint selector for $prefix"
echo "- Scans finite PLY checkpoints and rejects NaN/Inf rows."

if [[ "${SPLAT_CHECKPOINT_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

python3 scripts/select_checkpoint.py "$prefix"
