#!/usr/bin/env python3
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


def usage():
    print(
        "Usage: scripts/select_frames.py <source-images-dir> <output-images-dir> [max-frames]",
        file=sys.stderr,
    )

def load_gray_thumbnail(path, width=160):
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scale={width}:-1,format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )

    data = proc.stdout
    if not data:
        raise ValueError(f"empty thumbnail for {path}")
    height = max(1, len(data) // width)
    return list(data[: width * height]), width, height


def laplacian_variance(pixels, width, height):
    if width < 3 or height < 3:
        return 0.0
    values = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = pixels[row + x] * 4
            value = center - pixels[row + x - 1] - pixels[row + x + 1]
            value -= pixels[row - width + x] + pixels[row + width + x]
            values.append(value)
    return statistics.pvariance(values) if values else 0.0


def exposure_score(pixels):
    mean = statistics.fmean(pixels) / 255.0
    clipped = sum(1 for value in pixels if value < 8 or value > 247) / len(pixels)
    midtone = 1.0 - min(1.0, abs(mean - 0.5) * 2.0)
    return max(0.05, midtone * (1.0 - clipped))


def motion_score(previous, current):
    if previous is None:
        return 0.0
    prev_pixels, prev_width, prev_height = previous
    pixels, width, height = current
    count = min(len(prev_pixels), len(pixels), prev_width * prev_height, width * height)
    if count == 0:
        return 0.0
    diff = sum(abs(prev_pixels[i] - pixels[i]) for i in range(count)) / count
    return diff / 255.0


def score_frames(files):
    previous = None
    scored = []
    for index, path in enumerate(files):
        jpeg_bytes = path.stat().st_size
        try:
            thumb = load_gray_thumbnail(path)
            sharpness = laplacian_variance(*thumb)
            exposure = exposure_score(thumb[0])
            motion = motion_score(previous, thumb)
            previous = thumb
            score = (sharpness * exposure) + (motion * 250.0)
            method = "laplacian_exposure_motion"
        except Exception as exc:
            sharpness = 0.0
            exposure = 0.0
            motion = 0.0
            score = float(jpeg_bytes)
            method = f"jpeg_bytes_fallback:{exc.__class__.__name__}"
        scored.append(
            {
                "index": index,
                "path": path,
                "score": score,
                "jpeg_bytes": jpeg_bytes,
                "sharpness": sharpness,
                "exposure": exposure,
                "motion": motion,
                "method": method,
            }
        )
    return scored


def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        usage()
        return 1

    source_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    max_frames = int(sys.argv[3]) if len(sys.argv) == 4 else 180
    min_gap = int(os.environ.get("SPLAT_SELECT_MIN_GAP", "1"))
    mode = os.environ.get("SPLAT_SELECT_MODE", "symlink")

    if mode not in {"symlink", "copy"}:
        print("SPLAT_SELECT_MODE must be symlink or copy.", file=sys.stderr)
        return 1

    files = sorted(source_dir.glob("*.jpg"))
    if not files:
        print(f"No jpg frames found in {source_dir}", file=sys.stderr)
        return 1

    score_mode = os.environ.get("SPLAT_SELECT_SCORE", "visual_quality")
    if score_mode == "jpeg_bytes":
        scored = [
            {
                "index": index,
                "path": path,
                "score": path.stat().st_size,
                "jpeg_bytes": path.stat().st_size,
                "sharpness": 0.0,
                "exposure": 0.0,
                "motion": 0.0,
                "method": "jpeg_bytes",
            }
            for index, path in enumerate(files)
        ]
    elif score_mode == "visual_quality":
        scored = score_frames(files)
    else:
        print("SPLAT_SELECT_SCORE must be visual_quality or jpeg_bytes.", file=sys.stderr)
        return 1

    selected = []
    for item in sorted(scored, key=lambda x: x["score"], reverse=True):
        if any(abs(item["index"] - other["index"]) < min_gap for other in selected):
            continue
        selected.append(item)
        if len(selected) >= max_frames:
            break

    selected.sort(key=lambda x: x["index"])

    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.jpg"):
        old.unlink()

    manifest = {
        "source": str(source_dir),
        "output": str(output_dir),
        "mode": mode,
        "source_frames": len(files),
        "selected_frames": len(selected),
        "max_frames": max_frames,
        "min_gap": min_gap,
        "score": score_mode,
        "frames": [],
    }

    for output_index, item in enumerate(selected, start=1):
        target = output_dir / f"frame_{output_index:05d}.jpg"
        if mode == "copy":
            shutil.copy2(item["path"], target)
        else:
            target.symlink_to(os.path.relpath(item["path"], output_dir))
        manifest["frames"].append(
            {
                "source": str(item["path"]),
                "output": str(target),
                "source_index": item["index"],
                "score": item["score"],
                "jpeg_bytes": item["jpeg_bytes"],
                "sharpness": item["sharpness"],
                "exposure": item["exposure"],
                "motion": item["motion"],
                "method": item["method"],
            }
        )

    manifest_path = output_dir.parent / "frame-selection.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Selected {len(selected)} of {len(files)} frames into {output_dir}")
    print(f"Frame selection manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
