"""Environment status discovery for the JovyKit dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jovykit.commands import jupyter_access_url, load_env
from jovykit.config import JovyConfig, JovyKitError, read_state
from jovykit.runtime import compose_ps, is_build_stale


@dataclass(frozen=True)
class EnvironmentStatus:
    """Snapshot of project-local JovyKit environment state."""

    initialized: bool
    project_path: Path
    env_dir: Path | None
    status: str
    health: str
    build: str
    image: str
    base_image: str
    gpu: str
    port: str
    url: str
    package_count: int
    home_mount: str
    last_error: str | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the container appears to be running."""
        return self.status in {"running", "healthy", "unhealthy", "starting"}


def discover_status(env: Path | None = None) -> EnvironmentStatus:
    """Discover environment status without raising user-facing config errors."""
    try:
        config = load_env(env)
    except JovyKitError as exc:
        project_path = (env or Path.cwd()).resolve()
        return EnvironmentStatus(
            initialized=False,
            project_path=project_path,
            env_dir=None,
            status="not initialized",
            health="unknown",
            build="unknown",
            image="unavailable",
            base_image="unavailable",
            gpu="unknown",
            port="unavailable",
            url="unavailable",
            package_count=0,
            home_mount="unavailable",
            last_error=str(exc),
        )
    return status_from_config(config)


def status_from_config(config: JovyConfig) -> EnvironmentStatus:
    """Build a dashboard status snapshot from a loaded config."""
    state = read_state(config.env_dir)
    build = "stale" if is_build_stale(config) else "fresh"
    container_status, health, ps_error = _compose_status(config)
    last_error = _string_or_none(state.get("last_error")) or ps_error
    if last_error and container_status == "unknown":
        container_status = "error"
    return EnvironmentStatus(
        initialized=True,
        project_path=config.project_root,
        env_dir=config.env_dir,
        status=container_status,
        health=health,
        build=build,
        image=config.image_ref,
        base_image=config.base_image,
        gpu=_gpu_label(config.gpus),
        port=f"127.0.0.1:{config.port}",
        url=_url(config),
        package_count=len(config.python_packages),
        home_mount=str(config.home_path),
        last_error=last_error,
    )


def _compose_status(config: JovyConfig) -> tuple[str, str, str | None]:
    try:
        output = compose_ps(config).strip()
    except JovyKitError as exc:
        return "unknown", "unknown", str(exc)
    if not output:
        return "stopped", "unknown", None
    services = _parse_compose_ps(output)
    if not services:
        return "stopped", "unknown", None
    service = _find_jovy_service(services)
    raw_state = str(
        service.get("State")
        or service.get("state")
        or service.get("Status")
        or service.get("status")
        or ""
    ).lower()
    raw_health = str(service.get("Health") or service.get("health") or "").lower()
    status = _normalize_container_status(raw_state, raw_health)
    health = _normalize_health(raw_health)
    return status, health, None


def _parse_compose_ps(output: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        parsed_items: list[dict[str, Any]] = []
        for line in output.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                parsed_items.append(item)
        return parsed_items
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _find_jovy_service(services: list[dict[str, Any]]) -> dict[str, Any]:
    for service in services:
        name = str(service.get("Service") or service.get("Name") or "").lower()
        if "jovy" in name:
            return service
    return services[0]


def _normalize_container_status(raw_state: str, raw_health: str) -> str:
    if "running" in raw_state or raw_state == "up":
        if "unhealthy" in raw_health:
            return "unhealthy"
        if "healthy" in raw_health:
            return "healthy"
        return "running"
    if "starting" in raw_state or "created" in raw_state:
        return "starting"
    if "exited" in raw_state or "stopped" in raw_state:
        return "stopped"
    if "dead" in raw_state or "error" in raw_state:
        return "error"
    return "unknown"


def _normalize_health(raw_health: str) -> str:
    if "unhealthy" in raw_health:
        return "unhealthy"
    if "healthy" in raw_health:
        return "healthy"
    if "starting" in raw_health:
        return "starting"
    return "unknown"


def _gpu_label(value: str) -> str:
    if value in {"auto", "all"}:
        return "enabled"
    return "disabled"


def _url(config: JovyConfig) -> str:
    return jupyter_access_url(config)


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
