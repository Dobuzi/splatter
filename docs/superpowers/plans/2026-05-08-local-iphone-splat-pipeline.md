# Local iPhone Splat Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Mac-first iPhone video to Gaussian splat staging and GitHub Pages publishing pipeline.

**Architecture:** Keep the pipeline shell-script based and static-site based. Automate video frame extraction, COLMAP reconstruction, scene staging, local preview, and Pages deployment while leaving the Mac-specific training engine as a clearly documented plug-in step.

**Tech Stack:** POSIX shell, ffmpeg, COLMAP, PlayCanvas Engine via CDN, GitHub Pages Actions.

---

## Chunk 1: Pipeline Skeleton

### Task 1: Repository Structure

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `package.json`

- [ ] Create the minimal repository metadata and ignored generated directories.
- [ ] Verify `git status --short` shows only intentional new files.

### Task 2: Local Processing Scripts

**Files:**
- Create: `scripts/check_tools.sh`
- Create: `scripts/extract_frames.sh`
- Create: `scripts/run_colmap.sh`
- Create: `scripts/prepare_scene.sh`

- [ ] Add strict shell scripts with argument validation.
- [ ] Verify scripts with `zsh -n scripts/*.sh`.
- [ ] Run `scripts/check_tools.sh`.

### Task 3: Static Viewer

**Files:**
- Create: `public/index.html`
- Create: `public/main.js`
- Create: `public/styles.css`
- Create: `public/scene.json`
- Create: `public/assets/.gitkeep`

- [ ] Build a PlayCanvas viewer that loads the staged splat from `scene.json`.
- [ ] Show an empty state when no scene is staged.
- [ ] Verify the site can be served with `python3 -m http.server`.

### Task 4: GitHub Pages Deployment

**Files:**
- Create: `.github/workflows/deploy-pages.yml`

- [ ] Add a static Pages deployment workflow.
- [ ] Verify workflow file exists and references `public`.
