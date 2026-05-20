#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

from sample_ply_points import read_vertices
from stage_voxel_grids import stage_scene
from voxel_grid import bbox_from_mesh, build_grid


DEFAULT_RESOLUTIONS = [64, 80, 96, 112, 128]
DEFAULT_MIN_COUNTS = [1, 2, 3]
DEFAULT_DILATES = [0, 1]
MAX_ASSET_BYTES = 900_000
MAX_OCCUPIED = 45_000
MAX_ITERATIONS = 3


def usage():
    print("Usage: scripts/voxel_improve.py [resolution-list]", file=sys.stderr)


def parse_int_list(value, fallback):
    if not value:
        return fallback
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def load_primary_scenes():
    manifest = json.loads(Path("public/scenes.json").read_text(encoding="utf-8"))
    return [
        scene
        for scene in manifest.get("scenes", [])
        if scene.get("primaryTarget") is True and scene.get("id", "").endswith("-openmvs")
    ]


def asset_path(url):
    return Path("public") / url


def estimated_asset_bytes(occupied_voxels):
    return 88 + occupied_voxels * 15


def candidate_score(grid):
    occupied = grid["occupiedVoxels"]
    asset_bytes = estimated_asset_bytes(occupied)
    detail = math.log2(max(grid["resolution"], 2)) / 7.0
    coverage = grid["pointCoverage"]
    connected = grid["largestComponentRatio"]
    singleton_penalty = grid["singletonVoxelRatio"] * 0.18 if grid["minCount"] == 1 and grid["dilate"] == 0 else 0
    bloat_penalty = max(0, occupied - MAX_OCCUPIED) / MAX_OCCUPIED
    budget_penalty = max(0, asset_bytes - MAX_ASSET_BYTES) / MAX_ASSET_BYTES
    sparse_penalty = max(0, 2500 - occupied) / 2500
    return (
        coverage * 55
        + connected * 22
        + detail * 16
        + min(occupied, MAX_OCCUPIED) / MAX_OCCUPIED * 7
        - singleton_penalty * 20
        - bloat_penalty * 25
        - budget_penalty * 35
        - sparse_penalty * 18
    )


def refine_resolutions(best_resolution, previous):
    candidates = {
        best_resolution - 16,
        best_resolution - 8,
        best_resolution,
        best_resolution + 8,
        best_resolution + 16,
    }
    candidates.update(previous)
    return sorted(value for value in candidates if 24 <= value <= 192)


def refine_ints(best_value, previous, minimum, maximum):
    candidates = {best_value - 1, best_value, best_value + 1}
    candidates.update(previous)
    return sorted(value for value in candidates if minimum <= value <= maximum)


def evaluate_candidates(vertices, bbox, resolutions, min_counts, dilates):
    candidates = []
    for resolution in resolutions:
        for min_count in min_counts:
            for dilate in dilates:
                grid = build_grid(vertices, bbox, resolution, min_count, dilate)
                row = {
                    "resolution": resolution,
                    "minCount": min_count,
                    "dilate": dilate,
                    "dims": grid["dims"],
                    "occupiedVoxels": grid["occupiedVoxels"],
                    "pointCoverage": grid["pointCoverage"],
                    "largestComponentRatio": grid["largestComponentRatio"],
                    "componentCount": grid["componentCount"],
                    "singletonVoxelRatio": grid["singletonVoxelRatio"],
                    "estimatedAssetBytes": estimated_asset_bytes(grid["occupiedVoxels"]),
                }
                row["score"] = round(candidate_score(grid), 4)
                candidates.append(row)
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def evaluate_scene(scene, resolutions, min_counts, dilates):
    scene_path = Path("public") / scene["sceneUrl"]
    config = json.loads(scene_path.read_text(encoding="utf-8"))
    point_url = config.get("pointCloudAssetUrl")
    mesh_url = config.get("assetUrl")
    if not point_url or not mesh_url:
        return {"scene": scene["id"], "status": "skipped", "reason": "missing point cloud or mesh"}

    vertices = read_vertices(asset_path(point_url), 10_000_000)
    bbox = bbox_from_mesh(asset_path(mesh_url))
    iterations = []
    current_resolutions = resolutions
    current_min_counts = min_counts
    current_dilates = dilates
    best = None
    for iteration in range(1, MAX_ITERATIONS + 1):
        candidates = evaluate_candidates(vertices, bbox, current_resolutions, current_min_counts, current_dilates)
        iteration_best = candidates[0]
        iterations.append({
            "iteration": iteration,
            "resolutions": current_resolutions,
            "minCounts": current_min_counts,
            "dilates": current_dilates,
            "best": iteration_best,
            "topCandidates": candidates[:8],
        })
        if best and iteration_best["score"] <= best["score"]:
            break
        best = iteration_best
        current_resolutions = refine_resolutions(best["resolution"], current_resolutions)
        current_min_counts = refine_ints(best["minCount"], current_min_counts, 1, 5)
        current_dilates = refine_ints(best["dilate"], current_dilates, 0, 2)
    staged = stage_scene(scene, best["resolution"], best["minCount"], best["dilate"])
    return {"scene": scene["id"], "status": "staged", "best": best, "iterations": iterations, "staged": staged}


def main():
    if len(sys.argv) > 2:
        usage()
        return 1
    resolutions = parse_int_list(sys.argv[1] if len(sys.argv) == 2 else "", DEFAULT_RESOLUTIONS)
    min_counts = parse_int_list("", DEFAULT_MIN_COUNTS)
    dilates = parse_int_list("", DEFAULT_DILATES)
    rows = [evaluate_scene(scene, resolutions, min_counts, dilates) for scene in load_primary_scenes()]
    report = {
        "schemaVersion": 1,
        "strategy": "recursive candidate sweep scored by point coverage, voxel connectivity, detail, sparse noise, and asset budget",
        "maxIterations": MAX_ITERATIONS,
        "resolutions": resolutions,
        "minCounts": min_counts,
        "dilates": dilates,
        "scenes": rows,
    }
    staged_rows = [row["staged"] for row in rows if row.get("status") == "staged" and row.get("staged")]
    voxel_summary = {
        "strategy": "recursive-improvement",
        "scenes": staged_rows,
    }
    Path("public/voxel-improvement.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    Path("public/voxel-grids.json").write_text(json.dumps(voxel_summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
