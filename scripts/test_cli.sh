#!/usr/bin/env zsh
set -euo pipefail

cli="bin/splatter"

if [[ ! -x "$cli" ]]; then
  echo "Missing executable CLI: $cli" >&2
  exit 1
fi

"$cli" --help | grep -q "splatter - local iPhone video"
"$cli" --help | grep -q "quality-report"
"$cli" --help | grep -q "quality-stage"
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

SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage public/assets/img-9142-opensplat-webhq-5000-d3-200k-h1.sog "Dry Run" >/dev/null 2>&1 && {
  echo "Quality stage should reject non-PLY input" >&2
  exit 1
}

dry_run_output=$(SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage output/img-9142-opensplat-webhq-5000-d3.ply "Dry Run" web-hq)
printf '%s\n' "$dry_run_output" | grep -q "Preset: web-hq"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=30000"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=300000"

echo "CLI contract tests passed"
