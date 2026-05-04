# Images

Images are published to GitHub Container Registry as:

```text
ghcr.io/mihneateodorstoica/labkit:TYPE-YYYY-MM-DD
ghcr.io/mihneateodorstoica/labkit:TYPE
```

`TYPE` is one of `minimal`, `base`, `extended`, or `full`.

The dated tag is immutable for a build date. The floating `TYPE` tag points at the latest published image for that variation.

All image variations include client-side SSH tooling:

- `ssh`, `scp`, and `sftp` from OpenSSH
- `git` for SSH-backed remotes
- `rsync` for SSH-backed file sync

The notebook user home directory includes a pre-created `~/.ssh` directory with secure permissions, so keys and SSH config can be mounted into the container at runtime.
