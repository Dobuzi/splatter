#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from openmvs_batch import capture_candidates, primary_input_slugs, scene_id_for, slug_for_input


VIDEO_EXTS = {".mov", ".mp4", ".m4v"}


def usage():
    print("Usage: scripts/pipeline_manifest.py <input-dir> [output-json]", file=sys.stderr)


def read_json(path, fallback=None):
    if not Path(path).is_file():
        return fallback
    return json.loads(Path(path).read_text(encoding="utf-8"))


def asset_size(asset_url):
    if not asset_url:
        return 0
    path = Path("public") / asset_url
    return path.stat().st_size if path.is_file() else 0


def stage_status(row, input_slug):
    scene_url = row.get("sceneUrl") if row else f"scenes/{scene_id_for(input_slug)}/scene.json"
    scene_path = Path("public") / scene_url
    scene = read_json(scene_path, {})
    return {
        "sceneUrl": scene_url if scene_path.is_file() else None,
        "assetUrl": scene.get("assetUrl") or (row or {}).get("assetUrl"),
        "pointCloudAssetUrl": scene.get("pointCloudAssetUrl") or (row or {}).get("denseAssetUrl"),
        "textureAssetUrl": scene.get("textureAssetUrl") or (row or {}).get("textureAssetUrl"),
        "assetBytes": asset_size(scene.get("assetUrl") or (row or {}).get("assetUrl")),
        "pointCloudBytes": asset_size(scene.get("pointCloudAssetUrl") or (row or {}).get("denseAssetUrl")),
        "quality": scene.get("quality", {}),
    }


def build_manifest(input_dir):
    input_dir = Path(input_dir)
    ranking = read_json("public/openmvs-ranking.json", {"ranked": []}).get("ranked", [])
    ranked_by_slug = {row.get("input_slug"): row for row in ranking}
    primary_slugs = primary_input_slugs()
    inputs = []

    for input_path in sorted(path for path in input_dir.iterdir() if path.suffix.lower() in VIDEO_EXTS):
        input_slug = slug_for_input(input_path)
        row = ranked_by_slug.get(input_slug)
        captures = [path.name for path in capture_candidates(input_slug)]
        staged = stage_status(row, input_slug)
        inputs.append(
            {
                "input": input_path.name,
                "inputSlug": input_slug,
                "primaryTarget": input_slug in primary_slugs,
                "captures": captures,
                "selectedCapture": row.get("capture") if row else None,
                "selectedModel": row.get("model") if row else None,
                "stageStatus": row.get("stage_status") if row else "not staged",
                "score": row.get("score") if row else None,
                "registrationRatio": row.get("ratio") if row else None,
                "densePoints": row.get("densePoints") if row else None,
                "meshFaces": row.get("meshFaces") if row else None,
                "staged": staged,
                "nextActions": next_actions(row, staged, input_slug in primary_slugs),
            }
        )

    inputs.sort(key=lambda item: (0 if item["primaryTarget"] else 1, item["inputSlug"]))
    return {
        "schemaVersion": 1,
        "inputDir": str(input_dir),
        "primaryTargets": primary_slugs,
        "stages": [
            "capture variants",
            "COLMAP ranking",
            "OpenMVS dense/mesh",
            "largest-component cleanup",
            "viewer staging",
            "QA/deploy gates",
            "optional TRELLIS.2 branch",
        ],
        "inputs": inputs,
    }


def next_actions(row, staged, primary):
    actions = []
    if not row:
        actions.append("create capture variants and run COLMAP")
        return actions
    if row.get("stage_status") != "staged":
        actions.append("run openmvs-batch")
    if primary and staged.get("quality", {}).get("primaryTarget") is not True:
        actions.append("restage primary target metadata")
    if not staged.get("pointCloudAssetUrl"):
        actions.append("stage dense point cloud")
    if not actions:
        actions.append("ready")
    return actions


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1
    manifest = build_manifest(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
