#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

from sample_ply_points import read_vertices, write_point_cloud
from voxel_grid import flat_index, voxel_center


def usage():
    print(
        "Usage: scripts/voxel_free_space.py <points.ply> <occupancy.json> <camera-source> <summary.json> <free.ply> <navigable.ply> [max-rays] [max-free]",
        file=sys.stderr,
    )


def read_exact(handle, fmt):
    size = struct.calcsize(fmt)
    data = handle.read(size)
    if len(data) != size:
        raise ValueError("Unexpected end of COLMAP binary")
    return struct.unpack(fmt, data)


def read_c_string(handle):
    data = bytearray()
    while True:
        char = handle.read(1)
        if not char:
            raise ValueError("Unexpected end of COLMAP image name")
        if char == b"\x00":
            return data.decode("utf-8", "replace")
        data.extend(char)


def qvec_to_rotation(qvec):
    w, x, y, z = qvec
    return (
        (1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y),
        (2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x),
        (2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y),
    )


def camera_center(qvec, tvec):
    rotation = qvec_to_rotation(qvec)
    return tuple(
        -(rotation[0][axis] * tvec[0] + rotation[1][axis] * tvec[1] + rotation[2][axis] * tvec[2])
        for axis in range(3)
    )


def read_colmap_image_centers(images_bin):
    centers = []
    with Path(images_bin).open("rb") as handle:
        (image_count,) = read_exact(handle, "<Q")
        for _ in range(image_count):
            read_exact(handle, "<I")
            qvec = read_exact(handle, "<dddd")
            tvec = read_exact(handle, "<ddd")
            read_exact(handle, "<I")
            read_c_string(handle)
            (point_count,) = read_exact(handle, "<Q")
            handle.seek(point_count * struct.calcsize("<ddq"), 1)
            centers.append(camera_center(qvec, tvec))
    return centers


def read_camera_centers(camera_source):
    source = Path(camera_source)
    if source.is_dir():
        images_bin = source / "images.bin"
        if not images_bin.exists():
            raise ValueError(f"COLMAP images.bin not found: {images_bin}")
        return read_colmap_image_centers(images_bin)
    if source.suffix == ".json":
        data = json.loads(source.read_text(encoding="utf-8"))
        centers = data.get("cameraCenters", data if isinstance(data, list) else [])
        return [tuple(float(value) for value in center[:3]) for center in centers]
    raise ValueError(f"Unsupported camera source: {camera_source}")


def index_to_coords(index, dims):
    z = index // (dims[0] * dims[1])
    rem = index - z * dims[0] * dims[1]
    y = rem // dims[0]
    x = rem - y * dims[0]
    return x, y, z


def point_to_index(point, grid):
    coords = []
    for axis in range(3):
        value = int(math.floor((point[axis] - grid["origin"][axis]) / grid["cellSize"]))
        if value < 0 or value >= grid["dims"][axis]:
            return None
        coords.append(value)
    return flat_index(coords[0], coords[1], coords[2], grid["dims"])


def nearest_center(point, centers):
    best_center = centers[0]
    best_distance = float("inf")
    for center in centers:
        distance = sum((point[axis] - center[axis]) ** 2 for axis in range(3))
        if distance < best_distance:
            best_distance = distance
            best_center = center
    return best_center


def clipped_t_range(start, end, bbox, stop_t):
    low = 0.0
    high = stop_t
    for axis in range(3):
        delta = end[axis] - start[axis]
        if abs(delta) < 1e-12:
            if start[axis] < bbox["min"][axis] or start[axis] > bbox["max"][axis]:
                return None
            continue
        t0 = (bbox["min"][axis] - start[axis]) / delta
        t1 = (bbox["max"][axis] - start[axis]) / delta
        low = max(low, min(t0, t1))
        high = min(high, max(t0, t1))
    if high <= low:
        return None
    return low, high


def carve_free_voxels(points, centers, grid, max_free):
    occupied = set(grid["occupied"])
    free = set()
    ray_count = 0
    stop_t = 0.96
    for point in points:
        target = point[:3]
        center = nearest_center(target, centers)
        clipped = clipped_t_range(center, target, grid["bbox"], stop_t)
        if not clipped:
            continue
        start_t, end_t = clipped
        distance = math.sqrt(sum((target[axis] - center[axis]) ** 2 for axis in range(3)))
        steps = max(2, min(320, math.ceil((end_t - start_t) * distance / grid["cellSize"] * 1.5)))
        ray_count += 1
        for step in range(steps):
            t = start_t + (end_t - start_t) * step / max(1, steps - 1)
            sample = tuple(center[axis] + (target[axis] - center[axis]) * t for axis in range(3))
            index = point_to_index(sample, grid)
            if index is not None and index not in occupied:
                free.add(index)
        if len(free) > max_free * 2:
            free = set(sorted(free)[:max_free])
    return sorted(free)[:max_free], ray_count


