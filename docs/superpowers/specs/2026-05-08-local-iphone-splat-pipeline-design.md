# Local iPhone Splat Pipeline Design

## Goal

Build a Mac-first pipeline that turns an iPhone video into extracted frames and a COLMAP reconstruction, accepts a locally trained Gaussian splat export, previews it with PlayCanvas/SuperSplat-compatible tooling, and publishes a static viewer to GitHub Pages.

## Assumptions

- The current machine is an Apple Silicon Mac without CUDA.
- `ffmpeg` is available locally.
- `colmap` may need to be installed with Homebrew.
- Fully automated 3DGS training on this Mac depends on a Metal-capable training tool or a future CLI. CUDA-first tools such as Nerfstudio are documented but not the default local execution path.
- The publishable scene format is `.ply`, `.compressed.ply`, or `.sog`, all supported by PlayCanvas viewing tools.

## Architecture

- `scripts/check_tools.sh` reports required and optional local tools.
- `scripts/extract_frames.sh` extracts frames from an iPhone video into `captures/<name>/images`.
- `scripts/run_colmap.sh` runs CPU COLMAP reconstruction into `captures/<name>/colmap`.
- `scripts/prepare_scene.sh` copies a trained splat export into `public/assets` and writes `public/scene.json`.
- `public/` is a static PlayCanvas-based viewer suitable for GitHub Pages.
- `.github/workflows/deploy-pages.yml` deploys `public/` to GitHub Pages.

## Data Flow

1. User places an iPhone video under `input/`.
2. `extract_frames.sh` creates still images at a configurable FPS.
3. `run_colmap.sh` creates camera poses and sparse reconstruction.
4. User runs a Mac-compatible 3DGS trainer or external trainer against the COLMAP project and exports `.ply` or `.sog`.
5. `prepare_scene.sh` stages the exported file for the web viewer.
6. The user verifies the file in SuperSplat or the PlayCanvas viewer.
7. GitHub Pages serves the static viewer.

## Error Handling

Scripts fail early when required arguments or tools are missing. The viewer shows a clear empty state if no staged scene is present.

## Verification

- Shell syntax checks pass for all scripts.
- Tool check script runs on this Mac.
- A local static HTTP server serves the viewer.
- GitHub Pages workflow syntax is present and scoped to `public/`.
