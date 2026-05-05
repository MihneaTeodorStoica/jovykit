# Images

JovyKit images are published to GitHub Container Registry as:

```text
ghcr.io/mihneateodorstoica/jovykit-TYPE:latest
ghcr.io/mihneateodorstoica/jovykit-TYPE:nightly
ghcr.io/mihneateodorstoica/jovykit-TYPE:lts
```

`TYPE` is one of `minimal`, `base`, `extended`, or `full`.

All image variations include client-side SSH tooling:

- `ssh`, `scp`, and `sftp` from OpenSSH
- `git` for SSH-backed remotes
- `rsync` for SSH-backed file sync

The notebook user home directory includes a pre-created `~/.ssh` directory with secure permissions, so keys and SSH config can be mounted into the container at runtime.
