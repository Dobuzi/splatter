#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

from ply_metrics import mesh_metrics


def usage():
    print("Usage: scripts/openmvs_validate.py", file=sys.stderr)


def scene_configs():
    manifest = json.loads(Path("public/scenes.json").read_text(encoding="utf-8"))
    for scene in manifest.get("scenes", []):
        scene_path = Path("public") / scene["sceneUrl"]
        if scene_path.is_file():
            config = json.loads(scene_path.read_text(encoding="utf-8"))
            if config.get("format") == "PLY Mesh":
                yield scene, scene_path, config


def distance(left, right):
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def validate_scene(scene, scene_path, config):
    asset_path = Path("public") / config["assetUrl"]
    metrics = mesh_metrics(asset_path)
    center = metrics["bbox"]["center"]
    diagonal = max(metrics["bbox"]["diagonal"], 1.0)
    camera = config.get("camera", {})
    target = camera.get("target", [0, 0, 0])
    position = camera.get("position", [0, 0, 0])
    camera_distance = distance(target, position)
    texture_url = config.get("textureAssetUrl")
    texture_ok = not texture_url or (Path("public") / texture_url).is_file()
    issues = []

    if metrics["vertices"] <= 0 or metrics["faces"] <= 0:
        issues.append("empty mesh")
    if distance(center, target) > diagonal * 0.05:
        issues.append("camera target is not centered on mesh bbox")
    if camera_distance < diagonal * 0.75:
        issues.append("camera distance is too close for bbox diagonal")
    if metrics["largestComponentRatio"] < 0.7:
        issues.append("largest connected component is below 70% of used vertices")
    if metrics["degenerateFaceRatio"] > 0.01:
        issues.append("degenerate face ratio exceeds 1%")
    if texture_url and not metrics["hasTexcoords"]:
        issues.append("texture asset present but mesh has no UVs")
    if not texture_ok:
        issues.append("texture asset missing")

    return {
        "id": scene["id"],
        "scene": str(scene_path),
        "asset": config["assetUrl"],
        "textureAsset": texture_url,
        "vertices": metrics["vertices"],
        "faces": metrics["faces"],
        "bbox": metrics["bbox"],
        "componentCount": metrics["componentCount"],
        "largestComponentRatio": round(metrics["largestComponentRatio"], 4),
        "degenerateFaceRatio": round(metrics["degenerateFaceRatio"], 6),
        "cameraDistance": round(camera_distance, 4),
        "status": "pass" if not issues else "warn",
        "issues": issues,
    }


def main():
    if len(sys.argv) != 1:
        usage()
        return 1
    rows = [validate_scene(scene, scene_path, config) for scene, scene_path, config in scene_configs()]
    report = {
        "summary": {
            "scenes": len(rows),
            "pass": sum(row["status"] == "pass" for row in rows),
            "warn": sum(row["status"] == "warn" for row in rows),
        },
        "scenes": rows,
    }
    output_path = Path("public/openmvs-validation.json")
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
