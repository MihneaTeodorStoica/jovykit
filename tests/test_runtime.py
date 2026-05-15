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
        "pull = false",
        'pull = true\ntarget = "base"\nplatform = "linux/amd64"',
    )
    config_text = config_text.replace(
        "[image.build_args]",
        '[image.build_args]\nEXAMPLE = "1"',
    )
    config_text = config_text.replace(
        "[image.labels]",
        '[image.labels]\n"org.example.project" = "demo"',
    )
    (tmp_path / "jovy.toml").write_text(config_text, encoding="utf-8")
    config = load_config(env_dir)
    write_generated_files(config)
    calls: list[list[str]] = []

    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True, log=None: calls.append(args),
    )

    runtime.build(config)

    assert "--target" in calls[0]
    assert "--platform" in calls[0]
    assert "--build-arg" in calls[0]
    assert "--label" in calls[0]
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

    with pytest.raises(runtime.DockerError, match="exit code 7") as exc:
        runtime.run_command(["docker", "bad"], cwd=tmp_path)

    assert "err" in str(exc.value)
    assert capsys.readouterr().out == ""


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


def test_stream_command_streams_lines_and_returns_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "require_docker", lambda: None)
    popen_calls: list[dict[str, Any]] = []

    class FakeProcess:
        stdout = iter(["one\n", "two\n"])

        def wait(self) -> int:
            return 0

    def fake_popen(args: list[str], **kwargs: Any) -> FakeProcess:
        popen_calls.append(kwargs)
        return FakeProcess()

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    lines: list[str] = []

    return_code = runtime.stream_command(
        ["docker", "logs"], cwd=tmp_path, log=lines.append
    )

    assert return_code == 0
    assert lines == ["one", "two"]
    assert popen_calls[0]["cwd"] == tmp_path
    assert popen_calls[0]["stderr"] == runtime.subprocess.STDOUT


def test_stream_command_raises_when_checked_command_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProcess:
        stdout = iter(["bad\n"])

        def wait(self) -> int:
            return 9

    monkeypatch.setattr(
        runtime.subprocess, "Popen", lambda *args, **kwargs: FakeProcess()
    )

    with pytest.raises(runtime.DockerError, match="exit code 9"):
        runtime.stream_command(
            ["host", "bad"],
            cwd=tmp_path,
            log=lambda line: None,
            require_docker_path=False,
        )


def test_run_command_uses_streaming_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], bool]] = []

    def fake_stream(
        args: list[str],
        *,
        cwd: Path,
        log: runtime.LogCallback,
        check: bool = True,
        require_docker_path: bool = True,
    ) -> int:
        calls.append((args, require_docker_path))
        log("streamed")
        return 0

    monkeypatch.setattr(runtime, "stream_command", fake_stream)
    lines: list[str] = []

    runtime.run_command(["docker", "logs"], cwd=tmp_path, log=lines.append)

    assert calls == [(["docker", "logs"], True)]
    assert lines == ["streamed"]


def test_build_signature_tracks_config_and_lock(create_project: Any) -> None:
    project = create_project()
    lock_path = project.root / "jovy.lock"
    lock_path.write_text("numpy==1.26.0\n", encoding="utf-8")
    original = runtime.build_signature(project.config)

    lock_path.write_text("numpy==2.0.0\n", encoding="utf-8")

    assert runtime.build_signature(project.config) != original
    assert runtime.is_build_stale(project.config) is True


def test_missing_lock_is_stale(create_project: Any) -> None:
    project = create_project()

    assert runtime.is_build_stale(project.config) is True


def test_compile_requirements_lock_invokes_uv(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    input_file = project.root / "requirements.in"
    output_file = project.root / "jovy.lock"
    constraint = project.root / "constraints.txt"
    calls: list[tuple[list[str], Path, bool, runtime.LogCallback | None]] = []

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path,
        attached: bool = False,
        check: bool = True,
        log: runtime.LogCallback | None = None,
        require_docker_path: bool = True,
    ) -> None:
        calls.append((args, cwd, require_docker_path, log))

    monkeypatch.setattr(runtime, "run_command", fake_run_command)

    runtime.compile_requirements_lock(
        project.config,
        input_file=input_file,
        output_file=output_file,
        constraints=[constraint],
        upgrade=True,
        log=lambda line: None,
    )

    assert calls == [
        (
            [
                "uv",
                "pip",
                "compile",
                str(input_file),
                "--output-file",
                str(output_file),
                "--no-progress",
                "--no-annotate",
                "--custom-compile-command",
                "jovy install",
                "--constraints",
                str(constraint),
                "--upgrade",
            ],
            project.root,
            False,
            calls[0][3],
        )
    ]


