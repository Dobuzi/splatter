# Splatter

Mac-local CLI for publishing an iPhone video as a browser-viewable Gaussian Splat:

1. extract frames from iPhone video
2. reconstruct with COLMAP
3. train with OpenSplat on Apple Silicon MPS
4. convert the result to PlayCanvas SOG
5. preview in the static PlayCanvas viewer
6. deploy `public/` to GitHub Pages

This repository is production-ready for local use on this Mac. Heavy 3DGS work runs locally; GitHub Actions only validates and deploys the static viewer.

Published viewer:

```text
https://dobuzi.github.io/splatter/
```

## Requirements

Verified environment:

- macOS on Apple Silicon
- `ffmpeg`
- `python3`
- `colmap` 4.0.4, CPU reconstruction
- Homebrew `opencv`
- Homebrew `pytorch`
- Xcode Metal Toolchain
- OpenSplat built locally under `.local/OpenSplat`
- Node/npm dependencies from this repository

Install the common tools:

```sh
brew install ffmpeg colmap opencv pytorch
xcodebuild -downloadComponent MetalToolchain
npm install
```

Build OpenSplat as an external local dependency:

```sh
git clone https://github.com/pierotofy/OpenSplat .local/OpenSplat
cmake -S .local/OpenSplat -B .local/OpenSplat/build \
  -DCMAKE_PREFIX_PATH=/opt/homebrew/Cellar/pytorch/2.11.0/libexec/lib/python3.14/site-packages/torch \
  -DOpenCV_DIR=/opt/homebrew/Cellar/opencv/4.13.0_10/lib/cmake/opencv4 \
  -DGPU_RUNTIME=MPS
cmake --build .local/OpenSplat/build --parallel 10
```

Check the local setup:

```sh
bin/splatter check
```

## Install

Run the CLI directly from the repository:

```sh
bin/splatter --help
bin/splatter --version
```

Or link it locally as `splatter`:

```sh
npm link
splatter --help
```

The CLI version is read from `package.json`. Current version: `0.1.0`.

## Quickstart

Place a video under `input/`, then run the full local publish pipeline:

```sh
bin/splatter publish input/capture.mov my-capture 2 2000 4 "My Capture"
```

Arguments:

- `input/capture.mov`: source iPhone video
- `my-capture`: capture/output name
- `2`: extracted frames per second
- `2000`: OpenSplat training iterations
- `4`: OpenSplat downscale factor
- `"My Capture"`: title written to `public/scene.json`

For a smoke test that does not overwrite the staged production scene:

```sh
bin/splatter publish input/IMG_9142.MOV img-9142-fps2 2 5 4 "IMG 9142 Smoke" no-stage
```

## Quality Workflow

The current production scene uses progressive delivery: a tiny preview reaches the first usable render, then the higher-quality 200K-Gaussian asset replaces it.

```sh
bin/splatter train img-9142-fps2 5000 3 output/img-9142-opensplat-webhq-5000-d3.ply
SPLAT_DECIMATE=20000 SPLAT_HARMONICS=0 \
  bin/splatter convert output/img-9142-opensplat-webhq-5000-d3.ply \
  output/img-9142-opensplat-webhq-5000-d3-20k-h0.sog
SPLAT_DECIMATE=200000 SPLAT_HARMONICS=1 \
  bin/splatter convert output/img-9142-opensplat-webhq-5000-d3.ply \
  output/img-9142-opensplat-webhq-5000-d3-200k-h1.sog
SCENE_CAPTURE="IMG_9142, 30.43s, 59 COLMAP images" \
SCENE_TRAINING="OpenSplat MPS, 5000 iterations, downscale 3, final 200k SH1" \
SCENE_DELIVERY="Progressive preview: 20k SH0, 259KB" \
SCENE_PREVIEW_ASSET="output/img-9142-opensplat-webhq-5000-d3-20k-h0.sog" \
  bin/splatter stage output/img-9142-opensplat-webhq-5000-d3-200k-h1.sog \
  "IMG 9142 Web HQ"
```

For the repeatable version of that workflow, use the quality commands:

