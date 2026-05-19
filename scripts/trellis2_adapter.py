#!/usr/bin/env python3
import json
import os
import platform
import shlex
import subprocess
import sys
from importlib import metadata, util
from pathlib import Path


def usage():
    print("Usage: scripts/trellis2_adapter.py [--check] <image-or-frame> [output-dir]", file=sys.stderr)


def module_available(name):
    return util.find_spec(name) is not None


def torch_status():
    try:
        import torch
    except Exception as exc:
        return {"available": False, "error": str(exc), "cuda": False, "mps": False}
    return {
        "available": True,
        "version": getattr(torch, "__version__", "unknown"),
        "cuda": bool(torch.cuda.is_available()),
        "mps": bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available()),
    }


def mlx_status():
    try:
        version = metadata.version("mlx")
    except Exception:
        version = None
    return {
        "available": module_available("mlx"),
        "version": version,
        "usableForTrellis2": False,
        "reason": "TRELLIS.2 is PyTorch/CUDA-based upstream; MLX would require a model/runtime port.",
    }


def environment_report():
    torch = torch_status()
    mlx = mlx_status()
    return {
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "pythonModules": {
            "torch": torch,
            "mlx": mlx,
            "nvdiffrast": module_available("nvdiffrast"),
            "o_voxel": module_available("o_voxel"),
        },
        "upstreamReadme": {
            "imageTo3D": "README examples construct TrellisImageTo3DPipeline and call pipeline.cuda(); upstream requirements recommend an NVIDIA GPU with at least 24GB VRAM.",
            "cpuMention": "The README's Single CPU note applies to Textured Mesh -> O-Voxel dataset conversion, not to image-to-3D model inference.",
        },
        "localImageTo3D": {
            "possible": bool(platform.system() == "Linux" and torch.get("cuda")),
            "reason": "requires Linux/CUDA PyTorch runtime for the upstream image-to-3D pipeline",
        },
        "mlxAcceleration": {
            "possibleNow": False,
            "role": "capture triage, frame quality scoring, mask/depth helper models after separate MLX ports",
            "notSupportedFor": "direct acceleration of upstream TRELLIS.2 PyTorch/CUDA pipeline",
        },
    }


def command_for(input_path, output_dir, backend):
    command_name = "TRELLIS2_LOCAL_COMMAND" if backend == "local" else "TRELLIS2_REMOTE_COMMAND"
    configured = os.environ.get(command_name, "").strip()
    if not configured:
        return None
    return shlex.split(configured) + [str(input_path), str(output_dir)]


def selected_backend():
    backend = os.environ.get("TRELLIS2_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "local", "remote"}:
        raise ValueError("TRELLIS2_BACKEND must be auto, local, or remote")
    if backend != "auto":
        return backend
    if os.environ.get("TRELLIS2_LOCAL_COMMAND", "").strip():
        return "local"
    return "remote"


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        print(json.dumps({"backend": "trellis2-preflight", **environment_report()}, indent=2))
        return 0

    if len(sys.argv) not in (2, 3):
        usage()
        return 1

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else Path("output/trellis2") / input_path.stem
    execute = os.environ.get("SPLAT_TRELLIS2_EXECUTE", "0") == "1"
    try:
        backend = selected_backend()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    command = command_for(input_path, output_dir, backend)
    report = {
        "input": str(input_path),
        "outputDir": str(output_dir),
        "execute": execute,
        "backend": f"trellis2-{backend}",
        "status": "planned",
        "environment": environment_report(),
        "requirements": {
            "imageTo3D": "Linux + CUDA PyTorch runtime; upstream README examples call pipeline.cuda()",
            "cpuOnly": "README CPU note is for Textured Mesh -> O-Voxel conversion, not image-to-3D inference",
            "gpu": "NVIDIA CUDA GPU with at least 24GB VRAM recommended by upstream for TRELLIS.2-4B",
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
        report["status"] = f"{backend} command not configured"
        report["configure"] = f"Set TRELLIS2_{backend.upper()}_COMMAND to a wrapper that accepts: <input-image> <output-dir>"
        report["exampleWrapper"] = (
            "python /opt/trellis2/run_image_to_3d.py"
            if backend == "local"
            else "ssh trellis-host /opt/trellis2/run_image_to_3d.sh"
        )
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
