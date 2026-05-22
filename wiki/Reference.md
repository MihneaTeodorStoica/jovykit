# Reference

## CLI

The command reference is in [CLI](CLI).

Core project commands:

- `jovy init`: create `compose.yaml`, `Dockerfile`, `requirements.txt`,
  `.devcontainer/devcontainer.json`, `work/`, and `.jupyter/`.
- `jovy add` and `jovy remove`: edit `requirements.txt`.
- `jovy upgrade`: rewrite editable image, Python, GPU, port, and token settings.
- `jovy doctor`: check Docker, Compose, project files, repairs, and security.

## Config files

JovyKit stores project state in generated, editable files:

- `compose.yaml`: service settings, port binding, volumes, GPU mode, token, and
  build args.
- `Dockerfile`: local image layer built from `JOVY_BASE_IMAGE`.
- `requirements.txt`: project Python packages installed into `/opt/jovy`.
- `.devcontainer/devcontainer.json`: VS Code Dev Container attachment settings.
- `.jupyter/`: persisted Jupyter config and runtime state.
- `work/`: notebooks and project files mounted into JupyterLab.

## Images

Image level behavior and tags are in [Images](Images).

## Automation and checks

- Local checks:

```bash
ruff check .
black --check .
mypy jovykit tests main.py
pytest --cov=jovykit --cov-report=term-missing
```

- GitHub workflow overview: [Automation](Automation).
