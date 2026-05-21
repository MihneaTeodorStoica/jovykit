from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from jovykit import commands
from jovykit.config import JovyKitError


def test_init_project_writes_compose_dockerfile_requirements_and_persistent_dirs(
    tmp_path: Path,
) -> None:
    commands.init_project(
        tmp_path,
        level="minimal",
        python_version="3.11",
        gpu="all",
        port=7777,
        token="custom-token",
    )

    assert (tmp_path / "compose.yaml").exists()
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / "requirements.txt").exists()
    assert (tmp_path / ".devcontainer" / "devcontainer.json").exists()
    assert (tmp_path / "work").is_dir()
    assert (tmp_path / ".jupyter").is_dir()
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    service = compose["services"]["jovy"]
    assert service["volumes"] == [
        "./work:/home/jovyan/work",
        "./.jupyter:/home/jovyan/.jupyter",
    ]
    assert service["ports"] == ["127.0.0.1:7777:8888"]
    assert service["environment"] == {"JUPYTER_TOKEN": "custom-token"}
    assert service["gpus"] == "all"
    assert service["build"]["dockerfile"] == "Dockerfile"
    assert service["build"]["args"] == {
        "JOVY_BASE_IMAGE": ("ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.11"),
    }
    assert (tmp_path / "requirements.txt").read_text() == ""
    devcontainer = json.loads(
        (tmp_path / ".devcontainer" / "devcontainer.json").read_text()
    )
    assert devcontainer == {
        "name": tmp_path.name,
        "dockerComposeFile": "../compose.yaml",
        "service": "jovy",
        "workspaceFolder": "/home/jovyan/work",
        "shutdownAction": "stopCompose",
        "overrideCommand": False,
        "mounts": [
            "source=jovykit-vscode-server,target=/home/jovyan/.vscode-server,type=volume",
        ],
        "portsAttributes": {
            "8888": {
                "label": "JupyterLab",
                "protocol": "http",
                "onAutoForward": "silent",
            }
        },
        "otherPortsAttributes": {"onAutoForward": "silent"},
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-python.python",
                    "ms-python.vscode-pylance",
                    "ms-toolsai.jupyter",
                ],
                "settings": {
                    "python.defaultInterpreterPath": "/opt/jovy/bin/python",
                    "jupyter.jupyterServerType": "local",
                },
            }
        },
    }


def test_init_project_rejects_legacy_manifest(tmp_path: Path) -> None:
    (tmp_path / "jovy.toml").write_text("[project]\n", encoding="utf-8")

    with pytest.raises(JovyKitError, match="jovy.toml is no longer used"):
        commands.init_project(tmp_path)


def test_init_project_requires_force_for_existing_files(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("old", encoding="utf-8")

    with pytest.raises(JovyKitError, match="--force"):
        commands.init_project(tmp_path)


def test_init_project_requires_force_for_existing_devcontainer(tmp_path: Path) -> None:
    devcontainer = tmp_path / ".devcontainer" / "devcontainer.json"
    devcontainer.parent.mkdir()
    devcontainer.write_text("{}", encoding="utf-8")

    with pytest.raises(JovyKitError, match="--force"):
        commands.init_project(tmp_path)


def test_jupyter_url_reads_compose_port(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")

    assert commands.jupyter_url(tmp_path) == (
        "http://127.0.0.1:9999/lab?token=secret-token"
    )


def test_jupyter_url_encodes_token(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="a/b+c")

    assert commands.jupyter_url(tmp_path) == "http://127.0.0.1:9999/lab?token=a%2Fb%2Bc"


def test_install_docker_delegates_to_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_install_docker(**kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr(commands.docker_install, "install_docker", fake_install_docker)

    commands.install_docker(yes=True, skip_hello_world=True, emit=lambda _: None)

    assert called["yes"] is True
    assert called["skip_hello_world"] is True


def test_doctor_reports_missing_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands.shutil, "which", lambda name: None)
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "none")
    lines: list[str] = []

    commands.doctor(emit=lines.append)

    assert "docker: missing" in lines
    assert "compose: missing" in lines
    assert "daemon: unavailable" in lines
    assert "setup: run jovy install-docker --dry-run" in lines


def test_doctor_reports_unavailable_compose_and_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(commands.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "none")

    def fake_docker_capture(*args: str) -> tuple[int, str]:
        if args == ("--version",):
            return 0, "Docker version 28.0.0"
        return 1, "failed"

    monkeypatch.setattr(commands.runtime, "docker_capture", fake_docker_capture)
    lines: list[str] = []

    commands.doctor(emit=lines.append)

    assert "docker: Docker version 28.0.0" in lines
    assert "compose: unavailable" in lines
    assert "daemon: unavailable" in lines
    assert "setup: run jovy install-docker --dry-run" in lines


def test_load_project_settings_reads_compose(tmp_path: Path) -> None:
    commands.init_project(
        tmp_path,
        level="extended",
        python_version="3.12",
        gpu="all",
        port=9999,
        token="secret-token",
    )

    assert commands.load_project_settings(tmp_path) == commands.ProjectSettings(
        level="extended",
        python_version="3.12",
        gpu="all",
        port=9999,
        token="secret-token",
    )


def test_save_project_settings_updates_generated_files(tmp_path: Path) -> None:
    messages: list[str] = []
    commands.init_project(tmp_path, gpu="none")

    commands.save_project_settings(
        tmp_path,
        level="full",
        python_version="3.11",
        gpu="all",
        port=7777,
        token="new-token",
        emit=messages.append,
    )

    assert commands.load_project_settings(tmp_path) == commands.ProjectSettings(
        level="full",
        python_version="3.11",
        gpu="all",
        port=7777,
        token="new-token",
    )
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    service = compose["services"]["jovy"]
    assert service["ports"] == ["127.0.0.1:7777:8888"]
    assert service["environment"] == {"JUPYTER_TOKEN": "new-token"}
    assert service["gpus"] == "all"
    assert service["build"]["args"] == {
        "JOVY_BASE_IMAGE": "ghcr.io/mihneateodorstoica/jovykit:full-python-3.11",
    }
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert (
        "ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit:full-python-3.11"
        in dockerfile
    )
    assert "ARG PYTHON_VERSION" not in dockerfile
    assert messages == [
        "Saved compose.yaml",
        "Saved Dockerfile",
    ]


def test_save_project_settings_rejects_invalid_port(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none")

    with pytest.raises(JovyKitError, match="Port"):
        commands.save_project_settings(
            tmp_path,
            level="base",
            python_version="3.13",
            gpu="none",
            port=70000,
            token="jovykit",
        )


def test_save_project_settings_rejects_blank_token(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none")

    with pytest.raises(JovyKitError, match="token"):
        commands.save_project_settings(
            tmp_path,
            level="base",
            python_version="3.13",
            gpu="none",
            port=8888,
            token="",
        )


def test_add_packages_updates_requirements_txt(tmp_path: Path) -> None:
    messages: list[str] = []
    commands.init_project(tmp_path, gpu="none")

    commands.add_packages(
        ["pandas", "scikit-learn"], root=tmp_path, emit=messages.append
    )

    assert (tmp_path / "requirements.txt").read_text().splitlines() == [
        "pandas",
        "scikit-learn",
    ]
    assert messages == [
        "Added pandas",
        "Added scikit-learn",
        "Saved requirements.txt",
    ]


def test_remove_packages_updates_requirements_txt(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none")
    commands.add_packages(["pandas==2.3.3", "numpy"], root=tmp_path)

    commands.remove_packages(["pandas"], root=tmp_path)

    assert (tmp_path / "requirements.txt").read_text().splitlines() == ["numpy"]
