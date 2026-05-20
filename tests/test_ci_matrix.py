from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _image_matrix(workflow: dict[str, Any]) -> list[dict[str, str]]:
    steps = workflow["jobs"]["define-images"]["steps"]
    define_step = next(step for step in steps if step["name"] == "Define image matrix")
    match = re.search(
        r"cat <<'JSON'\n(?P<matrix>\{.*?\})\nJSON",
        define_step["run"],
        re.DOTALL,
    )

    assert match is not None
    return json.loads(match.group("matrix"))["include"]


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
    build_strategy = workflow["jobs"]["build-images"]["strategy"]
    publish_strategy = workflow["jobs"]["publish-images"]["strategy"]
    matrix = _image_matrix(workflow)
    targets: dict[str, list[str]] = {}
    for item in matrix:
        targets.setdefault(item["target"], []).append(item["python-version"])

    assert build_strategy["max-parallel"] == 6
    assert publish_strategy["max-parallel"] == 1
    assert (
        build_strategy["matrix"]
        == "${{ fromJSON(needs.define-images.outputs.matrix) }}"
    )
    assert (
        publish_strategy["matrix"]
        == "${{ fromJSON(needs.define-images.outputs.matrix) }}"
    )
    assert [(item["target"], item["python-version"]) for item in matrix] == [
        ("minimal", "3.9"),
        ("base", "3.9"),
        ("minimal", "3.10"),
        ("base", "3.10"),
        ("minimal", "3.11"),
        ("base", "3.11"),
        ("extended", "3.11"),
        ("full", "3.11"),
        ("minimal", "3.12"),
        ("base", "3.12"),
        ("extended", "3.12"),
        ("full", "3.12"),
        ("minimal", "3.13"),
        ("base", "3.13"),
        ("extended", "3.13"),
        ("full", "3.13"),
        ("minimal", "3.14"),
        ("base", "3.14"),
    ]
    assert targets == {
        "minimal": ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
        "base": ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
        "extended": ["3.11", "3.12", "3.13"],
        "full": ["3.11", "3.12", "3.13"],
    }


def test_image_workflow_define_step_writes_valid_output(tmp_path: Path) -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["define-images"]["steps"]
    define_step = next(step for step in steps if step["name"] == "Define image matrix")
    github_output = tmp_path / "github-output"

    subprocess.run(
        ["bash", "-e", "-c", define_step["run"]],
        check=True,
        env={**os.environ, "GITHUB_OUTPUT": str(github_output)},
    )

    lines = github_output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "matrix<<JSON"
    assert lines[-1] == "JSON"
    assert json.loads("\n".join(lines[1:-1]))["include"] == _image_matrix(workflow)


def test_image_workflow_uses_gha_cache_and_single_image_repository() -> None:
    text = Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    build_steps = workflow["jobs"]["build-images"]["steps"]
    publish_steps = workflow["jobs"]["publish-images"]["steps"]
    build_step = next(
        step for step in build_steps if step["name"] == "Build image cache"
    )
    publish_step = next(
        step for step in publish_steps if step["name"] == "Publish image"
    )
    metadata_step = next(
        step for step in publish_steps if step["name"] == "Extract metadata"
    )
    attest_step = next(
        step for step in publish_steps if step["name"] == "Attest image provenance"
    )

    assert build_step["with"]["push"] is False
    assert publish_step["with"]["push"] is True
    assert (
        build_step["with"]["cache-from"]
        == "${{ github.event_name != 'pull_request' && steps.plan.outputs.cache-from || '' }}"
    )
    assert (
        build_step["with"]["cache-to"]
        == "${{ github.event_name != 'pull_request' && steps.plan.outputs.cache-to || '' }}"
    )
    assert publish_step["with"]["cache-from"] == "${{ steps.plan.outputs.cache-from }}"
    assert "cache-to" not in publish_step["with"]
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
    assert publish_step["with"]["provenance"] is False
    assert publish_step["with"]["sbom"] is False
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
