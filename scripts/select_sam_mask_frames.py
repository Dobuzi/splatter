#!/usr/bin/env python3
import json
import shutil
import sys
from pathlib import Path

from select_frames import bucket_select, score_frames


def usage():
    print("Usage: scripts/select_sam_mask_frames.py <capture> [max-frames]", file=sys.stderr)


def select_sam_frames(capture, max_frames=24):
    source_dir = Path("captures") / capture / "images"
    output_dir = Path("captures") / capture / "sam_representative_frames"
    files = sorted(source_dir.glob("*.jpg"))
    if not files:
        raise ValueError(f"No jpg frames found in {source_dir}")
    scored = score_frames(files)
    selected = bucket_select(scored, max_frames, max(1, len(files) // max_frames // 2))
    selected.sort(key=lambda item: item["index"])
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.jpg"):
        old.unlink()
    rows = []
    for item in selected:
        target = output_dir / item["path"].name
        shutil.copy2(item["path"], target)
        rows.append(
            {
                "frame": item["path"].name,
                "source": str(item["path"]),
                "output": str(target),
                "sourceIndex": item["index"],
                "score": item["score"],
                "sharpness": item["sharpness"],
                "exposure": item["exposure"],
                "motion": item["motion"],
            }
        )
    report = {
        "capture": capture,
        "source": str(source_dir),
        "output": str(output_dir),
        "sourceFrames": len(files),
        "selectedFrames": len(rows),
        "maxFrames": max_frames,
        "strategy": "time-bucket visual quality with original frame names preserved",
        "maskOutputContract": {
            "directory": f"captures/{capture}/sam_masks/<label>",
            "filename": "<same frame stem>.png",
        },
        "frames": rows,
    }
    (output_dir / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1
    max_frames = int(sys.argv[2]) if len(sys.argv) == 3 else 24
    if max_frames <= 0:
        print("max-frames must be positive", file=sys.stderr)
        return 1
    print(json.dumps(select_sam_frames(sys.argv[1], max_frames), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
