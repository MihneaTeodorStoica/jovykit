# JovyKit

JovyKit provides layered Jupyter notebook container images for data science,
machine learning, and research workflows.

The images are designed as progressively larger environments, so users can pick
the smallest image that fits their workload:

- `minimal`: Jupyter runtime plus the core scientific Python stack.
- `base`: everyday data science, classical machine learning, statistics, and
  local data access.
- `extended`: advanced machine learning, NLP, time series, distributed compute,
  and API tooling.
- `full`: heavy frameworks, generative AI tooling, graph and geospatial
  analysis, big data, and additional research utilities.

## Images

Published image variants use the following naming pattern:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:latest
ghcr.io/mihneateodorstoica/jovykit-TYPE:nightly
ghcr.io/mihneateodorstoica/jovykit-TYPE:lts
```

`TYPE` is one of `minimal`, `base`, `extended`, or `full`.

All image variations include client-side SSH tooling for Git remotes, file
copying, and SSH-backed sync:

- `ssh`, `scp`, and `sftp` from OpenSSH
- `git`
- `rsync`

## Build Locally

Build a specific image target from the repository root:

```bash
docker build --target minimal -t jovykit-minimal ./image
docker build --target base -t jovykit-base ./image
docker build --target extended -t jovykit-extended ./image
docker build --target full -t jovykit-full ./image
```

## CLI

JovyKit includes a CLI for project-local container environments. The mental
model is:

```text
.jovy is to JovyKit what .venv is to Python.
```

Create an environment, add project packages, and run Jupyter:

```bash
jovy init .jovy --image base --gpus auto
jovy add pandas scikit-learn plotly
jovy run
```

The CLI writes a reproducible overlay build recipe under `.jovy/`:

```text
.jovy/
  jovy.toml
  requirements.txt
  Containerfile
  compose.yaml
  state.json
```

Useful commands:

```bash
jovy --version
jovy status
jovy status --json
jovy build --pull
jovy sync --no-build
jovy start --no-build
jovy run --watch
jovy logs --tail 100 --since 10m --timestamps --no-follow
jovy shell -c "python --version"
jovy exec python --version
jovy stop --timeout 10
jovy destroy --keep-image
```

Most commands accept `--env PATH` when you want to operate on a JovyKit
environment outside the current project tree. `jovy init` also supports
customizing the generated project name, overlay image name/tag, Jupyter port,
GPU mode, Jupyter token/log level, and mounted work directory.
Docker Compose watch runs with `jovy run`; `jovy start` stays detached.

## Repository Layout

```text
jovykit/              Python CLI package
image/               Dockerfile and layered image dependency manifests
docs/                mdBook documentation
.github/workflows/   CI, security, docs, and image publishing automation
```

## Documentation

The mdBook source lives in `docs/src`.

To build the documentation locally:

```bash
mdbook build docs
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the
development workflow and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community
expectations.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
