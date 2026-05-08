# TASK

## Current Level

**Production Pipeline Level: repeatable publishable capture is ready.**

CLI tool assessment:

- Current status: deployable local pipeline with a first stable CLI entrypoint.
- The repo can publish a capture end-to-end on this Mac with `scripts/process_publish.sh`.
- `bin/splatter` now provides a single command surface for the existing pipeline scripts.
- To call it a fully deployable CLI tool, it still needs broader documentation, release policy, and support matrix.
- Target CLI name: `splatter`.

The repository currently automates the reliable local stages on this Mac:

- iPhone/video frame extraction with `ffmpeg`
- COLMAP CPU reconstruction entrypoint
- COLMAP sparse model analysis
- One-command local capture processing
- OpenSplat training wrapper
- One-command production publish pipeline
- Gaussian splat result staging for web publishing
- SOG compression with SplatTransform
- PlayCanvas-based static viewer
- GitHub Pages deployment workflow
- CI validation before Pages deployment
- Basic tool checks and script syntax validation

CLI-tool complete:

- Single `splatter` executable entrypoint via `bin/splatter`.
- `splatter --help` and `splatter --version`.
- Subcommands for `check`, `capture`, `analyze`, `train`, `convert`, `stage`, `publish`, `validate`, and `serve`.
- CLI contract smoke tests through `scripts/test_cli.sh`.

Not yet CLI-tool complete:

- Install path documented for local use, for example `npm link` or `./bin/splatter`.
- Release/versioning policy.

Verified on this machine:

- `ffmpeg` is installed.
- `python3` is installed.
- `colmap` is installed as `COLMAP 4.0.4` without CUDA.
- `scripts/check_tools.sh` runs successfully.
- `npm run check` passes shell syntax validation.
- `scripts/extract_frames.sh` extracted frames from a generated smoke-test video.
- `scripts/analyze_colmap.sh` summarizes registered images, points, and reprojection error.
- `scripts/process_capture.sh` runs tool checks, frame extraction, COLMAP, and sparse analysis.
- `scripts/run_opensplat.sh` runs a verified OpenSplat training command.
- `scripts/convert_scene.sh` converts staged PLY output to SOG.
- `scripts/process_publish.sh` runs capture reuse/processing, OpenSplat, SOG conversion, and optional staging.
- `scripts/validate_public.sh` validates `public/scene.json`, the staged asset path, format, and asset size.
- `public/` serves locally at `http://localhost:8080`.

Production verification:

- Mac-compatible 3D Gaussian Splat training is verified with OpenSplat MPS.
- SOG compression is verified with SplatTransform CPU fallback.
- One-command production publish is verified in `no-stage` smoke mode.
- CI blocks Pages deployment if the viewer manifest or scene asset is invalid.
- Local viewer is verified on desktop and mobile viewport sizes.
- GitHub Pages deploys the SOG scene asset successfully.
- SuperSplat remains the manual visual cleanup tool; the automated pipeline now produces and publishes the optimized SOG preview without requiring that manual cleanup step.

## Success Target

Reach **Production Level: repeatable publishable capture**:

1. Drop an iPhone video into `input/`.
2. Run one command or a short command sequence.
3. Generate frames and COLMAP reconstruction locally.
4. Produce or import a Gaussian splat export.
5. Convert the preview to SOG for production web delivery.
6. Stage it into `public/assets`.
7. Publish the viewer through GitHub Pages.
8. Optionally inspect and clean it in SuperSplat when visual/artistic cleanup is needed.

Reach **Deployable CLI Tool Level**:

1. Install or run one command named `splatter`.
2. Show deterministic help/version output.
3. Run each production pipeline stage through documented subcommands.
4. Keep existing script internals reusable for direct debugging.
5. Validate CLI command behavior in CI without requiring heavy COLMAP/OpenSplat jobs.
6. Document dependencies, install steps, examples, and supported Mac-only scope.

## Levels

### Level 0: Repository Bootstrap

Status: done

- Static project structure exists.
- README documents the intended flow.
- GitHub Pages workflow exists.

### Level 1: Local Preprocessing

Status: done

