#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def usage():
    print("Usage: scripts/generate_masks.py <images-dir> <masks-dir>", file=sys.stderr)


def ellipse_mask(width, height, keep_ratio):
    yy, xx = np.mgrid[0:height, 0:width]
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    rx = max(1.0, width * keep_ratio / 2.0)
    ry = max(1.0, height * keep_ratio / 2.0)
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0


def saliency_mask(rgb):
    array = np.asarray(rgb).astype(np.float32) / 255.0
    maxc = array.max(axis=2)
    minc = array.min(axis=2)
    saturation = maxc - minc
    gray = array.mean(axis=2)
    gy, gx = np.gradient(gray)
    edge = np.sqrt((gx * gx) + (gy * gy))
    edge_threshold = np.quantile(edge, 0.72)
    sat_threshold = max(0.05, float(np.quantile(saturation, 0.55)))
    return (edge >= edge_threshold) | (saturation >= sat_threshold)


def make_mask(path, output_path, keep_ratio):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    small_width = 320
    small_height = max(1, round(height * small_width / width))
    small = image.resize((small_width, small_height), Image.Resampling.BILINEAR)
    mask = ellipse_mask(small_width, small_height, keep_ratio) | saliency_mask(small)

    mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(9))
    mask_image = mask_image.filter(ImageFilter.GaussianBlur(3))
    mask_image = mask_image.resize((width, height), Image.Resampling.BILINEAR)
    mask_image = mask_image.point(lambda value: 255 if value >= 32 else 0)
    mask_image.save(output_path)

    kept = np.asarray(mask_image, dtype=np.uint8) > 0
    return float(kept.mean())


def main():
    if len(sys.argv) != 3:
        usage()
        return 1

    images_dir = Path(sys.argv[1])
    masks_dir = Path(sys.argv[2])
    keep_ratio = float(os.environ.get("SPLAT_MASK_KEEP_RATIO", "0.82"))

    files = sorted(images_dir.glob("*.jpg"))
    if not files:
        print(f"No jpg frames found in {images_dir}", file=sys.stderr)
        return 1

    masks_dir.mkdir(parents=True, exist_ok=True)
    for old in masks_dir.glob("*.png"):
        old.unlink()

    coverages = []
    frames = []
    for image_path in files:
        output_path = masks_dir / f"{image_path.stem}.png"
        coverage = make_mask(image_path, output_path, keep_ratio)
        coverages.append(coverage)
        frames.append(
            {
                "image": str(image_path),
                "mask": str(output_path),
                "coverage": round(coverage, 4),
            }
        )

    manifest = {
        "backend": "local_center_saliency",
        "images": len(files),
        "keep_ratio": keep_ratio,
        "mean_coverage": round(float(np.mean(coverages)), 4),
        "min_coverage": round(float(np.min(coverages)), 4),
        "max_coverage": round(float(np.max(coverages)), 4),
        "frames": frames,
    }
    manifest_path = masks_dir.parent / "mask-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Generated {len(files)} local masks into {masks_dir}")
    print(f"Mask manifest: {manifest_path}")
    print(f"Mean mask coverage: {manifest['mean_coverage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
