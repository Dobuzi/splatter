# Local iPhone Gaussian Splat Pipeline

Mac-first pipeline for:

1. iPhone video
2. frame extraction
3. COLMAP reconstruction
4. Gaussian splat export staging
5. SuperSplat inspection
6. SOG compression
7. GitHub Pages publishing

This repository automates the full Mac-local path that has been verified on this Apple Silicon Mac: frame extraction, COLMAP, OpenSplat MPS training, SOG compression, PlayCanvas preview, and GitHub Pages publishing.

## Requirements

Required:

- macOS
- `ffmpeg`
- `python3`

Optional:

- `colmap` for reconstruction
- `splat-transform` for PlayCanvas SOG conversion when you want smaller web files

Check tools:

```sh
scripts/check_tools.sh
```

Install COLMAP if needed:

```sh
brew install colmap
```

Install project dependencies:

```sh
npm install
```

Run the CLI directly:

```sh
bin/splatter --help
```

Or link it locally as `splatter`:

```sh
npm link
splatter --help
```

## Capture Workflow

Place your iPhone video under `input/`, then extract frames:

```sh
scripts/extract_frames.sh input/capture.mov my-capture 2
```

Run COLMAP reconstruction:

```sh
scripts/run_colmap.sh my-capture
```

Analyze COLMAP reconstruction quality:

```sh
scripts/analyze_colmap.sh my-capture
```

Or run local preprocessing and COLMAP in one command:

```sh
scripts/process_capture.sh input/capture.mov my-capture 2
```

Run the full local publish pipeline in one command:

```sh
bin/splatter publish input/capture.mov my-capture 2 2000 4 "My Capture"
```

If you already have an exported splat file, pass it as the fourth argument to stage it after COLMAP analysis:

```sh
scripts/process_capture.sh input/capture.mov my-capture 2 output/scene.ply
```

This writes:

- `captures/my-capture/images`
- `captures/my-capture/colmap`

For a first local run, `fps=2` is a practical default on this M4 / 16GB Mac. The first 149.74s iPhone test video only registered small frame clusters. A better 30.43s capture, `input/IMG_9142.MOV`, produced 61 extracted frames and registered 59 images in one COLMAP sparse model, passing the 50-frame threshold for attempting 3DGS training.

Use the generated capture with a Mac-compatible 3D Gaussian Splat trainer. Export one of:

- `.ply`
- `.compressed.ply`
- `.sog`

## Train with OpenSplat

This Mac has been verified with OpenSplat as the first local 3DGS training path:

- OpenSplat source: `https://github.com/pierotofy/OpenSplat`
- Local build path: `.local/OpenSplat`
- Runtime: MPS when run outside the Codex sandbox
- Input: `captures/<capture-name>/colmap` plus `captures/<capture-name>/images`
- Output: `.ply`

Build prerequisites used on this Mac:

```sh
brew install opencv pytorch
xcodebuild -downloadComponent MetalToolchain
git clone https://github.com/pierotofy/OpenSplat .local/OpenSplat
cmake -S .local/OpenSplat -B .local/OpenSplat/build \
  -DCMAKE_PREFIX_PATH=/opt/homebrew/Cellar/pytorch/2.11.0/libexec/lib/python3.14/site-packages/torch \
  -DOpenCV_DIR=/opt/homebrew/Cellar/opencv/4.13.0_10/lib/cmake/opencv4 \
  -DGPU_RUNTIME=MPS
cmake --build .local/OpenSplat/build --parallel 10
```

Run a quick smoke test:

```sh
scripts/run_opensplat.sh img-9142-fps2 5 4 output/img-9142-opensplat-smoke.ply
```

Run a longer preview training pass:

```sh
scripts/run_opensplat.sh img-9142-fps2 2000 4 output/img-9142-opensplat-preview.ply
```

Convert the preview PLY to production SOG:

```sh
scripts/convert_scene.sh output/img-9142-opensplat-preview.ply output/img-9142-opensplat-preview.sog
```

The current staged production scene was generated with that command and staged with:

```sh
scripts/prepare_scene.sh output/img-9142-opensplat-preview.sog "IMG 9142 OpenSplat Preview"
```

The SOG asset is about 1.19MB, compared with the 12.67MB PLY preview.

For a non-staging smoke test, use:

```sh
bin/splatter publish input/IMG_9142.MOV img-9142-fps2 2 5 4 "IMG 9142 Smoke" no-stage
```

For browser sharing, inspect and clean the exported file in SuperSplat:

https://superspl.at/editor

## Stage a Scene for the Viewer

After exporting a splat:

```sh
scripts/prepare_scene.sh output/scene.ply "My Capture"
```

Preview locally:

```sh
npm run serve
```

Open:

```text
http://localhost:8080
```

## Publish with GitHub Pages

The workflow in `.github/workflows/deploy-pages.yml` deploys the `public/` directory on pushes to `main` or `master`.

Published URL:

```text
https://dobuzi.github.io/splatter/
```

In GitHub repository settings:

1. Open Settings.
2. Open Pages.
3. Set Source to GitHub Actions.
4. Push this repository.

## Notes on Free Local Processing

GitHub-hosted GPU runners are paid larger runners. Standard free GitHub-hosted runners do not provide CUDA GPUs. For free processing, use this Mac where possible or connect your own GPU machine as a self-hosted runner.

On this Mac, frame extraction, COLMAP CPU reconstruction, OpenSplat MPS preview training, and SOG compression are practical. GitHub-hosted runners are still used only for static Pages deployment, not GPU training.