```sh
bin/splatter quality-report img-9142-fps2 \
  public/assets/img-9142-opensplat-webhq-5000-d3-200k-h1.sog

bin/splatter quality-stage output/img-9142-opensplat-webhq-5000-d3.ply \
  "IMG 9142 Web HQ" web
```

Quality staging presets:

- `web`: preview 20K SH0, final 200K SH1.
- `web-hq`: preview 30K SH0, final 300K SH1.

Use `SPLAT_QUALITY_DRY_RUN=1` to inspect the conversion plan without running SOG conversion.

Quality experiment helpers:

```sh
# Find the most coherent temporal segment before spending time on 3DGS training.
bin/splatter segment-sweep input/capture.mov capture-name

# Execute segment reconstruction candidates. Keep the window list small at first.
SPLAT_SEGMENT_EXECUTE=1 \
SPLAT_SEGMENT_FPS=4 \
  bin/splatter segment-sweep input/capture.mov capture-name 45 15

# Gate COLMAP output before training.
bin/splatter colmap-gate capture-name-000-045-fps4-pinhole

# Print a matrix of candidate capture/training runs.
bin/splatter quality-sweep input/capture.mov capture-name "Capture Name"

# Execute the matrix. Keep the lists narrow; this can run for hours.
SPLAT_SWEEP_EXECUTE=1 \
SPLAT_SWEEP_FPS_LIST="8 12" \
SPLAT_SWEEP_CAMERA_MODELS="PINHOLE SIMPLE_PINHOLE" \
SPLAT_SWEEP_ITERS_LIST="5000" \
SPLAT_SWEEP_DOWNSCALES="1 2" \
  bin/splatter quality-sweep input/capture.mov capture-name "Capture Name"

# Compare a validation render against its withheld source frame.
bin/splatter compare-holdout \
  captures/capture-name-fps12-pinhole/images/frame_00010.jpg \
  output/metrics/capture-name-fps12-pinhole-opensplat-5000-d1/5000.png \
  output/metrics/capture-name-fps12-pinhole-opensplat-5000-d1/holdout-metrics.json

# Build a sharper, less redundant frame set from an existing capture.
bin/splatter select-frames capture-name-fps12 selected-capture 180
COLMAP_CAMERA_MODEL=PINHOLE scripts/run_colmap.sh selected-capture
bin/splatter colmap-gate selected-capture

# Try matcher variants when registration is the bottleneck.
SPLAT_MATCHER_EXECUTE=1 \
SPLAT_MATCHERS="sequential exhaustive" \
SPLAT_MATCHER_CAMERA_MODELS="PINHOLE" \
COLMAP_MAX_IMAGE_SIZE=960 \
COLMAP_NUM_THREADS=4 \
  bin/splatter matcher-sweep selected-capture selected-capture-match

# Rank existing COLMAP candidates by structural signals.
bin/splatter rank-captures selected-capture

# Use masks during COLMAP feature extraction when dynamic clutter dominates.
bin/splatter mask-frames selected-capture
COLMAP_CAMERA_MODEL=PINHOLE \
COLMAP_MATCHER=exhaustive \
COLMAP_MASK_PATH=captures/selected-capture/masks \
  scripts/run_colmap.sh selected-capture-masked

# Check whether generated depth priors cover every selected frame.
bin/splatter depth-priors selected-capture
bin/splatter depth-report selected-capture
```

Long OpenSplat runs should leave checkpoints:

```sh
OPENSPLAT_SAVE_EVERY=1000 OPENSPLAT_DEVICE=cpu \
  bin/splatter train selected-capture 10000 1 output/selected-capture-10000-d1.ply

bin/splatter select-checkpoint output/selected-capture-10000-d1
```

Additional OpenSplat flags can be passed with `OPENSPLAT_EXTRA_ARGS`, for example `--ssim-weight 0.1 --sh-degree 2`. Use `bin/splatter mlx-smoke` to check whether the local `gsplat-mlx` install is viable before trying MLX-based experiments. If the smoke run produces `nan`, use `bin/splatter mlx-diagnose --lr 1e-5` to identify whether the first backward pass or optimizer update is the source.

`quality-sweep` uses a middle capture frame as the default holdout and writes PSNR/SSIM metrics under `output/metrics/`. Set `SPLAT_SWEEP_VAL_IMAGE=none` to disable holdout validation, or set it to a specific frame filename such as `frame_00042.jpg`.

