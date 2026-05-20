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
    strategy = workflow["jobs"]["images"]["strategy"]
    matrix = strategy["matrix"]["include"]
    targets: dict[str, list[str]] = {}
    for item in matrix:
        targets.setdefault(item["target"], []).append(item["python-version"])

    assert strategy["max-parallel"] == 1
    assert [(item["target"], item["python-version"]) for item in matrix] == [
        ("minimal", "3.9"),
        ("minimal", "3.10"),
        ("minimal", "3.11"),
        ("minimal", "3.12"),
        ("minimal", "3.13"),
        ("minimal", "3.14"),
        ("base", "3.9"),
        ("base", "3.10"),
        ("base", "3.11"),
        ("base", "3.12"),
        ("base", "3.13"),
        ("base", "3.14"),
        ("extended", "3.11"),
        ("extended", "3.12"),
        ("extended", "3.13"),
        ("full", "3.11"),
        ("full", "3.12"),
        ("full", "3.13"),
    ]
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
    metadata_step = next(step for step in steps if step["name"] == "Extract metadata")
    attest_step = next(
        step for step in steps if step["name"] == "Attest image provenance"
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
    assert "artifact-metadata" not in text
    assert metadata_step["env"]["DOCKER_METADATA_ANNOTATIONS_LEVELS"] == "manifest"
    assert build_step["with"]["provenance"] is False
    assert build_step["with"]["sbom"] is False
    assert attest_step["with"]["push-to-registry"] is False
    assert attest_step["with"]["create-storage-record"] is False
    assert "value=latest" in text
    assert "matrix.target == 'minimal' && matrix.python-version == '3.14'" in text
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
