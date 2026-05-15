# Images

JovyKit publishes layered Jupyter notebook images to GitHub Container Registry.
Use the published images for normal projects.
Build them locally only when changing image contents.

## Published References

```text
ghcr.io/mihneateodorstoica/jovykit-minimal:latest
ghcr.io/mihneateodorstoica/jovykit-base:latest
ghcr.io/mihneateodorstoica/jovykit-extended:latest
ghcr.io/mihneateodorstoica/jovykit-full:latest
```

Rolling tags are also published:

```text
nightly
weekly
monthly
```

`jovy init` accepts friendly names:

| CLI value | Image |
| --- | --- |
| `minimal` | `ghcr.io/mihneateodorstoica/jovykit-minimal:latest` |
| `base` | `ghcr.io/mihneateodorstoica/jovykit-base:latest` |
| `extended` | `ghcr.io/mihneateodorstoica/jovykit-extended:latest` |
| `full` | `ghcr.io/mihneateodorstoica/jovykit-full:latest` |

## Pick An Image

Start with `base`.
It is the best default for notebooks, data work, and local experiments.

Use `minimal` when you want the smallest runtime and will add most packages
yourself.

Use `extended` when the project already needs larger ML, NLP, time-series,
distributed compute, or API tooling.

Use `full` when the project needs the heavy research stack.
It is useful, but it is large.

## Size Budget

Published `linux/amd64` `latest` sizes checked on 2026-05-15:

| Image | Compressed pull size | Layers | Direct packages | Cumulative packages |
| --- | ---: | ---: | ---: | ---: |
| `minimal` | 659 MiB | 37 | 17 | 17 |
| `base` | 927 MiB | 41 | 36 | 53 |
| `extended` | 4.1 GiB | 45 | 44 | 97 |
| `full` | 5.8 GiB | 49 | 57 | 154 |

Compressed pull size is not final disk use.
Docker also keeps unpacked layers, build cache, and the project overlay image.

Plan for:

- 2 CPU cores and 4 GiB RAM for `minimal` or `base`.
- 8 GiB RAM or more for `extended` or `full`.
- Several extra GiB of disk for cache and overlays.

Sizes can drift after image rebuilds.

## Layer Chain

The image chain is made from separate Dockerfiles:

```text
minimal -> base -> extended -> full
```

`minimal` starts from:

```text
quay.io/jupyter/minimal-notebook:python-3.13
```

It copies `uv` and `uvx` from:

```text
ghcr.io/astral-sh/uv:0.11.12
```

It installs:

- `git`
- `openssh-client`
- `rsync`
- `software-properties-common`
- `nvtop-nightly`
- `image/requirements-minimal.txt`

`base` extends `minimal` and installs:

```text
image/requirements-base.txt
```

`extended` extends `base` and installs:

```text
image/requirements-extended.txt
```

`full` extends `extended` and installs:

- `build-essential`
- `nodejs>=20,<23`
- `image/requirements-full.txt`
- a built JupyterLab frontend

`full` removes `build-essential` after the build step.

All variants include:

- `uv` and `uvx`
- `git`
- OpenSSH client tools: `ssh`, `scp`, and `sftp`
- `rsync`
- `nvtop-nightly`
- `/home/jovyan/.ssh` with secure permissions

## Project Overlay Images

`jovy init` does not mutate a published image.
Each project gets a small generated overlay:

```text
.jovy/Containerfile
jovy.lock
```

The overlay starts from the configured base image.
It copies `jovy.lock`.
It installs locked packages with uv into the notebook image.

The overlay image name and tag come from `jovy.toml`:

```toml
[image]
base = "ghcr.io/mihneateodorstoica/jovykit-base:latest"
name = "jovykit-my-project"
tag = "local"
username = "jovyan"
uid = 1000
gid = 100
```

The resulting image reference is:

```text
jovykit-my-project:local
```

## Build The Published Images Locally

Run from the repository root:

```bash
docker build -f image/minimal/Dockerfile -t jovykit-minimal ./image
docker build -f image/base/Dockerfile --build-arg BASE_IMAGE=jovykit-minimal -t jovykit-base ./image
docker build -f image/extended/Dockerfile --build-arg BASE_IMAGE=jovykit-base -t jovykit-extended ./image
docker build -f image/full/Dockerfile --build-arg BASE_IMAGE=jovykit-extended -t jovykit-full ./image
```

Build in that order.
Each layer uses the layer before it.

## Build The Project Overlay

```bash
jovy build
jovy build --no-cache --pull
```

Use `--pull` to refresh the configured base image.
Use `--no-cache` when Docker cache is stale.

Builds can take a while.
The CLI and dashboard show progress while long steps run.

## Customize Project Builds

Edit `jovy.toml` when a project needs custom image behavior:

```toml
[image]
pull_policy = "always"
username = "alice"
uid = 1001
gid = 1001

[image.labels]
"org.example.project" = "analytics"

[image.apt]
packages = ["libpq-dev"]

[image.build_args]
EXAMPLE = "value"

[python]
packages = ["psycopg[binary]", "sqlalchemy"]
pip_args = ["--extra-index-url", "https://example.invalid/simple"]
uv_link_mode = "copy"
```

Then apply the change:

```bash
jovy install
```

or restart the background environment:

```bash
jovy restart
```

## Automation

`.github/workflows/images.yml` builds images in one 45 minute job.
It builds in layer order:

```text
minimal -> base -> extended -> full
```

Pull requests build local `:ci` images.
Pushes and manual runs publish `latest`.
Schedules publish `nightly`, `weekly`, or `monthly`.

Non-PR runs also publish SBOM data and provenance attestations.
