#!/usr/bin/env python3
import argparse
import json
import os
import sys
from importlib import util
from pathlib import Path


def module_available(name):
    return util.find_spec(name) is not None


def check_environment(repo_dir, tag):
    repo_dir = repo_dir.resolve()
    config_path = repo_dir / "checkpoints" / tag / "pipeline.yaml"
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
    return {
        "repoDir": str(repo_dir),
        "notebookDir": str(notebook_dir),
        "configPath": str(config_path),
        "notebookPresent": notebook_dir.is_dir(),
        "configPresent": config_path.exists(),
        "pythonModules": modules,
        "ready": notebook_dir.is_dir() and config_path.exists() and all(modules.values()),
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
    repo_dir = args.sam3d_repo.resolve()
    env = check_environment(repo_dir, args.tag)
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
    config_path = repo_dir / "checkpoints" / args.tag / "pipeline.yaml"

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
        print(json.dumps({"mode": "sam3d-multi-object-gif-check", **check_environment(args.sam3d_repo, args.tag)}, indent=2))
        return 0
    if args.image is None or args.output_dir is None:
        parser.print_usage(sys.stderr)
        return 1
    return run_multi_object(args)


if __name__ == "__main__":
    raise SystemExit(main())
