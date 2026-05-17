#!/usr/bin/env python3
import json
import statistics
import sys
from pathlib import Path

from select_frames import score_frames


def usage():
    print("Usage: scripts/frame_quality.py <capture> [max-sample]", file=sys.stderr)


def percentile(values, ratio):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return ordered[index]


def quality_report(capture, max_sample=240):
    images_dir = Path("captures") / capture / "images"
    files = sorted(images_dir.glob("*.jpg"))
    if not files:
        raise ValueError(f"No jpg frames found in {images_dir}")
    stride = max(1, len(files) // max_sample)
    sampled = files[::stride][:max_sample]
    scored = score_frames(sampled)
    sharpness = [item["sharpness"] for item in scored]
    exposure = [item["exposure"] for item in scored]
    motion = [item["motion"] for item in scored]
    sharp_median = statistics.median(sharpness) if sharpness else 0.0
    blur_floor = max(8.0, sharp_median * 0.45)
    blur_rejects = sum(1 for value in sharpness if value < blur_floor)
    exposure_rejects = sum(1 for value in exposure if value < 0.25)
    return {
        "capture": capture,
        "frames": len(files),
        "sampled": len(scored),
        "sharpness": {
            "p10": percentile(sharpness, 0.10),
            "median": sharp_median,
            "p90": percentile(sharpness, 0.90),
        },
        "exposure": {
            "p10": percentile(exposure, 0.10),
            "median": statistics.median(exposure) if exposure else 0.0,
            "p90": percentile(exposure, 0.90),
        },
        "motion": {
            "median": statistics.median(motion) if motion else 0.0,
            "p90": percentile(motion, 0.90),
        },
        "blurRejectRatio": blur_rejects / len(scored) if scored else 0.0,
        "exposureRejectRatio": exposure_rejects / len(scored) if scored else 0.0,
        "recommendation": recommendation(sharp_median, blur_rejects / len(scored), exposure_rejects / len(scored)),
    }


def recommendation(sharpness_median, blur_ratio, exposure_ratio):
    notes = []
    if sharpness_median < 20:
        notes.append("increase fps only after improving focus or reducing motion blur")
    if blur_ratio > 0.25:
        notes.append("use select-frames before COLMAP to reject soft frames")
    if exposure_ratio > 0.20:
        notes.append("avoid clipped highlights and underexposed passes")
    if not notes:
        notes.append("frame quality is suitable for dense reconstruction")
    return notes


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1
    report = quality_report(sys.argv[1], int(sys.argv[2]) if len(sys.argv) == 3 else 240)
    output = Path("captures") / sys.argv[1] / "frame-quality.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
