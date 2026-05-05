from pathlib import Path

import pytest

import jovykit.watcher as watcher
from jovykit.config import initial_config_text, load_config
from jovykit.generate import write_generated_files


def test_apply_config_change_regenerates_and_restarts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_dir = tmp_path / ".jovy"
    env_dir.mkdir()
    (tmp_path / "jovy.toml").write_text(
        initial_config_text(
            project_name="My Project",
            env_name=".jovy",
            image="minimal",
            gpus="none",
            port=9999,
        ),
        encoding="utf-8",
    )
    config = load_config(env_dir)
    write_generated_files(config)
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(watcher, "is_build_stale", lambda config: False)
    monkeypatch.setattr(
        watcher,
        "compose",
        lambda config, *args, attached=False: calls.append(args),
    )

    watcher.apply_config_change(env_dir)

    assert calls == [("up", "-d", "jovy")]
