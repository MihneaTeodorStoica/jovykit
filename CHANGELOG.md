# Changelog

All notable changes to this project will be documented in this file.

This project follows a simple date-oriented changelog until formal releases are
introduced.

## Unreleased

## 8.1.1 - 2026-05-20

- Point `latest` at `minimal-python-3.14`.
- Remove the generated Compose image name so local builds do not try to pull it.

## 8.1.0 - 2026-05-19

- Publish all levels under the single `jovykit` image with `LEVEL-python-VERSION` tags.
- Point `latest` at `base-python-3.11`.
- Use level-specific scheduled tags such as `base-nightly-python-3.11`.
- Add `build.sh --latest` and `build.sh --channel` tag helpers.
- Remove generated Compose `pull_policy`.
- Add `lint.sh`, `test.sh`, and `check.sh`.

- Removed the Textual dashboard.
- Added a small CLI abstraction for `start`, `stop`, `restart`, `status`,
  `logs`, `shell`, `run`, `build`, and `watch`, with `jovy compose` as the
  Docker Compose escape hatch.
- Made `jovy add` and `jovy remove` edit `environment.yml` directly.
- Replaced per-layer image Dockerfiles with one multi-stage `image/Dockerfile`.
- Rebased published images on `condaforge/miniforge3:latest` with
  mamba-managed Python environments.
- Embedded the environment bootstrap in generated project Dockerfiles so stale
  base images without `jovy-install-environment` still work.
- Omitted the generated Compose `gpus` field for `--gpu none`.
- Kept the base image lean by moving heavier ML, validation, and cloud-file
  packages to the extended layer.
- Made `build.sh` tag the minimal image as base instead of building a separate
  base layer.
- Bumped package version to 8.0.0.
- Bumped package version to 3.1.0 for the dashboard and install workflow polish.
- Changed `jovy install` to build updates before quickly recreating a running
  container, avoiding a long stop-then-build downtime window.
- Reduced dashboard redraw flicker during background commands.
- Showed tokenized JupyterLab URLs consistently in CLI and dashboard output.
- Streamed `shell <command>` dashboard commands into the log panel instead of
  suspending the terminal.
- Bumped package version to 3.0.2.
- Removed generated Jupyter password configuration and kept token-only
  authentication with a default `jovykit` token.
- Bumped package version to 3.0.1.
- Moved the dashboard command input above the live log panel.
- Streamed destructive dashboard command output into the log panel so `destroy`
  no longer writes over the Textual screen.
- Suspended the dashboard cleanly for foreground commands such as `shell` and
  `run`, then restored input focus on return.
- Made dashboard `init` use the default Jupyter credential unless overridden.
- Bumped package version to 3.0.0.
- Replaced project environment `requirements.txt` manifests with
  `[python].packages` in `jovy.toml` plus a generated `.jovy/jovy.lock`.
- Added recursive `jovy add -r/--requirement` imports and
  `jovy install --upgrade` lock refreshes.
- Bumped package version to 2.1.1.
- Fixed dashboard command completion so Textual app-thread status updates no
  longer call `call_from_thread`.
- Bumped package version to 2.1.0.
- Escaped generated Argon2 Jupyter password hashes so Docker Compose no longer
  treats `$argon2id`, `$v`, or `$m` hash segments as environment variables.
- Added a Textual dashboard that opens with bare `jovy` while preserving the
  scriptable CLI command set.
- Switched generated Jupyter password hashes to Argon2 for security scanning.
- Bumped package version to 2.0.2.
- Added a default Jupyter password and print it from `jovy init` and `jovy up`.
- Bumped package version to 2.0.1.
- Changed the default Jupyter token to empty and always generated
  `JUPYTER_TOKEN`, so JovyKit no longer relies on Jupyter's generated token.
- Bumped package version to 2.0.0 for the breaking CLI lifecycle rename.
- Replaced `jovy sync` with `jovy install`.
- Replaced detached `jovy start` and `jovy stop` with `jovy up` and
  `jovy down`.
- Added `jovy remove`, `jovy restart`, and `jovy clean`.
- Fixed `jovy destroy` so removing the local overlay image invalidates build
  state before the next `jovy up`.
- Fixed generated Compose Watch paths for root-level config files.
- Added TOML customization for runtime, watch, and image build behavior.
- Moved `jovy.toml` to the project root and added config-change restarts.
- Changed new environments to use `work/` as the mounted project directory.
- Fixed detached startup so it does not pass Docker Compose watch.
- Added `jovy --version`, Jupyter init flags, and additional log filtering
  flags.
- Fixed generated Compose files so Jupyter token settings, custom workdirs, and
  Docker Compose watch configuration are honored.
- Added community health documentation.
- Added layered Jupyter notebook image definitions.