- `scripts/extract_frames.sh` extracts frames.
- `scripts/check_tools.sh` detects local dependencies.
- `colmap` is installed.
- Real input tested with `input/IMG_8593.MOV`.
- Improved input tested with `input/IMG_9142.MOV`.

Result:

- Source video: 149.74s, 2160x3840, H.264, 30fps, 450MB.
- `fps=1`: 150 frames, 34MB.
- `fps=2`: 299 frames, 67MB before COLMAP, 150MB after COLMAP.
- `fps=4`: 599 frames, 136MB.
- Improved source video: 30.43s, 2160x3840, H.264, 30fps, 94MB.
- Current recommendation: use `fps=2` as the first local reconstruction test.

### Level 2: Local COLMAP Reconstruction

Status: done for `input/IMG_9142.MOV`

- `scripts/run_colmap.sh` runs `colmap automatic_reconstructor` in CPU mode.
- The script uses a capture-local `HOME`/cache to avoid writing COLMAP cache files under the user's home directory.
- The script uses `data_type individual` to avoid COLMAP's vocabulary-tree download path.

Result from `img-8593-fps2`:

- Runtime: 101.46s wall time.
- Sparse output exists under `captures/img-8593-fps2/colmap/sparse`.
- Model `sparse/0`: 8 registered images, 1160 points, 0.829px mean reprojection error.
- Model `sparse/1`: 11 registered images, 823 points, 0.885px mean reprojection error.
- This is not enough for a strong 3DGS training run. The video likely contains long low-feature or discontinuous sections.

Segment retest from `input/IMG_8593.MOV`:

- `img-8593-000-030-fps4`: first 30s, 120 frames, COLMAP runtime 149.55s wall time.
- `img-8593-000-030-fps4/sparse/0`: 23 registered images, 3119 points, 0.825px mean reprojection error.
- `img-8593-085-115-fps4`: 85-115s segment, 120 frames, COLMAP runtime 181.82s wall time.
- `img-8593-085-115-fps4/sparse/0`: 10 registered images, 5052 points, 0.491px mean reprojection error.
- `img-8593-085-115-fps4/sparse/1`: 15 registered images, 2228 points, 0.831px mean reprojection error.
- `img-8593-085-115-fps4/sparse/2`: 11 registered images, 1829 points, 0.805px mean reprojection error.
- Best result improved from 11 to 23 registered images, but still misses the 50-frame threshold for 3DGS training.

One-command smoke test:

- `scripts/process_capture.sh input/IMG_8593_000_030.MOV img-8593-process-smoke-fps2 2` completed.
- It extracted 60 frames, ran COLMAP, and reported 11 registered images in the best sparse model.

Successful capture result from `input/IMG_9142.MOV`:

- `scripts/process_capture.sh input/IMG_9142.MOV img-9142-fps2 2` completed.
- Source video: 30.43s, 2160x3840, H.264, 30fps, 94MB.
- Extracted 61 frames at `fps=2`.
- Capture output size: 109MB total, including 47MB images and 62MB COLMAP output.
- Model `sparse/0`: 59 registered images, 13733 points, 1.143px mean reprojection error.
- This passes the 50-frame threshold for attempting 3DGS training.

Operational note:

- `captures/img-9142-fps2` is the first verified real input for Mac-compatible 3DGS training.

### Level 3: 3DGS Training

Status: done

Selected path:

- OpenSplat from `https://github.com/pierotofy/OpenSplat`.
- Local build under `.local/OpenSplat`.
- Required Homebrew packages installed: `opencv`, `pytorch`.
- Required Xcode component installed: Metal Toolchain.
- OpenSplat accepts `captures/img-9142-fps2/colmap` with `--colmap-image-path captures/img-9142-fps2/images`.
- OpenSplat exports `.ply`, suitable for SuperSplat inspection.
- MPS is available outside the Codex sandbox. Inside the sandbox, PyTorch reports MPS unavailable and falls back to CPU.

Verified command:

```sh
scripts/run_opensplat.sh img-9142-fps2 5 4 output/img-9142-opensplat-mps-smoke.ply
```

Result:

