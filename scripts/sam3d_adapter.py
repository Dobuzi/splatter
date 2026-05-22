#!/usr/bin/env python3
import json
import os
import platform
import shlex
import subprocess
import sys
from importlib import metadata, util
from pathlib import Path


MASK_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def usage():
    print("Usage: scripts/sam3d_adapter.py [--check] <image-or-frame> <mask-dir> [output-dir]", file=sys.stderr)


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
        "usableForSam3dObjects": False,
        "reason": "SAM 3D Objects is distributed as a PyTorch/CUDA project; MLX would require a separate model/runtime port.",
    }


def environment_report():
    torch = torch_status()
    return {
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "pythonModules": {
            "torch": torch,
            "mlx": mlx_status(),
        },
        "upstreamModel": {
            "name": "SAM 3D Objects",
            "imageMaskTo3D": "The upstream object pipeline takes an image and object mask, then reconstructs a 3D object asset.",
            "classification": "SAM 3D Objects is not a native semantic classifier; this adapter treats mask labels or wrapper objects.json metadata as object classes.",
        },
        "localImageMaskTo3D": {
            "possible": bool(platform.system() == "Linux" and torch.get("cuda")),
            "reason": "upstream setup requires linux-64, an NVIDIA GPU with at least 32GB VRAM, and gated model checkpoints",
        },
        "mlxAcceleration": {
            "possibleNow": False,
            "role": "mask generation, frame triage, and local metadata scoring after separate MLX-compatible helper models",
            "notSupportedFor": "direct acceleration of upstream SAM 3D Objects inference",
        },
    }


def selected_backend():
    backend = os.environ.get("SAM3D_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "local", "remote"}:
        raise ValueError("SAM3D_BACKEND must be auto, local, or remote")
    if backend != "auto":
        return backend
    if os.environ.get("SAM3D_LOCAL_COMMAND", "").strip():
        return "local"
    return "remote"


def command_for(image_path, mask_dir, output_dir, backend):
    command_name = "SAM3D_LOCAL_COMMAND" if backend == "local" else "SAM3D_REMOTE_COMMAND"
    configured = os.environ.get(command_name, "").strip()
    if not configured:
        return None
    return shlex.split(configured) + [str(image_path), str(mask_dir), str(output_dir)]


def mask_label(path):
    label = path.stem.replace("_", " ").replace("-", " ").strip()
    return label if label else path.stem


def mask_records(mask_dir):
    if not mask_dir.is_dir():
        return []
    records = []
    for path in sorted(mask_dir.iterdir()):
        if path.suffix.lower() in MASK_EXTENSIONS:
            records.append({"label": mask_label(path), "mask": str(path), "status": "planned"})
    return records


def read_objects(output_dir):
    objects_path = output_dir / "objects.json"
    if not objects_path.exists():
        return None
    try:
        with objects_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        return {"error": str(exc), "path": str(objects_path)}


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        print(json.dumps({"backend": "sam3d-preflight", **environment_report()}, indent=2))
        return 0

    if len(sys.argv) not in (3, 4):
        usage()
        return 1

    image_path = Path(sys.argv[1])
    mask_dir = Path(sys.argv[2])
    output_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("output/sam3d") / image_path.stem
    execute = os.environ.get("SPLAT_SAM3D_EXECUTE", "0") == "1"
    try:
        backend = selected_backend()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = {
        "inputImage": str(image_path),
        "maskDir": str(mask_dir),
        "outputDir": str(output_dir),
        "execute": execute,
        "backend": f"sam3d-{backend}",
        "status": "planned",
        "environment": environment_report(),
        "classification": {
            "mode": "mask-label metadata",
            "note": "Object classes come from mask filenames or wrapper-generated objects.json metadata, not native SAM 3D semantic classification.",
        },
        "objects": mask_records(mask_dir),
        "integrationUse": [
            "optional object reconstruction branch",
            "3D object assets for viewer/manifest staging",
            "not a replacement for COLMAP/OpenMVS camera-space reconstruction",
        ],
    }

    if not image_path.exists():
        report["status"] = "missing input image"
        print(json.dumps(report, indent=2))
        return 2
    if not mask_dir.is_dir():
        report["status"] = "missing mask dir"
        print(json.dumps(report, indent=2))
        return 2
    if not report["objects"]:
        report["status"] = "no object masks"
        print(json.dumps(report, indent=2))
        return 2

    command = command_for(image_path, mask_dir, output_dir, backend)
    if not command:
        report["status"] = f"{backend} command not configured"
        report["configure"] = f"Set SAM3D_{backend.upper()}_COMMAND to a wrapper that accepts: <input-image> <mask-dir> <output-dir>"
        report["exampleWrapper"] = (
            "python /opt/sam3d/run_objects.py"
            if backend == "local"
            else "ssh sam3d-host /opt/sam3d/run_objects.sh"
        )
        print(json.dumps(report, indent=2))
        return 0

    report["command"] = command
    if execute:
        output_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        report["exitCode"] = proc.returncode
        report["logTail"] = "\n".join(proc.stdout.splitlines()[-40:])
        wrapper_objects = read_objects(output_dir)
        if wrapper_objects is not None:
            report["wrapperObjects"] = wrapper_objects
        report["status"] = "completed" if proc.returncode == 0 else "failed"
        print(json.dumps(report, indent=2))
        return proc.returncode

    report["status"] = "ready to execute"
    report["executeWith"] = "SPLAT_SAM3D_EXECUTE=1"
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
