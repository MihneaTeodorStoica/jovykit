# Contributing

Thank you for considering a contribution to JovyKit.

## Ways to Contribute

- Report bugs or broken image builds.
- Suggest packages that belong in a specific image layer.
- Improve documentation.
- Tighten CI, security scanning, or release automation.
- Fix dependency or container build issues.

## Development Workflow

1. Fork the repository or create a branch.
2. Keep changes focused and scoped to one concern.
3. Update documentation when behavior, image contents, or workflows change.
4. Run the checks that apply to your change.
5. Open a pull request with a clear description of the change and verification.

## Local Checks

Install development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Run Python checks:

```bash
ruff check .
black --check .
mypy .
pytest
```

Build an image target:

```bash
docker build --target minimal -t jovykit-minimal ./image
```

Preview documentation changes:

Edit the Markdown pages in `wiki/` and review them with GitHub Wiki rendering
before merging.

## Image Layering Guidelines

- Put common notebook/runtime packages in `image/requirements-minimal.txt`.
- Put everyday data science packages in `image/requirements-base.txt`.
- Put advanced ML, NLP, distributed compute, and API packages in
  `image/requirements-extended.txt`.
- Put heavy frameworks and specialized research tools in
  `image/requirements-full.txt`.
- Prefer pinned package versions for reproducible image builds.

## Maintainer

Maintainer: Mihnea-Teodor Stoica <ms7322@columbia.edu>
