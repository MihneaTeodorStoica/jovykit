"""JovyKit image levels."""

from __future__ import annotations

import re

from jovykit.config import JovyKitError

DEFAULT_PYTHON_VERSION = "3.13"
LATEST_IMAGE_LEVEL = "base"
LATEST_PYTHON_VERSION = "3.11"
SUPPORTED_PYTHON_VERSIONS_BY_LEVEL = {
    "minimal": ("3.9", "3.10", "3.11", "3.12", "3.13", "3.14"),
    "base": ("3.9", "3.10", "3.11", "3.12", "3.13", "3.14"),
    "extended": ("3.11", "3.12", "3.13"),
    "full": ("3.11", "3.12", "3.13"),
}
SUPPORTED_PYTHON_VERSIONS = tuple(
    dict.fromkeys(
        version
        for versions in SUPPORTED_PYTHON_VERSIONS_BY_LEVEL.values()
        for version in versions
    )
)

IMAGE_REPOSITORY = "ghcr.io/mihneateodorstoica/jovykit"
LEGACY_IMAGE_REPOSITORIES = {
    "minimal": "ghcr.io/mihneateodorstoica/jovykit-minimal",
    "base": "ghcr.io/mihneateodorstoica/jovykit-base",
    "extended": "ghcr.io/mihneateodorstoica/jovykit-extended",
    "full": "ghcr.io/mihneateodorstoica/jovykit-full",
}
IMAGE_REPOSITORIES = {
    level: IMAGE_REPOSITORY for level in SUPPORTED_PYTHON_VERSIONS_BY_LEVEL
}
IMAGE_LEVELS = IMAGE_REPOSITORIES


def image_tag(level: str, python_version: str = DEFAULT_PYTHON_VERSION) -> str:
    """Return the level- and Python-specific JovyKit image tag."""
    return f"{level}-python-{python_version}"


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
    validate_python_version(level, python_version)
    return f"{repository}:{image_tag(level, python_version)}"


def validate_python_version(level: str, python_version: str) -> None:
    """Raise if an image level does not publish a Python tag."""
    versions = SUPPORTED_PYTHON_VERSIONS_BY_LEVEL[level]
    if python_version not in versions:
        supported = ", ".join(versions)
        raise JovyKitError(f"{level} images support Python versions: {supported}.")


def resolve_image(value: str) -> str:
    """Backward-compatible alias that rejects arbitrary image sources."""
    return resolve_image_level(value)


def image_level_from_reference(reference: str) -> str | None:
    """Return the JovyKit image level for a repository reference."""
    repository = _strip_tag_or_digest(reference)
    tag = _tag_from_reference(reference)
    if repository == IMAGE_REPOSITORY:
        if tag == "latest":
            return LATEST_IMAGE_LEVEL
        for level in IMAGE_LEVELS:
            if tag.startswith(f"{level}-python-"):
                return level
    for level, image_repository in LEGACY_IMAGE_REPOSITORIES.items():
        if repository == image_repository:
            return level
    return None


def python_version_from_image(
    reference: str, default: str = DEFAULT_PYTHON_VERSION
) -> str:
    """Read a Python version from a JovyKit image tag."""
    tag = _tag_from_reference(reference)
    if tag == "latest":
        return LATEST_PYTHON_VERSION
    for level in IMAGE_LEVELS:
        match = re.match(rf"^{level}-python-(\d+\.\d+)(?:$|-)", tag)
        if match:
            return match.group(1)
    if tag.startswith("python-"):
        return tag[len("python-") :]
    return default


def _strip_tag_or_digest(reference: str) -> str:
    repository = reference.split("@", 1)[0]
    tail = repository.rsplit("/", 1)[-1]
    if ":" in tail:
        repository = repository.rsplit(":", 1)[0]
    return repository


def _tag_from_reference(reference: str) -> str:
    return reference.rsplit(":", 1)[-1] if ":" in reference.rsplit("/", 1)[-1] else ""
