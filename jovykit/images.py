"""JovyKit image levels."""

from __future__ import annotations

from jovykit.config import JovyKitError

DEFAULT_PYTHON_VERSION = "3.13"
SUPPORTED_PYTHON_VERSIONS = ("3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14")

IMAGE_REPOSITORIES = {
    "minimal": "ghcr.io/mihneateodorstoica/jovykit-minimal",
    "base": "ghcr.io/mihneateodorstoica/jovykit-base",
    "extended": "ghcr.io/mihneateodorstoica/jovykit-extended",
    "full": "ghcr.io/mihneateodorstoica/jovykit-full",
}
IMAGE_LEVELS = IMAGE_REPOSITORIES


def image_tag(python_version: str = DEFAULT_PYTHON_VERSION) -> str:
    """Return the Python-specific JovyKit image tag."""
    return f"python-{python_version}"


def resolve_image_level(
    level: str, python_version: str = DEFAULT_PYTHON_VERSION
) -> str:
    """Resolve a supported JovyKit image level to an image reference."""
    try:
        repository = IMAGE_REPOSITORIES[level]
    except KeyError as exc:
        levels = ", ".join(IMAGE_REPOSITORIES)
        raise JovyKitError(
            f"Unknown image level {level!r}. Choose one of: {levels}."
        ) from exc
    return f"{repository}:{image_tag(python_version)}"


def resolve_image(value: str) -> str:
    """Backward-compatible alias that rejects arbitrary image sources."""
    return resolve_image_level(value)


def image_level_from_reference(reference: str) -> str | None:
    """Return the JovyKit image level for a repository reference."""
    repository = _strip_tag_or_digest(reference)
    for level, image_repository in IMAGE_REPOSITORIES.items():
        if repository == image_repository:
            return level
    return None


def python_version_from_image(
    reference: str, default: str = DEFAULT_PYTHON_VERSION
) -> str:
    """Read a Python version from a JovyKit image tag."""
    tag = reference.rsplit(":", 1)[-1] if ":" in reference.rsplit("/", 1)[-1] else ""
    if tag.startswith("python-"):
        return tag.removeprefix("python-")
    return default


def _strip_tag_or_digest(reference: str) -> str:
    repository = reference.split("@", 1)[0]
    tail = repository.rsplit("/", 1)[-1]
    if ":" in tail:
        repository = repository.rsplit(":", 1)[0]
    return repository
