#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

from voxel_free_space import qvec_to_rotation, read_c_string, read_exact
from voxel_grid import voxel_center


CAMERA_MODELS = {
    0: ("SIMPLE_PINHOLE", 3),
    1: ("PINHOLE", 4),
    2: ("SIMPLE_RADIAL", 4),
    3: ("RADIAL", 5),
    4: ("OPENCV", 8),
}
MASK_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
BASE_LABELS = {
    "unlabeled_surface": {"id": 1, "color": [226, 180, 92]},
}


def usage():
    print(
        "Usage: scripts/sam_mask_voxel_project.py <occupancy.json> <colmap-sparse-dir> <mask-dir> <summary.json> <semantic.ply> [min-votes]",
        file=sys.stderr,
    )


def read_colmap_cameras(cameras_bin):
    cameras = {}
    with Path(cameras_bin).open("rb") as handle:
        (camera_count,) = read_exact(handle, "<Q")
        for _ in range(camera_count):
            camera_id, model_id, width, height = read_exact(handle, "<IiQQ")
            model_name, param_count = CAMERA_MODELS.get(model_id, (f"MODEL_{model_id}", 0))
            params = read_exact(handle, "<" + "d" * param_count) if param_count else ()
            cameras[camera_id] = {
                "id": camera_id,
                "modelId": model_id,
                "model": model_name,
                "width": width,
                "height": height,
                "params": params,
            }
    return cameras


def read_colmap_images(images_bin):
    images = []
    with Path(images_bin).open("rb") as handle:
        (image_count,) = read_exact(handle, "<Q")
        for _ in range(image_count):
            image_id = read_exact(handle, "<I")[0]
            qvec = read_exact(handle, "<dddd")
            tvec = read_exact(handle, "<ddd")
            camera_id = read_exact(handle, "<I")[0]
            name = read_c_string(handle)
            (point_count,) = read_exact(handle, "<Q")
            handle.seek(point_count * struct.calcsize("<ddq"), 1)
            images.append({"id": image_id, "qvec": qvec, "tvec": tvec, "cameraId": camera_id, "name": name})
    return images


def camera_intrinsics(camera):
    params = camera["params"]
    if camera["model"] == "SIMPLE_PINHOLE":
        f, cx, cy = params[:3]
        return f, f, cx, cy
    if camera["model"] in {"PINHOLE", "OPENCV"}:
        return params[0], params[1], params[2], params[3]
    if camera["model"] in {"SIMPLE_RADIAL", "RADIAL"}:
        f, cx, cy = params[:3]
        return f, f, cx, cy
    raise ValueError(f"Unsupported COLMAP camera model: {camera['model']}")


def project(point, image, camera):
    rotation = qvec_to_rotation(image["qvec"])
    tvec = image["tvec"]
    camera_point = [
        rotation[row][0] * point[0] + rotation[row][1] * point[1] + rotation[row][2] * point[2] + tvec[row]
        for row in range(3)
    ]
    if camera_point[2] <= 1e-9:
        return None
    fx, fy, cx, cy = camera_intrinsics(camera)
    x = fx * camera_point[0] / camera_point[2] + cx
    y = fy * camera_point[1] / camera_point[2] + cy
    if x < 0 or y < 0 or x >= camera["width"] or y >= camera["height"]:
        return None
    return int(round(x)), int(round(y))


def load_mask(path):
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required to read SAM mask images") from exc
    image = Image.open(path).convert("L")
    return image.size, image.load()


def mask_label(path, mask_root):
    parent = path.parent
    if parent != mask_root:
        return parent.name.replace("_", " ").replace("-", " ").strip()
    stem = path.stem
    if "__" in stem:
        return stem.rsplit("__", 1)[1].replace("_", " ").replace("-", " ").strip()
    return "sam object"


def frame_key(path):
    stem = path.stem
    if "__" in stem:
        return stem.rsplit("__", 1)[0]
    return stem


def discover_masks(mask_dir):
    mask_root = Path(mask_dir)
    masks = {}
    for path in sorted(mask_root.rglob("*")):
        if path.suffix.lower() not in MASK_EXTENSIONS or not path.is_file():
            continue
        key = frame_key(path)
        label = mask_label(path, mask_root)
        masks.setdefault(key, []).append({"label": label, "path": path})
    return masks


def label_color(label):
    value = 2166136261
    for char in label.encode("utf-8"):
        value ^= char
        value = (value * 16777619) & 0xFFFFFFFF
    return [90 + value % 140, 70 + (value >> 8) % 150, 90 + (value >> 16) % 140]