def test_build_writes_state_after_success(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    (project.root / "jovy.lock").write_text("numpy==1.26.0\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True, log=None: calls.append(args),
    )

    runtime.build(project.config, no_cache=True, pull=True)

    state = read_state(project.env_dir)
    assert calls[0][-2:] == ["--pull", "."]
    assert "--no-cache" in calls[0]
    assert state["build_signature"] == runtime.build_signature(project.config)
    assert state["image"] == project.config.image_ref
    assert "built_at" in state


def test_build_quiet_path_ticks_tqdm_progress(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    (project.root / "jovy.lock").write_text("numpy==1.26.0\n", encoding="utf-8")
    progress_kwargs: list[dict[str, Any]] = []
    ticks: list[int] = []

    class FakeProgress:
        def __enter__(self) -> "FakeProgress":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def update(self, amount: int) -> None:
            ticks.append(amount)

    def fake_tqdm(**kwargs: Any) -> FakeProgress:
        progress_kwargs.append(kwargs)
        return FakeProgress()

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path,
        attached: bool = False,
        check: bool = True,
        log: runtime.LogCallback | None = None,
        require_docker_path: bool = True,
    ) -> None:
        assert log is not None
        log("step 1")
        log("step 2")

    monkeypatch.setattr(runtime, "tqdm", fake_tqdm)
    monkeypatch.setattr(runtime, "_supports_tqdm_progress", lambda: True)
    monkeypatch.setattr(runtime, "run_command", fake_run_command)

    runtime.build(project.config)

    assert progress_kwargs[0]["desc"] == "Building JovyKit image"
    assert progress_kwargs[0]["unit"] == "line"
    assert ticks == [1, 1]


def test_build_quiet_path_skips_tqdm_without_plain_terminal(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    (project.root / "jovy.lock").write_text("numpy==1.26.0\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path,
        attached: bool = False,
        check: bool = True,
        log: runtime.LogCallback | None = None,
        require_docker_path: bool = True,
    ) -> None:
        calls.append({"cwd": cwd, "log": log})

    monkeypatch.setattr(runtime, "_supports_tqdm_progress", lambda: False)
    monkeypatch.setattr(runtime, "run_command", fake_run_command)

    runtime.build(project.config)

    assert calls == [{"cwd": project.root, "log": None}]


def test_build_quiet_path_falls_back_when_tqdm_streaming_fd_fails(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    (project.root / "jovy.lock").write_text("numpy==1.26.0\n", encoding="utf-8")
    log_values: list[runtime.LogCallback | None] = []

    class FakeProgress:
        def __enter__(self) -> "FakeProgress":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def update(self, _amount: int) -> None:
            return None

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path,
        attached: bool = False,
        check: bool = True,
        log: runtime.LogCallback | None = None,
        require_docker_path: bool = True,
    ) -> None:
        log_values.append(log)
        if log is not None:
            raise ValueError("bad value(s) in fds_to_keep")

    monkeypatch.setattr(runtime, "_supports_tqdm_progress", lambda: True)
    monkeypatch.setattr(runtime, "tqdm", lambda **_kwargs: FakeProgress())
    monkeypatch.setattr(runtime, "run_command", fake_run_command)

    runtime.build(project.config)

    assert log_values[0] is not None
    assert log_values[1] is None


def test_build_streaming_writes_state_and_streams_output(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            "pull = false",
            'pull = true\ntarget = "base"\nplatform = "linux/amd64"',
        )
        .replace(
            "[image.build_args]",
            '[image.build_args]\nEXAMPLE = "1"',
        )
        .replace(
            "[image.labels]",
            '[image.labels]\n"org.example.project" = "demo"',
        )
    )
    (project.root / "jovy.lock").write_text("numpy==1.26.0\n", encoding="utf-8")
    calls: list[tuple[list[str], runtime.LogCallback]] = []

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path,
        attached: bool = False,
        check: bool = True,
        log: runtime.LogCallback | None = None,
        require_docker_path: bool = True,
    ) -> None:
        assert log is not None
        calls.append((args, log))
        log("building")

    monkeypatch.setattr(runtime, "run_command", fake_run_command)
    lines: list[str] = []

    runtime.build_streaming(project.config, no_cache=True, pull=True, log=lines.append)

    assert "--target" in calls[0][0]
    assert "--platform" in calls[0][0]
    assert "--build-arg" in calls[0][0]
    assert "--label" in calls[0][0]
    assert "--no-cache" in calls[0][0]
    assert lines == ["building"]
    assert read_state(project.env_dir)["image"] == project.config.image_ref


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


