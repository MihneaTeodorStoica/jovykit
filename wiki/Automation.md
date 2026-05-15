# Automation

The repository uses GitHub Actions for checks, security scans, images,
releases, labels, the website, and the wiki.

## Main CI And Release

`.github/workflows/ci-release.yml` runs on:

- pushes to `main`
- pull requests to `main`
- weekly schedules
- manual dispatches

Security jobs run first:

- CodeQL for Python
- Semgrep for Python and security audit rules
- Zizmor for workflow checks
- Dependency Review on pull requests

The security gate waits for those jobs.
When it passes, the Python matrix runs on Python 3.11 and 3.12:

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

On successful pushes and manual runs, release jobs read `pyproject.toml`.
They create a matching `vX.Y.Z` tag when needed.
They then build and publish the package.

## Time Budgets

These are the workflow timeout budgets.
They are useful when judging how much a change can cost.

Main CI and release job budgets:

| Job | Timeout |
| --- | ---: |
| CodeQL | 20 min |
| Semgrep | 15 min |
| Zizmor | 10 min |
| Dependency Review | 10 min |
| Security gate | 5 min |
| Python 3.11 | 15 min |
| Python 3.12 | 15 min |
| Create tag | 10 min |
| Build package from tag | 10 min |
| Publish to PyPI | 10 min |

Full push publish maximum runner budget:

```text
20 + 15 + 10 + 10 + 5 + 15 + 15 + 10 + 10 + 10 = 120 runner-min
```

Full push publish longest timeout path:

```text
20 security fanout + 5 gate + 15 Python + 10 tag + 10 package + 10 publish = 70 min
```

Pull request longest timeout path:

```text
20 security fanout + 5 gate + 15 Python = 40 min
```

Scheduled CI longest timeout path:

```text
20 security fanout + 5 gate = 25 min
```

Scheduled runs skip the Python matrix.

## Image Publishing

`.github/workflows/images.yml` builds and publishes the notebook images.

It has one 45 minute job.
The job builds separate Dockerfiles in layer order:

```text
minimal -> base -> extended -> full
```

Published images use:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:TAG
```

`TYPE` is:

```text
minimal
base
extended
full
```

Published tags are:

```text
latest
nightly
weekly
monthly
```

Pull requests build local `:ci` images.
Pushes and manual runs publish `latest`.
Scheduled runs publish the matching rolling tag.

Non-PR image runs also publish:

- SBOM data
- provenance attestations

Current `linux/amd64` `latest` size checks from 2026-05-15:

| Image | Compressed pull size | Layers |
| --- | ---: | ---: |
| `minimal` | 659 MiB | 37 |
| `base` | 927 MiB | 41 |
| `extended` | 4.1 GiB | 45 |
| `full` | 5.8 GiB | 49 |

See [Images](Images) for contents and local build commands.

## Website Publishing

`.github/workflows/pages.yml` publishes `site/` to GitHub Pages.

It runs on:

- pushes to `main` when `site/**` changes
- changes to `.github/workflows/pages.yml`
- manual dispatches

Timeout:

```text
10 min
```

## Wiki Publishing

Documentation source lives in `wiki/`.

`.github/workflows/wiki.yml` copies these pages into the GitHub Wiki:

```text
wiki/Home.md
wiki/CLI.md
wiki/Images.md
wiki/Automation.md
wiki/_Sidebar.md
wiki/_Footer.md
```

It runs on:

- pushes to `main` when `wiki/**` changes
- changes to `.github/workflows/wiki.yml`
- manual dispatches

Timeout:

```text
10 min
```

GitHub only exposes `jovykit.wiki.git` after the wiki exists.
If the workflow cannot clone it, create one wiki page in the GitHub UI.
Then rerun the workflow.

## Labels And Dependency Updates

`.github/workflows/pr-labels.yml` applies labels from `.github/labeler.yml`.

Timeout:

```text
5 min
```

`.github/dependabot.yml` controls dependency update pull requests.

Issue templates, the pull request template, security policy, support notes, and
governance files live under `.github/` and the repository root.