def navigable_candidates(free, occupied, dims, up_axis, floor_side, clearance_voxels, support_voxels):
    free_set = set(free)
    navigable = []
    floor_direction = 1 if floor_side == "min" else -1
    axis_limit = dims[up_axis]
    for index in free:
        coords = list(index_to_coords(index, dims))
        support = False
        for step in range(1, support_voxels + 1):
            below = list(coords)
            below[up_axis] -= floor_direction * step
            if 0 <= below[up_axis] < axis_limit and flat_index(below[0], below[1], below[2], dims) in occupied:
                support = True
                break
        if not support:
            continue
        clear = True
        for step in range(1, clearance_voxels + 1):
            above = list(coords)
            above[up_axis] += floor_direction * step
            if not 0 <= above[up_axis] < axis_limit:
                clear = False
                break
            above_index = flat_index(above[0], above[1], above[2], dims)
            if above_index in occupied or above_index not in free_set:
                clear = False
                break
        if clear:
            navigable.append(index)
    return navigable


def infer_navigable(free, occupied, dims, up_axis=1, clearance_voxels=5, support_voxels=4):
    by_side = {
        "min": navigable_candidates(free, occupied, dims, up_axis, "min", clearance_voxels, support_voxels),
        "max": navigable_candidates(free, occupied, dims, up_axis, "max", clearance_voxels, support_voxels),
    }
    side = "min" if len(by_side["min"]) >= len(by_side["max"]) else "max"
    return by_side[side], side


def write_index_ply(path, indices, grid, color):
    vertices = []
    spec = {"origin": grid["origin"], "cellSize": grid["cellSize"], "dims": grid["dims"]}
    for index in indices:
        x, y, z = voxel_center(index, spec)
        vertices.append((x, y, z, color[0], color[1], color[2]))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_point_cloud(path, vertices)


def create_free_space(points_path, occupancy_json, camera_source, summary_json, free_ply, navigable_ply, max_rays=60000, max_free=120000):
    grid = json.loads(Path(occupancy_json).read_text(encoding="utf-8"))
    points = read_vertices(points_path, max_rays)
    centers = read_camera_centers(camera_source)
    if not points:
        raise ValueError(f"No points found: {points_path}")
    if not centers:
        raise ValueError(f"No camera centers found: {camera_source}")

    free, ray_count = carve_free_voxels(points, centers, grid, max_free)
    navigable, floor_side = infer_navigable(free, set(grid["occupied"]), grid["dims"])
    write_index_ply(free_ply, free, grid, (70, 190, 255))
    write_index_ply(navigable_ply, navigable, grid, (94, 230, 157))

    total_voxels = grid["totalVoxels"]
    summary = {
        "schemaVersion": 1,
        "method": "camera-ray-carving",
        "cameraSource": str(camera_source),
        "pointSource": str(points_path),
        "occupancySource": str(occupancy_json),
        "sampledRays": len(points),
        "acceptedRays": ray_count,
        "cameraCount": len(centers),
        "freeVoxels": len(free),
        "navigableVoxels": len(navigable),
        "unknownVoxels": max(0, total_voxels - len(set(grid["occupied"])) - len(free)),
        "totalVoxels": total_voxels,
        "freeRatio": len(free) / total_voxels if total_voxels else 0,
        "navigableRatio": len(navigable) / total_voxels if total_voxels else 0,
        "upAxis": "y",
        "floorSide": floor_side,
        "freeColor": [70, 190, 255],
        "navigableColor": [94, 230, 157],
        "note": "Free means camera-observed empty space before a reconstructed surface; unknown space is intentionally not marked as free.",
    }
    Path(summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    if len(sys.argv) not in (7, 8, 9):
        usage()
        return 1
    max_rays = int(sys.argv[7]) if len(sys.argv) >= 8 else 60000
    max_free = int(sys.argv[8]) if len(sys.argv) == 9 else 120000
    if max_rays <= 0 or max_free <= 0:
        print("max-rays and max-free must be positive", file=sys.stderr)
        return 1
    report = create_free_space(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
        Path(sys.argv[5]),
        Path(sys.argv[6]),
        max_rays,
        max_free,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
