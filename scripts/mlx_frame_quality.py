#!/usr/bin/env python3
import json
import sys

from frame_quality import quality_report


def usage():
    print("Usage: scripts/mlx_frame_quality.py <capture> [max-sample]", file=sys.stderr)


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1
    max_sample = int(sys.argv[2]) if len(sys.argv) == 3 else 240
    if sys.argv[1] == "--dry-run":
        print(json.dumps({"backend": "mlx", "purpose": "frame quality scoring"}, indent=2))
        return 0

    try:
        import mlx.core as mx
    except Exception as exc:
        print(f"MLX unavailable for frame quality scoring: {exc}", file=sys.stderr)
        return 3

    report = quality_report(sys.argv[1], max_sample)
    sharp = mx.array(
        [
            report["sharpness"]["p10"],
            report["sharpness"]["median"],
            report["sharpness"]["p90"],
        ]
    )
    report["mlx"] = {
        "backend": "mlx",
        "sharpnessMean": float(mx.mean(sharp).item()),
        "use": "fast aggregate scoring for capture triage; COLMAP/OpenMVS remain CPU tools",
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
