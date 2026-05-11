# Splat Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeatable quality diagnostics, web-quality staging presets, and static viewer presentation controls for Gaussian Splat output.

**Architecture:** Keep expensive training explicit. Add shell scripts behind the existing `bin/splatter` CLI, reuse the current conversion and staging scripts, and validate all new static config from `scripts/validate_public.sh`.

**Tech Stack:** zsh scripts, Node syntax/config validation, PlayCanvas viewer config.

---

## Chunk 1: CLI Quality Surface

### Task 1: Failing CLI Contract Tests

**Files:**
- Modify: `scripts/test_cli.sh`
- Modify: `bin/splatter`

- [x] Add tests that expect help to list `quality-report` and `quality-stage`.
- [x] Add tests that expect both commands to reject missing required arguments.
- [x] Run `scripts/test_cli.sh` and verify the new tests fail before implementation.
- [x] Add the CLI command routing.
- [x] Run `scripts/test_cli.sh` and verify it passes.

## Chunk 2: Capture Diagnostics

### Task 2: Quality Report Script

**Files:**
- Create: `scripts/report_quality.sh`
- Modify: `bin/splatter`
- Modify: `README.md`

- [x] Implement frame count, image dimension, COLMAP analysis, optional scene size, and recommendations.
- [x] Keep the script read-only.
- [x] Document the command.
- [x] Run `bin/splatter quality-report img-9142-fps2 public/assets/img-9142-opensplat-webhq-5000-d3-200k-h1.sog`.

## Chunk 3: Progressive Quality Presets

### Task 3: Quality Stage Script

**Files:**
- Create: `scripts/stage_quality_scene.sh`
- Modify: `bin/splatter`
- Modify: `README.md`

- [x] Implement `web` and `web-hq` presets.
- [x] Convert preview and final SOG assets by calling `scripts/convert_scene.sh`.
- [x] Stage final output by calling `scripts/prepare_scene.sh` with preview metadata.
- [x] Add dry-run support for cheap contract testing.
- [x] Run dry-run verification.

## Chunk 4: Viewer Presentation Config

### Task 4: Static Viewer Controls

**Files:**
- Modify: `public/main.js`
- Modify: `public/scene.json`
- Modify: `scripts/validate_public.sh`
- Modify: `README.md`

- [x] Add optional `viewer.background` and `viewer.fov` support.
- [x] Validate optional values.
- [x] Preserve current defaults when absent.
- [x] Run `npm run check`.
