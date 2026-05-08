#!/usr/bin/env zsh
set -euo pipefail

required=(ffmpeg python3)
optional=(colmap splat-transform)

missing_required=()
missing_optional=()

for tool in "${required[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_required+=("$tool")
  fi
done

for tool in "${optional[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_optional+=("$tool")
  fi
done

if (( ${#missing_required[@]} > 0 )); then
  echo "Missing required tools: ${missing_required[*]}" >&2
  exit 1
fi

echo "Required tools found: ${required[*]}"

if (( ${#missing_optional[@]} > 0 )); then
  echo "Optional tools missing: ${missing_optional[*]}"
  if (( ${missing_optional[(Ie)colmap]} > 0 )); then
    echo "Install COLMAP for reconstruction: brew install colmap"
  fi
  if (( ${missing_optional[(Ie)splat-transform]} > 0 )); then
    echo "Install SOG conversion when available: npm install -g @playcanvas/splat-transform"
  fi
else
  echo "Optional tools found: ${optional[*]}"
fi