def write_semantic_ply(path, rows):
    header = f"""ply
format binary_little_endian 1.0
element vertex {len(rows)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
property uchar semantic_label
end_header
"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("wb") as handle:
        handle.write(header.encode("ascii"))
        for row in rows:
            handle.write(struct.pack("<fffBBBB", *row))


def create_sam_voxel_semantics(occupancy_json, sparse_dir, mask_dir, summary_json, semantic_ply, min_votes=1):
    grid = json.loads(Path(occupancy_json).read_text(encoding="utf-8"))
    sparse = Path(sparse_dir)
    cameras = read_colmap_cameras(sparse / "cameras.bin")
    images = read_colmap_images(sparse / "images.bin")
    masks = discover_masks(mask_dir)
    usable_images = [image for image in images if Path(image["name"]).stem in masks]

    spec = {"origin": grid["origin"], "cellSize": grid["cellSize"], "dims": grid["dims"]}
    centers = {index: voxel_center(index, spec) for index in grid["occupied"]}
    votes = {index: {} for index in grid["occupied"]}
    mask_cache = {}
    projected_tests = 0
    positive_votes = 0

    for image in usable_images:
        camera = cameras[image["cameraId"]]
        image_masks = masks[Path(image["name"]).stem]
        loaded_masks = []
        for record in image_masks:
            size, pixels = mask_cache.get(record["path"], (None, None))
            if pixels is None:
                size, pixels = load_mask(record["path"])
                mask_cache[record["path"]] = (size, pixels)
            loaded_masks.append({**record, "size": size, "pixels": pixels})

        for index, center in centers.items():
            pixel = project(center, image, camera)
            if pixel is None:
                continue
            projected_tests += 1
            for record in loaded_masks:
                width, height = record["size"]
                x = min(width - 1, max(0, pixel[0]))
                y = min(height - 1, max(0, pixel[1]))
                if record["pixels"][x, y] > 127:
                    label_votes = votes[index]
                    label_votes[record["label"]] = label_votes.get(record["label"], 0) + 1
                    positive_votes += 1

    labels = {"unlabeled_surface": BASE_LABELS["unlabeled_surface"]}
    assignments = {}
    for index, label_votes in votes.items():
        if not label_votes:
            assignments[index] = ("unlabeled_surface", 0)
            continue
        label, count = max(label_votes.items(), key=lambda item: item[1])
        assignments[index] = (label, count) if count >= min_votes else ("unlabeled_surface", count)
        if label not in labels:
            labels[label] = {"id": len(labels) + 1, "color": label_color(label)}

    rows = []
    counts = {}
    confident = 0
    for index, (label, count) in sorted(assignments.items()):
        if label != "unlabeled_surface":
            confident += 1
        counts[label] = counts.get(label, 0) + 1
        x, y, z = centers[index]
        red, green, blue = labels[label]["color"]
        rows.append((x, y, z, red, green, blue, labels[label]["id"]))
    write_semantic_ply(semantic_ply, rows)

    summary = {
        "schemaVersion": 1,
        "method": "sam-mask-multiview-projection",
        "occupancySource": str(occupancy_json),
        "cameraSource": str(sparse_dir),
        "maskDir": str(mask_dir),
        "semanticAsset": str(semantic_ply),
        "minVotes": min_votes,
        "registeredImages": len(images),
        "maskFrames": len(masks),
        "matchedMaskFrames": len(usable_images),
        "maskFiles": sum(len(records) for records in masks.values()),
        "projectedVoxelTests": projected_tests,
        "positiveVotes": positive_votes,
        "labeledVoxels": confident,
        "surfaceVoxels": len(grid["occupied"]),
        "labelCoverage": confident / len(grid["occupied"]) if grid["occupied"] else 0,
        "labels": labels,
        "counts": counts,
        "status": "segmented" if usable_images and confident else "no matching SAM masks",
        "inputContract": {
            "layoutA": "masks/<label>/<frame_stem>.png",
            "layoutB": "masks/<frame_stem>__<label>.png",
            "threshold": "mask pixel > 127",
        },
    }
    Path(summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    if len(sys.argv) not in (6, 7):
        usage()
        return 1
    min_votes = int(sys.argv[6]) if len(sys.argv) == 7 else 1
    if min_votes <= 0:
        print("min-votes must be positive", file=sys.stderr)
        return 1
    report = create_sam_voxel_semantics(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
        Path(sys.argv[5]),
        min_votes,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
