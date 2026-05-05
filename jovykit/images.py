"""Image name helpers for JovyKit base images."""

from __future__ import annotations

IMAGE_LEVELS = {
    "minimal": "ghcr.io/mihneateodorstoica/jovykit-minimal:latest",
    "base": "ghcr.io/mihneateodorstoica/jovykit-base:latest",
    "extended": "ghcr.io/mihneateodorstoica/jovykit-extended:latest",
    "full": "ghcr.io/mihneateodorstoica/jovykit-full:latest",
}


def resolve_image(value: str) -> str:
    """Return a full image reference for a friendly level or image ref."""
    return IMAGE_LEVELS.get(value, value)
