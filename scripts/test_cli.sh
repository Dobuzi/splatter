#!/usr/bin/env zsh
set -euo pipefail

cli="bin/splatter"

if [[ ! -x "$cli" ]]; then
  echo "Missing executable CLI: $cli" >&2
  exit 1
fi

"$cli" --help | grep -q "splatter - local iPhone video"
"$cli" --help | grep -q "quality-report"
"$cli" --help | grep -q "compare-holdout"
"$cli" --help | grep -q "quality-stage"
"$cli" --help | grep -q "quality-sweep"
"$cli" --help | grep -q "segment-sweep"
"$cli" --help | grep -q "segment-sweep-fine"
"$cli" --help | grep -q "matcher-sweep"
"$cli" --help | grep -q "rank-captures"
"$cli" --help | grep -q "select-frames"
"$cli" --help | grep -q "frame-quality"
"$cli" --help | grep -q "colmap-gate"
"$cli" --help | grep -q "select-checkpoint"
"$cli" --help | grep -q "mask-frames"
"$cli" --help | grep -q "depth-priors"
"$cli" --help | grep -q "depth-report"
"$cli" --help | grep -q "mesh-validate"
"$cli" --help | grep -q "mesh-simplify"
"$cli" --help | grep -q "mesh-largest-component"
"$cli" --help | grep -q "surface-reconstruct"
"$cli" --help | grep -q "openmvs-batch"
"$cli" --help | grep -q "openmvs-sweep"
"$cli" --help | grep -q "openmvs-sweep-all"
"$cli" --help | grep -q "openmvs-validate"
"$cli" --help | grep -q "viewer-qa"
"$cli" --help | grep -q "mlx-smoke"
"$cli" --help | grep -q "mlx-diagnose"
"$cli" --help | grep -q "mlx-frame-quality"
"$cli" --version | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+'
"$cli" validate >/dev/null

if "$cli" unknown >/dev/null 2>&1; then
  echo "Unknown command should fail" >&2
  exit 1
fi

if "$cli" publish >/dev/null 2>&1; then
  echo "Publish without required args should fail" >&2
  exit 1
fi

if "$cli" quality-report >/dev/null 2>&1; then
  echo "Quality report without required args should fail" >&2
  exit 1
fi

if "$cli" quality-stage >/dev/null 2>&1; then
  echo "Quality stage without required args should fail" >&2
  exit 1
fi

if "$cli" quality-sweep >/dev/null 2>&1; then
  echo "Quality sweep without required args should fail" >&2
  exit 1
fi

if "$cli" select-frames >/dev/null 2>&1; then
  echo "Select frames without required args should fail" >&2
  exit 1
fi

if "$cli" frame-quality >/dev/null 2>&1; then
  echo "Frame quality without required args should fail" >&2
  exit 1
fi

if "$cli" segment-sweep >/dev/null 2>&1; then
  echo "Segment sweep without required args should fail" >&2
  exit 1
fi

if "$cli" matcher-sweep >/dev/null 2>&1; then
  echo "Matcher sweep without required args should fail" >&2
  exit 1
fi

if "$cli" rank-captures >/dev/null 2>&1; then
  echo "Rank captures without required args should fail" >&2
  exit 1
fi

if "$cli" colmap-gate >/dev/null 2>&1; then
  echo "COLMAP gate without required args should fail" >&2
  exit 1
fi

if "$cli" select-checkpoint >/dev/null 2>&1; then
  echo "Select checkpoint without required args should fail" >&2
  exit 1
fi

if "$cli" mask-frames >/dev/null 2>&1; then
  echo "Mask frames without required args should fail" >&2
  exit 1
fi

if "$cli" depth-priors >/dev/null 2>&1; then
  echo "Depth priors without required args should fail" >&2
  exit 1
fi

if "$cli" depth-report >/dev/null 2>&1; then
  echo "Depth report without required args should fail" >&2
  exit 1
fi

if "$cli" mesh-validate >/dev/null 2>&1; then
  echo "Mesh validate without required args should fail" >&2
  exit 1
fi

if "$cli" mesh-simplify >/dev/null 2>&1; then
  echo "Mesh simplify without required args should fail" >&2
  exit 1
fi

