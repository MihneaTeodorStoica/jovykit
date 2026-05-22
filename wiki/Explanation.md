# Explanation

## Why there is no hidden config file

JovyKit uses generated project files:
`compose.yaml`, `Dockerfile`, and `requirements.txt`.
That makes environment state easy to inspect, diff, and share.

## Security model

Local security controls and defaults are documented in [Security](Security).

## Image levels

JovyKit image levels trade size for preinstalled tooling.
`minimal` is the smallest base for custom packages, `base` is the default
notebook image, `extended` adds broader data-science tooling, and `full` is the
largest batteries-included option.

Each project `Dockerfile` starts from a published JovyKit image through
`JOVY_BASE_IMAGE`.
Project packages from `requirements.txt` are installed in a local layer, so the
published image remains reusable while project dependencies stay inspectable.

## Docker model

JovyKit is Compose-first.
`compose.yaml` is the source of truth for the `jovy` service, port binding,
volumes, GPU setting, environment variables, and build args.
The service mounts `./work` for notebooks and `./.jupyter` for Jupyter state.
`jovy build`, `jovy up`, `jovy down`, and related commands delegate to Docker
Compose with these generated files.

## Release process

Versioning and publish flow are described in [Release](Release).

## How JovyKit is built

- Local environment files are generated per project.
- `./build.sh` is the canonical local path for image builds.
- Published images are versioned in GitHub Container Registry.
