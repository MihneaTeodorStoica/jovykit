from __future__ import annotations

from pathlib import Path

import yaml


def test_python_ci_runs_supported_host_versions() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/ci-release.yml").read_text(encoding="utf-8")
    )
    versions = workflow["jobs"]["python"]["strategy"]["matrix"]["python-version"]

    assert versions == ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]