Quality gates used before staging:

- COLMAP passes `bin/splatter colmap-gate`: registered image count, registration ratio, sparse point count, and reprojection error.
- Matcher candidates are ranked with `bin/splatter rank-captures` before training; low point distribution proxy means OpenSplat will likely learn a partial shell.
- Optional masks are passed through `COLMAP_MASK_PATH` so COLMAP feature extraction can ignore dynamic clutter.
- Optional depth priors must pass `bin/splatter depth-report` coverage before using depth consistency as a ranking or training signal.
- Training runs on MPS, not CPU fallback.
- OpenSplat checkpoint selection rejects NaN/Inf PLY files before conversion.
- Web asset stays under the 25MB Pages gate.
- SOG conversion finishes in practical local time.
- Viewer reaches `Ready` on desktop and mobile viewports with zero console warnings/errors.
- Screenshot checks show a nonblank rendered canvas.
- Final quality asset is at least 2x the previous staged Gaussian count.
- First render payload is at least 2x smaller than the previous staged asset.

Actual measured result:

- Previous staged asset: 100K gaussians, SH1, 1.89MB.
- New preview asset: 20K gaussians, SH0, 259KB, about 7.5x less first-render payload.
- New final asset: 200K gaussians, SH1, 3.24MB, 2x the previous Gaussian count.
- Local Playwright app metrics: preview `Ready` generally 36-65ms; HQ replacement generally 75-105ms.

Avoid publishing raw high-density PLY output directly. In testing, `7000 iterations / downscale 2` produced a 188MB PLY with 793K vertices but exceeded the SOG conversion time budget. The deployable balance is progressive 20K preview plus 200K final SOG from the 5000/d3 training result.

## CLI Commands

```sh
bin/splatter check
bin/splatter validate
bin/splatter capture input/capture.mov my-capture 2
bin/splatter analyze my-capture
bin/splatter train my-capture 2000 4 output/my-capture.ply
bin/splatter select-frames my-capture my-capture-selected 180
bin/splatter convert output/my-capture.ply output/my-capture.sog
bin/splatter stage output/my-capture.sog "My Capture"
bin/splatter quality-report my-capture output/my-capture.sog
bin/splatter compare-holdout captures/my-capture/images/frame_00010.jpg output/metrics/my-capture/5000.png
bin/splatter quality-stage output/my-capture.ply "My Capture" web
bin/splatter quality-sweep input/capture.mov my-capture "My Capture"
bin/splatter segment-sweep input/capture.mov my-capture
bin/splatter matcher-sweep my-capture my-capture-match
bin/splatter rank-captures my-capture
bin/splatter colmap-gate my-capture
bin/splatter select-checkpoint output/my-capture-opensplat-10000-d1
bin/splatter mask-frames my-capture
bin/splatter depth-priors my-capture
bin/splatter depth-report my-capture
bin/splatter mesh-validate output/my-capture.ply
bin/splatter mlx-smoke
bin/splatter mlx-diagnose --lr 1e-5
bin/splatter publish input/capture.mov my-capture 2 2000 4 "My Capture"
bin/splatter serve
```

The `scripts/*.sh` entrypoints remain available for debugging each stage directly.

## Outputs

Expected generated outputs:

- `captures/<name>/images`: extracted frames
- `captures/<name>/colmap`: COLMAP reconstruction
- `output/<name>-opensplat-<iterations>.ply`: OpenSplat training result
- `output/<name>-opensplat-<iterations>.sog`: compressed PlayCanvas asset
- `public/assets/<scene>.sog`: staged production web asset
- `public/scene.json`: default viewer scene
- `public/scenes.json`: optional multi-scene manifest for the viewer selector

Optional SOG conversion controls:

- `SPLAT_DECIMATE=<count|percent>`: cap Gaussian count for browser delivery.
- `SPLAT_HARMONICS=<0..3>`: remove spherical harmonic bands above the chosen level.
- `SPLAT_SOG_ITERATIONS=<count>`: tune SOG SH compression iterations.

Optional viewer presentation controls in `public/scene.json`:

- `viewer.background`: RGB values from 0 to 1.
- `viewer.fov`: camera field of view from 20 to 90 degrees.

