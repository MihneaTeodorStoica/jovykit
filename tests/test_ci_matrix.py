from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import re
from typing import Any

import yaml


def _define_step(workflow: dict[str, Any]) -> dict[str, Any]:
    steps = workflow["jobs"]["define-images"]["steps"]
    return next(step for step in steps if step["name"] == "Define image matrix")


def _image_matrix(
    workflow: dict[str, Any],
    *,
    event_name: str = "push",
    event_schedule: str = "",
    tmp_path: Path,
) -> list[dict[str, str]]:
    define_step = _define_step(workflow)
    github_output = tmp_path / f"github-output-{event_name}"

    subprocess.run(
        ["bash", "-e", "-c", define_step["run"]],
        check=True,
        env={
            **os.environ,
            "GITHUB_OUTPUT": str(github_output),
            "EVENT_NAME": event_name,
            "EVENT_SCHEDULE": event_schedule,
        },
    )

    lines = github_output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "matrix<<JSON"
    assert lines[-1] == "JSON"
    return json.loads("\n".join(lines[1:-1]))["include"]


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


def test_python_ci_audits_all_dependency_manifests() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/ci-release.yml").read_text(encoding="utf-8")
    )
    python_job = workflow["jobs"]["python"]
    steps = python_job["steps"]

    package_step = next(
        step for step in steps if step["name"] == "Audit package dependency manifest"
    )
    manifest_step = next(
        step for step in steps if step["name"] == "Audit Python dependency manifests"
    )

    assert package_step["run"].strip() == "pip-audit ."
    assert "requirements.txt" in manifest_step["run"]
    assert "requirements-dev.txt" in manifest_step["run"]
    assert "image/requirements.txt" in manifest_step["run"]
    assert "image/requirements-base.txt" in manifest_step["run"]
    assert "image/requirements-minimal.txt" in manifest_step["run"]
    assert "image/requirements-extended.txt" in manifest_step["run"]
    assert "image/requirements-full.txt" in manifest_step["run"]
    assert "--ignore-vuln CVE-2025-69872" in manifest_step["run"]


def test_image_workflow_builds_supported_image_versions(tmp_path: Path) -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    )
    image_strategy = workflow["jobs"]["images"]["strategy"]
    publish_jobs = _publish_jobs(workflow)
    matrix = _image_matrix(workflow, tmp_path=tmp_path)
    targets: dict[str, list[str]] = {}
    for item in matrix:
        targets.setdefault(item["target"], []).append(item["python-version"])

    assert workflow["jobs"]["images"]["runs-on"] == "ubuntu-latest"
    assert image_strategy["max-parallel"] == 6
    assert publish_jobs == {}
    assert (
        image_strategy["matrix"]
        == "${{ fromJSON(needs.define-images.outputs.matrix) }}"
    )
    assert (
        workflow["jobs"]["images"]["steps"][-1]["uses"]
        == "./.github/actions/publish-image"
    )
    assert workflow["jobs"]["images"]["steps"][-1]["with"] == {
        "target": "${{ matrix.target }}",
        "python-version": "${{ matrix.python-version }}",
        "push": "${{ github.event_name != 'pull_request' }}",
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
    assert _image_matrix(workflow, event_name="pull_request", tmp_path=tmp_path) == [
        {"target": "full", "python-version": "3.12"},
    ]
    assert _image_matrix(
        workflow,
        event_name="schedule",
        event_schedule="30 6 * * *",
        tmp_path=tmp_path,
    ) == [
        {"target": "minimal", "python-version": "3.12"},
        {"target": "base", "python-version": "3.12"},
    ]


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
    image_steps = workflow["jobs"]["images"]["steps"]
    publish_steps = _publish_action_steps()
    workflow_build_step = next(
        step for step in image_steps if step["name"] == "Build image"
    )
    action_build_step = next(
        step for step in publish_steps if step["name"] == "Build image"
    )
    metadata_step = next(
        step for step in publish_steps if step["name"] == "Extract metadata"
    )
    attest_step = next(
        step for step in publish_steps if step["name"] == "Attest image provenance"
    )

    assert (
        workflow_build_step["with"]["push"]
        == "${{ github.event_name != 'pull_request' }}"
    )
    assert action_build_step["with"]["push"] == "${{ inputs.push }}"
    assert action_build_step["with"]["load"] == "${{ inputs.push != 'true' }}"
    assert (
        action_build_step["with"]["cache-from"]
        == "${{ steps.plan.outputs.cache-from }}"
    )
    assert (
        action_build_step["with"]["cache-to"]
        == "${{ inputs.push == 'true' && steps.plan.outputs.cache-to || '' }}"
    )
    assert "jovykit-buildcache" not in text
    assert "type=registry" not in text
    assert 'image_name="jovykit"' in text
    assert "value=${{ inputs.target }}-python-${{ inputs.python-version }}" in text
    assert "type=sha" not in text
    assert "CI_IMAGE_TAG" not in text
    assert "artifact-metadata" not in text
    assert metadata_step["if"] == "inputs.push == 'true'"
    assert metadata_step["env"]["DOCKER_METADATA_ANNOTATIONS_LEVELS"] == "manifest"
    assert action_build_step["with"]["provenance"] is False
    assert action_build_step["with"]["sbom"] is False
    assert attest_step["if"] == "inputs.push == 'true'"
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
    assert "monthly-python" not in text
    assert 'if [ "${{ inputs.target }}" != "full" ]; then' in text


def test_image_publish_action_fails_fast_on_invalid_target() -> None:
    action_text = Path(".github/actions/publish-image/action.yml").read_text(
        encoding="utf-8"
    )
    action = yaml.safe_load(action_text)
    plan_step = next(
        step
        for step in action["runs"]["steps"]
        if step.get("name") == "Plan image build"
    )
    run_text = plan_step["run"]

    assert re.search(r"\n\s*\*\)\s*$", run_text, flags=re.M) is not None
    assert "echo \"Invalid target '${{ inputs.target }}'" in run_text
    assert re.search(r"\n\s*exit 2\s*$", run_text, flags=re.M) is not None


def test_image_workflow_skips_heavy_nightly_targets(tmp_path: Path) -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/images.yml").read_text(encoding="utf-8")
    )
    nightly_matrix = _image_matrix(
        workflow,
        event_name="schedule",
        event_schedule="30 6 * * *",
        tmp_path=tmp_path,
    )

    assert {item["target"] for item in nightly_matrix} == {"minimal", "base"}
