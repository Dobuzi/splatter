#!/usr/bin/env python3
import json
import math
import subprocess
import sys
from pathlib import Path


def usage():
    print("Usage: scripts/compare_holdout.py <reference-image> <render-image> [metrics-json]", file=sys.stderr)


def image_size(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    width, height = result.stdout.strip().split("x", 1)
    return int(width), int(height)


def decode_rgb(path, width, height):
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"scale={width}:{height}:flags=bicubic",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    expected = width * height * 3
    if len(result.stdout) != expected:
        raise RuntimeError(f"Decoded {len(result.stdout)} bytes from {path}, expected {expected}")
    return result.stdout


def psnr(reference, render):
    total = 0
    for a, b in zip(reference, render):
        delta = a - b
        total += delta * delta
    mse = total / len(reference)
    if mse == 0:
        return float("inf"), mse
    return 10 * math.log10((255 * 255) / mse), mse


def luma(rgb):
    gray = bytearray(len(rgb) // 3)
    out = 0
    for i in range(0, len(rgb), 3):
        gray[out] = int(0.2126 * rgb[i] + 0.7152 * rgb[i + 1] + 0.0722 * rgb[i + 2])
        out += 1
    return gray


def window_ssim(ref_gray, ren_gray, width, height, window=8, stride=8):
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    scores = []

    max_y = max(1, height - window + 1)
    max_x = max(1, width - window + 1)
    for y in range(0, max_y, stride):
        for x in range(0, max_x, stride):
            ref_values = []
            ren_values = []
            for yy in range(y, min(y + window, height)):
                start = yy * width + x
                end = yy * width + min(x + window, width)
                ref_values.extend(ref_gray[start:end])
                ren_values.extend(ren_gray[start:end])

            n = len(ref_values)
            if n < 2:
                continue
            mean_ref = sum(ref_values) / n
            mean_ren = sum(ren_values) / n
            var_ref = sum((v - mean_ref) ** 2 for v in ref_values) / (n - 1)
            var_ren = sum((v - mean_ren) ** 2 for v in ren_values) / (n - 1)
            cov = sum((a - mean_ref) * (b - mean_ren) for a, b in zip(ref_values, ren_values)) / (n - 1)
            score = ((2 * mean_ref * mean_ren + c1) * (2 * cov + c2)) / (
                (mean_ref * mean_ref + mean_ren * mean_ren + c1) * (var_ref + var_ren + c2)
            )
            scores.append(score)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def main(argv):
    if len(argv) not in (3, 4):
        usage()
        return 1

    reference = Path(argv[1])
    render = Path(argv[2])
    output = Path(argv[3]) if len(argv) == 4 else None

    if not reference.is_file():
        print(f"Reference image not found: {reference}", file=sys.stderr)
        return 1
    if not render.is_file():
        print(f"Render image not found: {render}", file=sys.stderr)
        return 1

    width, height = image_size(render)
    ref_rgb = decode_rgb(reference, width, height)
    ren_rgb = decode_rgb(render, width, height)
    psnr_db, mse = psnr(ref_rgb, ren_rgb)
    ssim = window_ssim(luma(ref_rgb), luma(ren_rgb), width, height)

    metrics = {
        "reference": str(reference),
        "render": str(render),
        "width": width,
        "height": height,
        "mse": mse,
        "psnr_db": psnr_db,
        "ssim": ssim,
    }

    print(f"Holdout metrics for {render}")
    print(f"- Reference: {reference}")
    print(f"- Render size: {width}x{height}")
    print(f"- MSE: {mse:.6f}")
    print(f"- PSNR: {psnr_db:.3f} dB")
    print(f"- SSIM: {ssim:.4f}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        print(f"- JSON: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