- OpenSplat printed `Using MPS`.
- It read 13733 COLMAP points.
- It wrote `output/img-9142-opensplat-mps-smoke.ply`.
- Output file is a binary little-endian PLY with 13733 vertices.
- A longer preview pass completed with `scripts/run_opensplat.sh img-9142-fps2 2000 4 output/img-9142-opensplat-preview.ply`.
- The preview file is 12MB, binary little-endian PLY, generated at iteration 2000 with 51090 vertices.

Operational note:

- Run longer training if visual quality needs improvement.

### Level 4: Web Staging and Local Viewer

Status: done

- `scripts/prepare_scene.sh` stages `.ply`, `.compressed.ply`, or `.sog`.
- `public/main.js` loads the staged scene through PlayCanvas.
- `public/main.js` shows loading, ready, failure, and scene metadata states.
- `public/scene.json` points to `assets/img-9142-opensplat-preview.sog`.
- `public/assets/img-9142-opensplat-preview.sog` is staged for local and Pages preview.
- Local Playwright verification passed on desktop and mobile viewport sizes with zero console warnings/errors.

Operational note:

- Tune camera or cleanup in SuperSplat if the scene needs artistic polish.

### Level 5: GitHub Pages Publishing

Status: done

- `.github/workflows/deploy-pages.yml` deploys `public/`.
- `https://dobuzi.github.io/splatter/` returns HTTP 200.
- `https://dobuzi.github.io/splatter/assets/img-9142-opensplat-preview.sog` returns HTTP 200.

Operational note:

- Continue using the GitHub Actions Pages workflow on pushes to `main`.

## Near-Term Tasks

### P0: CLI Tool Packaging

- [x] Add `bin/splatter` as the stable CLI entrypoint.
- [x] Add package metadata: `name`, `version`, `bin`, and description.
- [x] Implement `splatter --help`.
- [x] Implement `splatter --version`.
- [x] Add subcommands that delegate to existing scripts:
  `check`, `capture`, `analyze`, `train`, `convert`, `stage`, `publish`, `validate`, `serve`.
- [x] Keep backward-compatible `scripts/*.sh` commands.
- [x] Add `npm link` or local execution instructions.

### P0: CLI Contract Tests

- [x] Add a lightweight CLI smoke test script.
- [x] Verify `splatter --help`.
- [x] Verify `splatter --version`.
- [x] Verify invalid command rejects with non-zero exit.
- [x] Verify `splatter publish` rejects missing required input with non-zero exit.
- [x] Verify `splatter validate` succeeds against the staged public viewer.
- [x] Run CLI contract tests in `npm run check`.
- [x] Run CLI contract tests in GitHub Actions before Pages deployment.

### P1: CLI Documentation

- [ ] Add README quickstart using `splatter`.
- [ ] Document Mac-only dependency requirements.
- [ ] Document full publish command for a new video.
- [ ] Document smoke-test command that does not overwrite the staged production scene.
- [ ] Document expected outputs and ignored working directories.
- [ ] Document known limits: local MPS requirement, SuperSplat manual cleanup, GitHub Actions no GPU training.

### P1: Release Readiness

- [ ] Add versioning policy.
- [ ] Add changelog or release notes section.
- [ ] Add license decision.
- [ ] Add support matrix for macOS / Apple Silicon / COLMAP / OpenSplat.
- [ ] Decide whether `.local/OpenSplat` stays external or becomes a documented bootstrap command.

### P0: Clean Repository State

- [x] Decide whether to keep `docs/superpowers/*` in the repo.
  Keep the design and implementation plan for now because they document the current scaffold decisions.
- [x] Remove accidental `.DS_Store` before staging.
- [x] Create the first commit once the initial scaffold is accepted.

### P0: Real iPhone Capture Test

- [x] Add one iPhone `.mov` file under `input/`.
- [x] Run `scripts/extract_frames.sh input/<video>.mov <capture-name> 2`.
- [x] Count extracted frames.
- [x] Check disk usage under `captures/<capture-name>`.
- [x] Adjust README if the recommended FPS changes.

### P0: COLMAP Real Capture Test

- [x] Run `scripts/run_colmap.sh <capture-name>`.
- [x] Confirm COLMAP creates sparse reconstruction output.
- [x] Record runtime on this M4 / 16GB Mac.
- [x] If reconstruction fails, adjust capture guidance before changing code.

