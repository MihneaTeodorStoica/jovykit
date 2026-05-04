# Images

Images are published to GitHub Container Registry as:

```text
ghcr.io/mihneateodorstoica/labkit-TYPE:latest
ghcr.io/mihneateodorstoica/labkit-TYPE:nightly
ghcr.io/mihneateodorstoica/labkit-TYPE:lts
```

`TYPE` is one of `minimal`, `base`, `extended`, or `full`.

All image variations include client-side SSH tooling:

- `ssh`, `scp`, and `sftp` from OpenSSH
- `git` for SSH-backed remotes
- `rsync` for SSH-backed file sync

The notebook user home directory includes a pre-created `~/.ssh` directory with secure permissions, so keys and SSH config can be mounted into the container at runtime.
