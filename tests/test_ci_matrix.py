from __future__ import annotations

from pathlib import Path

import yaml


def test_python_ci_runs_supported_host_versions() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/ci-release.yml").read_text(encoding="utf-8")
    )
    versions = workflow["jobs"]["python"]["strategy"]["matrix"]["python-version"]

    assert versions == ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]


def test_image_workflow_builds_supported_image_versions() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    )
    matrix = workflow["jobs"]["images"]["strategy"]["matrix"]["include"]
    targets: dict[str, list[str]] = {}
    for item in matrix:
        targets.setdefault(item["target"], []).append(item["python-version"])

    assert targets == {
        "minimal": ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
        "base": ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
        "extended": ["3.11", "3.12", "3.13"],
        "full": ["3.11", "3.12", "3.13"],
    }


def test_image_workflow_uses_gha_cache_and_single_image_repository() -> None:
    text = Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    steps = workflow["jobs"]["images"]["steps"]
    build_step = next(
        step for step in steps if step["name"] == "Build and publish image"
    )

    assert (
        build_step["with"]["cache-from"]
        == "${{ github.event_name != 'pull_request' && steps.plan.outputs.cache-from || '' }}"
    )
    assert (
        build_step["with"]["cache-to"]
        == "${{ github.event_name != 'pull_request' && steps.plan.outputs.cache-to || '' }}"
    )
    assert "jovykit-buildcache" not in text
    assert "type=registry" not in text
    assert 'image_name="jovykit"' in text
    assert "value=${{ matrix.target }}-python-${{ matrix.python-version }}" in text
    assert "type=sha" not in text
    assert "CI_IMAGE_TAG" not in text
    assert "value=latest" in text
    assert "matrix.target == 'base' && matrix.python-version == '3.11'" in text
    assert (
        "value=${{ matrix.target }}-nightly-python-${{ matrix.python-version }}" in text
    )
    assert (
        "value=${{ matrix.target }}-weekly-python-${{ matrix.python-version }}" in text
    )
    assert (
        "value=${{ matrix.target }}-monthly-python-${{ matrix.python-version }}" in text
    )


def test_image_workflow_skips_heavy_nightly_targets() -> None:
    text = Path(".github/workflows/images.yml").read_text(encoding="utf-8")

    assert 'github.event.schedule }}" = "30 6 * * *"' in text
    assert "minimal|base) should_build=true" in text
    assert "*) should_build=false" in text
