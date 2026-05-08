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

This writes:

- `captures/my-capture/images`
- `captures/my-capture/colmap`

For a first local run, `fps=2` is a practical default on this M4 / 16GB Mac. A 149.74s iPhone test video produced 299 frames and completed COLMAP CPU reconstruction in about 102 seconds, but the reconstruction only registered small frame clusters. Segment retests at `fps=4` improved the best model to 23 registered frames, still below the 50-frame threshold for a useful 3DGS attempt. For better 3DGS input, capture a shorter 30-60s continuous orbit around one subject with textured surroundings.

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
