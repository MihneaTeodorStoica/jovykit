# Images

JovyKit publishes layered Jupyter notebook images to GitHub Container Registry.
The CLI can use these images directly, or you can build them from the repository
for local testing.

## Published references

```text
ghcr.io/mihneateodorstoica/jovykit-minimal:latest
ghcr.io/mihneateodorstoica/jovykit-base:latest
ghcr.io/mihneateodorstoica/jovykit-extended:latest
ghcr.io/mihneateodorstoica/jovykit-full:latest
```

The image publishing workflow may also publish `nightly` and `lts` tags.

`jovy init` accepts these friendly names and maps them to the `latest` images:

| CLI value | Image |
| --- | --- |
| `minimal` | `ghcr.io/mihneateodorstoica/jovykit-minimal:latest` |
| `base` | `ghcr.io/mihneateodorstoica/jovykit-base:latest` |
| `extended` | `ghcr.io/mihneateodorstoica/jovykit-extended:latest` |
| `full` | `ghcr.io/mihneateodorstoica/jovykit-full:latest` |

## Layers

The Dockerfile defines four build targets:

- `minimal` starts from Jupyter's minimal notebook image and installs the core
  JovyKit runtime packages from `image/requirements-minimal.txt`.
- `base` extends `minimal` with everyday data-science packages from
  `image/requirements-base.txt`.
- `extended` starts from Jupyter's base notebook image and installs the
  minimal, base, and extended dependency manifests.
- `full` extends `extended` with the heavier packages in
  `image/requirements-full.txt`.

All image variants include:

- `uv` and `uvx`
- `git`
- OpenSSH client tools: `ssh`, `scp`, and `sftp`
- `rsync`
- a pre-created `/home/jovyan/.ssh` directory with secure permissions

That setup supports SSH-backed Git remotes, SSH file copy, and runtime mounting
of local SSH configuration.

## Project overlay images

`jovy init` does not modify a published base image. Instead, each project gets a
small generated overlay image:

```text
.jovy/Containerfile
jovy.lock
```

The overlay image starts from the configured base image, copies the project
lockfile, and installs locked packages with uv into the system Python
environment inside the notebook image.

The overlay image name and tag come from `jovy.toml`:

```toml
[image]
base = "ghcr.io/mihneateodorstoica/jovykit-base:latest"
name = "jovykit-my-project"
tag = "local"
```

The resulting image reference is:

```text
jovykit-my-project:local
```

## Build locally

Build one published-image target from the repository root:

```bash
docker build --target minimal -t jovykit-minimal ./image
docker build --target base -t jovykit-base ./image
docker build --target extended -t jovykit-extended ./image
docker build --target full -t jovykit-full ./image
```

Build the current project's overlay image:

```bash
jovy build
jovy build --no-cache --pull
```

Use `--no-cache` when the image cache is stale, and `--pull` to refresh base
images before build.

## Customize project builds

Edit `jovy.toml` when a project needs extra operating-system packages, build
arguments, or pip options:

```toml
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

or restart the background environment with:

```bash
jovy restart
```
