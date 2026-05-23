#!/usr/bin/env python3
import json
import struct
import sys
from pathlib import Path

from sample_ply_points import read_vertices
from voxel_free_space import point_to_index
from voxel_grid import voxel_center


LABELS = {
    "occupied_surface": {
        "id": 1,
        "color": [226, 180, 92],
        "description": "Reconstructed occupied surface voxel",
    },
    "observed_free_space": {
        "id": 2,
        "color": [70, 190, 255],
        "description": "Camera-observed empty voxel before a reconstructed surface",
    },
    "navigable_space": {
        "id": 3,
        "color": [94, 230, 157],
        "description": "Observed free voxel with local support and clearance",
    },
}


def usage():
    print(
        "Usage: scripts/voxel_semantic_segment.py <occupancy.json> <free.ply> <navigable.ply> <summary.json> <semantic.ply>",
        file=sys.stderr,
    )


def indices_from_ply(path, grid):
    if not path or not Path(path).exists():
        return set()
    indices = set()
    for vertex in read_vertices(path, 10_000_000):
        index = point_to_index(vertex[:3], grid)
        if index is not None:
            indices.add(index)
    return indices


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


def create_semantic_segmentation(occupancy_json, free_ply, navigable_ply, summary_json, semantic_ply):
    grid = json.loads(Path(occupancy_json).read_text(encoding="utf-8"))
    occupied = set(grid["occupied"])
    free = indices_from_ply(free_ply, grid) - occupied
    navigable = indices_from_ply(navigable_ply, grid) - occupied
    free -= navigable

    labels_by_index = {}
    for index in occupied:
        labels_by_index[index] = "occupied_surface"
    for index in free:
        labels_by_index[index] = "observed_free_space"
    for index in navigable:
        labels_by_index[index] = "navigable_space"

    spec = {"origin": grid["origin"], "cellSize": grid["cellSize"], "dims": grid["dims"]}
    rows = []
    for index, label_name in sorted(labels_by_index.items()):
        x, y, z = voxel_center(index, spec)
        label = LABELS[label_name]
        red, green, blue = label["color"]
        rows.append((x, y, z, red, green, blue, label["id"]))
    write_semantic_ply(semantic_ply, rows)

    counts = {
        "unknown": max(0, grid["totalVoxels"] - len(labels_by_index)),
        "occupied_surface": sum(1 for label in labels_by_index.values() if label == "occupied_surface"),
        "observed_free_space": sum(1 for label in labels_by_index.values() if label == "observed_free_space"),
        "navigable_space": sum(1 for label in labels_by_index.values() if label == "navigable_space"),
    }
    summary = {
        "schemaVersion": 1,
        "method": "occupancy-free-space-fusion",
        "occupancySource": str(occupancy_json),
        "freeSpaceSource": str(free_ply),
        "navigableSource": str(navigable_ply),
        "semanticAsset": str(semantic_ply),
        "labels": LABELS,
        "counts": counts,
        "labeledVoxels": len(labels_by_index),
        "totalVoxels": grid["totalVoxels"],
        "labeledRatio": len(labels_by_index) / grid["totalVoxels"] if grid["totalVoxels"] else 0,
        "note": "Unknown voxels are counted but not rendered to avoid treating unobserved space as a semantic class.",
    }
    Path(summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    if len(sys.argv) != 6:
        usage()
        return 1
    report = create_semantic_segmentation(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
        Path(sys.argv[5]),
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
