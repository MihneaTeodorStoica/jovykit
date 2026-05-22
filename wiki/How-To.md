# How-To

## New project setup

Use `jovy init` when a directory is empty.
If a project already exists, `jovy` prints its help.

```bash
jovy init
jovy up -d
jovy open
```

## Day-to-day tasks

- [Add or remove packages](CLI#add--remove)
- [Run and restart](CLI#project-commands)
- [Inspect logs](CLI#compose-commands)
- [Rebuild images](CLI#compose-commands)

## Add packages

Use `jovy add` for PyPI packages that should rebuild into the local image.

```bash
jovy add pandas matplotlib
jovy build
jovy up -d
```

Use `jovy remove` to remove packages from `requirements.txt`.

```bash
jovy remove matplotlib
jovy build
```

## Change Python

Pick the target Python version with `jovy upgrade`.

```bash
jovy upgrade --python 3.13
jovy build
jovy up -d
```

Use `--dry-run` before writing files.

```bash
jovy upgrade --python 3.13 --dry-run
```

## Use GPU

Create or upgrade a project with GPU access enabled.

```bash
jovy init --gpu all
# or
jovy upgrade --gpu all
```

Then rebuild and start the service.

```bash
jovy build
jovy up -d
```

## Troubleshooting

Start with:

```bash
jovy doctor
jovy logs -f
```

If that is not enough, follow the detailed checklist in [Troubleshooting](Troubleshooting).

## Automation and releases

- [Run repository checks](Automation)
- [Prepare release process](Release)
