# Tutorial

Use this page to get a first working JovyKit project.

## First run

```bash
pip install jovykit
jovy init
jovy up -d
jovy open
```

## First run checks

```bash
jovy doctor
jovy status
jovy open
```

## Add and remove packages

```bash
jovy add pandas numpy
jovy remove numpy
```

## Pick image and Python version

```bash
jovy init --image-level base --python 3.13
jovy init --image-level full --gpu all
```

## Next pages

Use [How-To](How-To) when you need task-specific workflows.
Use [Reference](Reference) for command and image details.
