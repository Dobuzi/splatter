#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ply_metrics import camera_for_metrics, mesh_metrics, public_metrics
from sample_ply_points import sample_point_cloud


VIDEO_EXTS = {".mov", ".mp4", ".m4v"}


def slug_for_input(path):
    stem = path.stem.lower()
    if stem.startswith("img_"):
        stem = "img-" + stem[4:]
    elif re.match(r"^\d{4}-\d{2}-\d{2}-", stem):
        stem = "video-" + stem.replace("-", "")
        stem = stem[:14] + "-" + stem[14:20] + "-" + stem[20:]
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return slug


def usage():
    print("Usage: scripts/openmvs_batch.py <input-dir>", file=sys.stderr)


def analyze_model(model_dir):
    proc = subprocess.run(
        ["colmap", "model_analyzer", "--path", str(model_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    metrics = {"registered": 0, "points": 0, "error": 999.0}
    for line in proc.stdout.splitlines():
        if "Registered images:" in line:
            match = re.search(r"Registered images:\s*(\d+)", line)
            if match:
                metrics["registered"] = int(match.group(1))
        elif "Points:" in line:
            match = re.search(r"Points:\s*(\d+)", line)
            if match:
                metrics["points"] = int(match.group(1))
        elif "Mean reprojection error:" in line:
            match = re.search(r"Mean reprojection error:\s*([0-9.]+)\s*px", line)
            if match:
                metrics["error"] = float(match.group(1))
    return metrics


def best_model(capture_dir):
    sparse_dir = capture_dir / "colmap" / "sparse"
    if not sparse_dir.is_dir():
        return None
    best = None
    for model_dir in sorted(path for path in sparse_dir.iterdir() if path.is_dir()):
        metrics = analyze_model(model_dir)
        metrics["model"] = model_dir.name
        if best is None or (
            metrics["registered"],
            metrics["points"],
            -metrics["error"],
        ) > (
            best["registered"],
            best["points"],
            -best["error"],
        ):
            best = metrics
    return best


def capture_candidates(slug):
    captures_root = Path("captures")
    if not captures_root.is_dir():
        return []

    candidates = []
    for capture_dir in sorted(path for path in captures_root.iterdir() if path.is_dir()):
        name = capture_dir.name
        if (
            name == slug
            or name.startswith(f"{slug}-fps")
            or name.startswith(f"{slug}-seg")
            or name.startswith(f"{slug}-selected")
        ):
            candidates.append(capture_dir)
    return candidates


def score_candidate(capture_dir, model):
    frame_count = len(list((capture_dir / "images").glob("*.jpg")))
    ratio = model["registered"] / frame_count if frame_count else 0.0
    points_per_registered = model["points"] / model["registered"] if model["registered"] else 0.0
    score = (
        model["registered"] * 100.0
        + ratio * 1000.0
        + model["points"] / 100.0
        + points_per_registered
        - model["error"] * 120.0
    )
    return {
        "capture": capture_dir.name,
        "model": model["model"],
        "frames": frame_count,
        "registered": model["registered"],
        "ratio": round(ratio, 4),
        "points": model["points"],
        "points_per_registered": round(points_per_registered, 2),
        "reprojection_error": model["error"],
        "score": round(score, 2),
    }


def file_size(path):
    return path.stat().st_size if path.is_file() else 0


def human_size(bytes_count):
    if bytes_count >= 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    if bytes_count >= 1024:
        return f"{bytes_count / 1024:.1f} KB"
    return f"{bytes_count} B"


def ply_counts(path):
    if not path.is_file():
        return {"vertices": 0, "faces": 0}
    counts = {"vertices": 0, "faces": 0}
    with path.open("rb") as handle:
        for raw in handle:
            line = raw.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex "):
                counts["vertices"] = int(line.rsplit(" ", 1)[1])
            elif line.startswith("element face "):
                counts["faces"] = int(line.rsplit(" ", 1)[1])
            elif line == "end_header":
                break
    return counts


def stage_dense_point_cloud(row, dense_path, assets_dir):
    if not dense_path.is_file():
        return None
    max_points = int(os_environ().get("SPLAT_DENSE_POINTCLOUD_MAX_POINTS", "200000"))
    dense_asset_name = f"{row['input_slug']}-openmvs-scene_dense_points.ply"
    dense_asset_path = assets_dir / dense_asset_name
    report = sample_point_cloud(dense_path, dense_asset_path, max_points)
    row["denseAssetUrl"] = f"assets/{dense_asset_name}"
    row["denseAssetBytes"] = file_size(dense_asset_path)
    row["densePointCloud"] = {
        "points": report["points"],
        "maxPoints": report["maxPoints"],
        "source": dense_path.name,
    }
    return row["denseAssetUrl"]


def scene_id_for(input_slug):
    return f"{input_slug}-openmvs"


def stage_scene(row):
    openmvs_dir = Path("captures") / row["capture"] / "openmvs"
    mesh_path = openmvs_dir / "scene_textured.ply"
    texture_path = openmvs_dir / "scene_textured0.png"
    asset_kind = "textured mesh"
    if not mesh_path.is_file() or not texture_path.is_file():
        mesh_path = openmvs_dir / "scene_refined.ply"
        texture_path = None
        asset_kind = "refined mesh"
    if not mesh_path.is_file():
        mesh_path = openmvs_dir / "scene_mesh.ply"
        asset_kind = "mesh"
    dense_path = openmvs_dir / "scene_dense.ply"
    if not mesh_path.is_file():
        row["stage_status"] = "missing mesh"
        return

    assets_dir = Path("public/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_name = f"{row['input_slug']}-openmvs-{mesh_path.name}"
    asset_path = assets_dir / asset_name
    shutil.copyfile(mesh_path, asset_path)
    row["assetUrl"] = f"assets/{asset_name}"
    row["assetBytes"] = file_size(asset_path)
    row["meshAssetKind"] = asset_kind

    texture_asset_url = None
    if texture_path and texture_path.is_file():
        texture_asset_name = f"{row['input_slug']}-openmvs-{texture_path.name}"
        texture_asset_path = assets_dir / texture_asset_name
        shutil.copyfile(texture_path, texture_asset_path)
        texture_asset_url = f"assets/{texture_asset_name}"
        row["textureAssetUrl"] = texture_asset_url
        row["textureAssetBytes"] = file_size(texture_asset_path)

    stage_dense = os_environ().get("SPLAT_STAGE_DENSE_POINTCLOUD", "1") == "1"
    dense_asset_url = None
    if stage_dense:
        dense_asset_url = stage_dense_point_cloud(row, dense_path, assets_dir)

    metrics = mesh_metrics(mesh_path)
    row["meshVertices"] = metrics["vertices"]
    row["meshFaces"] = metrics["faces"]
    row["meshMetrics"] = public_metrics(metrics)

    scene_dir = Path("public/scenes") / scene_id_for(row["input_slug"])
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_config = {
        "title": f"{row['input']} OpenMVS Mesh",
        "assetUrl": row["assetUrl"],
        "format": "PLY Mesh",
        "fileSize": human_size(row["assetBytes"]),
        "capture": f"{row['capture']}, {row['frames']} frames, {row['registered']} COLMAP images",
        "training": f"OpenMVS CPU dense, {row.get('densePoints', 0)} dense points, {row['meshVertices']} vertices, {row['meshFaces']} faces",
        "delivery": f"{asset_kind.title()} {human_size(row['assetBytes'])}; dense point cloud {human_size(row.get('denseAssetBytes', 0)) if dense_asset_url else 'kept in captures'}",
        "viewer": {
            "background": [0.02, 0.025, 0.03],
            "fov": 42,
            "meshColor": [0.72, 0.78, 0.84],
        },
        "transform": {
            "pivot": [0, 0, 0],
            "position": [0, 0, 0],
            "rotation": [0, 0, 0],
            "scale": [1, -1, 1],
        },
        "camera": camera_for_metrics(metrics),
        "metrics": row["meshMetrics"],
    }
    if texture_asset_url:
        scene_config["textureAssetUrl"] = texture_asset_url
    if dense_asset_url:
        scene_config["pointCloudAssetUrl"] = dense_asset_url
        scene_config["metrics"]["pointCloud"] = row["densePointCloud"]
    (scene_dir / "scene.json").write_text(json.dumps(scene_config, indent=2) + "\n", encoding="utf-8")
    row["sceneUrl"] = f"scenes/{scene_id_for(row['input_slug'])}/scene.json"
    row["stage_status"] = "staged"


def update_manifest(rows):
    manifest_path = Path("public/scenes.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"scenes": []}
    scenes = [scene for scene in manifest.get("scenes", []) if not scene.get("id", "").endswith("-openmvs")]
    for row in rows:
        if row.get("stage_status") != "staged":
            continue
        scenes.append(
            {
                "id": scene_id_for(row["input_slug"]),
                "input": row["input"],
                "label": f"{row['input']} OpenMVS Mesh",
                "sceneUrl": row["sceneUrl"],
            }
        )
    manifest["scenes"] = scenes
    if not manifest.get("defaultScene") and scenes:
        manifest["defaultScene"] = scenes[0]["id"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run_openmvs(row):
    openmvs_dir = Path("captures") / row["capture"] / "openmvs"
    if os_environ().get("SPLAT_OPENMVS_SKIP_RUN") == "1" and (openmvs_dir / "scene_dense.ply").is_file():
        row["openmvs_exit_code"] = 0
        row["openmvs_log_tail"] = "Skipped OpenMVS run; reused existing openmvs outputs."
        return True

    env = dict(**os_environ())
    env["SPLAT_SURFACE_BACKEND"] = "openmvs"
    env.setdefault("COLMAP_DENSE_MAX_IMAGE_SIZE", "640")
    env.setdefault("COLMAP_NUM_THREADS", "4")
    env.setdefault("SPLAT_OPENMVS_BIN_DIR", ".local/vcpkg/installed/arm64-osx/tools/openmvs")
    proc = subprocess.run(
        ["bin/splatter", "surface-reconstruct", row["capture"], row["model"]],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    row["openmvs_log_tail"] = "\n".join(proc.stdout.splitlines()[-20:])
    row["openmvs_exit_code"] = proc.returncode
    return proc.returncode == 0


def os_environ():
    import os

    return os.environ.copy()


def main():
    if len(sys.argv) != 2:
        usage()
        return 1
    input_dir = Path(sys.argv[1])
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1
    if not shutil.which("colmap"):
        print("COLMAP is required for OpenMVS input ranking.", file=sys.stderr)
        return 1

    rows = []
    for input_path in sorted(path for path in input_dir.iterdir() if path.suffix.lower() in VIDEO_EXTS):
        input_slug = slug_for_input(input_path)
        ranked = []
        for capture_dir in capture_candidates(input_slug):
            model = best_model(capture_dir)
            if model:
                ranked.append(score_candidate(capture_dir, model))
        ranked.sort(key=lambda row: row["score"], reverse=True)
        if not ranked:
            rows.append({"input": input_path.name, "input_slug": input_slug, "status": "no capture"})
            continue
        row = ranked[0]
        row["input"] = input_path.name
        row["input_slug"] = input_slug
        row["alternates"] = ranked[1:5]
        if run_openmvs(row):
            dense_counts = ply_counts(Path("captures") / row["capture"] / "openmvs" / "scene_dense.ply")
            row["densePoints"] = dense_counts["vertices"]
            stage_scene(row)
        else:
            row["status"] = "openmvs failed"
        rows.append(row)

    rows.sort(key=lambda row: row.get("score", -1), reverse=True)
    update_manifest(rows)
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    report = {"inputDir": str(input_dir), "ranked": rows}
    (output_dir / "openmvs-ranking.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    public_rows = [
        {
            key: row.get(key)
            for key in [
                "input",
                "input_slug",
                "capture",
                "model",
                "frames",
                "registered",
                "ratio",
                "points",
                "score",
                "densePoints",
                "meshVertices",
                "meshFaces",
                "meshMetrics",
                "meshAssetKind",
                "assetUrl",
                "textureAssetUrl",
                "denseAssetUrl",
                "densePointCloud",
                "sceneUrl",
                "stage_status",
            ]
            if key in row
        }
        for row in rows
    ]
    Path("public/openmvs-ranking.json").write_text(
        json.dumps({"inputDir": str(input_dir), "ranked": public_rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
