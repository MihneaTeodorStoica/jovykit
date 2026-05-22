from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from jovykit import commands


def test_no_args_initializes_empty_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "none")

    result = run_cli([])

    assert (tmp_path / "compose.yaml").exists()
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / "requirements.txt").exists()
    assert (tmp_path / ".devcontainer" / "devcontainer.json").exists()
    assert "Created compose.yaml" in result.output
    assert "Created Dockerfile" in result.output
    assert "Created requirements.txt" in result.output
    assert "Created .devcontainer/devcontainer.json" in result.output
    assert "Created work/" in result.output
    assert "Created .jupyter/" in result.output
    assert "gpus:" not in (tmp_path / "compose.yaml").read_text()


def test_no_args_prints_help_when_project_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = run_cli([])

    assert "JovyKit" in result.output
    assert "jovy up" in result.output


def test_compose_command_passes_to_compose(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    calls: list[list[str]] = []

    def fake_compose(args: list[str], **kwargs: object) -> int:
        calls.append(list(args))
        return 7

    monkeypatch.setattr(
        commands,
        "compose_passthrough",
        fake_compose,
    )

    result = run_cli(["compose", "logs", "-f"], expected_code=7)

    assert calls == [["logs", "-f"]]
    assert result.output == ""


def test_compose_like_commands_pass_args(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_up(args: list[str]) -> int:
        calls.append(("up", list(args)))
        return 0

    def fake_config(args: list[str]) -> int:
        calls.append(("config", list(args)))
        return 0

    monkeypatch.setattr(commands, "up", fake_up)
    monkeypatch.setattr(commands, "config", fake_config)

    run_cli(["up", "-d", "--build"])
    run_cli(["config", "--quiet"])

    assert calls == [("up", ["-d", "--build"]), ("config", ["--quiet"])]


def test_unknown_command_errors(run_cli) -> None:
    result = run_cli(["pull"], expected_code=2)

    assert "unknown command: pull" in result.output
    assert "jovy up" in result.output


def test_init_accepts_python_level_gpu_and_port(tmp_path: Path, run_cli) -> None:
    run_cli(
        [
            "init",
            str(tmp_path),
            "--image-level",
            "extended",
            "--python",
            "3.12",
            "--gpu",
            "all",
            "--port",
            "9999",
            "--token",
            "custom-token",
        ]
    )

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    service = compose["services"]["jovy"]
    assert service["build"]["args"] == {
        "JOVY_BASE_IMAGE": ("ghcr.io/mihneateodorstoica/jovykit:extended-python-3.12"),
    }
    assert service["gpus"] == "all"
    assert service["environment"] == {"JUPYTER_TOKEN": "custom-token"}
    assert (tmp_path / "requirements.txt").read_text() == ""
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert (
        "ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit:extended-python-3.12"
        in dockerfile
    )
    assert "ARG PYTHON_VERSION" not in dockerfile


def test_token_commands_dispatch(monkeypatch: pytest.MonkeyPatch, run_cli) -> None:
    monkeypatch.setattr(
        commands, "token_show", lambda: "URL: http://example\nToken: tok"
    )
    monkeypatch.setattr(commands, "token_rotate", lambda *, emit: "new-token")

    show = run_cli(["token", "show"])
    rotate = run_cli(["token", "rotate"])

    assert "URL: http://example" in show.output
    assert "Token: tok" in show.output
    assert "new-token" in rotate.output


def test_init_auto_enables_detected_gpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "all")

    run_cli(["init", str(tmp_path)])

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    assert compose["services"]["jovy"]["gpus"] == "all"


def test_init_auto_port_selects_free_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.setattr(commands, "detect_gpu_mode", lambda: "none")

    def fake_is_free_port(port: int, host: str = "127.0.0.1") -> bool:
        del host
        return port != 8888

    monkeypatch.setattr(commands, "_is_free_port", fake_is_free_port)
    result = run_cli(["init", str(tmp_path), "--port", "auto"])

    compose = yaml.safe_load((tmp_path / "compose.yaml").read_text())
    selected_port = compose["services"]["jovy"]["ports"][0].split(":")[1]
    assert selected_port != "8888"
    assert "Warning: selected port" in result.output


def test_help_is_compose_first(run_cli) -> None:
    result = run_cli(["--help"])

    assert "jovy up" in result.output
    assert "jovy start" in result.output
    assert "jovy config" in result.output
    assert "jovy compose COMMAND" in result.output
    assert "jovy add PACKAGE" in result.output
    assert "jovy upgrade" in result.output
    assert "destroy" not in result.output
    assert "clean" not in result.output


@pytest.mark.parametrize(
    "spec",
    [
        "git+https://example.com/repo.git",
        "https://example.com/repo.whl",
        "--find-links",
        "-r",
    ],
)
def test_add_rejects_unsafe_requirement_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run_cli,
    spec: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["init"])

    result = run_cli(["add", spec], expected_code=1)

    assert "Unsafe requirements are disabled by default" in result.output
    assert (tmp_path / "requirements.txt").read_text() == ""


