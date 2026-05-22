from __future__ import annotations

import re

from pathlib import Path
from typing import Any

import yaml

WORKFLOW_PATHS = [
    *Path(".github/workflows").glob("*.yml"),
    *Path(".github/workflows").glob("*.yaml"),
    *Path(".github/actions").glob("*/action.yml"),
    *Path(".github/actions").glob("*/action.yaml"),
]


_ACTION_USE = re.compile(r"^\s*uses:\s*(?P<action>[^\s#]+)(?:\s+#\s*(?P<comment>.+))?")
_SHA_REF = re.compile(r"^[0-9a-f]{40}$")
_UPSTREAM_REF = re.compile(r"^(?:v\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?|release/\S+)$")
_PR_HEAD_CONTEXTS = (
    "github.event.pull_request.head",
    "github.head_ref",
)


def _load_yaml(path: Path) -> dict[Any, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _workflow_events(workflow: dict[Any, Any]) -> Any:
    return workflow.get("on", workflow.get(True, {}))


def _has_pull_request_target(events: Any) -> bool:
    if isinstance(events, str):
        return events == "pull_request_target"
    if isinstance(events, list):
        return "pull_request_target" in events
    if isinstance(events, dict):
        return "pull_request_target" in events
    return False


def test_workflows_do_not_embed_tokens_in_urls() -> None:
    offenders = [
        path
        for path in WORKFLOW_PATHS
        if "x-access-token:" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_workflows_pin_actions_to_full_shas_with_comments() -> None:
    offenders = []
    for path in WORKFLOW_PATHS:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _ACTION_USE.match(line)
            if not match:
                continue
            action = match.group("action")
            comment = (match.group("comment") or "").strip()

            if action.startswith("./"):
                continue

            if "@" not in action:
                offenders.append((str(path), line_number, "missing '@'"))
                continue

            _repository, ref = action.rsplit("@", 1)
            if _repository.count("/") < 1:
                continue

            if not _SHA_REF.fullmatch(ref):
                offenders.append(
                    (str(path), line_number, f"non-sha action ref '{ref}'")
                )
                continue

            if not comment or not _UPSTREAM_REF.match(comment):
                offenders.append(
                    (str(path), line_number, f"missing/invalid comment '{comment}'")
                )

    assert offenders == []


def test_ci_release_uses_pinned_release_requirements() -> None:
    workflow_text = Path(".github/workflows/ci-release.yml").read_text(encoding="utf-8")
    assert "python -m pip install -r requirements-release.txt" in workflow_text
    assert "python -m pip install build twine" not in workflow_text

    release_requirements = (
        Path("requirements-release.txt").read_text(encoding="utf-8").splitlines()
    )
    tool_versions = {
        line.split("==", 1)[0].strip(): line.strip()
        for line in release_requirements
        if line.strip() and not line.startswith("#")
    }
    assert "build" in tool_versions
    assert "twine" in tool_versions
    assert tool_versions["build"] == "build==1.5.0"
    assert tool_versions["twine"] == "twine==6.2.0"


def test_pull_request_target_workflows_do_not_checkout_pr_code() -> None:
    offenders = []
    for path in Path(".github/workflows").glob("*.yml"):
        workflow = _load_yaml(path)
        if not _has_pull_request_target(_workflow_events(workflow)):
            continue

        for job_name, job in workflow.get("jobs", {}).items():
            for step in job.get("steps", []):
                if not str(step.get("uses", "")).startswith("actions/checkout@"):
                    continue

                checkout_with = step.get("with", {})
                checkout_values = "\n".join(
                    str(value) for value in checkout_with.values()
                )
                if any(context in checkout_values for context in _PR_HEAD_CONTEXTS):
                    offenders.append(
                        (str(path), job_name, step.get("name", "checkout"))
                    )

    assert offenders == []


def test_image_publish_pushes_sbom_and_provenance_attestations() -> None:
    action = _load_yaml(Path(".github/actions/publish-image/action.yml"))
    steps = action["runs"]["steps"]
    build_step = next(step for step in steps if step["name"] == "Build image")
    attest_step = next(
        step for step in steps if step["name"] == "Attest image provenance"
    )

    assert build_step["with"]["provenance"] == "${{ inputs.push == 'true' }}"
    assert build_step["with"]["sbom"] == "${{ inputs.push == 'true' }}"
    assert attest_step["if"] == "inputs.push == 'true'"
    assert attest_step["with"]["push-to-registry"] is True
