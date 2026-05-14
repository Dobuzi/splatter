#!/usr/bin/env zsh
set -euo pipefail

repo_dir="${GSPLAT_MLX_DIR:-.local/gsplat-mlx}"
python_bin="${GSPLAT_MLX_PYTHON:-$repo_dir/.venv313/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  echo "gsplat-mlx Python not found: $python_bin" >&2
  echo "Install gsplat-mlx first or set GSPLAT_MLX_PYTHON." >&2
  exit 1
fi

"$python_bin" scripts/diagnose_mlx_gsplat.py --repo "$repo_dir" "$@"
