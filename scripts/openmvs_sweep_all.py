#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from openmvs_batch import (
    VIDEO_EXTS,
    best_model,
    capture_candidates,
    score_candidate,
    slug_for_input,
)


def usage():
    print("Usage: scripts/openmvs_sweep_all.py <input-dir>", file=sys.stderr)


def best_rows(input_dir):
    rows = []
    for input_path in sorted(path for path in input_dir.iterdir() if path.suffix.lower() in VIDEO_EXTS):
        input_slug = slug_for_input(input_path)
        ranked = []
        for capture_dir in capture_candidates(input_slug):
            model = best_model(capture_dir)
            if model:
                ranked.append(score_candidate(capture_dir, model))
        ranked.sort(key=lambda row: row["score"], reverse=True)
        if ranked:
            row = ranked[0]
            row["input"] = input_path.name
            row["input_slug"] = input_slug
            rows.append(row)
        else:
            rows.append({"input": input_path.name, "input_slug": input_slug, "status": "no capture"})
    return rows


def apply_best_sweep(row, sweep_report):
    ranked = sweep_report.get("ranked", [])
    if not ranked or ranked[0].get("score", -9999) <= -9999:
        row["sweepApplyStatus"] = "no successful variant"
        return
    variant = ranked[0]["variant"]
    source_dir = Path("captures") / row["capture"] / f"openmvs-sweep-{variant}"
    target_dir = Path("captures") / row["capture"] / "openmvs"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ["scene_textured.ply", "scene_textured0.png", "scene_refined.ply", "scene_mesh.ply", "scene_dense.ply", "scene_dense.mvs", "scene.mvs"]:
        source = source_dir / name
        if source.is_file():
            shutil.copyfile(source, target_dir / name)
            copied.append(name)
    row["sweepWinner"] = variant
    row["sweepWinnerScore"] = ranked[0]["score"]
    row["sweepApplyStatus"] = f"copied {', '.join(copied)}"


def run_sweep(row):
    report_path = Path("public") / f"openmvs-sweep-{row['capture']}.json"
    reuse = os.environ.get("SPLAT_OPENMVS_SWEEP_REUSE", "1") == "1"
    if reuse and report_path.is_file():
        return json.loads(report_path.read_text(encoding="utf-8"))
    env = os.environ.copy()
    if row.get("frames", 0) > int(os.environ.get("SPLAT_OPENMVS_DETAIL_FRAME_LIMIT", "160")):
        env.setdefault("SPLAT_OPENMVS_SWEEP_VARIANTS", "fast,balanced")
    proc = subprocess.run(
        ["bin/splatter", "openmvs-sweep", row["capture"], row["model"]],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    row["sweepLogTail"] = "\n".join(proc.stdout.splitlines()[-20:])
    row["sweepExitCode"] = proc.returncode
    if not report_path.is_file():
        return {"capture": row["capture"], "ranked": [], "error": "sweep report missing"}
    return json.loads(report_path.read_text(encoding="utf-8"))


def main():
    if len(sys.argv) != 2:
        usage()
        return 1
    input_dir = Path(sys.argv[1])
    if os.environ.get("SPLAT_OPENMVS_SWEEP_ALL_DRY_RUN") == "1":
        candidates = best_rows(input_dir) if input_dir.is_dir() else []
        print(json.dumps({"inputDir": str(input_dir), "candidates": candidates}, indent=2))
        return 0
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    rows = best_rows(input_dir)
    for row in rows:
        if row.get("status"):
            continue
        sweep_report = run_sweep(row)
        row["sweepReport"] = f"public/openmvs-sweep-{row['capture']}.json"
        row["sweepRanked"] = [
            {
                key: variant.get(key)
                for key in ["variant", "score", "vertices", "faces", "assetBytes", "componentCount", "largestComponentRatio"]
                if key in variant
            }
            for variant in sweep_report.get("ranked", [])
        ]
        apply_best_sweep(row, sweep_report)

    env = os.environ.copy()
    env["SPLAT_OPENMVS_SKIP_RUN"] = "1"
    env["SPLAT_STAGE_DENSE_POINTCLOUD"] = "1"
    subprocess.run(["bin/splatter", "openmvs-batch", str(input_dir)], env=env, check=True)

    report = {"inputDir": str(input_dir), "ranked": rows}
    output = Path("public/openmvs-sweep-all.json")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
