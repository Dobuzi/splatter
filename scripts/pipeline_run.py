#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

from pipeline_manifest import build_manifest


def usage():
    print("Usage: scripts/pipeline_run.py <input-dir>", file=sys.stderr)


def run_command(args, env=None):
    proc = subprocess.run(args, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return {"args": args, "exitCode": proc.returncode, "logTail": "\n".join(proc.stdout.splitlines()[-20:])}


def write_manifest(input_dir):
    manifest = build_manifest(input_dir)
    output_path = Path("public/pipeline-manifest.json")
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    if len(sys.argv) != 2:
        usage()
        return 1

    input_dir = sys.argv[1]
    execute = os.environ.get("SPLAT_PIPELINE_EXECUTE", "0") == "1"
    report = {
        "inputDir": input_dir,
        "execute": execute,
        "steps": [],
    }

    before = write_manifest(input_dir)
    report["before"] = {
        "primaryTargets": before["primaryTargets"],
        "inputs": [
            {
                "inputSlug": item["inputSlug"],
                "primaryTarget": item["primaryTarget"],
                "stageStatus": item["stageStatus"],
                "nextActions": item["nextActions"],
            }
            for item in before["inputs"]
        ],
    }

    if execute:
        env = os.environ.copy()
        env.setdefault("SPLAT_OPENMVS_SKIP_RUN", "1")
        report["steps"].append(run_command(["bin/splatter", "openmvs-batch", input_dir], env=env))
        if report["steps"][-1]["exitCode"] != 0:
            print(json.dumps(report, indent=2))
            return report["steps"][-1]["exitCode"]
        after = write_manifest(input_dir)
    else:
        report["steps"].append(
            {
                "args": ["bin/splatter", "openmvs-batch", input_dir],
                "executeWith": "SPLAT_PIPELINE_EXECUTE=1",
                "envDefaults": {"SPLAT_OPENMVS_SKIP_RUN": "1"},
            }
        )
        after = before

    report["after"] = {
        "manifest": "public/pipeline-manifest.json",
        "primaryReady": [
            item["inputSlug"]
            for item in after["inputs"]
            if item["primaryTarget"] and item["stageStatus"] == "staged" and item["nextActions"] == ["ready"]
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