def test_add_accepts_unsafe_requirement_with_raw_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["init"])

    result = run_cli(["add", "--raw", "git+https://example.com/repo.git"])

    assert "Added git+https://example.com/repo.git" in result.output
    assert (
        tmp_path / "requirements.txt"
    ).read_text() == "git+https://example.com/repo.git\n"


def test_add_accepts_unsafe_requirement_with_allow_unsafe_requirement_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["init"])

    run_cli(["add", "--allow-unsafe-requirement", "./local/path"])

    assert (tmp_path / "requirements.txt").read_text().splitlines() == ["./local/path"]


def test_add_accepts_standard_version_specifiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["init"])

    run_cli(["add", "requests>=2.31.0", "numpy==1.26.4"])

    assert (tmp_path / "requirements.txt").read_text().splitlines() == [
        "requests>=2.31.0",
        "numpy==1.26.4",
    ]


def test_install_docker_command_defaults_to_dry_run(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    called: dict[str, object] = {}

    def fake_install_docker(**kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr(commands, "install_docker", fake_install_docker)

    run_cli(["install-docker", "--dry-run", "--skip-hello-world"])

    assert called["yes"] is False
    assert called["skip_hello_world"] is True


def test_install_docker_command_can_execute(
    monkeypatch: pytest.MonkeyPatch, run_cli
) -> None:
    called: dict[str, object] = {}

    def fake_install_docker(**kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr(commands, "install_docker", fake_install_docker)

    run_cli(["install-docker", "--yes"])

    assert called["yes"] is True
    assert called["skip_hello_world"] is False


def test_status_json_outputs_machine_readable_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, run_cli
) -> None:
    monkeypatch.chdir(tmp_path)
    compose_ps_payload = json.dumps(
        [
            {
                "Name": "project-jovy-1",
                "Service": "jovy",
                "State": "running",
                "Image": "ghcr.io/mihneateodorstoica/jovykit:base-python-3.11",
            }
        ]
    )
    monkeypatch.setattr(commands.runtime, "compose_ps", lambda _: compose_ps_payload)
    commands.init_project(
        tmp_path,
        python_version="3.11",
        gpu="none",
        token="explicit-token",
    )
    result = run_cli(["status", "--json"], expected_code=0)

    payload = json.loads(result.output)
    assert payload["container_state"] == "running"
    assert payload["url"] == "http://127.0.0.1:8888/lab?token=%2A%2A%2A"
    assert payload["image"] == "ghcr.io/mihneateodorstoica/jovykit:base-python-3.11"
    assert payload["python_version"] == "3.11"
    assert payload["level"] == "base"
    assert payload["gpu"] == "none"
    assert payload["port"] == 8888
    assert payload["token_source"] == "compose"
    assert payload["compose_file"] == str(tmp_path / "compose.yaml")
    assert payload["token"] == "***"


def test_upgrade_command_dispatches_options(
    monkeypatch: pytest.MonkeyPatch,
    run_cli,
) -> None:
    called: dict[str, object] = {}

    def fake_upgrade_project(**kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr(commands, "upgrade_project", fake_upgrade_project)

    run_cli(
        [
            "upgrade",
            "--image-level",
            "extended",
            "--python",
            "3.12",
            "--gpu",
            "all",
            "--port",
            "9999",
            "--token",
            "x",
            "--dry-run",
        ]
    )

    assert called["level"] == "extended"
    assert called["python_version"] == "3.12"
    assert called["gpu"] == "all"
    assert called["port"] == "9999"
    assert called["token"] == "x"
    assert called["dry_run"] is True