def test_compose_passes_streaming_log_callback(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    calls: list[tuple[list[str], runtime.LogCallback]] = []

    def fake_run_command(args: list[str], **kwargs: Any) -> None:
        calls.append((args, kwargs["log"]))

    monkeypatch.setattr(runtime, "run_command", fake_run_command)

    runtime.compose(project.config, "logs", log=lambda line: None)

    assert calls[0][0] == ["docker", "compose", "-f", "compose.yaml", "logs"]


def test_compose_capture_returns_output_and_raises_on_checked_failure(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    monkeypatch.setattr(runtime, "require_docker", lambda: None)

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        assert args == ["docker", "compose", "-f", "compose.yaml", "ps"]
        return runtime.subprocess.CompletedProcess(
            args=args,
            returncode=4,
            stdout="out",
            stderr="err",
        )

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)

    assert runtime.compose_capture(project.config, "ps") == "outerr"
    with pytest.raises(runtime.DockerError, match="exit code 4"):
        runtime.compose_capture(project.config, "ps", check=True)


def test_compose_ps_logs_and_host_command_delegate_to_helpers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, create_project: Any
) -> None:
    project = create_project()
    compose_calls: list[tuple[str, ...]] = []
    stream_calls: list[tuple[list[str], bool]] = []

    def fake_compose_capture(config: Any, *args: str, check: bool = False) -> str:
        compose_calls.append(args)
        return "compose-output"

    def fake_stream_command(
        args: list[str],
        *,
        cwd: Path,
        log: runtime.LogCallback,
        check: bool = True,
        require_docker_path: bool = True,
    ) -> int:
        stream_calls.append((args, require_docker_path))
        log("host-output")
        return 5

    monkeypatch.setattr(runtime, "compose_capture", fake_compose_capture)
    monkeypatch.setattr(runtime, "stream_command", fake_stream_command)
    lines: list[str] = []

    assert runtime.compose_ps(project.config) == "compose-output"
    assert runtime.compose_logs(project.config, tail="12") == "compose-output"
    assert runtime.run_host_command(["pwd"], cwd=tmp_path, log=lines.append) == 5

    assert compose_calls == [
        ("ps", "--format", "json"),
        ("logs", "--tail", "12"),
    ]
    assert stream_calls == [(["pwd"], False)]
    assert lines == ["host-output"]


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
    compose_calls: list[tuple[tuple[str, ...], bool, bool]] = []
    run_calls: list[list[str]] = []
    monkeypatch.setattr(
        runtime,
        "compose",
        lambda config, *args, attached=False, check=True, log=None: compose_calls.append(
            (args, attached, log is not None)
        ),
    )

    def fake_run(
        args: list[str], **_kwargs: Any
    ) -> runtime.subprocess.CompletedProcess[str]:
        run_calls.append(args)
        return runtime.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        fake_run,
    )

    runtime.destroy(project.config)

    assert compose_calls == [(("down", "--remove-orphans"), False, True)]
    assert run_calls == [["docker", "image", "rm", "-f", project.config.image_ref]]
    assert read_state(project.env_dir) == {"other": "kept"}


def test_destroy_streams_output_to_log(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    compose_calls: list[tuple[tuple[str, ...], bool, bool]] = []
    run_calls: list[list[str]] = []

    def log(_line: str) -> None:
        return None

    monkeypatch.setattr(
        runtime,
        "compose",
        lambda config, *args, attached=False, check=True, log=None: compose_calls.append(
            (args, attached, log is not None)
        ),
    )

    def fake_run(
        args: list[str], **_kwargs: Any
    ) -> runtime.subprocess.CompletedProcess[str]:
        run_calls.append(args)
        return runtime.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        fake_run,
    )

    runtime.destroy(project.config, log=log)

    assert compose_calls == [(("down", "--remove-orphans"), False, True)]
    assert run_calls == [["docker", "image", "rm", "-f", project.config.image_ref]]


def test_destroy_can_remove_legacy_named_volumes_when_requested(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    compose_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runtime,
        "compose",
        lambda config, *args, attached=False, check=True, log=None: compose_calls.append(
            args
        ),
    )
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda args, **kwargs: runtime.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        ),
    )

    runtime.destroy(project.config, remove_volumes=True)

    assert compose_calls == [("down", "--remove-orphans", "--volumes")]


def test_destroy_missing_image_is_not_fatal_and_logs_friendly_message(
    monkeypatch: pytest.MonkeyPatch, create_project: Any
) -> None:
    project = create_project()
    lines: list[str] = []
    monkeypatch.setattr(
        runtime,
        "compose",
        lambda config, *args, attached=False, check=True, log=None: None,
    )
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda args, **kwargs: runtime.subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr=f"Error response from daemon: No such image: {project.config.image_ref}\n",
        ),
    )

    runtime.destroy(project.config, log=lines.append)

    assert any("Image already absent" in line for line in lines)


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
    monkeypatch.setattr(
        runtime, "compose", lambda config, *args, attached=False, log=None: None
    )
    monkeypatch.setattr(
        runtime,
        "run_command",
        lambda args, *, cwd, attached=False, check=True: pytest.fail(
            "image should not be removed"
        ),
    )

    runtime.destroy(project.config, remove_image=False)

    assert read_state(project.env_dir) == state
