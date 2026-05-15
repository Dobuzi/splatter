#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path


def usage():
    print("Usage: scripts/rank_captures.py <capture-prefix>", file=sys.stderr)


def analyze_model(model_dir):
    proc = subprocess.run(
        ["colmap", "model_analyzer", "--path", str(model_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    metrics = {"registered": 0, "points": 0, "error": 999.0}
    for line in proc.stdout.splitlines():
        if "Registered images:" in line:
            match = re.search(r"Registered images:\s*(\d+)", line)
            if match:
                metrics["registered"] = int(match.group(1))
        elif "Points:" in line:
            match = re.search(r"Points:\s*(\d+)", line)
            if match:
                metrics["points"] = int(match.group(1))
        elif "Mean reprojection error:" in line:
            match = re.search(r"Mean reprojection error:\s*([0-9.]+)\s*px", line)
            if match:
                metrics["error"] = float(match.group(1))
    return metrics


def best_model(capture_dir):
    sparse_dir = capture_dir / "colmap" / "sparse"
    if not sparse_dir.is_dir():
        return None

    best = None
    for model_dir in sorted(path for path in sparse_dir.iterdir() if path.is_dir()):
        metrics = analyze_model(model_dir)
        metrics["model"] = model_dir.name
        if best is None or (
            metrics["registered"],
            metrics["points"],
            -metrics["error"],
        ) > (
            best["registered"],
            best["points"],
            -best["error"],
        ):
            best = metrics
    return best


def main():
    if len(sys.argv) != 2:
        usage()
        return 1

    prefix = sys.argv[1]
    captures_root = Path("captures")
    rows = []

    for capture_dir in sorted(captures_root.glob(f"{prefix}*")):
        images_dir = capture_dir / "images"
        if not capture_dir.is_dir() or not images_dir.is_dir():
            continue
        frame_count = len(list(images_dir.glob("*.jpg")))
        best = best_model(capture_dir)
        if best is None:
            continue
        ratio = best["registered"] / frame_count if frame_count else 0.0
        points_per_registered = best["points"] / best["registered"] if best["registered"] else 0.0
        score = (
            best["registered"] * 100.0
            + ratio * 1000.0
            + best["points"] / 100.0
            + points_per_registered
            - best["error"] * 120.0
        )
        rows.append(
            {
                "capture": capture_dir.name,
                "model": best["model"],
                "frames": frame_count,
                "registered": best["registered"],
                "ratio": round(ratio, 4),
                "points": best["points"],
                "points_per_registered": round(points_per_registered, 2),
                "reprojection_error": best["error"],
                "score": round(score, 2),
                "diagnosis": diagnose(ratio, best["points"], points_per_registered),
            }
        )

    rows.sort(key=lambda row: row["score"], reverse=True)
    print(json.dumps({"prefix": prefix, "ranked": rows}, indent=2))
    return 0 if rows else 2


def diagnose(ratio, points, points_per_registered):
    notes = []
    if ratio < 0.35:
        notes.append("low registration overlap")
    if points < 15000:
        notes.append("sparse point count below 3D structure target")
    if points_per_registered < 250:
        notes.append("weak point distribution proxy")
    return notes or ["strongest available candidate"]


if __name__ == "__main__":
    raise SystemExit(main())
