# Automation

The repository uses GitHub Actions for Python checks, security scanning, image
publishing, pull request labeling, releases, website publishing, and wiki
publishing.

## Main CI and release workflow

`.github/workflows/ci-release.yml` runs on pushes to `main`, pull requests,
weekly schedules, and manual dispatches.

Security jobs run first:

- CodeQL for Python.
- Semgrep with Python and security-audit rules.
- Zizmor for GitHub Actions workflow checks.
- Dependency Review on pull requests.

When the security gate passes, the Python matrix runs on Python 3.11 and 3.12:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing --cov-fail-under=90
```

The Python 3.12 job also runs:

```bash
pip-audit -r requirements.txt
python -m build
```

On successful pushes or manual runs, the release portion reads the version from
`pyproject.toml`, creates the matching `vX.Y.Z` tag when needed, and continues
into the release jobs.

## Image publishing

`.github/workflows/images.yml` builds and publishes the layered notebook images.
The Dockerfile targets are:

- `minimal`
- `base`
- `extended`
- `full`

Images are published to GitHub Container Registry under:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:TAG
```

See [Images](Images) for the image layout and local build commands.

## Website publishing

`.github/workflows/pages.yml` publishes the promotional website from `site/` to
GitHub Pages. It runs on pushes to `main` when website files change, and it can
also be run manually.

## Wiki publishing

Documentation source lives in `wiki/`. The `Wiki` workflow copies those pages
into the GitHub Wiki repository:

```text
wiki/Home.md
wiki/CLI.md
wiki/Images.md
wiki/Automation.md
wiki/_Sidebar.md
```

The workflow runs when `wiki/**` or the workflow file changes on `main`, and it
can also be run manually.

GitHub only exposes the backing `jovykit.wiki.git` repository after the wiki has
been initialized. If the workflow reports that the wiki repository is not
available yet, create the first wiki page once in the GitHub UI, then rerun the
workflow.

## Labels and dependency updates

`.github/workflows/pr-labels.yml` applies labels using `.github/labeler.yml`.

`.github/dependabot.yml` controls dependency update pull requests.

Issue templates, the pull request template, security policy, support notes, and
governance files live under `.github/` and the repository root.
