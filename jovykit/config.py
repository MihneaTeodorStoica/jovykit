"""Small shared errors and constants."""

from __future__ import annotations

DEFAULT_JUPYTER_TOKEN = "jovykit"


class JovyKitError(RuntimeError):
    """Base class for user-facing JovyKit failures."""


class ConfigError(JovyKitError):
    """Raised when a project cannot be represented as Compose."""
