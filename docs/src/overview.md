# Overview

JovyKit provides layered Jupyter notebook container images for data science,
machine learning, and research workflows.

The project has two main surfaces:

- Published notebook images for different workload sizes.
- A `jovy` CLI for project-local container environments.

The image definitions live in `image/` and are split into four Docker targets:

- `minimal`
- `base`
- `extended`
- `full`

The CLI creates a `.jovy/` directory in a project, generates readable Docker
files, tracks direct project packages in `jovy.toml`, compiles `.jovy/jovy.lock`
with uv, and runs Jupyter through Docker Compose.
