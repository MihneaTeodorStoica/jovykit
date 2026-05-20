from __future__ import annotations

import pytest

from jovykit import docker_install
from jovykit.config import JovyKitError


def test_ubuntu_plan_matches_official_repository_flow() -> None:
    plan = docker_install.build_install_plan(
        system="Linux",
        os_release={"ID": "ubuntu"},
        is_root=False,
        has_systemd=True,
    )

    assert plan.supported is True
    assert plan.distro == "ubuntu"
    assert (
        "sudo apt remove -y $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)"
        in plan.commands
    )
    assert (
        "sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc"
        in plan.commands
    )
    assert any(
        "URIs: https://download.docker.com/linux/ubuntu" in command
        for command in plan.commands
    )
    assert any(
        'Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")'
        in command
        for command in plan.commands
    )
    assert "sudo systemctl enable --now docker" in plan.commands
    assert plan.commands[-1] == "docker run hello-world"


def test_debian_plan_uses_debian_codename() -> None:
    plan = docker_install.build_install_plan(
        system="Linux",
        os_release={"ID": "debian"},
        is_root=True,
        has_systemd=False,
        skip_hello_world=True,
    )

    assert (
        "apt remove -y $(dpkg --get-selections docker.io docker-compose docker-doc podman-docker containerd runc | cut -f1)"
        in plan.commands
    )
    assert any(
        "URIs: https://download.docker.com/linux/debian" in command
        for command in plan.commands
    )
    assert any(
        'Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")' in command
        for command in plan.commands
    )
    assert "docker run hello-world" not in plan.commands


def test_fedora_plan_uses_addrepo_command() -> None:
    plan = docker_install.build_install_plan(
        system="Linux",
        os_release={"ID": "fedora"},
        is_root=False,
        has_systemd=True,
    )

    assert (
        "sudo dnf config-manager addrepo --from-repofile https://download.docker.com/linux/fedora/docker-ce.repo"
        in plan.commands
    )
    assert "sudo systemctl enable --now docker" in plan.commands


def test_rhel_and_centos_are_supported() -> None:
    rhel = docker_install.build_install_plan(
        system="Linux",
        os_release={"ID": "rhel"},
        is_root=False,
        has_systemd=True,
    )
    centos = docker_install.build_install_plan(
        system="Linux",
        os_release={"ID": "centos"},
        is_root=False,
        has_systemd=True,
    )

    assert any("linux/rhel/docker-ce.repo" in command for command in rhel.commands)
    assert any("linux/centos/docker-ce.repo" in command for command in centos.commands)


def test_macos_and_windows_are_manual_guides() -> None:
    macos = docker_install.build_install_plan(system="Darwin")
    windows = docker_install.build_install_plan(system="Windows")

    assert macos.supported is False
    assert "mac-install" in macos.guide_url
    assert windows.supported is False
    assert "windows-install" in windows.guide_url


def test_dry_run_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = docker_install.DockerInstallPlan(
        "Linux",
        "ubuntu",
        True,
        docker_install.GUIDES["linux"],
        ("echo install",),
    )
    monkeypatch.setattr(docker_install, "build_install_plan", lambda **kwargs: plan)

    lines: list[str] = []
    docker_install.install_docker(
        emit=lines.append,
        runner=lambda command: pytest.fail(f"executed: {command}"),
    )

    assert "$ echo install" in lines
    assert "Dry run only. Run with --yes to execute." in lines


def test_yes_executes_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = docker_install.DockerInstallPlan(
        "Linux",
        "ubuntu",
        True,
        docker_install.GUIDES["linux"],
        ("echo one", "echo two"),
    )
    monkeypatch.setattr(docker_install, "build_install_plan", lambda **kwargs: plan)
    calls: list[str] = []

    def runner(command: str) -> int:
        calls.append(command)
        return 0

    docker_install.install_docker(yes=True, runner=runner)

    assert calls == ["echo one", "echo two"]


def test_yes_rejects_unsupported_os(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = docker_install.DockerInstallPlan(
        "Darwin",
        None,
        False,
        docker_install.GUIDES["macos"],
        (),
    )
    monkeypatch.setattr(docker_install, "build_install_plan", lambda **kwargs: plan)

    with pytest.raises(JovyKitError, match="not supported"):
        docker_install.install_docker(yes=True)
