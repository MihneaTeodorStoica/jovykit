"""Docker install planning helpers."""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from jovykit.config import JovyKitError

Emitter = Callable[[str], None]
Command = tuple[str, ...]
Runner = Callable[[Command], int]

GUIDES = {
    "linux": "https://docs.docker.com/engine/install/",
    "macos": "https://docs.docker.com/desktop/setup/install/mac-install/",
    "windows": "https://docs.docker.com/desktop/setup/install/windows-install/",
}


@dataclass(frozen=True)
class DockerInstallPlan:
    """A printable or executable Docker install plan."""

    system: str
    distro: str | None
    supported: bool
    guide_url: str
    commands: tuple[Command, ...]
    notes: tuple[str, ...] = ()


def read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    """Read os-release key values."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def build_install_plan(
    *,
    system: str | None = None,
    os_release: Mapping[str, str] | None = None,
    is_root: bool | None = None,
    has_systemd: bool | None = None,
    skip_hello_world: bool = False,
) -> DockerInstallPlan:
    """Build a Docker install plan for the current host."""
    detected_system = system or platform.system()
    normalized_system = detected_system.lower()
    if normalized_system == "darwin":
        return _manual_plan(detected_system, "macos")
    if normalized_system.startswith(("win", "msys", "cygwin")):
        return _manual_plan(detected_system, "windows")
    if normalized_system != "linux":
        return DockerInstallPlan(
            detected_system,
            None,
            False,
            GUIDES["linux"],
            (),
            ("Install Docker manually for this OS.",),
        )

    release = dict(read_os_release() if os_release is None else os_release)
    distro = _linux_distro(release)
    sudo: Command = (
        () if (os.geteuid() == 0 if is_root is None else is_root) else ("sudo",)
    )
    systemd = (
        Path("/run/systemd/system").exists() if has_systemd is None else has_systemd
    )
    notes = (
        "If docker info reports permission denied, add your user to the docker group and log out/in: sudo usermod -aG docker $USER",
        "The docker group grants root-equivalent access.",
    )
    commands = _linux_commands(
        distro,
        os_release=release,
        sudo=sudo,
        has_systemd=systemd,
    )
    if commands is None:
        return DockerInstallPlan(
            detected_system,
            distro,
            False,
            GUIDES["linux"],
            (),
            ("Automatic install supports Ubuntu, Debian, Fedora, RHEL, and CentOS.",),
        )

    checks: tuple[Command, ...] = (
        ("docker", "--version"),
        ("docker", "compose", "version"),
        ("docker", "info"),
    )
    if not skip_hello_world:
        checks = (*checks, ("docker", "run", "hello-world"))
    return DockerInstallPlan(
        detected_system,
        distro,
        True,
        GUIDES["linux"],
        (*commands, *checks),
        notes,
    )


def install_docker(
    *,
    yes: bool = False,
    skip_hello_world: bool = False,
    emit: Emitter = lambda _: None,
    runner: Runner | None = None,
) -> None:
    """Print or run the Docker install plan."""
    plan = build_install_plan(skip_hello_world=skip_hello_world)
    detected = plan.system if plan.distro is None else f"{plan.system} {plan.distro}"
    emit(f"detected: {detected}")
    emit(f"guide: {plan.guide_url}")
    if not plan.supported:
        for note in plan.notes:
            emit(note)
        if yes:
            raise JovyKitError("automatic Docker install is not supported for this OS.")
        return

    for command in plan.commands:
        emit(f"$ {_format_command(command)}")
    for note in plan.notes:
        emit(note)
    if not yes:
        emit("Dry run only. Run with --yes to execute.")
        return

    run = _run_command if runner is None else runner
    for command in plan.commands:
        code = run(command)
        if code != 0:
            raise JovyKitError(
                f"Docker install command failed with exit code {code}: "
                f"{_format_command(command)}"
            )
    emit("Docker install complete.")


def _manual_plan(system: str, key: str) -> DockerInstallPlan:
    return DockerInstallPlan(
        system,
        None,
        False,
        GUIDES[key],
        (),
        ("Install Docker Desktop manually, then run: jovy doctor",),
    )


def _linux_distro(os_release: Mapping[str, str]) -> str | None:
    identifiers = [os_release.get("ID", "").lower()]
    identifiers.extend(os_release.get("ID_LIKE", "").lower().split())
    for distro in ("ubuntu", "debian", "fedora", "rhel", "centos"):
        if distro in identifiers:
            return distro
    return identifiers[0] or None


def _linux_commands(
    distro: str | None,
    *,
    os_release: Mapping[str, str],
    sudo: Command,
    has_systemd: bool,
) -> tuple[Command, ...] | None:
    if distro in {"ubuntu", "debian"}:
        old_packages = (
            "docker.io",
            "docker-compose",
            "docker-doc",
            "podman-docker",
            "containerd",
            "runc",
        ) + (("docker-compose-v2",) if distro == "ubuntu" else ())
        suite = _linux_suite(os_release, distro)
        architecture = _docker_architecture()
        old_package_selection = " ".join(shlex.quote(pkg) for pkg in old_packages)
        return (
            (
                *sudo,
                "sh",
                "-c",
                "dpkg --get-selections "
                + old_package_selection
                + " | awk '$2==\"install\"{print $1}' | xargs -r apt remove -y",
            ),
            (*sudo, "apt", "update"),
            (*sudo, "apt", "install", "-y", "ca-certificates", "curl"),
            (*sudo, "install", "-m", "0755", "-d", "/etc/apt/keyrings"),
            (
                *sudo,
                "curl",
                "-fsSL",
                f"https://download.docker.com/linux/{distro}/gpg",
                "-o",
                "/etc/apt/keyrings/docker.asc",
            ),
            (*sudo, "chmod", "a+r", "/etc/apt/keyrings/docker.asc"),
            _apt_source_command(
                distro, suite=suite, architecture=architecture, sudo=sudo
            ),
            (*sudo, "apt", "update"),
            (
                *sudo,
                "apt",
                "install",
                "-y",
                "docker-ce",
                "docker-ce-cli",
                "containerd.io",
                "docker-buildx-plugin",
                "docker-compose-plugin",
            ),
            *(_systemd_command(sudo, has_systemd)),
        )
    if distro == "fedora":
        return (
            (
                *sudo,
                "dnf",
                "remove",
                "-y",
                "docker",
                "docker-client",
                "docker-client-latest",
                "docker-common",
                "docker-latest",
                "docker-latest-logrotate",
                "docker-logrotate",
                "docker-selinux",
                "docker-engine-selinux",
                "docker-engine",
            ),
            (
                *sudo,
                "dnf",
                "config-manager",
                "addrepo",
                "--from-repofile",
                "https://download.docker.com/linux/fedora/docker-ce.repo",
            ),
            (
                *sudo,
                "dnf",
                "install",
                "-y",
                "docker-ce",
                "docker-ce-cli",
                "containerd.io",
                "docker-buildx-plugin",
                "docker-compose-plugin",
            ),
            *(_systemd_command(sudo, has_systemd)),
        )
    if distro == "rhel":
        return (
            (*sudo, "dnf", "-y", "install", "dnf-plugins-core"),
            (
                *sudo,
                "dnf",
                "config-manager",
                "--add-repo",
                "https://download.docker.com/linux/rhel/docker-ce.repo",
            ),
            (
                *sudo,
                "dnf",
                "install",
                "-y",
                "docker-ce",
                "docker-ce-cli",
                "containerd.io",
                "docker-buildx-plugin",
                "docker-compose-plugin",
            ),
            *(_systemd_command(sudo, has_systemd)),
        )
    if distro == "centos":
        return (
            (
                *sudo,
                "dnf",
                "remove",
                "-y",
                "docker",
                "docker-client",
                "docker-client-latest",
                "docker-common",
                "docker-latest",
                "docker-latest-logrotate",
                "docker-logrotate",
                "docker-engine",
            ),
            (*sudo, "dnf", "-y", "install", "dnf-plugins-core"),
            (
                *sudo,
                "dnf",
                "config-manager",
                "--add-repo",
                "https://download.docker.com/linux/centos/docker-ce.repo",
            ),
            (
                *sudo,
                "dnf",
                "install",
                "-y",
                "docker-ce",
                "docker-ce-cli",
                "containerd.io",
                "docker-buildx-plugin",
                "docker-compose-plugin",
            ),
            *(_systemd_command(sudo, has_systemd)),
        )
    return None


def _linux_suite(os_release: Mapping[str, str], distro: str) -> str:
    if distro == "ubuntu":
        return (
            os_release.get("UBUNTU_CODENAME")
            or os_release.get("VERSION_CODENAME")
            or "stable"
        )
    return os_release.get("VERSION_CODENAME") or "stable"


def _docker_architecture() -> str:
    machine = platform.machine().lower()
    return {
        "x86_64": "amd64",
        "aarch64": "arm64",
        "armv7l": "armhf",
    }.get(machine, machine)


def _apt_source_command(
    distro: str,
    *,
    suite: str,
    architecture: str,
    sudo: Command,
) -> Command:
    marker = "/etc/apt/sources.list.d/docker.sources"
    safe_suite = suite.replace("\n", "")
    safe_arch = architecture.replace("\n", "")
    content = (
        "Types: deb\n"
        f"URIs: https://download.docker.com/linux/{distro}\n"
        f"Suites: {safe_suite}\n"
        "Components: stable\n"
        f"Architectures: {safe_arch}\n"
        "Signed-By: /etc/apt/keyrings/docker.asc\n"
    )
    script = (
        "from pathlib import Path; "
        f"Path({marker!r}).write_text("
        f"{content!r}, encoding='utf-8')"
    )
    return (*sudo, "python3", "-c", script)


def _systemd_command(sudo: Command, has_systemd: bool) -> tuple[Command, ...]:
    if not has_systemd:
        return ()
    return ((*sudo, "systemctl", "enable", "--now", "docker"),)


def _format_command(command: Command) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_command(command: Command) -> int:
    result = subprocess.run(command, check=False)
    return result.returncode
