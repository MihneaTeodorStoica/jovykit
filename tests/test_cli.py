from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import jovykit.cli as cli
from jovykit import commands as command_ops
from jovykit.config import read_state, write_state


def fake_compile_lock(*args: Any, **kwargs: Any) -> None:
    kwargs["output_file"].write_text("locked\n", encoding="utf-8")


def test_run_without_environment_prints_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_cli(["run"], expected_code=1)

    assert "No JovyKit environment found" in result.output
    assert "Traceback" not in result.output


def test_init_existing_environment_prints_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["init", ".jovy"])

    result = run_cli(["init", ".jovy"], expected_code=1)

    assert "JovyKit environment already exists" in result.output
    assert "Traceback" not in result.output


def test_init_refuses_to_force_non_jovykit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".jovy").mkdir()
    (tmp_path / ".jovy" / "notes.txt").write_text("not a jovy env", encoding="utf-8")

    result = run_cli(["init", ".jovy", "--force"], expected_code=1)

    assert "Refusing to force initialize non-JovyKit directory" in result.output


def test_version_flag_prints_package_version(run_cli: Any) -> None:
    result = run_cli(["--version"])

    assert "jovykit" in result.output


def test_bare_command_launches_dashboard(
    monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    launched: list[bool] = []
    monkeypatch.setattr(cli, "launch_dashboard", lambda: launched.append(True))

    run_cli([])

    assert launched == [True]


def test_config_command_launches_editor(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    launched: list[Path | None] = []
    monkeypatch.setattr(
        "jovykit.config_editor.run_config_editor",
        lambda **kwargs: launched.append(kwargs["env"]),
    )

    run_cli(["config", "--env", str(project.env_dir)])

    assert launched == [project.env_dir]


def test_help_does_not_launch_dashboard(
    monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.setattr(
        cli,
        "launch_dashboard",
        lambda: pytest.fail("dashboard should not launch for --help"),
    )

    result = run_cli(["--help"])

    assert "Manage project-local JovyKit" in result.output


def test_init_accepts_project_and_jupyter_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    run_cli(
        [
            "init",
            ".jovy",
            "--token",
            "dev-token",
            "--log-level",
            "INFO",
            "--name",
            "Example Project",
            "--image-name",
            "custom-image",
            "--tag",
            "dev",
            "--workdir",
            "notebooks",
        ],
    )

    config_text = (tmp_path / "jovy.toml").read_text(encoding="utf-8")
    assert 'name = "Example Project"' in config_text
    assert 'name = "custom-image"' in config_text
    assert 'tag = "dev"' in config_text
    assert 'token = "dev-token"' in config_text
    assert "password" not in config_text
    assert 'log_level = "INFO"' in config_text
    assert (tmp_path / "notebooks").is_dir()


def test_init_prints_default_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_cli: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_cli(["init", ".jovy"])

    assert "Jupyter: http://127.0.0.1:8888/lab?token=jovykit" in result.output
    assert "Token: jovykit" in result.output


def test_add_updates_toml_packages_and_clears_build_signature(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    write_state(project.env_dir, {"build_signature": "old", "other": "kept"})

    run_cli(["add", "numpy", "pandas", "numpy"])

    assert 'packages = ["numpy", "pandas"]' in (project.root / "jovy.toml").read_text(
        encoding="utf-8"
    )
    assert read_state(project.env_dir) == {"other": "kept"}


def test_add_imports_requirements_file_recursively(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    (project.root / "nested.txt").write_text("pandas\n", encoding="utf-8")
    (project.root / "constraints.txt").write_text("numpy<2\n", encoding="utf-8")
    (project.root / "requirements.txt").write_text(
        "numpy\n-r nested.txt\n-c constraints.txt\n", encoding="utf-8"
    )

    run_cli(["add", "-r", "requirements.txt"])

    config_text = (project.root / "jovy.toml").read_text(encoding="utf-8")
    assert 'packages = ["numpy", "pandas"]' in config_text
    assert 'constraints = ["constraints.txt"]' in config_text


def test_add_requires_packages_or_requirement_file(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)

    run_cli(["add"], expected_code=2)


def test_remove_updates_toml_packages_and_clears_build_signature(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project(
        config_transform=lambda text: text.replace(
            "packages = []", 'packages = ["numpy", "pandas"]'
        )
    )
    monkeypatch.chdir(project.root)
    write_state(project.env_dir, {"build_signature": "old", "other": "kept"})

    run_cli(["remove", "numpy"])

    assert 'packages = ["pandas"]' in (project.root / "jovy.toml").read_text(
        encoding="utf-8"
    )
    assert read_state(project.env_dir) == {"other": "kept"}


def test_install_no_build_warns_without_building(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: True)
    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "build_streaming",
        lambda config: pytest.fail("build should be skipped by --no-build"),
    )

    result = run_cli(["install", "--no-build"])

    assert "Build is stale" in result.output


def test_install_regenerates_and_builds_when_stale(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    built: list[str] = []
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: True)
    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "build_image",
        lambda config, **kwargs: built.append(config.image_ref),
    )

    run_cli(["install"])

    assert built == [project.config.image_ref]


def test_install_upgrade_refreshes_lock(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[bool] = []
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: False)

    def compile_lock(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs["upgrade"])
        fake_compile_lock(*args, **kwargs)

    monkeypatch.setattr(command_ops, "compile_requirements_lock", compile_lock)

    run_cli(["install", "--upgrade"])

    assert calls == [True]


def test_install_migrates_legacy_requirements_file(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    (project.env_dir / "requirements.txt").write_text(
        "numpy\npandas\n", encoding="utf-8"
    )
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: False)
    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)

    run_cli(["install", "--no-build"])

    config_text = (project.root / "jovy.toml").read_text(encoding="utf-8")
    assert 'packages = ["numpy", "pandas"]' in config_text
    assert not (project.env_dir / "requirements.txt").exists()


@pytest.mark.parametrize("command", ["sync", "start", "stop"])
def test_removed_lifecycle_commands_are_not_registered(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    create_project: Any,
    run_cli: Any,
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)

    run_cli([command], expected_code=2)


def test_build_forwards_build_options(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[bool, bool]] = []
    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "build_image",
        lambda config, *, no_cache=False, pull=False: calls.append((no_cache, pull)),
    )
    monkeypatch.setattr(
        command_ops,
        "build_streaming",
        lambda config, *, no_cache=False, pull=False, log=None: calls.append(
            (no_cache, pull)
        ),
    )

    run_cli(["build", "--no-cache", "--pull"])

    assert calls == [(True, True)]


def test_run_uses_compose_watch_by_default(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    started: list[Path] = []
    stopped: list[Path] = []

    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )
    monkeypatch.setattr(
        command_ops, "start_watcher", lambda env_dir: started.append(env_dir)
    )
    monkeypatch.setattr(
        command_ops, "stop_watcher", lambda env_dir: stopped.append(env_dir)
    )

    run_cli(["run", "--no-build"])

    assert calls == [("up", "--watch")]
    assert started == [project.env_dir]
    assert stopped == [project.env_dir]


def test_run_no_watch_skips_watcher(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    started: list[Path] = []

    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )
    monkeypatch.setattr(
        command_ops, "start_watcher", lambda env_dir: started.append(env_dir)
    )

    run_cli(["run", "--no-build", "--no-watch"])

    assert calls == [("up",)]
    assert started == []


def test_up_does_not_combine_detach_with_compose_watch(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    started: list[Path] = []

    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )
    monkeypatch.setattr(
        command_ops, "start_watcher", lambda env_dir: started.append(env_dir)
    )

    result = run_cli(["up", "--no-build"])

    assert calls == [("up", "-d")]
    assert started == [project.env_dir]
    assert "Jupyter: http://127.0.0.1:9999/lab?token=jovykit" in result.output
    assert "Token: jovykit" in result.output


def test_down_stops_config_watcher_and_accepts_timeout(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    stopped: list[Path] = []

    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )
    monkeypatch.setattr(
        command_ops, "stop_watcher", lambda env_dir: stopped.append(env_dir)
    )

    run_cli(["down", "--timeout", "5"])

    assert calls == [("stop", "--timeout", "5")]
    assert stopped == [project.env_dir]


def test_restart_stops_installs_and_starts_detached(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    started: list[Path] = []
    stopped: list[Path] = []

    monkeypatch.setattr(command_ops, "compile_requirements_lock", fake_compile_lock)
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )
    monkeypatch.setattr(
        command_ops, "start_watcher", lambda env_dir: started.append(env_dir)
    )
    monkeypatch.setattr(
        command_ops, "stop_watcher", lambda env_dir: stopped.append(env_dir)
    )

    run_cli(["restart", "--no-build", "--timeout", "5"])

    assert calls == [("stop", "--timeout", "5"), ("up", "-d")]
    assert stopped == [project.env_dir]
    assert started == [project.env_dir]


def test_logs_accepts_since_timestamps_and_no_follow(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )

    run_cli(["logs", "--tail", "50", "--since", "10m", "--timestamps", "--no-follow"])

    assert calls == [("logs", "--tail", "50", "--since", "10m", "--timestamps")]


def test_shell_and_exec_construct_compose_commands(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        command_ops,
        "compose",
        lambda config, *args, attached=False, log=None: calls.append(args),
    )

    run_cli(["shell", "--command", "python --version"])
    run_cli(["exec", "python", "--version"])

    assert calls == [
        ("exec", "jovy", "bash", "-lc", "python --version"),
        ("exec", "jovy", "python", "--version"),
    ]


def test_exec_without_command_is_usage_error(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)

    run_cli(["exec"], expected_code=2)


def test_destroy_stops_watcher_removes_environment_and_can_keep_image(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    destroyed: list[bool] = []
    stopped: list[Path] = []
    monkeypatch.setattr(
        command_ops, "stop_watcher", lambda env_dir: stopped.append(env_dir)
    )
    monkeypatch.setattr(
        command_ops,
        "destroy_environment",
        lambda config, *, remove_image=True, log=None: destroyed.append(remove_image),
    )

    run_cli(["destroy", "--keep-image", "--remove-dir"])

    assert stopped == [project.env_dir]
    assert destroyed == [False]
    assert not project.env_dir.exists()


def test_clean_removes_generated_artifacts_but_keeps_manifest(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    (project.env_dir / "jovy.lock").write_text("locked\n", encoding="utf-8")

    run_cli(["clean"])

    assert not (project.env_dir / "Containerfile").exists()
    assert not (project.env_dir / "compose.yaml").exists()
    assert not (project.env_dir / "state.json").exists()
    assert (project.env_dir / "jovy.lock").exists()
    assert not (project.env_dir / "requirements.txt").exists()


def test_status_outputs_json(
    monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: False)

    result = run_cli(["status", "--json"])

    data = json.loads(result.output)
    assert data["environment"] == str(project.env_dir)
    assert data["project_image"] == project.config.image_ref
    assert data["build_stale"] is False


def test_env_option_loads_environment_outside_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, create_project: Any, run_cli: Any
) -> None:
    project = create_project()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setattr(command_ops, "is_build_stale", lambda config: False)

    result = run_cli(["status", "--env", str(project.env_dir), "--json"])

    assert json.loads(result.output)["environment"] == str(project.env_dir)
