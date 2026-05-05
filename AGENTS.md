# Repository Guidelines

## Project Structure & Module Organization

JovyKit is a Python 3.11+ CLI package for project-local Jupyter container environments. Core package code lives in `jovykit/`, with the Typer entry point in `jovykit/cli.py` and the console script exposed as `jovy`. Tests live in `tests/` and mirror package behavior by feature, for example `tests/test_cli.py` and `tests/test_config.py`. Container image definitions and layered dependency manifests live in `image/`; update the correct `requirements-*.txt` file for the target image layer. Documentation source pages live in `wiki/` and are published to the GitHub Wiki.

## Build, Test, and Development Commands

- `python -m pip install --upgrade pip && python -m pip install -r requirements-dev.txt`: install local development tooling.
- `python -m pip install -e .`: install JovyKit in editable mode so `jovy` resolves locally.
- `ruff check .`: run Python lint checks.
- `black --check .`: verify formatting without rewriting files.
- `mypy jovykit tests main.py`: type-check the package, tests, and top-level launcher.
- `pytest --cov=jovykit --cov-report=term-missing`: run the full test suite with coverage, matching CI.
- `docker build --target minimal -t jovykit-minimal ./image`: build one image layer locally; replace `minimal` with `base`, `extended`, or `full` as needed.
- Edit Markdown files in `wiki/`: update GitHub Wiki documentation.

## Coding Style & Naming Conventions

Use Black-formatted Python with 4-space indentation and type annotations for public functions and non-obvious values. Keep CLI command names short, lower-case, and venv-like (`init`, `add`, `sync`, `run`). Prefer `Path` objects for filesystem work and raise `JovyKitError` for user-facing failures instead of leaking tracebacks. Test files should be named `test_*.py`, and test functions should describe behavior, such as `test_run_without_environment_prints_clean_error`.

## Testing Guidelines

Add or update pytest coverage for behavior changes, especially CLI error handling, generated environment files, dependency mutation, and Docker command construction. Use `tmp_path` and `monkeypatch` for filesystem and argv isolation. Run focused tests with `pytest tests/test_cli.py -k init` before the full suite when iterating.

## Commit & Pull Request Guidelines

Recent history uses concise imperative subjects and conventional prefixes such as `chore:` and `ci:`; follow that style when practical. Keep commits scoped to one concern. Pull requests should include a summary, verification commands, linked issues when applicable, and notes about image, docs, security, or release impacts. Follow `.github/PULL_REQUEST_TEMPLATE.md`.

## Security & Configuration Tips

Do not commit generated `.jovy/` environments, secrets, registry tokens, or local virtualenvs. Keep image dependencies pinned where possible, and run `pip-audit -r requirements.txt` after dependency changes.
