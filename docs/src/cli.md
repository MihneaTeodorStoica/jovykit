# CLI

JovyKit manages project-local Jupyter container environments. A root
`jovy.toml` file belongs to one project, while `.jovy/` contains generated
Docker files, dependency manifests, watcher logs, and local build state.
Project files live in `work/` by default and are mounted into the container.

## Create an environment

```bash
jovy init .jovy --image base --gpus auto --port 8888
jovy init .jovy --password dev-password --log-level INFO
```

Image levels are `minimal`, `base`, `extended`, and `full`. You can also pass a
full image reference to `--image`.

Useful initialization options:

- `--name`: project name written to `jovy.toml`
- `--image-name`: overlay image name
- `--tag`: overlay image tag
- `--token`: Jupyter access token. Defaults to empty so JovyKit does not use token auth.
- `--password`: Jupyter password. Defaults to `jovykit`.
- `--log-level`: Jupyter server log level
- `--workdir`: project path mounted into the container
- `--force`: refresh an existing JovyKit environment without initializing a
  non-JovyKit directory

## Add packages

```bash
jovy add pandas scikit-learn plotly
jovy remove plotly
```

Packages are appended to `.jovy/requirements.txt` only when they are not already
present. Removing packages deletes exact manifest entries. Package changes mark
the overlay image stale; run `jovy install`, `jovy run`, or `jovy up` to apply
them.

## Install and run

```bash
jovy install
jovy install --no-build
jovy build
jovy build --no-cache --pull
jovy run
jovy run --watch
jovy up
jovy restart
```

`jovy install` regenerates environment files and builds the overlay image when
the build inputs are stale. `jovy build` only builds the image and does not
start anything. `jovy run` installs if stale and starts Jupyter in the
foreground; `jovy up` installs if stale and starts it in the background. Use
`--no-build` to skip the stale-build check. Docker Compose watch is available
through `jovy run`. Detached `jovy up` and `jovy restart` also launch a
lightweight config watcher that restarts the container when `jovy.toml` changes.

## Customize with TOML

`jovy.toml` supports runtime env vars, extra volumes, restart policy, user,
Jupyter command/logging, Compose Watch controls, build args, build
target/platform, apt packages, and uv/pip install options.

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
jovy down --timeout 10
```

Most commands discover the nearest `jovy.toml` by walking upward from the
current directory. Pass `--env PATH` with either a project root or `.jovy`
directory to operate on a specific environment.

## Clean up

```bash
jovy clean
jovy destroy
jovy destroy --keep-image
jovy destroy --remove-dir
```

`jovy clean` removes generated files and local build state while preserving the
package manifest. `jovy destroy` stops the environment, removes Docker Compose
resources, and removes the project overlay image. `--keep-image` preserves the
image. `--remove-dir` also deletes the JovyKit environment directory.

## Error handling

JovyKit reports common CLI problems without Python tracebacks. For example,
running a command outside a project environment tells you to run `jovy init .jovy`
or pass `--env PATH`; initializing an existing JovyKit environment points to
`--force`.
