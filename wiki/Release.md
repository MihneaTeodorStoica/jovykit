# Release Process

Use this for every release, including package and image publishing.

## Version and changelog checklist

Before merging to `main`:

- Set the next release in `pyproject.toml`:
  - `[project]`
  - `version = "X.Y.Z"`
- Move planned notes into a new section in `CHANGELOG.md`:
  - `## X.Y.Z - YYYY-MM-DD`
- Keep release notes grouped by area (`CLI`, `Images`, `Packaging`, `Docs`, etc.).
- Keep the notes section non-empty for the release version.
- Validate core checks:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing
```

## Release workflow

`.github/workflows/ci-release.yml` handles:

1. security and Python checks
2. version read from `pyproject.toml`
3. tag creation as `vX.Y.Z` if missing
4. package build
5. PyPI publish with trusted publishing
6. GitHub release notes from `CHANGELOG.md`

`ci-release` reads the `## X.Y.Z` heading from `CHANGELOG.md`.
If the section is missing or empty, release notes extraction fails and publish stops.

Tag behavior:

- tag already exists: workflow skips publish on normal runs
- tag exists + manual `workflow_dispatch`: workflow republishes that tag
- new tag missing: workflow creates and pushes `vX.Y.Z`, then publishes

Recommended manual triggers and checks:

```bash
gh workflow run ci-release.yml --ref main
gh run list --workflow ci-release.yml --limit 5
gh run view <RUN_ID> --log-failed
```

## PyPI trusted publishing

`ci-release.yml` uses:

- `id-token: write`
- `pypa/gh-action-pypi-publish@release/v1`
- GitHub environment `pypi`

PyPI must allow trusted publishing for repository `MihneaTeodorStoica/jovykit`.
Use a new version bump for rollback instead of overwrite.

## Image publishing

`.github/workflows/images.yml` builds image targets from `image/Dockerfile`:

`minimal`, `base`, `extended`, `full`

Current published tags:

- `<level>-python-<major.minor>`
- `<level>-<channel>-python-<major.minor>` for scheduled builds (`nightly`, `weekly`)
- `<level>-python-<major.minor>-<tag>` for tag-triggered releases
- `latest` is set for `minimal`/`3.14` in publish metadata

Scheduled image publishes run with:

- `minimal` and `base` for Python 3.12 only

Scheduled image runs:

- daily (`30 6 * * *`) publishes `-nightly` tags
- weekly (`30 6 * * 1`) publishes `-weekly` tags

## Rollback strategy

- package problem: publish the next version and yank the bad release in PyPI if needed
- image problem: delete/retag via GitHub Container Registry UI and re-run image workflow with the desired targets
