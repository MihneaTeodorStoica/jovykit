"""Small shared errors and constants."""

from __future__ import annotations

import secrets


def generate_default_jupyter_token() -> str:
    """Generate a random default Jupyter token."""
    return secrets.token_urlsafe(32)


class JovyKitError(RuntimeError):
    """Base class for user-facing JovyKit failures."""


class ConfigError(JovyKitError):
    """Raised when a project cannot be represented as Compose."""
