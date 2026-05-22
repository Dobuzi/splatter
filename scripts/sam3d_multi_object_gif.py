#!/usr/bin/env python3
import argparse
import contextlib
import io
import json
import os
import sys
from importlib import util
from pathlib import Path


def module_available(name):
    return util.find_spec(name) is not None


def import_inference_probe(repo_dir, sparse_backends):
    if sparse_backends["spconv"]:
        backend = "spconv"
    elif sparse_backends["torchsparse"]:
        backend = "torchsparse"
    else:
        return {"ok": False, "backend": None, "error": "no sparse backend importable"}

    root = Path.cwd()
    os.environ.setdefault("SPARSE_BACKEND", backend)
    os.environ.setdefault("LIDRA_SKIP_INIT", "true")
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".local" / "mpl"))
    os.environ.setdefault("XDG_CACHE_HOME", str(root / ".local"))
    os.environ.setdefault("WARP_CACHE_PATH", str(root / ".local" / "warp"))
    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "notebook"))
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            import inference  # noqa: F401
    except Exception as exc:
        return {
            "ok": False,
            "backend": backend,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "stdoutTail": stdout.getvalue()[-1000:],
            "stderrTail": stderr.getvalue()[-1000:],
        }
    return {"ok": True, "backend": backend, "stdoutTail": stdout.getvalue()[-1000:], "stderrTail": stderr.getvalue()[-1000:]}


def checkpoint_config_path(checkpoint_root, tag):
    root = checkpoint_root.resolve()
    if root.name == tag:
        return root / "pipeline.yaml"
    return root / tag / "pipeline.yaml"


def default_checkpoint_root(repo_dir):
    env_root = os.environ.get("SAM3D_CHECKPOINT_ROOT")
    if env_root:
        return Path(env_root)
    models_root = Path("models/checkpoints")
    if models_root.exists():
        return models_root
    return repo_dir / "checkpoints"


def check_environment(repo_dir, tag, checkpoint_root=None):
    repo_dir = repo_dir.resolve()
    checkpoint_root = default_checkpoint_root(repo_dir) if checkpoint_root is None else checkpoint_root
    config_path = checkpoint_config_path(checkpoint_root, tag)
    notebook_dir = repo_dir / "notebook"
    modules = {
        "PIL": module_available("PIL"),
        "imageio": module_available("imageio"),
        "numpy": module_available("numpy"),
        "omegaconf": module_available("omegaconf"),
        "hydra": module_available("hydra"),
        "torch": module_available("torch"),
        "kaolin": module_available("kaolin"),
        "pytorch3d": module_available("pytorch3d"),
        "sam3d_objects": module_available("sam3d_objects"),
    }
    sparse_backends = {
        "spconv": module_available("spconv"),
        "torchsparse": module_available("torchsparse"),
    }
    inference_import = {"ok": False, "backend": None, "error": "base environment not ready"}
    if notebook_dir.is_dir() and config_path.exists() and all(modules.values()) and any(sparse_backends.values()):
        inference_import = import_inference_probe(repo_dir, sparse_backends)
    return {
        "repoDir": str(repo_dir),
        "checkpointRoot": str(checkpoint_root),
        "notebookDir": str(notebook_dir),
        "configPath": str(config_path),
        "notebookPresent": notebook_dir.is_dir(),
        "configPresent": config_path.exists(),
        "pythonModules": modules,
        "sparseBackends": sparse_backends,
        "inferenceImport": inference_import,
        "ready": notebook_dir.is_dir() and config_path.exists() and all(modules.values()) and inference_import["ok"],
    }


def numbered_masks(image_path, extension):
    masks = []
    folder = image_path.parent
    index = 0
    while (folder / f"{index}{extension}").exists():
        masks.append(folder / f"{index}{extension}")
        index += 1
    return masks


