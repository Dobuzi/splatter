#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from sam_mask_voxel_project import create_sam_voxel_semantics, discover_masks
from stage_voxel_grids import human_size


def usage():
    print("Usage: scripts/stage_sam_voxel_semantics.py [min-votes]", file=sys.stderr)


def asset_url_to_path(url):
    return Path("public") / url


def capture_slug(config):
    return str(config.get("capture", "")).split(",", 1)[0].strip()


def mask_dir_for_capture(capture):
    root = Path("captures") / capture / "sam_masks"
    object_dir = root / "object"
    if object_dir.exists() and any(path.suffix.lower() == ".png" for path in object_dir.iterdir() if path.is_file()):
        return object_dir
    return root


def sparse_model_for_capture(capture):
    sparse_root = Path("captures") / capture / "colmap" / "sparse"
    candidates = [path for path in sparse_root.iterdir() if path.is_dir() and (path / "images.bin").exists() and (path / "cameras.bin").exists()]
    if not candidates:
        raise ValueError(f"No COLMAP sparse model found for {capture}")
    return max(candidates, key=lambda path: (path / "images.bin").stat().st_size)


def stage_scene(scene, min_votes):
    scene_path = Path("public") / scene["sceneUrl"]
    config = json.loads(scene_path.read_text(encoding="utf-8"))
    voxel_url = config.get("voxelGridUrl")
    if config.get("format") != "PLY Mesh" or not voxel_url:
        return None

    capture = capture_slug(config)
    scene_id = scene["id"]
    suffix = Path(voxel_url).stem.replace(f"{scene_id}-occupancy-", "")
    summary_json = Path("public/assets") / f"{scene_id}-sam-semantic-{suffix}.json"
    semantic_ply = Path("public/assets") / f"{scene_id}-sam-semantic-{suffix}.ply"
    mask_dir = mask_dir_for_capture(capture)
    sparse_model = sparse_model_for_capture(capture)
    masks = discover_masks(mask_dir) if mask_dir.exists() else {}
    if not masks:
        config.setdefault("metrics", {})["samSemanticVoxels"] = {
            "method": "sam-mask-multiview-projection",
            "status": "missing SAM masks",
            "maskDir": str(mask_dir),
            "inputContract": {
                "layoutA": "sam_masks/<label>/<frame_stem>.png",
                "layoutB": "sam_masks/<frame_stem>__<label>.png",
                "threshold": "mask pixel > 127",
            },
        }
        config.pop("samSemanticVoxelUrl", None)
        config.pop("samSemanticVoxelAssetUrl", None)
        scene_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return {
            "scene": scene_id,
            "capture": capture,
            "maskDir": str(mask_dir),
            "sparseModel": str(sparse_model),
            "status": "missing SAM masks",
            "nextAction": f"write SAM/SAM3 mask PNGs into {mask_dir}",
            "inputContract": config["metrics"]["samSemanticVoxels"]["inputContract"],
        }

    summary = create_sam_voxel_semantics(
        asset_url_to_path(voxel_url),
        sparse_model,
        mask_dir,
        summary_json,
        semantic_ply,
        min_votes,
    )

    config["samSemanticVoxelUrl"] = f"assets/{summary_json.name}"
    config["samSemanticVoxelAssetUrl"] = f"assets/{semantic_ply.name}"
    config.setdefault("metrics", {})["samSemanticVoxels"] = {
        "method": summary["method"],
        "status": summary["status"],
        "maskDir": str(mask_dir),
        "minVotes": min_votes,
        "maskFrames": summary["maskFrames"],
        "matchedMaskFrames": summary["matchedMaskFrames"],
        "maskFiles": summary["maskFiles"],
        "labeledVoxels": summary["labeledVoxels"],
        "surfaceVoxels": summary["surfaceVoxels"],
        "labelCoverage": summary["labelCoverage"],
        "labels": summary["labels"],
        "counts": summary["counts"],
    }
    if summary["status"] == "segmented":
        delivery = config.get("delivery", "")
        sam_delivery = f"SAM-mask semantic voxels {human_size(semantic_ply.stat().st_size)}"
        parts = [part.strip() for part in delivery.split(";") if part.strip() and "SAM-mask semantic voxels" not in part]
        parts.append(sam_delivery)
        config["delivery"] = "; ".join(parts)
    scene_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "scene": scene_id,
        "capture": capture,
        "maskDir": str(mask_dir),
        "sparseModel": str(sparse_model),
        "samSemanticVoxelUrl": config["samSemanticVoxelUrl"],
        "samSemanticVoxelAssetUrl": config["samSemanticVoxelAssetUrl"],
        "assetBytes": semantic_ply.stat().st_size if semantic_ply.exists() else 0,
        **summary,
    }


def main():
    if len(sys.argv) > 2:
        usage()
        return 1
    min_votes = int(sys.argv[1]) if len(sys.argv) == 2 else 1
    if min_votes <= 0:
        print("min-votes must be positive", file=sys.stderr)
        return 1
    manifest = json.loads(Path("public/scenes.json").read_text(encoding="utf-8"))
    staged = []
    for scene in manifest.get("scenes", []):
        if scene.get("primaryTarget") is True and scene.get("id", "").endswith("-openmvs"):
            row = stage_scene(scene, min_votes)
            if row:
                staged.append(row)
    report = {
        "strategy": "SAM/SAM3-level 2D masks projected into COLMAP/OpenMVS voxel space",
        "minVotes": min_votes,
        "scenes": staged,
    }
    Path("public/sam-voxel-semantics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
