#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

from ply_metrics import mesh_metrics


VARIANTS = [
    {
        "name": "fast",
        "COLMAP_DENSE_MAX_IMAGE_SIZE": "640",
        "SPLAT_OPENMVS_RESOLUTION_LEVEL": "2",
        "SPLAT_OPENMVS_NUMBER_VIEWS": "5",
        "SPLAT_OPENMVS_NUMBER_VIEWS_FUSE": "3",
        "SPLAT_OPENMVS_REFINE_DECIMATE": "0",
        "SPLAT_OPENMVS_TEXTURE_SIZE": "2048",
    },
    {
        "name": "balanced",
        "COLMAP_DENSE_MAX_IMAGE_SIZE": "640",
        "SPLAT_OPENMVS_RESOLUTION_LEVEL": "1",
        "SPLAT_OPENMVS_NUMBER_VIEWS": "5",
        "SPLAT_OPENMVS_NUMBER_VIEWS_FUSE": "3",
        "SPLAT_OPENMVS_REFINE_DECIMATE": "0",
        "SPLAT_OPENMVS_TEXTURE_SIZE": "4096",
    },
    {
        "name": "detail",
        "COLMAP_DENSE_MAX_IMAGE_SIZE": "960",
        "SPLAT_OPENMVS_RESOLUTION_LEVEL": "1",
        "SPLAT_OPENMVS_NUMBER_VIEWS": "7",
        "SPLAT_OPENMVS_NUMBER_VIEWS_FUSE": "3",
        "SPLAT_OPENMVS_REFINE_DECIMATE": "1",
        "SPLAT_OPENMVS_TEXTURE_SIZE": "4096",
    },
]


def usage():
    print("Usage: scripts/openmvs_sweep.py <capture> [model]", file=sys.stderr)


def score(metrics, asset_bytes):
    component_penalty = max(metrics["componentCount"] - 1, 0) * 250.0
    degenerate_penalty = metrics["degenerateFaceRatio"] * 10000.0
    size_penalty = asset_bytes / (1024 * 1024) * 2.0
    return round(
        metrics["faces"] / 1000.0
        + metrics["largestComponentRatio"] * 100.0
        + (10.0 if metrics["hasTexcoords"] else 0.0)
        - component_penalty
        - degenerate_penalty
        - size_penalty,
        2,
    )


def run_variant(capture, model, variant):
    env = os.environ.copy()
    env["SPLAT_SURFACE_BACKEND"] = "openmvs"
    env.setdefault("SPLAT_OPENMVS_BIN_DIR", ".local/vcpkg/installed/arm64-osx/tools/openmvs")
    env.setdefault("COLMAP_NUM_THREADS", "4")
    for key, value in variant.items():
        if key != "name":
            env[key] = value
    env["SPLAT_OPENMVS_OUTPUT_SUFFIX"] = f"-sweep-{variant['name']}"
    openmvs_dir = Path("captures") / capture / f"openmvs-sweep-{variant['name']}"
    mesh_path = openmvs_dir / "scene_textured.ply"
    if not mesh_path.is_file():
        mesh_path = openmvs_dir / "scene_refined.ply"

    if os.environ.get("SPLAT_OPENMVS_SWEEP_REUSE", "1") == "1" and mesh_path.is_file():
        metrics = mesh_metrics(mesh_path)
        return {
            "variant": variant["name"],
            "settings": {key: value for key, value in variant.items() if key != "name"},
            "exitCode": 0,
            "logTail": "Reused existing sweep output.",
            "mesh": str(mesh_path),
            "assetBytes": mesh_path.stat().st_size,
            "vertices": metrics["vertices"],
            "faces": metrics["faces"],
            "componentCount": metrics["componentCount"],
            "largestComponentRatio": metrics["largestComponentRatio"],
            "degenerateFaceRatio": metrics["degenerateFaceRatio"],
            "hasTexcoords": metrics["hasTexcoords"],
            "score": score(metrics, mesh_path.stat().st_size),
        }

    proc = subprocess.run(
        ["bin/splatter", "surface-reconstruct", capture, model],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    mesh_path = openmvs_dir / "scene_textured.ply"
    if not mesh_path.is_file():
        mesh_path = openmvs_dir / "scene_refined.ply"

    row = {
        "variant": variant["name"],
        "settings": {key: value for key, value in variant.items() if key != "name"},
        "exitCode": proc.returncode,
        "logTail": "\n".join(proc.stdout.splitlines()[-20:]),
    }
    if mesh_path.is_file():
        metrics = mesh_metrics(mesh_path)
        row.update(
            {
                "mesh": str(mesh_path),
                "assetBytes": mesh_path.stat().st_size,
                "vertices": metrics["vertices"],
                "faces": metrics["faces"],
                "componentCount": metrics["componentCount"],
                "largestComponentRatio": metrics["largestComponentRatio"],
                "degenerateFaceRatio": metrics["degenerateFaceRatio"],
                "hasTexcoords": metrics["hasTexcoords"],
                "score": score(metrics, mesh_path.stat().st_size),
            }
        )
    else:
        row["score"] = -9999
    return row


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1
    capture = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) == 3 else "best"
    selected_names = [
        name.strip()
        for name in os.environ.get("SPLAT_OPENMVS_SWEEP_VARIANTS", "").split(",")
        if name.strip()
    ]
    variants = [variant for variant in VARIANTS if not selected_names or variant["name"] in selected_names]
    if not variants:
        print(f"No OpenMVS variants selected: {selected_names}", file=sys.stderr)
        return 1

    if os.environ.get("SPLAT_OPENMVS_SWEEP_DRY_RUN") == "1":
        print(json.dumps({"capture": capture, "model": model, "variants": variants}, indent=2))
        return 0

    rows = [run_variant(capture, model, variant) for variant in variants]
    rows.sort(key=lambda row: row["score"], reverse=True)
    report = {"capture": capture, "model": model, "ranked": rows}
    output_path = Path("public") / f"openmvs-sweep-{capture}.json"
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if rows and rows[0]["score"] > -9999 else 2


if __name__ == "__main__":
    raise SystemExit(main())
