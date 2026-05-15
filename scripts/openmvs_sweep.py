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

    proc = subprocess.run(
        ["bin/splatter", "surface-reconstruct", capture, model],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    openmvs_dir = Path("captures") / capture / f"openmvs-sweep-{variant['name']}"
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
    if os.environ.get("SPLAT_OPENMVS_SWEEP_DRY_RUN") == "1":
        print(json.dumps({"capture": capture, "model": model, "variants": VARIANTS}, indent=2))
        return 0

    rows = [run_variant(capture, model, variant) for variant in VARIANTS]
    rows.sort(key=lambda row: row["score"], reverse=True)
    report = {"capture": capture, "model": model, "ranked": rows}
    output_path = Path("public") / f"openmvs-sweep-{capture}.json"
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if rows and rows[0]["score"] > -9999 else 2


if __name__ == "__main__":
    raise SystemExit(main())
