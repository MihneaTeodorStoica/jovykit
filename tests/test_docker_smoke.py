from __future__ import annotations

import shutil

import pytest

from jovykit import runtime


@pytest.mark.docker
def test_docker_compose_version_smoke() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")

    code, output = runtime.docker_capture("compose", "version")

    assert code == 0
    assert "Docker Compose" in output
