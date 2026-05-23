#!/usr/bin/env python3
import json
import shutil
import sys
import zipfile
from pathlib import Path


PRIMARY_CAPTURES = {
    "img-9142": "img-9142-fps2",
    "img-9205": "img-9205-fps1-pinhole",
}


def usage():
    print("Usage: scripts/prepare_sam_mask_workspace.py [output-dir]", file=sys.stderr)


def read_manifest(capture):
    path = Path("captures") / capture / "sam_representative_frames" / "manifest.json"
    if not path.exists():
        raise ValueError(f"Missing representative frame manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_readme(path, input_slug, capture, frames):
    frame_lines = "\n".join(f"- {frame['frame']} -> masks/object/{Path(frame['frame']).stem}.png" for frame in frames)
    text = f"""# SAM/SAM3 Mask Package: {input_slug}

Capture: `{capture}`

## What To Run In SAM/SAM3

Use the JPG files in `images/` as the input images.

## Where To Put Mask Results

Save binary mask PNG files under:

```text
masks/object/<same-frame-stem>.png
```

Example:

```text
images/frame_00030.jpg
masks/object/frame_00030.png
```

White/bright pixels are treated as object, black pixels as background.

## Selected Frames

{frame_lines}

## Import Back Into Splatter

After mask PNGs are ready, copy this package's `masks/object/*.png` files into:

```text
captures/{capture}/sam_masks/object/
```

Then run:

```sh
cd /Users/jw/Dev/codex/Splatter
bin/splatter sam-stage-voxel-semantics
npm run check
```
"""
    path.write_text(text, encoding="utf-8")


def zip_dir(source_dir, zip_path):
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent))


def prepare_package(input_slug, capture, root):
    manifest = read_manifest(capture)
    package_dir = root / input_slug
    images_dir = package_dir / "images"
    masks_dir = package_dir / "masks" / "object"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    for old in images_dir.glob("*.jpg"):
        old.unlink()
    for frame in manifest["frames"]:
        shutil.copy2(frame["output"], images_dir / Path(frame["output"]).name)

    (masks_dir / ".keep").write_text("", encoding="utf-8")
    package_manifest = {
        "inputSlug": input_slug,
        "capture": capture,
        "imageDir": str(images_dir),
        "maskDir": str(masks_dir),
        "targetMaskDir": f"captures/{capture}/sam_masks/object",
        "selectedFrames": manifest["selectedFrames"],
        "frames": [
            {
                "image": f"images/{frame['frame']}",
                "expectedMask": f"masks/object/{Path(frame['frame']).stem}.png",
                "source": frame["source"],
                "sharpness": frame["sharpness"],
                "exposure": frame["exposure"],
            }
            for frame in manifest["frames"]
        ],
    }
    (package_dir / "manifest.json").write_text(json.dumps(package_manifest, indent=2) + "\n", encoding="utf-8")
    write_readme(package_dir / "README.md", input_slug, capture, manifest["frames"])
    zip_path = root / f"{input_slug}-sam-mask-package.zip"
    zip_dir(package_dir, zip_path)
    return {
        "inputSlug": input_slug,
        "capture": capture,
        "packageDir": str(package_dir),
        "zip": str(zip_path),
        "frames": manifest["selectedFrames"],
        "maskOutput": str(masks_dir),
        "targetMaskDir": f"captures/{capture}/sam_masks/object",
    }


def prepare_workspace(output_dir=Path("output/sam_input_packages")):
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = [prepare_package(input_slug, capture, output_dir) for input_slug, capture in PRIMARY_CAPTURES.items()]
    report = {
        "outputDir": str(output_dir),
        "packages": packages,
        "next": [
            "Open each package zip or packageDir in the SAM/SAM3 tool.",
            "Save mask PNGs into masks/object with the same frame stem.",
            "Copy masks/object/*.png back to the package targetMaskDir.",
            "Run bin/splatter sam-stage-voxel-semantics && npm run check.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    if len(sys.argv) > 2:
        usage()
        return 1
    output_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("output/sam_input_packages")
    print(json.dumps(prepare_workspace(output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
