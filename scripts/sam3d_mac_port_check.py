#!/usr/bin/env python3
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def run_probe(python_path, repo_dir, sparse_backend):
    env = os.environ.copy()
    root = Path.cwd()
    env.update(
        {
            "LIDRA_SKIP_INIT": "true",
            "MPLCONFIGDIR": str(root / ".local" / "mpl"),
            "XDG_CACHE_HOME": str(root / ".local"),
            "WARP_CACHE_PATH": str(root / ".local" / "warp"),
            "SPARSE_BACKEND": sparse_backend,
        }
    )
    code = r"""
import importlib.util
import json
import os
import sys
from pathlib import Path

repo = Path(os.environ["SAM3D_REPO"]).resolve()
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "notebook"))

def module_available(name):
    return importlib.util.find_spec(name) is not None

report = {"modules": {}, "inferenceImport": {"ok": False}}
for name in [
    "torch",
    "torchvision",
    "sam3d_objects",
    "pytorch3d",
    "kaolin",
    "utils3d",
    "spconv",
    "torchsparse",
    "timm",
    "plyfile",
]:
    report["modules"][name] = module_available(name)

try:
    import torch
    report["torch"] = {
        "version": getattr(torch, "__version__", "unknown"),
        "mpsBuilt": bool(torch.backends.mps.is_built()),
        "mpsAvailable": bool(torch.backends.mps.is_available()),
        "cudaAvailable": bool(torch.cuda.is_available()),
    }
except Exception as exc:
    report["torch"] = {"error": str(exc)}

try:
    import inference
    report["inferenceImport"] = {"ok": True}
except Exception as exc:
    report["inferenceImport"] = {
        "ok": False,
        "errorType": type(exc).__name__,
        "error": str(exc),
    }

config_path = repo / "checkpoints" / "hf" / "pipeline.yaml"
report["checkpoints"] = {
    "pipelineYaml": str(config_path),
    "pipelineYamlPresent": config_path.exists(),
}
print(json.dumps(report))
"""
    proc = subprocess.run(
        [str(python_path), "-c", code],
        cwd=repo_dir,
        env={**env, "SAM3D_REPO": str(repo_dir)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                pass
            break
    return {
        "backend": sparse_backend,
        "exitCode": proc.returncode,
        "report": payload,
        "stderrTail": "\n".join(proc.stderr.splitlines()[-20:]),
        "stdoutTail": "\n".join(proc.stdout.splitlines()[-20:]),
    }


def main():
    repo_dir = Path(os.environ.get("SAM3D_REPO", ".local/sam-3d-objects"))
    python_path = Path(os.environ.get("SAM3D_PYTHON", ".local/sam3d-mac-venv/bin/python"))
    if not repo_dir.is_absolute():
        repo_dir = Path.cwd() / repo_dir
    if not python_path.is_absolute():
        python_path = Path.cwd() / python_path
    repo_dir = repo_dir.resolve()
    result = {
        "mode": "sam3d-mac-port-check",
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "repoDir": str(repo_dir),
        "python": str(python_path),
        "pythonPresent": python_path.exists(),
        "repoPresent": repo_dir.exists(),
        "probes": [],
        "nextBlockers": [],
    }
    if not repo_dir.exists() or not python_path.exists():
        result["status"] = "missing local SAM 3D repo or venv"
        print(json.dumps(result, indent=2))
        return 0

    for backend in ["spconv", "torchsparse"]:
        result["probes"].append(run_probe(python_path, repo_dir, backend))

    blockers = []
    best = None
    for probe in result["probes"]:
        report = probe.get("report") or {}
        if report.get("inferenceImport", {}).get("ok"):
            best = probe
            break
        err = report.get("inferenceImport", {}).get("error")
        if err and err not in blockers:
            blockers.append(err)
    if best:
        result["status"] = "notebook inference import ready"
        checkpoint = best["report"].get("checkpoints", {})
        if not checkpoint.get("pipelineYamlPresent"):
            result["nextBlockers"].append("download gated SAM 3D Objects checkpoints to checkpoints/hf")
    else:
        result["status"] = "notebook inference import blocked"
        result["nextBlockers"].extend(blockers)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
