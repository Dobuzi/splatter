#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from voxel_grid import create_voxel_grid


def usage():
    print("Usage: scripts/stage_voxel_grids.py [resolution]", file=sys.stderr)


def asset_url_to_path(url):
    return Path("public") / url


def human_size(bytes_count):
    units = ["B", "KB", "MB", "GB"]
    size = float(bytes_count)
    unit = 0
    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1
    return f"{size:.2f} {units[unit]}" if unit else f"{int(size)} B"


def stage_scene(scene, resolution):
    scene_path = Path("public") / scene["sceneUrl"]
    config = json.loads(scene_path.read_text(encoding="utf-8"))
    point_url = config.get("pointCloudAssetUrl")
    mesh_url = config.get("assetUrl")
    if config.get("format") != "PLY Mesh" or not point_url or not mesh_url:
        return None

    scene_id = scene["id"]
    output_json = Path("public/assets") / f"{scene_id}-occupancy-r{resolution}.json"
    output_ply = Path("public/assets") / f"{scene_id}-occupancy-r{resolution}.ply"
    report = create_voxel_grid(asset_url_to_path(point_url), output_json, output_ply, resolution, asset_url_to_path(mesh_url))
    grid = json.loads(output_json.read_text(encoding="utf-8"))

    config["voxelGridUrl"] = f"assets/{output_json.name}"
    config["voxelGridAssetUrl"] = f"assets/{output_ply.name}"
    config.setdefault("metrics", {})["voxelGrid"] = {
        "resolution": resolution,
        "dims": grid["dims"],
        "cellSize": grid["cellSize"],
        "occupiedVoxels": grid["occupiedVoxels"],
        "totalVoxels": grid["totalVoxels"],
        "occupancyRatio": grid["occupancyRatio"],
        "source": point_url,
    }
    delivery = config.get("delivery", "")
    voxel_size = human_size(output_ply.stat().st_size)
    if "occupancy voxels" not in delivery:
        config["delivery"] = f"{delivery}; occupancy voxels {voxel_size}" if delivery else f"occupancy voxels {voxel_size}"
    scene_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    report["scene"] = scene_id
    report["voxelGridUrl"] = config["voxelGridUrl"]
    report["voxelGridAssetUrl"] = config["voxelGridAssetUrl"]
    report["assetBytes"] = output_ply.stat().st_size
    report["jsonBytes"] = output_json.stat().st_size
    return report


def main():
    if len(sys.argv) > 2:
        usage()
        return 1
    resolution = int(sys.argv[1]) if len(sys.argv) == 2 else 96
    if resolution <= 0 or resolution > 512:
        print("resolution must be between 1 and 512", file=sys.stderr)
        return 1

    manifest_path = Path("public/scenes.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    staged = []
    for scene in manifest.get("scenes", []):
        if scene.get("primaryTarget") is True and scene.get("id", "").endswith("-openmvs"):
            row = stage_scene(scene, resolution)
            if row:
                staged.append(row)
    report = {"resolution": resolution, "scenes": staged}
    Path("public/voxel-grids.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
