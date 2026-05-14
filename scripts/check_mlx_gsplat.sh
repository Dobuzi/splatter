#!/usr/bin/env zsh
set -euo pipefail

if (( $# > 2 )); then
  echo "Usage: scripts/check_mlx_gsplat.sh [steps] [gaussians]" >&2
  exit 1
fi

steps="${1:-10}"
gaussians="${2:-50}"
repo_dir="${GSPLAT_MLX_DIR:-.local/gsplat-mlx}"
python_bin="${GSPLAT_MLX_PYTHON:-$repo_dir/.venv313/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  echo "gsplat-mlx Python not found: $python_bin" >&2
  echo "Install gsplat-mlx first or set GSPLAT_MLX_PYTHON." >&2
  exit 1
fi

"$python_bin" - <<'PY'
import mlx.core as mx
from gsplat_mlx import rasterization
print(f"mlx device: {mx.default_device()}")
print(f"rasterization callable: {callable(rasterization)}")
PY

set +e
output=$("$python_bin" "$repo_dir/examples/simple_trainer.py" \
  --num-steps "$steps" \
  --num-gaussians "$gaussians" \
  --width 16 \
  --height 16 \
  --lr "${GSPLAT_MLX_LR:-1e-3}" 2>&1)
exit_code=$?
set -e

printf '%s\n' "$output"

if (( exit_code != 0 )); then
  echo "gsplat-mlx smoke failed with exit code $exit_code" >&2
  exit "$exit_code"
fi

if printf '%s\n' "$output" | grep -Eiq '(^|[^a-z])(nan|inf)([^a-z]|$)'; then
  echo "gsplat-mlx smoke produced non-finite loss; do not use as production trainer yet." >&2
  exit 2
fi

echo "gsplat-mlx smoke passed"
