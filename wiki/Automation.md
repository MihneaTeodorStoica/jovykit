# Automation

The repository uses GitHub Actions for checks, releases, images, the website,
and the wiki.

## CI And Release

`.github/workflows/ci-release.yml` runs lint, formatting, typing, tests, audits,
package build, and release publishing.

Local equivalent:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing
```

## Images

`.github/workflows/images.yml` builds `image/Dockerfile` targets:

```text
minimal
base
extended
full
```

Published image names:

```text
ghcr.io/mihneateodorstoica/jovykit-minimal:python-3.13
ghcr.io/mihneateodorstoica/jovykit-base:python-3.13
ghcr.io/mihneateodorstoica/jovykit-extended:python-3.13
ghcr.io/mihneateodorstoica/jovykit-full:python-3.13
```

Schedules publish `nightly-python-3.x`, `weekly-python-3.x`, and `monthly-python-3.x`
for every supported Python version. The default Python version also gets
`nightly`, `weekly`, and `monthly`.

Local image builds use:

```bash
./build.sh
./build.sh --python-version 3.13 minimal
./build.sh --python 3.13 --python 3.14 minimal base
```

## Website

`.github/workflows/pages.yml` publishes `site/` to GitHub Pages.

## Wiki

Documentation source lives in `wiki/`.

`.github/workflows/wiki.yml` copies:

```text
wiki/Home.md
wiki/CLI.md
wiki/Images.md
wiki/Automation.md
wiki/_Sidebar.md
wiki/_Footer.md
```

GitHub exposes `jovykit.wiki.git` only after the wiki exists.
