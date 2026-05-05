"""Config-file watcher for running JovyKit environments."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from jovykit.config import JovyKitError, load_config
from jovykit.generate import write_generated_files
from jovykit.runtime import build as build_image
from jovykit.runtime import compose, is_build_stale

PID_FILE = "config-watch.pid"
LOG_FILE = "config-watch.log"


def pid_path(env_dir: Path) -> Path:
    """Return the watcher PID file path."""
    return env_dir / PID_FILE


def log_path(env_dir: Path) -> Path:
    """Return the watcher log file path."""
    return env_dir / LOG_FILE


def is_process_running(pid: int) -> bool:
    """Return whether a process ID appears to still be alive."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def start_watcher(env_dir: Path) -> None:
    """Start the background config watcher unless it is already running."""
    env_dir = env_dir.resolve()
    env_dir.mkdir(parents=True, exist_ok=True)
    pid_file = pid_path(env_dir)
    if pid_file.exists():
        with suppress(ValueError):
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if is_process_running(pid):
                return
        pid_file.unlink(missing_ok=True)

    with log_path(env_dir).open("ab") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "jovykit.watcher", str(env_dir)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")


def stop_watcher(env_dir: Path) -> None:
    """Stop the background config watcher if it is running."""
    env_dir = env_dir.resolve()
    pid_file = pid_path(env_dir)
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return

    if is_process_running(pid):
        with suppress(OSError):
            os.kill(pid, signal.SIGTERM)
    pid_file.unlink(missing_ok=True)


def apply_config_change(env_dir: Path) -> None:
    """Reload config and apply run/build changes to the Compose service."""
    config = load_config(env_dir)
    write_generated_files(config)
    if is_build_stale(config):
        build_image(config)
    compose(config, "up", "-d", "jovy", attached=False)


def watch_config(env_dir: Path, *, poll_interval: float = 1.0) -> None:
    """Poll jovy.toml and apply changes while the process is alive."""
    env_dir = env_dir.resolve()
    config = load_config(env_dir)
    config_path = config.config_path
    last_mtime = config_path.stat().st_mtime
    print(f"Watching {config_path}", flush=True)
    while True:
        time.sleep(poll_interval)
        try:
            current_mtime = config_path.stat().st_mtime
        except FileNotFoundError:
            continue
        if current_mtime == last_mtime:
            continue
        last_mtime = current_mtime
        try:
            apply_config_change(env_dir)
            print(f"Applied config change from {config_path}", flush=True)
        except JovyKitError as exc:
            print(f"Error: {exc}", flush=True)


def main() -> None:
    """Module entrypoint for the background watcher."""
    parser = argparse.ArgumentParser()
    parser.add_argument("env_dir", type=Path)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()
    watch_config(args.env_dir, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
