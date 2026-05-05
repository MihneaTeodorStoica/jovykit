from __future__ import annotations

import shutil
import subprocess

import pytest

import jovykit.runtime as runtime


@pytest.mark.docker
def test_docker_smoke_can_query_docker_version() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")

    runtime.require_docker()
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
