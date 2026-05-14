#!/usr/bin/env zsh
set -euo pipefail

cli="bin/splatter"

if [[ ! -x "$cli" ]]; then
  echo "Missing executable CLI: $cli" >&2
  exit 1
fi

"$cli" --help | grep -q "splatter - local iPhone video"
"$cli" --help | grep -q "quality-report"
"$cli" --help | grep -q "compare-holdout"
"$cli" --help | grep -q "quality-stage"
"$cli" --help | grep -q "quality-sweep"
"$cli" --help | grep -q "select-frames"
"$cli" --help | grep -q "mlx-smoke"
"$cli" --help | grep -q "mlx-diagnose"
"$cli" --version | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+'
"$cli" validate >/dev/null

if "$cli" unknown >/dev/null 2>&1; then
  echo "Unknown command should fail" >&2
  exit 1
fi

if "$cli" publish >/dev/null 2>&1; then
  echo "Publish without required args should fail" >&2
  exit 1
fi

if "$cli" quality-report >/dev/null 2>&1; then
  echo "Quality report without required args should fail" >&2
  exit 1
fi

if "$cli" quality-stage >/dev/null 2>&1; then
  echo "Quality stage without required args should fail" >&2
  exit 1
fi

if "$cli" quality-sweep >/dev/null 2>&1; then
  echo "Quality sweep without required args should fail" >&2
  exit 1
fi

if "$cli" select-frames >/dev/null 2>&1; then
  echo "Select frames without required args should fail" >&2
  exit 1
fi

SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage public/assets/img-9142-opensplat-webhq-5000-d3-200k-h1.sog "Dry Run" >/dev/null 2>&1 && {
  echo "Quality stage should reject non-PLY input" >&2
  exit 1
}

dry_run_output=$(SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage output/nonexistent-quality-source.ply "Dry Run" web-hq)
printf '%s\n' "$dry_run_output" | grep -q "Preset: web-hq"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=30000"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=300000"

temp_video=$(mktemp "${TMPDIR:-/tmp}/splatter-quality-sweep.XXXXXX.mov")
trap 'rm -f "$temp_video"' EXIT
sweep_output=$("$cli" quality-sweep "$temp_video" dry-run-title "Dry Run")
printf '%s\n' "$sweep_output" | grep -q "Execute: 0"
printf '%s\n' "$sweep_output" | grep -q "Holdout: auto"
printf '%s\n' "$sweep_output" | grep -q "COLMAP_CAMERA_MODEL=PINHOLE"
printf '%s\n' "$sweep_output" | grep -q "OPENSPLAT_SAVE_EVERY=1000"

echo "CLI contract tests passed"
