#!/usr/bin/env zsh
set -euo pipefail

if (( $# != 1 )); then
  echo "Usage: scripts/mesh_validate.sh <input-ply>" >&2
  exit 1
fi

input_ply="$1"
sugar_dir="${SUGAR_REPO:-}"

echo "Surface validation for $input_ply"
echo "- Optional path: SuGaR surface-aligned Gaussian extraction."
echo "- Set SUGAR_REPO to a local SuGaR checkout to run project-specific mesh validation."

if [[ "${SPLAT_MESH_DRY_RUN:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -f "$input_ply" ]]; then
  echo "Input PLY not found: $input_ply" >&2
  exit 1
fi

if [[ -z "$sugar_dir" || ! -d "$sugar_dir" ]]; then
  echo "SUGAR_REPO is not set to a local SuGaR checkout." >&2
  exit 2
fi

echo "SuGaR integration is environment-specific."
echo "Use this PLY as the Gaussian source and compare extracted mesh holes against the viewer render:"
echo "  $input_ply"
