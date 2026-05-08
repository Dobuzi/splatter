# TASK

## Current Level

**Level 1: Mac-local pipeline scaffold is ready.**

The repository currently automates the reliable local stages on this Mac:

- iPhone/video frame extraction with `ffmpeg`
- COLMAP CPU reconstruction entrypoint
- Gaussian splat result staging for web publishing
- PlayCanvas-based static viewer
- GitHub Pages deployment workflow
- Basic tool checks and script syntax validation

Verified on this machine:

- `ffmpeg` is installed.
- `python3` is installed.
- `colmap` is installed as `COLMAP 4.0.4` without CUDA.
- `scripts/check_tools.sh` runs successfully.
- `npm run check` passes shell syntax validation.
- `scripts/extract_frames.sh` extracted frames from a generated smoke-test video.
- `public/` serves locally at `http://localhost:8080`.

Not yet verified:

- Mac-compatible capture quality sufficient for 3DGS training.
- Mac-compatible 3D Gaussian Splat training.
- SuperSplat cleanup/export round trip with a real scene.

## Success Target

Reach **Level 4: repeatable publishable capture**:

1. Drop an iPhone video into `input/`.
2. Run one command or a short command sequence.
3. Generate frames and COLMAP reconstruction locally.
4. Produce or import a Gaussian splat export.
5. Inspect and clean it in SuperSplat.
6. Stage it into `public/assets`.
7. Publish the viewer through GitHub Pages.

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

Result:

- Source video: 149.74s, 2160x3840, H.264, 30fps, 450MB.
- `fps=1`: 150 frames, 34MB.
- `fps=2`: 299 frames, 67MB before COLMAP, 150MB after COLMAP.
- `fps=4`: 599 frames, 136MB.
- Current recommendation: use `fps=2` as the first local reconstruction test.

### Level 2: Local COLMAP Reconstruction

Status: runs locally, capture quality needs improvement

- `scripts/run_colmap.sh` runs `colmap automatic_reconstructor` in CPU mode.
- The script uses a capture-local `HOME`/cache to avoid writing COLMAP cache files under the user's home directory.
- The script uses `data_type individual` to avoid COLMAP's vocabulary-tree download path.

Result from `img-8593-fps2`:

- Runtime: 101.46s wall time.
- Sparse output exists under `captures/img-8593-fps2/colmap/sparse`.
- Model `sparse/0`: 8 registered images, 1160 points, 0.829px mean reprojection error.
- Model `sparse/1`: 11 registered images, 823 points, 0.885px mean reprojection error.
- This is not enough for a strong 3DGS training run. The video likely contains long low-feature or discontinuous sections.

Next proof:

- Create or select a tighter capture segment with continuous orbit motion and textured subject/background.
- Re-run extraction and COLMAP until one model registers a useful share of frames.

### Level 3: 3DGS Training

Status: not automated yet

Current blocker:

- Most open 3DGS training stacks are CUDA-first.
- This Mac has Apple Silicon/Metal, not CUDA.

Next proof:

- Select one Mac-compatible training path.
- Confirm it accepts COLMAP output.
- Confirm it exports `.ply`, `.compressed.ply`, or `.sog`.

Candidate paths:

- A Mac Metal 3D Gaussian Splatting app with manual or scriptable export.
- A Python/Metal-compatible trainer if stable enough.
- A self-hosted GPU runner later, if local Mac training is too slow or blocked.

### Level 4: Web Staging and Local Viewer

Status: scaffold done, pending real scene

- `scripts/prepare_scene.sh` stages `.ply`, `.compressed.ply`, or `.sog`.
- `public/main.js` loads the staged scene through PlayCanvas.
- Empty-state UI appears when no scene is staged.

Next proof:

- Stage a real splat file.
- Verify it renders locally in the browser.
- Verify camera controls and scene scale are usable.

### Level 5: GitHub Pages Publishing

Status: workflow exists, pending remote repository setup

- `.github/workflows/deploy-pages.yml` deploys `public/`.

Next proof:

- Connect this folder to a GitHub repository.
- Enable Pages source as GitHub Actions.
- Push to `main` or `master`.
- Confirm public URL loads the viewer and scene asset.

## Near-Term Tasks

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

- [ ] Capture a shorter 30-60s video with continuous orbit around one subject.
- [ ] Keep the subject and textured background visible throughout the shot.
- [ ] Avoid pointing at blank walls, sky, glossy surfaces, or motion-blurred sections.
- [ ] Re-run `scripts/extract_frames.sh input/<video>.mov <capture-name> 2`.
- [ ] Re-run `scripts/run_colmap.sh <capture-name>`.
- [ ] Confirm the largest sparse model registers at least 50 frames before attempting 3DGS training.

### P1: Pick the Mac Training Path

- [ ] Test at least one Mac-compatible 3DGS trainer or app.
- [ ] Confirm input format from COLMAP.
- [ ] Confirm export format for SuperSplat or PlayCanvas.
- [ ] Document the exact training command or manual steps.
- [ ] Add an automation wrapper only after the path is proven.

### P1: SuperSplat Round Trip

- [ ] Open exported scene in `https://superspl.at/editor`.
- [ ] Clean/crop/orient the scene.
- [ ] Export the optimized scene.
- [ ] Stage it with `scripts/prepare_scene.sh`.
- [ ] Confirm local viewer renders it.

### P1: Viewer Hardening

- [ ] Add loading and asset-load failure states.
- [ ] Add scene metadata display: file name, format, capture date.
- [ ] Test desktop and mobile viewport sizes.
- [ ] Tune default camera position for real scenes.

### P2: SOG Compression

- [ ] Install or vendor the PlayCanvas splat transform tooling.
- [ ] Add `scripts/convert_scene.sh` if conversion works locally.
- [ ] Compare `.ply` and `.sog` file sizes.
- [ ] Update `prepare_scene.sh` if `.sog` becomes the default publish format.

### P2: One-Command Orchestration

- [ ] Add `scripts/process_capture.sh`.
- [ ] Run tool checks.
- [ ] Extract frames.
- [ ] Run COLMAP.
- [ ] Print the next exact training step.
- [ ] Optionally stage a provided exported scene.

### P2: GitHub Pages End-to-End

- [x] Create or connect a GitHub repository.
- [x] Push the scaffold.
- [x] Enable GitHub Pages through Actions.
- [x] Confirm the deployed URL.
- [x] Add the deployed URL to README.

## Current Commands

Check tools:

```sh
scripts/check_tools.sh
```

Extract frames:

```sh
scripts/extract_frames.sh input/capture.mov my-capture 2
```

Run COLMAP:

```sh
scripts/run_colmap.sh my-capture
```

Stage a scene:

```sh
scripts/prepare_scene.sh output/scene.ply "My Capture"
```

Preview:

```sh
npm run serve
```