if "$cli" mesh-largest-component >/dev/null 2>&1; then
  echo "Mesh largest component without required args should fail" >&2
  exit 1
fi

if "$cli" surface-reconstruct >/dev/null 2>&1; then
  echo "Surface reconstruct without required args should fail" >&2
  exit 1
fi

SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage public/assets/img-9142-opensplat-webhq-5000-d3-200k-h1.sog "Dry Run" >/dev/null 2>&1 && {
  echo "Quality stage should reject non-PLY input" >&2
  exit 1
}

dry_run_output=$(SPLAT_QUALITY_DRY_RUN=1 "$cli" quality-stage output/nonexistent-quality-source.ply "Dry Run" web-hq)
printf '%s\n' "$dry_run_output" | grep -q "Preset: web-hq"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=30000"
printf '%s\n' "$dry_run_output" | grep -q "SPLAT_DECIMATE=300000"

temp_video=$(mktemp "${TMPDIR:-/tmp}/splatter-quality-sweep.XXXXXX.mov")
trap 'rm -f "$temp_video"' EXIT
sweep_output=$("$cli" quality-sweep "$temp_video" dry-run-title "Dry Run")
printf '%s\n' "$sweep_output" | grep -q "Execute: 0"
printf '%s\n' "$sweep_output" | grep -q "Holdout: auto"
printf '%s\n' "$sweep_output" | grep -q "COLMAP_CAMERA_MODEL=PINHOLE"
printf '%s\n' "$sweep_output" | grep -q "OPENSPLAT_SAVE_EVERY=1000"

segment_output=$("$cli" segment-sweep "$temp_video" segment-dry-run)
printf '%s\n' "$segment_output" | grep -q "Segment sweep"
printf '%s\n' "$segment_output" | grep -q "Execute: 0"
printf '%s\n' "$segment_output" | grep -q "scripts/run_colmap.sh"
fine_segment_output=$("$cli" segment-sweep-fine "$temp_video" segment-dry-run)
printf '%s\n' "$fine_segment_output" | grep -q "Window: 20s"
printf '%s\n' "$fine_segment_output" | grep -q "Stride: 5s"

matcher_output=$("$cli" matcher-sweep segment-dry-run)
printf '%s\n' "$matcher_output" | grep -q "Matcher sweep"
printf '%s\n' "$matcher_output" | grep -q "sequential"
printf '%s\n' "$matcher_output" | grep -q "COLMAP_MATCHER"

rank_output=$(SPLAT_RANK_DRY_RUN=1 "$cli" rank-captures segment-dry-run)
printf '%s\n' "$rank_output" | grep -q "Capture ranking"
printf '%s\n' "$rank_output" | grep -q "point distribution"

colmap_plan=$(SPLAT_COLMAP_DRY_RUN=1 COLMAP_MATCHER=sequential COLMAP_MASK_PATH=captures/missing/masks scripts/run_colmap.sh missing-capture)
printf '%s\n' "$colmap_plan" | grep -q "Matcher: sequential"
printf '%s\n' "$colmap_plan" | grep -q "ImageReader.mask_path"

gate_output=$(SPLAT_COLMAP_GATE_DRY_RUN=1 "$cli" colmap-gate missing-capture)
printf '%s\n' "$gate_output" | grep -q "COLMAP quality gate"
printf '%s\n' "$gate_output" | grep -q "Minimum registered images"

checkpoint_output=$(SPLAT_CHECKPOINT_DRY_RUN=1 "$cli" select-checkpoint output/missing-prefix)
printf '%s\n' "$checkpoint_output" | grep -q "Checkpoint selector"
printf '%s\n' "$checkpoint_output" | grep -q "finite PLY"

checkpoint_dir=$(mktemp -d "${TMPDIR:-/tmp}/splatter-checkpoint.XXXXXX")
trap 'rm -f "$temp_video"; rm -rf "$checkpoint_dir"' EXIT
python3 - "$checkpoint_dir/sample_1000.ply" <<'PY'
import struct
import sys

path = sys.argv[1]
header = """ply
format binary_little_endian 1.0
element vertex 1
property float x
property float y
property float z
end_header
"""
with open(path, "wb") as handle:
    handle.write(header.encode("ascii"))
    handle.write(struct.pack("<fff", 1.0, 2.0, 3.0))
