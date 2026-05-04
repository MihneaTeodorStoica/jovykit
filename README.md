# Labkit

Labkit provides layered Jupyter notebook container images for data science,
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
ghcr.io/mihneateodorstoica/labkit-TYPE:latest
ghcr.io/mihneateodorstoica/labkit-TYPE:nightly
ghcr.io/mihneateodorstoica/labkit-TYPE:lts
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
docker build --target minimal -t labkit-minimal ./image
docker build --target base -t labkit-base ./image
docker build --target extended -t labkit-extended ./image
docker build --target full -t labkit-full ./image
```

## CLI Preview

LabKit also includes an early CLI for project-local container environments. The
mental model is:

```text
.lab is to LabKit what .venv is to Python.
```

Create an environment, add project packages, and run Jupyter:

```bash
lab init .lab --image base --gpus auto
lab add pandas scikit-learn plotly
lab run
```

The CLI writes a reproducible overlay build recipe under `.lab/`:

```text
.lab/
  lab.toml
  requirements.txt
  Containerfile
  compose.yaml
  state.json
```

Useful MVP commands:

```bash
lab build
lab start
lab stop
lab shell
lab logs
lab destroy
```

## Repository Layout

```text
labkit/              Python CLI package
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