Ignored local working directories:

- `input/`: private source videos
- `captures/`: generated frames and COLMAP output
- `output/`: generated training and conversion artifacts
- `.local/`: external local tools such as OpenSplat

## Viewer and Publishing

Preview locally:

```sh
npm run serve
```

Open:

```text
http://localhost:8080
```

The viewer reads `public/scenes.json` when present and shows a scene selector using the original input filenames. Open a specific scene with:

```text
http://localhost:8080/?scene=img-9189
```

Validate the deployable viewer:

```sh
bin/splatter validate
```

The GitHub Actions workflow in `.github/workflows/deploy-pages.yml` runs `npm run check` and deploys `public/` on pushes to `main` or `master`.

GitHub Pages source should be set to GitHub Actions in repository settings.

## Viewer Controls

The viewer targets the dense center of the current splat instead of the world origin. For the current `IMG_9142` scene, the camera target is `[-1.15, 0.69, 0.18]`, based on SOG coordinate summaries.

Controls:

- iPhone / touch: one-finger drag orbits, two-finger pinch zooms, two-finger drag pans.
- Mac mouse: left drag orbits, wheel zooms, right or middle drag pans.
- Mac trackpad: scroll zooms, horizontal or Shift-scroll pans.
- Keyboard modifier: Shift or Option/Alt while dragging pans.

Coordinate tools:

- `Flip Y` is applied by default for the current scene to correct the upside-down axis.
- `Flip X`, `Flip Z`, and `X/Y/Z 90` adjust the viewer transform around the measured scene pivot.
- `Save` persists the transform in browser `localStorage`.
- `Copy JSON` copies the current `scene.json` content with the active transform for committing back to the repo.
- `Reset` restores the transform from `public/scene.json`.

## SuperSplat

The automated pipeline publishes a SOG preview without requiring manual cleanup. Use SuperSplat when visual cleanup, cropping, or artistic adjustment is needed:

```text
https://superspl.at/editor
```

Export the cleaned scene from SuperSplat, then stage it:

```sh
bin/splatter stage output/cleaned-scene.sog "Cleaned Scene"
```

## Support Matrix

| Component | Status |
| --- | --- |
| macOS / Apple Silicon | Supported and verified locally |
| macOS / Intel | Not verified |
| Linux | Not supported by this repo's local training path |
| GitHub Actions | Static validation and Pages deployment only |
| COLMAP | Verified with 4.0.4 CPU reconstruction |
| OpenSplat | External dependency under `.local/OpenSplat`, verified at commit `1f4dc9b` |
| GPU runtime | Apple MPS locally; no CUDA runner is required |
| PlayCanvas SOG | Verified with `@playcanvas/splat-transform` 2.0.6 |

## Known Limits

- Local OpenSplat training requires Apple Silicon MPS for practical runtime on this Mac.
- Inside restricted sandboxes, PyTorch may not expose MPS and can fall back to CPU.
- GitHub-hosted free runners do not provide the GPU training environment for this pipeline.
- SuperSplat cleanup is still manual when the raw capture needs visual trimming or editing.
- Low-texture, glossy, blurry, or discontinuous videos can fail COLMAP registration.
- GitHub Pages serves only the static viewer and staged assets; it does not run reconstruction or training.

## Versioning and Release Notes

This repository is currently private/internal and uses CLI version `0.1.0`.

Release policy:

- Use SemVer once the CLI is published or shared outside this repository.
- While the version remains `0.x`, command flags and positional arguments may change.
- Patch releases should not break documented commands.
- Minor releases may add commands or adjust pipeline behavior with README updates.

Release notes:

- `0.1.0`: first deployable local Mac CLI with `splatter` entrypoint, contract tests, production SOG staging, Pages validation, and documented local support matrix.

License decision:

- No public license is included yet.
- Treat the code as private/internal until a `LICENSE` file is added before public reuse or package publication.

## Free Processing Notes

Frame extraction, COLMAP CPU reconstruction, OpenSplat MPS preview training, SOG compression, local viewer validation, and Pages publishing are usable without paid cloud GPU runners.

Standard free GitHub-hosted runners are used only for static validation and deployment. For remote GPU processing, use a self-hosted machine or a paid runner.