### P0: Improve Capture Input

- [x] Capture a shorter 30-60s video with continuous orbit around one subject.
- [x] Keep the subject and textured background visible throughout the shot.
- [x] Avoid pointing at blank walls, sky, glossy surfaces, or motion-blurred sections.
- [x] Select tighter 30s segments from the existing `input/IMG_8593.MOV` as a fallback test.
- [x] Re-run extraction and COLMAP on existing-video segments.
- [x] Record that the best existing-video segment reached 23 registered frames.
- [x] Re-run `scripts/extract_frames.sh input/<video>.mov <capture-name> 2`.
- [x] Re-run `scripts/run_colmap.sh <capture-name>`.
- [x] Confirm the largest sparse model registers at least 50 frames before attempting 3DGS training.

### P1: Pick the Mac Training Path

- [x] Test at least one Mac-compatible 3DGS trainer or app.
- [x] Confirm input format from COLMAP.
- [x] Confirm export format for SuperSplat or PlayCanvas.
- [x] Document the exact training command or manual steps.
- [x] Add an automation wrapper only after the path is proven.

### P1: SuperSplat Round Trip

- [x] Keep SuperSplat as the manual visual cleanup step.
- [x] Produce an optimized production web asset without manual cleanup by converting the OpenSplat preview to SOG.
- [x] Stage the current OpenSplat preview with `scripts/prepare_scene.sh`.
- [x] Stage the SOG production export with `scripts/prepare_scene.sh`.
- [x] Confirm local viewer renders it.

### P1: Viewer Hardening

- [x] Add loading and asset-load failure states.
- [x] Add scene metadata display: format, size, capture, training.
- [x] Test desktop and mobile viewport sizes.
- [x] Tune default camera position for real scenes through `scene.json`.

### P2: SOG Compression

- [x] Install PlayCanvas SplatTransform as a repo-local dev dependency.
- [x] Add `scripts/convert_scene.sh`.
- [x] Compare `.ply` and `.sog` file sizes.
- [x] Update `prepare_scene.sh` metadata output for `.sog` publishing.

### P2: One-Command Orchestration

- [x] Add `scripts/process_capture.sh`.
- [x] Add `scripts/process_publish.sh`.
- [x] Run tool checks.
- [x] Extract frames.
- [x] Run COLMAP.
- [x] Add `scripts/analyze_colmap.sh` to summarize sparse reconstruction quality.
- [x] Print the next exact training step.
- [x] Optionally stage a provided exported scene.
- [x] Optionally run full train/convert/stage publish flow.

### P2: GitHub Pages End-to-End

- [x] Create or connect a GitHub repository.
- [x] Push the scaffold.
- [x] Enable GitHub Pages through Actions.
- [x] Confirm the deployed URL.
- [x] Add the deployed URL to README.

### P2: Production CI Gate

- [x] Add `scripts/validate_public.sh`.
- [x] Validate `public/scene.json` is parseable and points to a local asset.
- [x] Validate staged asset exists, is non-empty, uses a supported format, and stays under the production size limit.
- [x] Add `npm run check` to the GitHub Pages workflow before artifact upload.
- [x] Verify the CI gate locally.

## Current Commands

Check tools:

```sh
scripts/check_tools.sh
```

Validate deployable public viewer:

```sh
scripts/validate_public.sh
```

Extract frames:

```sh
scripts/extract_frames.sh input/capture.mov my-capture 2
```

Run COLMAP:

```sh
scripts/run_colmap.sh my-capture
```

Analyze COLMAP:

```sh
scripts/analyze_colmap.sh my-capture
```

Process a capture:

```sh
scripts/process_capture.sh input/capture.mov my-capture 2
```

Process, train, convert, and stage:

```sh
scripts/process_publish.sh input/capture.mov my-capture 2 2000 4 "My Capture"
```

Process a capture and stage an exported scene:

```sh
scripts/process_capture.sh input/capture.mov my-capture 2 output/scene.ply
```

Stage a scene:

```sh
scripts/prepare_scene.sh output/scene.ply "My Capture"
```

Preview:

```sh
npm run serve
```
