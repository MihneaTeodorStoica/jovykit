from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_script_tags_match_published_scheme(tmp_path: Path) -> None:
    docker = tmp_path / "docker"
    log = tmp_path / "docker.log"
    docker.write_text(
        "#!/usr/bin/env bash\n" 'printf \'%s\\n\' "$*" >> "$DOCKER_LOG"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {
        "DOCKER_LOG": str(log),
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
    }

    subprocess.run(
        [
            str(REPO_ROOT / "build.sh"),
            "--python",
            "3.14",
            "--release",
            "v8.5.0",
            "--channel",
            "nightly",
            "--latest",
            "minimal",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )

    assert log.read_text(encoding="utf-8").strip() == (
        "build --build-arg PYTHON_VERSION=3.14 --target minimal "
        "-t ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.14 "
        "-t ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.14-v8.5.0 "
        "-t ghcr.io/mihneateodorstoica/jovykit:minimal-nightly-python-3.14 "
        "-t ghcr.io/mihneateodorstoica/jovykit:latest ./image"
    )


def test_build_script_rejects_unknown_channel() -> None:
    result = subprocess.run(
        [str(REPO_ROOT / "build.sh"), "--channel", "daily", "base"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unknown channel: daily" in result.stderr
