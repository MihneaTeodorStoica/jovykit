from __future__ import annotations

from jovykit.cli import main


def test_entrypoint_exists() -> None:
    assert callable(main)
