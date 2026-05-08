# Local iPhone Gaussian Splat Pipeline

Mac-first pipeline for:

1. iPhone video
2. frame extraction
3. COLMAP reconstruction
4. Gaussian splat export staging
5. SuperSplat inspection
6. GitHub Pages publishing

This repository automates the parts that are reliable on an Apple Silicon Mac. The 3DGS training step is intentionally pluggable because most open 3DGS trainers are CUDA-first, while this Mac uses Apple Silicon/Metal.

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

On this Mac, frame extraction and COLMAP CPU reconstruction are practical. Full 3DGS training depends on a Metal-compatible trainer or a manual export from a Mac app.
