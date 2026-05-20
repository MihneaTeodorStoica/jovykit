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


def _publish_jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        name: job
        for name, job in workflow["jobs"].items()
        if name.startswith("publish-python-")
    }


def _publish_action_steps() -> list[dict[str, Any]]:
    action = yaml.safe_load(
        Path(".github/actions/publish-image/action.yml").read_text(encoding="utf-8")
    )
    return action["runs"]["steps"]


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
    publish_jobs = _publish_jobs(workflow)
    matrix = _image_matrix(workflow)
    targets: dict[str, list[str]] = {}
    for item in matrix:
        targets.setdefault(item["target"], []).append(item["python-version"])

    publish_groups: dict[str, tuple[list[str], str, int, str | list[str]]] = {
        "publish-python-3-9": (["minimal", "base"], "3.9", 2, "build-images"),
        "publish-python-3-10": (
            ["minimal", "base"],
            "3.10",
            2,
            ["build-images", "publish-python-3-9"],
        ),
        "publish-python-3-11": (
            ["minimal", "base", "extended", "full"],
            "3.11",
            4,
            ["build-images", "publish-python-3-10"],
        ),
        "publish-python-3-12": (
            ["minimal", "base", "extended", "full"],
            "3.12",
            4,
            ["build-images", "publish-python-3-11"],
        ),
        "publish-python-3-13": (
            ["minimal", "base", "extended", "full"],
            "3.13",
            4,
            ["build-images", "publish-python-3-12"],
        ),
        "publish-python-3-14": (
            ["minimal", "base"],
            "3.14",
            2,
            ["build-images", "publish-python-3-13"],
        ),
    }

    assert build_strategy["max-parallel"] == 6
    assert list(publish_jobs) == list(publish_groups)
    assert (
        build_strategy["matrix"]
        == "${{ fromJSON(needs.define-images.outputs.matrix) }}"
    )
    for job_id, (job_targets, version, max_parallel, needs) in publish_groups.items():
        job = publish_jobs[job_id]
        assert job["needs"] == needs
        assert job["strategy"]["max-parallel"] == max_parallel
        assert job["strategy"]["matrix"] == {
            "target": job_targets,
            "python-version": [version],
        }
        assert job["steps"][-1]["uses"] == "./.github/actions/publish-image"
        assert job["steps"][-1]["with"] == {
            "target": "${{ matrix.target }}",
            "python-version": "${{ matrix.python-version }}",
        }
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
    workflow_text = Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    action_text = Path(".github/actions/publish-image/action.yml").read_text(
        encoding="utf-8"
    )
    text = workflow_text + action_text
    workflow = yaml.safe_load(workflow_text)
    assert ".github/actions/publish-image/action.yml" in workflow[True]["push"]["paths"]
    assert (
        ".github/actions/publish-image/action.yml"
        in workflow[True]["pull_request"]["paths"]
    )
    build_steps = workflow["jobs"]["build-images"]["steps"]
    publish_steps = _publish_action_steps()
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
    assert "value=${{ inputs.target }}-python-${{ inputs.python-version }}" in text
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
    assert "inputs.target == 'minimal' && inputs.python-version == '3.14'" in text
    assert (
        "value=${{ inputs.target }}-nightly-python-${{ inputs.python-version }}" in text
    )
    assert (
        "value=${{ inputs.target }}-weekly-python-${{ inputs.python-version }}" in text
    )
    assert (
        "value=${{ inputs.target }}-monthly-python-${{ inputs.python-version }}" in text
    )


def test_image_workflow_skips_heavy_nightly_targets() -> None:
    text = Path(".github/workflows/images.yml").read_text(encoding="utf-8") + Path(
        ".github/actions/publish-image/action.yml"
    ).read_text(encoding="utf-8")

    assert 'github.event.schedule }}" = "30 6 * * *"' in text
    assert "minimal|base) should_build=true" in text
    assert "*) should_build=false" in text
