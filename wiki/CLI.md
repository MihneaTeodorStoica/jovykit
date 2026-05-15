# CLI

The `jovy` CLI manages one project-local Jupyter environment at a time.

Most commands walk up from the current directory and find the nearest
`jovy.toml`.
Use `--env PATH` when targeting a specific project root or `.jovy` directory.

```bash
jovy              # open the dashboard
jovy dashboard    # same dashboard, explicit command
jovy status       # print project status
jovy open         # open the current Jupyter URL
```

## Global Pattern

Most subcommands accept `--env`:

```bash
jovy --env /path/to/project status
jovy --env .jovy logs --tail 100
```

## init

Create a new environment.

```bash
jovy init .jovy
jovy init .jovy --image base --gpus auto --port 8888
jovy init .jovy --token dev-token --log-level INFO
```

Common options:

- `--image`: `minimal`, `base`, `extended`, `full`, or a full image reference.
- `--gpus`: `auto`, `none`, or `all`.
- `--port`: local port mapped to container port `8888`.
- SSH is exposed on `127.0.0.1:22` to container port `22` by default.
- `--token`: token shown in the Jupyter URL. Default: `jovykit`.
- `--log-level`: Jupyter server log level.
- `--name`: project name stored in `jovy.toml`.
- `--image-name`: project overlay image name.
- `--tag`: project overlay image tag. Default: `local`.
- `--workdir`: mounted work directory. Default: `work`.
- `--force`: refresh an existing environment.

After `init`, run `jovy add ...` or `jovy up`.
`init` does not claim Jupyter is running.

## add / remove

```bash
jovy add pandas scikit-learn plotly
jovy add -r requirements.txt
jovy add -r requirements.txt -r requirements-dev.txt
jovy remove plotly
```

`add` writes entries to `[python].packages`.
`add -r` stores constraints under `[python].constraints`.

- `add` and `remove` update `jovy.toml`.
- `add` and `remove` refresh `jovy.lock`.
- `jovy install`, `jovy build`, `jovy run`, or `jovy up` apply the lock to the
  generated overlay image.

## install and build

```bash
jovy install
jovy install --upgrade
jovy install --no-build
jovy build
jovy build --no-cache --pull
jovy build -v
```

`install` does three things:

- regenerate `.jovy/compose.yaml` and `.jovy/Containerfile`
- update `jovy.lock` through uv
- build the project overlay image when inputs are stale

Use `--upgrade` to refresh locked package versions.
Use `--no-build` when you only need local file refresh.

Long install and build work shows progress in the CLI and dashboard.

## run, up, start, down, stop, restart

```bash
jovy run
jovy run --watch
jovy run --no-watch
jovy up
jovy start      # alias for up
jovy down
jovy stop       # alias for down
jovy down --timeout 10
jovy restart
```

- `run` starts Jupyter in the foreground and streams logs.
- `up` starts Jupyter in the background.
- `start` is an alias for `up`.
- `down` stops the environment without deleting generated files, images,
  lockfiles, work files, or home data.
- `stop` is an alias for `down`.
- `restart` restarts the background environment.

Use `run` when you want the current terminal to own the process.
Use `up` when you want to keep working in the same shell or dashboard.

## open

```bash
jovy open
jovy --env /path/to/project open
```

`open` opens the current Jupyter URL in the default browser.
It does not start the container.
If no URL is available, start the project with:

```bash
jovy up
```

## status and logs

```bash
jovy status
jovy status --json
jovy logs
jovy logs --tail 100
jovy logs --since 10m --timestamps
jovy logs --no-follow
```

`status --json` is useful for scripts.
It contains image reference, URL, home mount, work mount, package count, build
state, and environment path.

## shell and exec

```bash
jovy shell
jovy shell --command "python --version"
jovy exec python --version
jovy exec pip list
```

`shell` opens an interactive shell inside the running container by default.
`exec` requires a command and runs directly in the container.

## config

```bash
jovy config
```

The interactive config editor manages common runtime options:

- images and ports
- GPU mode
- Jupyter arguments
- restart policy
- env vars and extra volumes
- packages and install tooling options

When editing `jovy.toml` by hand, run `jovy install` before restarting an
environment.

## clean and destroy

```bash
jovy clean
jovy destroy
jovy destroy --keep-image
jovy destroy --purge
jovy destroy --yes --purge
```

- `clean` removes generated local build state and keeps `jovy.toml`,
  `jovy.lock`, the work directory, and `.jovy/home/`.
- `destroy` removes runtime resources and the overlay image by default.
- `destroy` preserves home data at `.jovy/home/`.
- `destroy --keep-image` preserves the overlay image.
- `destroy --purge` also deletes `.jovy/home/` and asks for confirmation.
- `destroy --yes --purge` is the non-interactive purge path for automation.
- `destroy --remove-dir` is deprecated. It is skipped unless `--purge` is also
  passed.

## Dashboard

Open the dashboard:

```bash
jovy
jovy dashboard
jovy dashboard --env /path/to/project
```

Enter commands without the `jovy` prefix:

```text
status
up
down
add numpy
install
config
open
```

The dashboard keeps one command active at a time.
If you enter more commands during a build or start, they are queued and run in
order.

Run host shell commands with `!`:

```text
!pwd
!git status
```

Dashboard-local helper commands:

- `help`, `?`
- `clear`, `cls`
- `open`, `url`, `browser`
- `refresh`, `reload`
- `quit`, `exit`, `q`

Dashboard aliases:

- `build`, `b`, `rebuild`
- `up`, `start`, `u`
- `down`, `stop`, `d`
- `restart`, `r`
- `shell`, `sh`
- `exec`, `x`
- `status`, `s`, `ps`
- `config`, `settings`, `c`
- `clean`, `reset-build`

Blocked in the dashboard:

- `run`: use `up` in-dashboard, or run `jovy run` in your terminal.
- `logs`: use the dashboard log view or run `jovy logs` in your terminal.
- `destroy`: run `jovy destroy` in your shell so confirmation is visible.
- `sync`: no dedicated sync command exists; use `install`.

## Error Handling

JovyKit wraps expected user-facing failures in clean messages and exits with a
non-zero code.

Common issues:

- running outside a JovyKit project
- invalid `jovy.toml`
- using `jovy init` in a non-empty directory that is not already managed
- trying to open a URL before the environment has started
