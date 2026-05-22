from __future__ import annotations

import re

from pathlib import Path

WORKFLOW_PATHS = [
    *Path(".github/workflows").glob("*.yml"),
    *Path(".github/workflows").glob("*.yaml"),
    *Path(".github/actions").glob("*/action.yml"),
    *Path(".github/actions").glob("*/action.yaml"),
]


_ACTION_USE = re.compile(r"^\s*uses:\s*(?P<action>[^\s#]+)(?:\s+#\s*(?P<comment>.+))?")
_SHA_REF = re.compile(r"^[0-9a-f]{40}$")
_UPSTREAM_REF = re.compile(r"^(?:v\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?|release/\S+)$")


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
