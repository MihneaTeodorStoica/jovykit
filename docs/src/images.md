# Images

Images are published to GitHub Container Registry as:

```text
ghcr.io/mihneateodorstoica/labkit:TYPE-YYYY-MM-DD
ghcr.io/mihneateodorstoica/labkit:TYPE
```

`TYPE` is one of `minimal`, `base`, `extended`, or `full`.

The dated tag is immutable for a build date. The floating `TYPE` tag points at the latest published image for that variation.
