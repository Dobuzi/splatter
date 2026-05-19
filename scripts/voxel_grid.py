#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

from ply_metrics import mesh_metrics
from sample_ply_points import read_vertices


def usage():
    print("Usage: scripts/voxel_grid.py <input-points.ply> <output.json> <output.ply> [resolution] [bbox-mesh.ply]", file=sys.stderr)


def bbox_from_vertices(vertices):
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


def bbox_from_mesh(path):
    metrics = mesh_metrics(path)
    return {
        "min": metrics["bbox"]["min"],
        "max": metrics["bbox"]["max"],
    }


def grid_spec(bbox, resolution):
    size = [bbox["max"][index] - bbox["min"][index] for index in range(3)]
    cell_size = max(size) / resolution if max(size) > 0 else 1.0
    dims = [max(1, math.ceil(value / cell_size) + 1) for value in size]
    return {"origin": bbox["min"], "size": size, "cellSize": cell_size, "dims": dims}


def flat_index(ix, iy, iz, dims):
    return ix + dims[0] * (iy + dims[1] * iz)


def voxel_center(index, spec):
    dims = spec["dims"]
    z = index // (dims[0] * dims[1])
    rem = index - z * dims[0] * dims[1]
    y = rem // dims[0]
    x = rem - y * dims[0]
    return tuple(spec["origin"][axis] + ([x, y, z][axis] + 0.5) * spec["cellSize"] for axis in range(3))


def build_grid(vertices, bbox, resolution):
    spec = grid_spec(bbox, resolution)
    dims = spec["dims"]
    counts = {}
    for vertex in vertices:
        coords = []
        for axis in range(3):
            value = int(math.floor((vertex[axis] - spec["origin"][axis]) / spec["cellSize"]))
            coords.append(min(max(value, 0), dims[axis] - 1))
        key = flat_index(coords[0], coords[1], coords[2], dims)
        counts[key] = counts.get(key, 0) + 1
    occupied = sorted(counts)
    total_voxels = dims[0] * dims[1] * dims[2]
    return {
        "schemaVersion": 1,
        "resolution": resolution,
        "origin": spec["origin"],
        "cellSize": spec["cellSize"],
        "dims": dims,
        "bbox": {"min": bbox["min"], "max": bbox["max"], "size": spec["size"]},
        "occupied": occupied,
        "counts": [counts[index] for index in occupied],
        "occupiedVoxels": len(occupied),
        "totalVoxels": total_voxels,
        "occupancyRatio": len(occupied) / total_voxels if total_voxels else 0,
    }


def write_voxel_ply(path, grid):
    max_count = max(grid["counts"]) if grid["counts"] else 1
    header = f"""ply
format binary_little_endian 1.0
element vertex {len(grid["occupied"])}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
"""
    spec = {"origin": grid["origin"], "cellSize": grid["cellSize"], "dims": grid["dims"]}
    with Path(path).open("wb") as handle:
        handle.write(header.encode("ascii"))
        for index, count in zip(grid["occupied"], grid["counts"]):
            x, y, z = voxel_center(index, spec)
            density = min(1.0, math.log1p(count) / math.log1p(max_count))
            red = int(96 + 120 * density)
            green = int(170 + 60 * density)
            blue = int(220 + 35 * density)
            handle.write(struct.pack("<fffBBB", x, y, z, red, green, blue))


def create_voxel_grid(input_path, output_json, output_ply, resolution=96, bbox_mesh=None):
    vertices = read_vertices(input_path, 10_000_000)
    if not vertices:
        raise ValueError(f"No vertices found in {input_path}")
    bbox = bbox_from_mesh(bbox_mesh) if bbox_mesh else bbox_from_vertices(vertices)
    grid = build_grid(vertices, bbox, resolution)
    grid["input"] = str(input_path)
    if bbox_mesh:
        grid["bboxSource"] = str(bbox_mesh)
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_ply).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(grid, indent=2) + "\n", encoding="utf-8")
    write_voxel_ply(output_ply, grid)
    return {
        "input": str(input_path),
        "outputJson": str(output_json),
        "outputPly": str(output_ply),
        "resolution": resolution,
        "dims": grid["dims"],
        "occupiedVoxels": grid["occupiedVoxels"],
        "totalVoxels": grid["totalVoxels"],
        "occupancyRatio": grid["occupancyRatio"],
    }


def main():
    if len(sys.argv) not in (4, 5, 6):
        usage()
        return 1
    resolution = int(sys.argv[4]) if len(sys.argv) >= 5 else 96
    if resolution <= 0 or resolution > 512:
        print("resolution must be between 1 and 512", file=sys.stderr)
        return 1
    bbox_mesh = Path(sys.argv[5]) if len(sys.argv) == 6 else None
    report = create_voxel_grid(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), resolution, bbox_mesh)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
