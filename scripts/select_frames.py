#!/usr/bin/env python3
import json
import os
import shutil
import sys
from pathlib import Path


def usage():
    print(
        "Usage: scripts/select_frames.py <source-images-dir> <output-images-dir> [max-frames]",
        file=sys.stderr,
    )


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

    # Keep the selector dependency-free. JPEG byte size is a useful proxy for
    # detail/sharpness after fixed-q extraction, and min_gap keeps viewpoints diverse.
    scored = [
        {"index": index, "path": path, "score": path.stat().st_size}
        for index, path in enumerate(files)
    ]

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
        "score": "jpeg_bytes",
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
                "jpeg_bytes": item["score"],
            }
        )

    manifest_path = output_dir.parent / "frame-selection.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Selected {len(selected)} of {len(files)} frames into {output_dir}")
    print(f"Frame selection manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
