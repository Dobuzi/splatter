#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from stage_voxel_grids import human_size
from voxel_free_space import create_free_space


def usage():
    print("Usage: scripts/stage_free_space_grids.py [max-rays] [max-free]", file=sys.stderr)


def asset_url_to_path(url):
    return Path("public") / url


def capture_slug(config):
    return str(config.get("capture", "")).split(",", 1)[0].strip()


def best_sparse_model(capture):
    sparse_root = Path("captures") / capture / "colmap" / "sparse"
    candidates = [path for path in sparse_root.iterdir() if path.is_dir() and (path / "images.bin").exists()]
    if not candidates:
        raise ValueError(f"No COLMAP sparse model found for {capture}")
    return max(candidates, key=lambda path: (path / "images.bin").stat().st_size)


def stage_scene(scene, max_rays, max_free):
    scene_path = Path("public") / scene["sceneUrl"]
    config = json.loads(scene_path.read_text(encoding="utf-8"))
    point_url = config.get("pointCloudAssetUrl")
    voxel_url = config.get("voxelGridUrl")
    if config.get("format") != "PLY Mesh" or not point_url or not voxel_url:
        return None

    capture = capture_slug(config)
    if not capture:
        raise ValueError(f"{scene['id']} is missing capture metadata")

    scene_id = scene["id"]
    suffix = Path(voxel_url).stem.replace(f"{scene_id}-occupancy-", "")
    summary_json = Path("public/assets") / f"{scene_id}-free-space-{suffix}.json"
    free_ply = Path("public/assets") / f"{scene_id}-free-space-{suffix}.ply"
    navigable_ply = Path("public/assets") / f"{scene_id}-navigable-{suffix}.ply"
    sparse_model = best_sparse_model(capture)

    summary = create_free_space(
        asset_url_to_path(point_url),
        asset_url_to_path(voxel_url),
        sparse_model,
        summary_json,
        free_ply,
        navigable_ply,
        max_rays,
        max_free,
    )

    config["freeSpaceGridUrl"] = f"assets/{summary_json.name}"
    config["freeSpaceGridAssetUrl"] = f"assets/{free_ply.name}"
    config["navigableGridAssetUrl"] = f"assets/{navigable_ply.name}"
    config.setdefault("metrics", {})["freeSpaceGrid"] = {
        "method": summary["method"],
        "cameraCount": summary["cameraCount"],
        "sampledRays": summary["sampledRays"],
        "acceptedRays": summary["acceptedRays"],
        "freeVoxels": summary["freeVoxels"],
        "navigableVoxels": summary["navigableVoxels"],
        "unknownVoxels": summary["unknownVoxels"],
        "freeRatio": summary["freeRatio"],
        "navigableRatio": summary["navigableRatio"],
        "upAxis": summary["upAxis"],
        "floorSide": summary["floorSide"],
        "source": point_url,
    }

    delivery = config.get("delivery", "")
    free_delivery = f"free-space mask {human_size(free_ply.stat().st_size)}"
    navigable_delivery = f"navigable mask {human_size(navigable_ply.stat().st_size)}"
    parts = [
        part.strip()
        for part in delivery.split(";")
        if part.strip() and "free-space mask" not in part and "navigable mask" not in part
    ]
    parts.extend([free_delivery, navigable_delivery])
    config["delivery"] = "; ".join(parts)
    scene_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "scene": scene_id,
        "capture": capture,
        "sparseModel": str(sparse_model),
        "freeSpaceGridUrl": config["freeSpaceGridUrl"],
        "freeSpaceGridAssetUrl": config["freeSpaceGridAssetUrl"],
        "navigableGridAssetUrl": config["navigableGridAssetUrl"],
        "freeBytes": free_ply.stat().st_size,
        "navigableBytes": navigable_ply.stat().st_size,
        **summary,
    }


def main():
    if len(sys.argv) > 3:
        usage()
        return 1
    max_rays = int(sys.argv[1]) if len(sys.argv) >= 2 else 60000
    max_free = int(sys.argv[2]) if len(sys.argv) == 3 else 120000
    if max_rays <= 0 or max_free <= 0:
        print("max-rays and max-free must be positive", file=sys.stderr)
        return 1

    manifest = json.loads(Path("public/scenes.json").read_text(encoding="utf-8"))
    staged = []
    for scene in manifest.get("scenes", []):
        if scene.get("primaryTarget") is True and scene.get("id", "").endswith("-openmvs"):
            row = stage_scene(scene, max_rays, max_free)
            if row:
                staged.append(row)
    report = {"maxRays": max_rays, "maxFree": max_free, "scenes": staged}
    Path("public/free-space-grids.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
