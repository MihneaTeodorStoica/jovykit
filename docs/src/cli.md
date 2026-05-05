# CLI

JovyKit manages project-local Jupyter container environments. A `.jovy`
directory belongs to one project and contains the configuration, generated
Docker files, dependency manifest, and local build state for that project.
Project files live in `work/` by default and are mounted into the container.

## Create an environment

```bash
jovy init .jovy --image base --gpus auto --port 8888
jovy init .jovy --token dev-token --log-level INFO
```

Image levels are `minimal`, `base`, `extended`, and `full`. You can also pass a
full image reference to `--image`.

Useful initialization options:

- `--name`: project name written to `jovy.toml`
- `--image-name`: overlay image name
- `--tag`: overlay image tag
- `--token`: Jupyter access token, or `auto` for Jupyter's generated token
- `--log-level`: Jupyter server log level
- `--workdir`: project path mounted into the container
- `--force`: refresh an existing JovyKit environment without initializing a
  non-JovyKit directory

## Add packages

```bash
jovy add pandas scikit-learn plotly
jovy add polars --sync
```

Packages are appended to `.jovy/requirements.txt` only when they are not already
present. Adding packages marks the overlay image stale; `--sync` regenerates the
environment files and rebuilds immediately.

## Build and run

```bash
jovy build
jovy build --no-cache --pull
jovy sync
jovy sync --no-build
jovy run
jovy run --watch
jovy start
```

`jovy run` starts Jupyter in the foreground. `jovy start` starts it in the
background. Both regenerate files and build the overlay image when the build
inputs are stale. Use `--no-build` to skip the stale-build check.
Docker Compose watch is available through `jovy run`; detached `jovy start`
does not enable watch because Compose does not support combining both modes.

## Operate on a running environment

```bash
jovy status
jovy --version
jovy status --json
jovy logs --tail 100
jovy logs --since 10m --timestamps
jovy logs --no-follow
jovy shell
jovy shell -c "python --version"
jovy exec python --version
jovy stop --timeout 10
```

Most commands discover the nearest `.jovy/jovy.toml` by walking upward from the
current directory. Pass `--env PATH` to operate on a specific environment.

## Clean up

```bash
jovy destroy
jovy destroy --keep-image
jovy destroy --remove-dir
```

`jovy destroy` removes Docker Compose resources and the project overlay image.
`--keep-image` preserves the image. `--remove-dir` also deletes the JovyKit
environment directory.

## Error handling

JovyKit reports common CLI problems without Python tracebacks. For example,
running a command outside a project environment tells you to run `jovy init .jovy`
or pass `--env PATH`; initializing an existing JovyKit environment points to
`--force`.