PY
checkpoint_binary_output=$("$cli" select-checkpoint "$checkpoint_dir/sample")
printf '%s\n' "$checkpoint_binary_output" | grep -q '"format": "binary_little_endian"'
printf '%s\n' "$checkpoint_binary_output" | grep -q '"finite": true'
python3 - "$checkpoint_dir/two-components.ply" <<'PY'
import struct
import sys

path = sys.argv[1]
header = """ply
format binary_little_endian 1.0
element vertex 6
property float x
property float y
property float z
element face 2
property list uchar int vertex_indices
end_header
"""
vertices = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (10.0, 0.0, 0.0),
    (11.0, 0.0, 0.0),
    (10.0, 1.0, 0.0),
]
with open(path, "wb") as handle:
    handle.write(header.encode("ascii"))
    for vertex in vertices:
        handle.write(struct.pack("<fff", *vertex))
    handle.write(struct.pack("<Biii", 3, 0, 1, 2))
    handle.write(struct.pack("<Biii", 3, 3, 4, 5))
PY
largest_output=$("$cli" mesh-largest-component "$checkpoint_dir/two-components.ply" "$checkpoint_dir/largest.ply")
printf '%s\n' "$largest_output" | grep -q '"outputFaces": 1'

mask_output=$(SPLAT_MASK_DRY_RUN=1 "$cli" mask-frames missing-capture)
printf '%s\n' "$mask_output" | grep -q "Mask generation"
printf '%s\n' "$mask_output" | grep -q "Backend:"

depth_output=$(SPLAT_DEPTH_DRY_RUN=1 "$cli" depth-priors missing-capture)
printf '%s\n' "$depth_output" | grep -q "Depth prior generation"
printf '%s\n' "$depth_output" | grep -q "Depth Anything"

depth_report_output=$(SPLAT_DEPTH_REPORT_DRY_RUN=1 "$cli" depth-report missing-capture)
printf '%s\n' "$depth_report_output" | grep -q "Depth prior report"
printf '%s\n' "$depth_report_output" | grep -q "coverage"

mesh_output=$(SPLAT_MESH_DRY_RUN=1 "$cli" mesh-validate output/missing.ply)
printf '%s\n' "$mesh_output" | grep -q "Surface validation"
printf '%s\n' "$mesh_output" | grep -q "SuGaR"

surface_output=$(SPLAT_SURFACE_DRY_RUN=1 "$cli" surface-reconstruct missing-capture)
printf '%s\n' "$surface_output" | grep -q "COLMAP surface reconstruction"
printf '%s\n' "$surface_output" | grep -q "stereo_fusion"
openmvs_surface_output=$(SPLAT_SURFACE_DRY_RUN=1 SPLAT_SURFACE_BACKEND=openmvs "$cli" surface-reconstruct missing-capture)
printf '%s\n' "$openmvs_surface_output" | grep -q "Backend: openmvs"
printf '%s\n' "$openmvs_surface_output" | grep -q "DensifyPointCloud"
openmvs_batch_output=$(SPLAT_OPENMVS_BATCH_DRY_RUN=1 "$cli" openmvs-batch input)
printf '%s\n' "$openmvs_batch_output" | grep -q "OpenMVS batch"
printf '%s\n' "$openmvs_batch_output" | grep -q "output/openmvs-ranking.json"
openmvs_sweep_output=$(SPLAT_OPENMVS_SWEEP_DRY_RUN=1 "$cli" openmvs-sweep missing-capture)
printf '%s\n' "$openmvs_sweep_output" | grep -q "balanced"
printf '%s\n' "$openmvs_sweep_output" | grep -q "detail"
openmvs_sweep_all_output=$(SPLAT_OPENMVS_SWEEP_ALL_DRY_RUN=1 "$cli" openmvs-sweep-all missing-input)
printf '%s\n' "$openmvs_sweep_all_output" | grep -q "candidates"
"$cli" viewer-qa >/dev/null
mlx_frame_output=$("$cli" mlx-frame-quality --dry-run)
printf '%s\n' "$mlx_frame_output" | grep -q "frame quality scoring"

echo "CLI contract tests passed"
