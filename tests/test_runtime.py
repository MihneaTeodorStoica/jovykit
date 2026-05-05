from pathlib import Path
from typing import Any

import pytest

import jovykit.runtime as runtime
from jovykit.config import initial_config_text, load_config, read_state, write_state
from jovykit.generate import write_generated_files


def test_build_uses_image_tuning_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    config_text = initial_config_text(
        project_name="My Project",
        env_name=".jovy",
        image="minimal",
        gpus="none",
        port=9999,
    )
    config_text = config_text.replace(
        "pull = false\n\n[image.build_args]",
        'pull = true\ntarget = "base"\nplatform = "linux/amd64"\n\n[image.build_args]\nEXAMPLE = "1"',
    )
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")
    config = load_config(env_dir)
    write_generated_files(config)
    calls: list[list[str]] = []

    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: calls.append(args),
    )

    runtime.build(config)

    assert "--target" in calls[0]
    assert "--platform" in calls[0]
    assert "--build-arg" in calls[0]
    assert "--pull" in calls[0]


def test_require_docker_reports_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)

    with pytest.raises(runtime.DockerError, match="Docker was not found"):
        runtime.require_docker()


def test_run_command_captures_output_and_raises_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "require_docker", lambda: None)

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        assert kwargs["cwd"] == tmp_path
        assert kwargs["capture_output"] is True
        return runtime.subprocess.CompletedProcess(
            args=args,
            returncode=7,
            stdout="out\n",
            stderr="err\n",
        )

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    with pytest.raises(runtime.DockerError, match="exit code 7"):
        runtime.run_command(["docker", "bad"], cwd=tmp_path)

    assert capsys.readouterr().out == "out\nerr\n"


def test_run_command_attached_skips_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "require_docker", lambda: None)
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        calls.append(kwargs)
        return runtime.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    runtime.run_command(["docker", "compose", "up"], cwd=tmp_path, attached=True)

    assert calls == [{"cwd": tmp_path, "check": False}]


def test_build_signature_tracks_config_and_requirements(create_project: Any) -> None:
    project = create_project()
    original = runtime.build_signature(project.config)

    (project.env_dir / "requirements.txt").write_text("numpy\n", encoding="utf-8")

    assert runtime.build_signature(project.config) != original
    assert runtime.is_build_stale(project.config) is True


def test_build_writes_state_after_success(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: calls.append(args),
    )

    runtime.build(project.config, no_cache=True, pull=True)

    state = read_state(project.env_dir)
    assert calls[0][-2:] == ["--pull", "."]
    assert "--no-cache" in calls[0]
    assert state["build_signature"] == runtime.build_signature(project.config)
    assert state["image"] == project.config.image_ref
    assert "built_at" in state


def test_compose_constructs_compose_file_command(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[tuple[list[str], bool, bool]] = []
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: calls.append(
            (args, attached, check)
        ),
    )

    runtime.compose(project.config, "logs", "-f", attached=True, check=False)

    assert calls == [
        (
            ["docker", "compose", "-f", "compose.yaml", "logs", "-f"],
            True,
            False,
        )
    ]


def test_destroy_removes_compose_resources_and_optionally_image(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    write_state(
        project.env_dir,
        {
            "build_signature": "fresh",
            "image": project.config.image_ref,
            "built_at": "2026-05-05T00:00:00+00:00",
            "other": "kept",
        },
    )
    compose_calls: list[tuple[str, ...]] = []
    command_calls: list[list[str]] = []
    monkeypatch.setattr(
        runtime,
        "compose",
        lambda config, *args, attached=False, check=True: compose_calls.append(args),
    )
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: command_calls.append(args),
    )

    runtime.destroy(project.config)

    assert compose_calls == [("down", "--volumes", "--remove-orphans")]
    assert command_calls == [["docker", "image", "rm", "-f", project.config.image_ref]]
    assert read_state(project.env_dir) == {"other": "kept"}


def test_destroy_keep_image_preserves_build_state(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    state = {
        "build_signature": "fresh",
        "image": project.config.image_ref,
        "built_at": "2026-05-05T00:00:00+00:00",
    }
    write_state(project.env_dir, state)
    monkeypatch.setattr(runtime, "compose", lambda config, *args, attached=False: None)
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: pytest.fail(
            "image should not be removed"
        ),
    )

    runtime.destroy(project.config, remove_image=False)

    assert read_state(project.env_dir) == state
