#!/usr/bin/env python3
import json
import math
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

from sam_mask_voxel_project import read_colmap_images


def usage():
    print("Usage: scripts/generate_sam_mask_assets.py <capture> [max-frames] [label]", file=sys.stderr)


def frame_number(name):
    digits = "".join(char for char in Path(name).stem if char.isdigit())
    return int(digits) if digits else 0


def selected_images(capture, max_frames):
    sparse = Path("captures") / capture / "colmap" / "sparse" / "0"
    images = read_colmap_images(sparse / "images.bin")
    images = sorted(images, key=lambda item: frame_number(item["name"]))
    if len(images) <= max_frames:
        return images
    return [images[round(index * (len(images) - 1) / (max_frames - 1))] for index in range(max_frames)]


def median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else 0


def border_background(pixels, width, height, step):
    samples = []
    for x in range(0, width, step):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(0, height, step):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])
    return tuple(median([sample[channel] for sample in samples]) for channel in range(3))


def component_keep(mask, width, height):
    visited = bytearray(width * height)
    best = []
    center_x = width / 2
    center_y = height / 2
    for start_y in range(height):
        for start_x in range(width):
            start_index = start_x + width * start_y
            if visited[start_index] or not mask[start_index]:
                continue
            queue = deque([(start_x, start_y)])
            visited[start_index] = 1
            component = []
            score = 0.0
            while queue:
                x, y = queue.popleft()
                component.append(x + width * y)
                distance = math.hypot((x - center_x) / width, (y - center_y) / height)
                score += 1.0 / (0.2 + distance)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        index = nx + width * ny
                        if not visited[index] and mask[index]:
                            visited[index] = 1
                            queue.append((nx, ny))
            if len(component) >= 32 and (not best or score > best[0]):
                best = (score, component)
    result = bytearray(width * height)
    if best:
        for index in best[1]:
            result[index] = 255
    return result


def bootstrap_mask(image_path, output_path):
    original = Image.open(image_path).convert("RGB")
    width, height = original.size
    scale = min(1.0, 360 / max(width, height))
    work_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    work = original.resize(work_size, Image.Resampling.BILINEAR)
    pixels = work.load()
    work_width, work_height = work.size
    background = border_background(pixels, work_width, work_height, max(1, min(work_width, work_height) // 48))
    distances = []
    center_x = work_width / 2
    center_y = work_height / 2
    mask = bytearray(work_width * work_height)
    for y in range(work_height):
        for x in range(work_width):
            red, green, blue = pixels[x, y]
            color_distance = math.sqrt((red - background[0]) ** 2 + (green - background[1]) ** 2 + (blue - background[2]) ** 2)
            saturation = max(red, green, blue) - min(red, green, blue)
            center_bias = 1.0 - min(1.0, math.hypot((x - center_x) / work_width, (y - center_y) / work_height) * 1.7)
            score = color_distance + saturation * 0.35 + center_bias * 38
            distances.append(score)
    threshold = sorted(distances)[round(len(distances) * 0.68)]
    for index, score in enumerate(distances):
        if score >= threshold:
            mask[index] = 1
    mask = component_keep(mask, work_width, work_height)
    mask_image = Image.frombytes("L", work.size, bytes(mask))
    mask_image = mask_image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    mask_image = mask_image.resize((width, height), Image.Resampling.NEAREST)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask_image.save(output_path)
    coverage = sum(1 for value in mask_image.getdata() if value > 127) / (width * height)
    return coverage


def generate_masks(capture, max_frames=24, label="bootstrap_object"):
    capture_dir = Path("captures") / capture
    output_dir = capture_dir / "sam_masks" / label
    rows = []
    for image in selected_images(capture, max_frames):
        image_path = capture_dir / "images" / image["name"]
        if not image_path.exists():
            continue
        output_path = output_dir / f"{Path(image['name']).stem}.png"
        coverage = bootstrap_mask(image_path, output_path)
        rows.append({"frame": image["name"], "mask": str(output_path), "coverage": coverage})
    report = {
        "capture": capture,
        "method": "bootstrap-center-foreground",
        "status": "generated" if rows else "no frames",
        "label": label,
        "frames": len(rows),
        "maskDir": str(output_dir),
        "note": "SAM-compatible bootstrap masks. Replace this folder with real SAM/SAM3 masks for higher quality without changing the voxel projection pipeline.",
        "masks": rows,
    }
    (capture_dir / "sam_masks" / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    if len(sys.argv) not in (2, 3, 4):
        usage()
        return 1
    max_frames = int(sys.argv[2]) if len(sys.argv) >= 3 else 24
    label = sys.argv[3] if len(sys.argv) == 4 else "bootstrap_object"
    if max_frames <= 0:
        print("max-frames must be positive", file=sys.stderr)
        return 1
    print(json.dumps(generate_masks(sys.argv[1], max_frames, label), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
