#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from stage_voxel_grids import human_size
from voxel_semantic_segment import create_semantic_segmentation


def usage():
    print("Usage: scripts/stage_voxel_semantics.py", file=sys.stderr)


def asset_url_to_path(url):
    return Path("public") / url


def stage_scene(scene):
    scene_path = Path("public") / scene["sceneUrl"]
    config = json.loads(scene_path.read_text(encoding="utf-8"))
    voxel_url = config.get("voxelGridUrl")
    free_url = config.get("freeSpaceGridAssetUrl")
    navigable_url = config.get("navigableGridAssetUrl")
    if config.get("format") != "PLY Mesh" or not voxel_url or not free_url or not navigable_url:
        return None

    scene_id = scene["id"]
    suffix = Path(voxel_url).stem.replace(f"{scene_id}-occupancy-", "")
    summary_json = Path("public/assets") / f"{scene_id}-semantic-{suffix}.json"
    semantic_ply = Path("public/assets") / f"{scene_id}-semantic-{suffix}.ply"
    summary = create_semantic_segmentation(
        asset_url_to_path(voxel_url),
        asset_url_to_path(free_url),
        asset_url_to_path(navigable_url),
        summary_json,
        semantic_ply,
    )

    config["semanticVoxelUrl"] = f"assets/{summary_json.name}"
    config["semanticVoxelAssetUrl"] = f"assets/{semantic_ply.name}"
    config.setdefault("metrics", {})["semanticVoxels"] = {
        "method": summary["method"],
        "labels": {name: {"id": value["id"], "color": value["color"]} for name, value in summary["labels"].items()},
        "counts": summary["counts"],
        "labeledVoxels": summary["labeledVoxels"],
        "totalVoxels": summary["totalVoxels"],
        "labeledRatio": summary["labeledRatio"],
    }

    delivery = config.get("delivery", "")
    semantic_delivery = f"semantic voxels {human_size(semantic_ply.stat().st_size)}"
    parts = [part.strip() for part in delivery.split(";") if part.strip() and "semantic voxels" not in part]
    parts.append(semantic_delivery)
    config["delivery"] = "; ".join(parts)
    scene_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "scene": scene_id,
        "semanticVoxelUrl": config["semanticVoxelUrl"],
        "semanticVoxelAssetUrl": config["semanticVoxelAssetUrl"],
        "assetBytes": semantic_ply.stat().st_size,
        **summary,
    }


def main():
    if len(sys.argv) != 1:
        usage()
        return 1
    manifest = json.loads(Path("public/scenes.json").read_text(encoding="utf-8"))
    staged = []
    for scene in manifest.get("scenes", []):
        if scene.get("primaryTarget") is True and scene.get("id", "").endswith("-openmvs"):
            row = stage_scene(scene)
            if row:
                staged.append(row)
    report = {"scenes": staged}
    Path("public/voxel-semantics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
