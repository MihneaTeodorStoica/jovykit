"""Image name helpers for LabKit base images."""

from __future__ import annotations

IMAGE_LEVELS = {
    "minimal": "ghcr.io/mihneateodorstoica/labkit-minimal:latest",
    "base": "ghcr.io/mihneateodorstoica/labkit-base:latest",
    "extended": "ghcr.io/mihneateodorstoica/labkit-extended:latest",
    "full": "ghcr.io/mihneateodorstoica/labkit-full:latest",
}


def resolve_image(value: str) -> str:
    """Return a full image reference for a friendly level or image ref."""
    return IMAGE_LEVELS.get(value, value)
