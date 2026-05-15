#!/usr/bin/env python3
import glob
import json
import math
import re
import sys
from pathlib import Path


def usage():
    print("Usage: scripts/select_checkpoint.py <ply-prefix-or-file>", file=sys.stderr)


def checkpoint_iteration(path):
    match = re.search(r"_(\d+)\.ply$", path.name)
    if match:
        return int(match.group(1))
    match = re.search(r"-(\d+)(?:-d\d+)?\.ply$", path.name)
    if match:
        return int(match.group(1))
    return 0


def inspect_ply(path):
    vertex_count = 0
    properties = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("format ") and "ascii" not in line:
                return {"path": str(path), "finite": False, "reason": "non-ascii PLY"}
            if line.startswith("element vertex "):
                vertex_count = int(line.split()[-1])
            elif line.startswith("property "):
                properties.append(line.split()[-1])
            elif line == "end_header":
                break

        checked = 0
        bad_rows = 0
        for line in handle:
            if checked >= vertex_count:
                break
            values = line.split()
            for value in values:
                try:
                    number = float(value)
                except ValueError:
                    bad_rows += 1
                    break
                if not math.isfinite(number):
                    bad_rows += 1
                    break
            checked += 1

    return {
        "path": str(path),
        "finite": bad_rows == 0 and checked == vertex_count,
        "reason": "ok" if bad_rows == 0 else "nan-or-inf",
        "vertices": vertex_count,
        "checked_vertices": checked,
        "bad_rows": bad_rows,
        "iteration": checkpoint_iteration(path),
        "properties": len(properties),
    }


def main():
    if len(sys.argv) != 2:
        usage()
        return 1

    prefix = Path(sys.argv[1])
    if prefix.is_file():
        candidates = [prefix]
    else:
        candidates = [Path(path) for path in sorted(glob.glob(f"{prefix}*.ply"))]

    if not candidates:
        print(f"No checkpoint PLY files found for prefix: {prefix}", file=sys.stderr)
        return 1

    reports = [inspect_ply(path) for path in candidates]
    finite = [report for report in reports if report["finite"]]
    best = max(finite, key=lambda item: (item["iteration"], item["vertices"])) if finite else None
    result = {"best": best, "checkpoints": reports}
    print(json.dumps(result, indent=2))
    return 0 if best else 2


if __name__ == "__main__":
    raise SystemExit(main())
