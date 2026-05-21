from __future__ import annotations

from pathlib import Path


WORKFLOW_PATHS = [
    *Path(".github/workflows").glob("*.yml"),
    *Path(".github/workflows").glob("*.yaml"),
    *Path(".github/actions").glob("*/action.yml"),
    *Path(".github/actions").glob("*/action.yaml"),
]


def test_workflows_do_not_embed_tokens_in_urls() -> None:
    offenders = [
        path
        for path in WORKFLOW_PATHS
        if "x-access-token:" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
