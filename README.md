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

## CLI Commands

```sh
bin/splatter check
bin/splatter validate
bin/splatter capture input/capture.mov my-capture 2
bin/splatter analyze my-capture
bin/splatter train my-capture 2000 4 output/my-capture.ply
bin/splatter convert output/my-capture.ply output/my-capture.sog
bin/splatter stage output/my-capture.sog "My Capture"
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
- `public/scene.json`: viewer manifest

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

Validate the deployable viewer:

```sh
bin/splatter validate
```

The GitHub Actions workflow in `.github/workflows/deploy-pages.yml` runs `npm run check` and deploys `public/` on pushes to `main` or `master`.

GitHub Pages source should be set to GitHub Actions in repository settings.

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