def run_multi_object(args):
    root = Path.cwd()
    os.environ.setdefault("LIDRA_SKIP_INIT", "true")
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".local" / "mpl"))
    os.environ.setdefault("XDG_CACHE_HOME", str(root / ".local"))
    os.environ.setdefault("WARP_CACHE_PATH", str(root / ".local" / "warp"))
    repo_dir = args.sam3d_repo.resolve()
    checkpoint_root = args.checkpoint_root or default_checkpoint_root(repo_dir)
    env = check_environment(repo_dir, args.tag, checkpoint_root)
    image_path = args.image.resolve()
    output_dir = args.output_dir.resolve()
    masks = numbered_masks(image_path, args.mask_extension)
    report = {
        "mode": "sam3d-multi-object-gif",
        "image": str(image_path),
        "outputDir": str(output_dir),
        "tag": args.tag,
        "maskExtension": args.mask_extension,
        "maskCount": len(masks),
        "masks": [str(path) for path in masks],
        "environment": env,
    }
    if not image_path.exists():
        report["status"] = "missing input image"
        print(json.dumps(report, indent=2))
        return 2
    if not masks:
        report["status"] = "no numbered masks"
        print(json.dumps(report, indent=2))
        return 2
    if not env["ready"]:
        report["status"] = "environment not ready"
        report["notebookSource"] = "facebookresearch/sam-3d-objects notebook/demo_multi_object.ipynb"
        print(json.dumps(report, indent=2))
        return 2

    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "notebook"))
    os.chdir(repo_dir / "notebook")

    try:
        import imageio
        from inference import (
            Inference,
            load_image,
            load_masks,
            make_scene,
            ready_gaussian_for_video_rendering,
            render_video,
        )
    except Exception as exc:
        report["status"] = "import failed"
        report["error"] = str(exc)
        print(json.dumps(report, indent=2))
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    image_name = args.name or image_path.parent.name
    posed_path = output_dir / f"{image_name}_posed.ply"
    ply_path = output_dir / f"{image_name}.ply"
    gif_path = output_dir / f"{image_name}.gif"
    config_path = checkpoint_config_path(checkpoint_root, args.tag)

    image = load_image(str(image_path))
    masks = load_masks(str(image_path.parent), extension=args.mask_extension)
    inference = Inference(str(config_path), compile=False)
    outputs = [inference(image, mask, seed=args.seed) for mask in masks]
    scene_gs = make_scene(*outputs)
    scene_gs.save_ply(str(posed_path))
    scene_gs = ready_gaussian_for_video_rendering(scene_gs)
    scene_gs.save_ply(str(ply_path))
    video = render_video(scene_gs, r=args.radius, fov=args.fov, resolution=args.resolution)["color"]
    imageio.mimsave(str(gif_path), video, format="GIF", duration=1000 / args.fps, loop=0)

    report["status"] = "completed"
    report["outputs"] = {
        "posedPly": str(posed_path),
        "ply": str(ply_path),
        "gif": str(gif_path),
    }
    print(json.dumps(report, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the SAM 3D Objects multi-object notebook flow and export PLY/GIF.")
    parser.add_argument("--check", action="store_true", help="Only report environment readiness.")
    parser.add_argument("--sam3d-repo", type=Path, default=Path(".local/sam-3d-objects"))
    parser.add_argument("--checkpoint-root", type=Path, help="Directory containing hf/pipeline.yaml, defaults to SAM3D_CHECKPOINT_ROOT, models/checkpoints, then <sam3d-repo>/checkpoints.")
    parser.add_argument("--tag", default="hf")
    parser.add_argument("--mask-extension", default=".png")
    parser.add_argument("--name")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--radius", type=float, default=1.0)
    parser.add_argument("--fov", type=float, default=60.0)
    parser.add_argument("image", nargs="?", type=Path)
    parser.add_argument("output_dir", nargs="?", type=Path)
    args = parser.parse_args()

    if args.check:
        checkpoint_root = args.checkpoint_root or default_checkpoint_root(args.sam3d_repo)
        print(json.dumps({"mode": "sam3d-multi-object-gif-check", **check_environment(args.sam3d_repo, args.tag, checkpoint_root)}, indent=2))
        return 0
    if args.image is None or args.output_dir is None:
        parser.print_usage(sys.stderr)
        return 1
    return run_multi_object(args)


if __name__ == "__main__":
    raise SystemExit(main())
