#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def usage():
    print("Usage: scripts/trellis2_adapter.py <image-or-frame> [output-dir]", file=sys.stderr)


def command_for(input_path, output_dir):
    remote_command = os.environ.get("TRELLIS2_REMOTE_COMMAND", "").strip()
    if not remote_command:
        return None
    return shlex.split(remote_command) + [str(input_path), str(output_dir)]


def main():
    if len(sys.argv) not in (2, 3):
        usage()
        return 1

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else Path("output/trellis2") / input_path.stem
    execute = os.environ.get("SPLAT_TRELLIS2_EXECUTE", "0") == "1"
    command = command_for(input_path, output_dir)
    report = {
        "input": str(input_path),
        "outputDir": str(output_dir),
        "execute": execute,
        "backend": "trellis2-remote",
        "status": "planned",
        "requirements": {
            "system": "Linux",
            "gpu": "NVIDIA CUDA GPU with at least 24GB VRAM recommended by upstream",
            "model": "microsoft/TRELLIS.2-4B",
        },
        "integrationUse": [
            "optional generated-asset branch",
            "compare against OpenMVS reconstruction",
            "not a replacement for COLMAP/OpenMVS real camera-space reconstruction",
        ],
    }

    if not input_path.exists():
        report["status"] = "missing input"
        print(json.dumps(report, indent=2))
        return 2

    if not command:
        report["status"] = "remote command not configured"
        report["configure"] = "Set TRELLIS2_REMOTE_COMMAND to a wrapper that accepts: <input-image> <output-dir>"
        report["exampleWrapper"] = "ssh trellis-host /opt/trellis2/run_image_to_3d.sh"
        print(json.dumps(report, indent=2))
        return 0

    report["command"] = command
    if execute:
        output_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        report["exitCode"] = proc.returncode
        report["logTail"] = "\n".join(proc.stdout.splitlines()[-40:])
        report["status"] = "completed" if proc.returncode == 0 else "failed"
        print(json.dumps(report, indent=2))
        return proc.returncode

    report["status"] = "ready to execute"
    report["executeWith"] = "SPLAT_TRELLIS2_EXECUTE=1"
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
