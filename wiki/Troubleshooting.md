# Troubleshooting

Use `jovy doctor` first for a quick runtime baseline.

```bash
jovy doctor
```

## Docker daemon unavailable

If doctor shows `daemon: unavailable`:

```bash
docker info
```

Fix:

- Start Docker Engine and then retry `jovy doctor`.
- Linux (systemd): `sudo systemctl start docker`
- macOS/Windows: start Docker Desktop and wait for it to become ready.

`jovy up -d` needs a running daemon.

## Docker socket permission denied

Common message:
`permission denied while trying to connect to the docker daemon socket`

Fix:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Then verify with:

```bash
docker run --rm hello-world
```

If `newgrp` is not enough, log out/in and retry.

## Port already in use

Common message:
`port is already allocated`

Identify the process using the host port:

```bash
lsof -i :8888
```

Then change the host side of the port mapping in `compose.yaml` to a free port:

```yaml
services:
  jovy:
    ports:
      - "127.0.0.1:8899:8888"
```

Restart:

```bash
jovy down
jovy up -d
```

## Image pull timeout

Common message:
`error pulling image` / request timed out.

Use a direct image pull first, then rerun start:

```bash
docker pull ghcr.io/mihneateodorstoica/jovykit:<tag>
jovy up -d --pull always
```

Repeat once the network is stable, and keep `jovy up -d` retrying from a clean state.

## Broken `compose.yaml`

If compose fails before container starts, validate first:

```bash
jovy compose config
```

Most failures are caused by syntax drift:

- broken indentation
- invalid YAML list entries for `ports`/`environment`
- truncated file

If you can restore from source control, revert `compose.yaml` and patch only the needed lines:

```bash
git checkout -- compose.yaml
```

For local edits, keep `compose.yaml` valid YAML and restart with `jovy up -d`.

## Lost Jupyter token

`jovy open` prints a URL containing the active token from compose.

```bash
jovy open
```

If the token in the URL no longer works:

- Read `JUPYTER_TOKEN` in `compose.yaml`.
- Replace it with a new token string.
- Restart the service:

```bash
jovy down
jovy up -d
```

## Helpful commands

```bash
jovy doctor
jovy logs --tail 100
jovy compose config
```
