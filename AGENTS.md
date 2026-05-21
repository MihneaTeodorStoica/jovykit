# Repository Guidelines

## Project Structure & Module Organization

JovyKit is a Python 3.11+ CLI package for project-local Jupyter container environments. Core package code lives in `jovykit/`, with the Typer entry point in `jovykit/cli.py` and the console script exposed as `jovy`. Tests live in `tests/` and mirror package behavior by feature, for example `tests/test_cli.py` and `tests/test_config.py`. Container image definitions and layered dependency manifests live in `image/`; update the correct `requirements-*.txt` file for the target image layer. The promotional website lives in `site/` and is published to GitHub Pages. Documentation source pages live in `wiki/` and are published to the GitHub Wiki.

## Build, Test, and Development Commands

- `python -m pip install --upgrade pip && python -m pip install -r requirements-dev.txt`: install local development tooling.
- `python -m pip install -e .`: install JovyKit in editable mode so `jovy` resolves locally.
- `ruff check .`: run Python lint checks.
- `black --check .`: verify formatting without rewriting files.
- `mypy jovykit tests main.py`: type-check the package, tests, and top-level launcher.
- `pytest --cov=jovykit --cov-report=term-missing`: run the full test suite with coverage, matching CI.
- `./build.sh`: build container images locally; use this script whenever building images instead of invoking `docker build` directly.
- Open `site/index.html` in a browser: preview the GitHub Pages website.
- Edit Markdown files in `wiki/`: update GitHub Wiki documentation.

## Coding Style & Naming Conventions

Use Black-formatted Python with 4-space indentation and type annotations for public functions and non-obvious values. Keep CLI command names short, lower-case, and venv-like (`init`, `add`, `sync`, `run`). Prefer `Path` objects for filesystem work and raise `JovyKitError` for user-facing failures instead of leaking tracebacks. Test files should be named `test_*.py`, and test functions should describe behavior, such as `test_run_without_environment_prints_clean_error`.

## Testing Guidelines

Add or update pytest coverage for behavior changes, especially CLI error handling, generated environment files, dependency mutation, and Docker command construction. Use `tmp_path` and `monkeypatch` for filesystem and argv isolation. Run focused tests with `pytest tests/test_cli.py -k init` before the full suite when iterating.

## Commit & Pull Request Guidelines

Recent history uses concise imperative subjects and conventional prefixes such as `chore:` and `ci:`; follow that style when practical. Keep commits scoped to one concern. Pull requests should include a summary, verification commands, linked issues when applicable, and notes about image, docs, security, or release impacts. Follow `.github/PULL_REQUEST_TEMPLATE.md`.

## Release Notes & Changelog

For version bumps, tags, PyPI publishes, or GitHub Releases, update `CHANGELOG.md` before the release. Write user-facing notes under the exact `## X.Y.Z - YYYY-MM-DD` heading that matches `pyproject.toml`, grouped by impact such as breaking changes, CLI, images, packaging, docs, fixes, and upgrade notes. Keep notes accurate to the tag diff; do not dump commit logs or use version bumps as release notes unless that is the only user-visible change. Mention image tag changes, PyPI/package changes, breaking behavior, and upgrade steps when applicable.

## Security & Configuration Tips

Do not commit generated `.jovy/` environments, secrets, registry tokens, or local virtualenvs. Keep image dependencies pinned where possible, and run `pip-audit -r requirements.txt` after dependency changes.

## Audit-to-Issues Workflow

When asked to audit, hunt bugs, review security, or find improvement opportunities, act as a senior security, reliability, and product reviewer. Map the repository first, then inspect domain-specific risk surfaces: application input validation, filesystem and subprocess use, Docker and host interaction, GitHub Actions and release automation, dependencies and package metadata, lifecycle/config state, CLI/UX, tests, documentation, product gaps, and performance. Prefer concrete code evidence over generic advice, label hypotheses clearly, and do not exploit third-party systems, leak secrets, run destructive commands, or make network calls except safe dependency/security metadata lookups.

Use parallel subagents or workstreams where available, divided by domain rather than randomly. When spawning subagents for this workflow, use model `gpt-5.3-codex-spark` by default for faster parallel inspection unless the task explicitly needs a stronger model. Consolidate and deduplicate results into small, actionable findings. For every valid finding, either open a GitHub issue with `gh issue create` or, when public disclosure would be unsafe, prepare/report it as a private security advisory instead of a public issue. Each issue/report must include title, type, severity or priority, affected files/functions/workflows, concrete evidence, reproduction steps or reasoning, expected behavior, actual behavior/risk, suggested fix, suggested tests, and whether it is safe to publish publicly.

## Issue-Fixing Workflow

When asked to fix issues, burn down the backlog, resolve audit findings, or work through GitHub issues, triage the open issues first and group them by domain, dependency, and risk. Prioritize security, release, CI/CD, correctness, and failing tests before lower-priority UX, docs, and polish. Use parallel subagents or workstreams where available, assigning each one a clear ownership area such as security fixes, CI/CD hardening, Docker/image work, CLI/config bugs, tests, documentation, or product features. When spawning subagents for this workflow, use model `gpt-5.3-codex-spark` by default for faster parallel fixing unless the task explicitly needs a stronger model. Tell subagents they are not alone in the codebase and must not revert or overwrite other work.

Fix issues one by one or in small compatible batches. For each issue, inspect only the files needed, implement the smallest safe change, add or update focused tests/docs, run the relevant targeted validation, and link the result back to the issue. When a bug is fixed, push the branch and open a pull request for the fix. After pull request workflows pass, merge the pull request. Close each issue after its fix is implemented, validated, and committed. Do not close an issue before the fix is implemented, validated, and committed unless explicitly requested. Once workflows pass for a pull request, merge it before starting unrelated cleanup. After closing a solved issue, continue with the next open issue until the requested backlog is done. If an issue is invalid, duplicate, too risky, or needs a product decision, comment with concrete evidence and leave it open unless instructed otherwise. Prefer concise commits with issue references, keep security-sensitive details out of public comments when needed, and never include secrets, destructive cleanup, force-pushes, or broad rewrites without explicit approval.
