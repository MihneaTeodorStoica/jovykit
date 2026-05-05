from __future__ import annotations

import runpy
from typing import Any

import main


def test_top_level_main_reexports_cli_main() -> None:
    assert main.main.__module__ == "jovykit.cli"


def test_top_level_script_invokes_main(monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.setattr("jovykit.cli.main", lambda: calls.append("called"))

    runpy.run_module("main", run_name="__main__")

    assert calls == ["called"]
