# Changelog

All notable changes to JovyKit are documented here.

Release notes are written for users. Keep each version section accurate to the
tagged diff and group changes by impact.

## Unreleased

## 8.5.0 - 2026-05-21

### CLI

- Add Pylance and quiet Jupyter port metadata to generated Dev Container
  config.
- Persist the VS Code Server directory in a named Dev Container volume for
  faster reconnects without baking editor-specific server binaries into images.

## 8.4.0 - 2026-05-21

### Images

- Add the VS Code Python shell auto-activation block to published images so
  integrated terminals can activate the selected interpreter environment.

## 8.3.2 - 2026-05-20

### Images

- Keep `pip` current in published images and route `pip` commands through the
  writable JovyKit environment to avoid user-install and outdated-version
  warnings.

## 8.3.1 - 2026-05-20

### CLI

- Generate `.devcontainer/devcontainer.json` during `jovy init` so VS Code can
  reopen the Compose-backed JovyKit project as a Dev Container.

### Packaging

- Refresh package, image, documentation, and website version references for
  8.3.1.

## 8.2.1 - 2026-05-20

### Packaging

- Refresh package, image, documentation, and website version references for
  8.2.1.

## 8.2.0 - 2026-05-20

### CLI

- Add `jovy install-docker` to print or run Docker Engine and Compose plugin
  setup for Ubuntu, Debian, Fedora, RHEL, and CentOS.
- Improve `jovy doctor` so Docker CLI, Compose plugin, and daemon access are
  reported separately.
- Fix the Docker install helper so shell truth checks do not leak into generated
  installer commands.

### Docs

- Document Docker requirements and macOS/Windows Docker Desktop setup guidance.

## 8.1.2 - 2026-05-20

### Images

- Publish image variants per Python version from the image workflow.
- Split image build and publish ordering so publish steps run after all matrix
  builds complete.
- Keep provenance attestations out of registry image publication.
- Fix image annotations and matrix output handling.

### Docs

- Improve onboarding copy, tokenized open instructions, and demo media.

### Tests

- Format image workflow tests.

## 8.1.1 - 2026-05-20

### Images

- Point the floating `latest` image tag at `minimal-python-3.14`.
- Remove the generated Compose image name so local builds do not try to pull an
  unpublished overlay image.

## 8.1.0 - 2026-05-19

### Images

- Move published images into one `ghcr.io/mihneateodorstoica/jovykit` package
  with level-first tags such as `base-python-3.11`.
- Point `latest` at `base-python-3.11`.
- Add release, scheduled, and local `build.sh` helpers for channel and latest
  image tags.
- Keep legacy split image references parseable for compatibility.
- Remove the generated Compose `pull_policy`.
- Remove Panel from the extended image and refresh image dependency pins.

### Tooling

- Add `lint.sh`, `test.sh`, and `check.sh`.
- Fix Dependabot image dependency graph metadata.

## 8.0.0 - 2026-05-19

### Breaking Changes

- Remove the Textual dashboard and make `jovy` a compact compose-first CLI.
- Replace project package editing through `jovy.toml` with direct
  `environment.yml` updates from `jovy add` and `jovy remove`.
- Replace split image packages with one multi-stage `image/Dockerfile` and a
  new image build workflow.

### CLI

- Add direct lifecycle and utility commands for `start`, `stop`, `restart`,
  `status`, `logs`, `shell`, `run`, `build`, and `watch`.
- Keep `jovy compose` as the Docker Compose escape hatch.
- Simplify generated project files and keep tokenized JupyterLab URLs visible in
  command output.

### Images

- Build image levels across Python 3.8 through 3.14, including scheduled
  nightly, weekly, and monthly tags.
- Shrink the minimal image by switching to `uv:bookworm-slim` and trimming the
  minimal dependency layer.
- Move heavier ML, validation, and cloud-file packages to the extended image
  layer.
- Add `build.sh` for local image builds and tag generation.

### Docs

- Rewrite the README, website, and wiki pages around the compose-first CLI and
  new image layout.

### Upgrade Notes

- Existing users should review generated Compose files and image tags before
  upgrading from 7.x because the image package layout, project dependency file,
  and dashboard workflow changed.
