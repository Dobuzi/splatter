#!/usr/bin/env zsh
set -euo pipefail

cli="bin/splatter"

if [[ ! -x "$cli" ]]; then
  echo "Missing executable CLI: $cli" >&2
  exit 1
fi

"$cli" --help | grep -q "splatter - local iPhone video"
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

echo "CLI contract tests passed"
