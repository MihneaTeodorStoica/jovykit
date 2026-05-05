from pathlib import Path

import pytest

import jovykit.runtime as runtime
from jovykit.config import initial_config_text, load_config
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
