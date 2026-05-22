from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from jovykit import commands
from jovykit.config import generate_default_jupyter_token
from jovykit.config import JovyKitError


def test_init_project_writes_compose_dockerfile_requirements_and_persistent_dirs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[tuple[list[str], Path]] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        cwd = kwargs["cwd"]
        assert isinstance(cwd, Path)
        run_calls.append((args, cwd))
        if args == ["/usr/bin/git", "init"]:
            (cwd / ".git").mkdir()
        return subprocess.CompletedProcess(args, 0, stdout="")

    monkeypatch.setattr(
        commands.shutil,
        "which",
        lambda name: "/usr/bin/git" if name == "git" else None,
    )
    monkeypatch.setattr(commands.subprocess, "run", fake_run)

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
    assert (tmp_path / ".gitignore").read_text() == ".jupyter/\nwork/\n"
    assert (tmp_path / ".git").is_dir()
    assert run_calls == [
        (["/usr/bin/git", "init"], tmp_path),
        (
            [
                "/usr/bin/git",
                "add",
                "--",
                "compose.yaml",
                "Dockerfile",
                "requirements.txt",
                ".devcontainer/devcontainer.json",
                ".gitignore",
            ],
            tmp_path,
        ),
        (
            [
                "/usr/bin/git",
                "-c",
                "user.name=JovyKit",
                "-c",
                "user.email=jovykit@users.noreply.github.com",
                "commit",
                "-m",
                "Initialize JovyKit project",
            ],
            tmp_path,
        ),
    ]
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
        "remoteUser": "jovyan",
        "shutdownAction": "stopCompose",
        "overrideCommand": False,
        "mounts": [
            f"source=jovykit-{tmp_path.name}-vscode-server,target=/home/jovyan/.vscode-server,type=volume",
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


def test_init_project_requires_force_for_existing_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("old", encoding="utf-8")

    with pytest.raises(JovyKitError, match="--force"):
        commands.init_project(tmp_path)


def test_init_project_fails_when_git_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(commands.shutil, "which", lambda name: None)

    with pytest.raises(JovyKitError, match="git not found"):
        commands.init_project(tmp_path, gpu="none")


def test_jupyter_url_reads_compose_port(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")

    assert commands.jupyter_url(tmp_path) == (
        "http://127.0.0.1:9999/lab?token=secret-token"
    )


def test_jupyter_url_rejects_invalid_host_port(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text(encoding="utf-8"))
    compose["services"]["jovy"]["ports"] = ["127.0.0.1:not-a-port:8888"]
    (tmp_path / "compose.yaml").write_text(yaml.safe_dump(compose), encoding="utf-8")

    with pytest.raises(JovyKitError, match="Malformed compose.yaml port mapping"):
        commands.jupyter_url(tmp_path)


def test_jupyter_url_rejects_missing_host_port(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text(encoding="utf-8"))
    compose["services"]["jovy"]["ports"] = ["127.0.0.1::8888"]
    (tmp_path / "compose.yaml").write_text(yaml.safe_dump(compose), encoding="utf-8")

    with pytest.raises(JovyKitError, match="Malformed compose.yaml port mapping"):
        commands.jupyter_url(tmp_path)


def test_jupyter_url_uses_default_when_container_port_is_not_jupyter(
    tmp_path: Path,
) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text(encoding="utf-8"))
    compose["services"]["jovy"]["ports"] = ["127.0.0.1:9999:9999"]
    (tmp_path / "compose.yaml").write_text(yaml.safe_dump(compose), encoding="utf-8")

    assert (
        commands.jupyter_url(tmp_path) == "http://127.0.0.1:8888/lab?token=secret-token"
    )


def test_jupyter_url_accepts_ipv6_host_port_mapping(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret-token")
    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text(encoding="utf-8"))
    compose["services"]["jovy"]["ports"] = ["[::1]:7777:8888"]
    (tmp_path / "compose.yaml").write_text(yaml.safe_dump(compose), encoding="utf-8")

    assert (
        commands.jupyter_url(tmp_path) == "http://127.0.0.1:7777/lab?token=secret-token"
    )


def test_jupyter_url_encodes_token(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="a/b+c")

    assert commands.jupyter_url(tmp_path) == "http://127.0.0.1:9999/lab?token=a%2Fb%2Bc"


def test_generated_default_tokens_are_random_urlsafe() -> None:
    first = generate_default_jupyter_token()
    second = generate_default_jupyter_token()

    assert first != second
    assert len(first) >= 22
    assert all(character.isalnum() or character in "-_" for character in first)


def test_token_show_reads_token(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none", port=9999, token="secret/token")

    assert commands.token_show(tmp_path) == (
        "URL: http://127.0.0.1:9999/lab?token=secret%2Ftoken\n"
        "Token: secret/token"
    )


def test_token_show_generates_warning_when_token_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose = tmp_path / "compose.yaml"
    commands.init_project(tmp_path, gpu="none")
    data = yaml.safe_load(compose.read_text(encoding="utf-8"))
    del data["services"]["jovy"]["environment"]["JUPYTER_TOKEN"]
    compose.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(
        commands,
        "generate_default_jupyter_token",
        lambda: "ephemeral-token",
    )

    assert commands.token_show(tmp_path) == (
        "URL: http://127.0.0.1:8888/lab?token=ephemeral-token\n"
        "Token: ephemeral-token\n"
        "Warning: JUPYTER_TOKEN is missing from compose.yaml. "
        "Run `jovy token rotate` to persist a real token."
    )


def test_token_rotate_stores_token_in_dict_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    commands.init_project(tmp_path, gpu="none")
    monkeypatch.setattr(
        commands,
        "generate_default_jupyter_token",
        lambda: "new-token",
    )

    assert commands.token_rotate(tmp_path, emit=messages.append) == "new-token"

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    assert compose["services"]["jovy"]["environment"] == {"JUPYTER_TOKEN": "new-token"}
    assert messages == ["Rotated token in compose.yaml"]


def test_token_rotate_preserves_list_environment(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    commands.init_project(tmp_path, gpu="none")
    data = yaml.safe_load(compose.read_text(encoding="utf-8"))
    data["services"]["jovy"]["environment"] = ["FOO=bar", "JUPYTER_TOKEN=old"]
    compose.write_text(yaml.safe_dump(data), encoding="utf-8")

    token = commands.token_rotate(tmp_path)

    data = yaml.safe_load(compose.read_text(encoding="utf-8"))
    env = data["services"]["jovy"]["environment"]
    assert env == ["FOO=bar", f"JUPYTER_TOKEN={token}"]


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


def test_status_returns_error_state_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        commands.runtime, "compose_ps", lambda _root: "this is not json"
    )

    result = commands.status()

    payload = json.loads(result)
    assert payload["state"] == "error"
    assert payload["message"] == "this is not json"


def test_status_returns_error_state_on_docker_daemon_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        commands.runtime,
        "compose_ps",
        lambda _root: "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
    )

    result = commands.status()

    payload = json.loads(result)
    assert payload["state"] == "error"
    assert "Cannot connect to the Docker daemon" in payload["message"]


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


def test_load_project_settings_rejects_non_mapping_compose_root(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("- item\n", encoding="utf-8")

    with pytest.raises(JovyKitError, match="top-level mapping"):
        commands.load_project_settings(tmp_path)


def test_load_project_settings_rejects_missing_services(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("{}", encoding="utf-8")

    with pytest.raises(JovyKitError, match="services mapping"):
        commands.load_project_settings(tmp_path)


def test_load_project_settings_rejects_scalar_jovy_service(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        "services:\n  jovy: false\n", encoding="utf-8"
    )

    with pytest.raises(JovyKitError, match="services\\.jovy mapping"):
        commands.load_project_settings(tmp_path)


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
            token="invalid-port",
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
        ["requests>=2.31.0", "scikit-learn==1.4.2"], root=tmp_path, emit=messages.append
    )

    assert (tmp_path / "requirements.txt").read_text().splitlines() == [
        "requests>=2.31.0",
        "scikit-learn==1.4.2",
    ]
    assert messages == [
        "Added requests>=2.31.0",
        "Added scikit-learn==1.4.2",
        "Saved requirements.txt",
    ]


@pytest.mark.parametrize(
    "spec",
    [
        "git+https://example.com/repo.git",
        "./local/path",
        "mypkg @ git+https://example.com/repo.git",
        "https://example.com/repo.whl",
        "--extra-index-url https://example.com/simple",
        "-e",
    ],
)
def test_add_packages_rejects_unsafe_requirement_spec(
    tmp_path: Path, spec: str
) -> None:
    commands.init_project(tmp_path, gpu="none")

    with pytest.raises(JovyKitError, match="Unsafe requirements are disabled"):
        commands.add_packages([spec], root=tmp_path)


@pytest.mark.parametrize(
    "spec",
    [
        "git+https://example.com/repo.git",
        "./local/path",
        "mypkg @ git+https://example.com/repo.git",
    ],
)
def test_add_packages_allows_unsafe_requirement_spec(tmp_path: Path, spec: str) -> None:
    messages: list[str] = []
    commands.init_project(tmp_path, gpu="none")

    commands.add_packages(
        [spec], root=tmp_path, allow_unsafe_requirement=True, emit=messages.append
    )

    assert (tmp_path / "requirements.txt").read_text().splitlines() == [spec]
    assert messages == [f"Added {spec}", "Saved requirements.txt"]


@pytest.mark.parametrize("spec", ["1invalid", "my pkg"])
def test_add_packages_rejects_invalid_requirement_name(
    tmp_path: Path, spec: str
) -> None:
    commands.init_project(tmp_path, gpu="none")

    with pytest.raises(JovyKitError, match="Invalid requirement name"):
        commands.add_packages([spec], root=tmp_path)


def test_add_packages_rejects_option_like_unsafe_spec(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none")

    with pytest.raises(JovyKitError, match="Unsafe requirements are disabled"):
        commands.add_packages(["-r"], root=tmp_path)


def test_remove_packages_updates_requirements_txt(tmp_path: Path) -> None:
    commands.init_project(tmp_path, gpu="none")
    commands.add_packages(["pandas==2.3.3", "numpy"], root=tmp_path)

    commands.remove_packages(["pandas"], root=tmp_path)

    assert (tmp_path / "requirements.txt").read_text().splitlines() == ["numpy"]
