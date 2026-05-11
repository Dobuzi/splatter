# Splat Quality Improvements Design

## Goal

Improve 3D Gaussian Splat output quality from three angles without forcing an expensive retrain during normal validation:

- capture and COLMAP diagnostics before training
- repeatable multi-tier SOG conversion and staging presets after training
- viewer presentation controls that make the staged splat easier to inspect

## Assumptions

- Heavy OpenSplat training remains local and manual/explicit.
- Generated `input/`, `captures/`, `output/`, and `.local/` artifacts stay uncommitted.
- GitHub Pages keeps the 25MB static asset gate.
- The current `img-9142` 5000/d3 PLY is the known good high-quality source.

## Approach

Add a `quality` CLI surface with two focused operations:

- `splatter quality-report <capture-name> [scene-file]` reports frame count, image dimensions, COLMAP registered images, sparse points, reprojection error, optional scene size, and actionable recommendations.
- `splatter quality-stage <input.ply> <title> [preset]` converts a source PLY into progressive preview/final SOG assets using named presets, then stages the final asset with preview metadata.

The viewer gets optional presentation settings in `scene.json`, read by `public/main.js`. This keeps render-time tuning static-host compatible while avoiding a new UI surface.

## Quality Presets

- `web`: preview 20K SH0, final 200K SH1. This matches the current deployable balance.
- `web-hq`: preview 30K SH0, final 300K SH1. This is a cautious higher-quality candidate while staying far below the 25MB Pages gate for typical SOG output.

Each preset uses the existing `scripts/convert_scene.sh` environment controls, then calls `scripts/prepare_scene.sh` with `SCENE_PREVIEW_ASSET` and metadata.

## Viewer Presentation

`scene.json` may include:

```json
"viewer": {
  "background": [0.02, 0.025, 0.03],
  "fov": 45
}
```

Missing values preserve current behavior. Validation checks types and sensible ranges.

## Testing

- Extend CLI contract tests to cover new commands and argument failures.
- Add validation checks for optional `viewer.background` and `viewer.fov`.
- Run `npm run check`.

## Out Of Scope

- Running new OpenSplat training in this implementation.
- Automatically cleaning splats like SuperSplat.
- Committing generated assets from `output/`.
