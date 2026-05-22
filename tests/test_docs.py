from __future__ import annotations

import re
from pathlib import Path

DOC_LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")
DOC_SECTIONS = (
    "Tutorial",
    "How-To",
    "Reference",
    "Explanation",
)


def _resolve_markdown_link(source: Path, link: str) -> Path | None:
    target = link.strip()
    if not target:
        return None
    if target.startswith(("#", "http://", "https://", "mailto:", "ftp://")):
        return None
    if target.startswith("/"):
        target = target[1:]
    target = target.split("#", 1)[0]
    if not target:
        return None
    candidate = Path(target)
    if candidate.suffix == "":
        if not candidate.exists():
            candidate = candidate.with_suffix(".md")
    if candidate.parts and candidate.parts[0] == "wiki":
        return candidate
    return source.parent / candidate


def test_readme_has_all_doc_sections() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    for section in DOC_SECTIONS:
        assert f"wiki/{section}.md" in readme


def test_sidebar_has_new_navigation_sections() -> None:
    sidebar = Path("wiki/_Sidebar.md").read_text(encoding="utf-8")
    for section in DOC_SECTIONS:
        assert f"[{section}]({section})" in sidebar


def test_all_internal_markdown_links_resolve() -> None:
    docs = [Path("README.md"), *sorted(Path("wiki").glob("*.md"))]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for link in DOC_LINK_RE.findall(text):
            resolved = _resolve_markdown_link(doc, link)
            if resolved is None:
                continue
            assert resolved.exists(), f"{doc}: broken link {link!r} -> {resolved}"


def test_security_doc_mentions_core_security_topics() -> None:
    security = Path("wiki/Security.md").read_text(encoding="utf-8")
    for topic in (
        "127.0.0.1",
        "JUPYTER_TOKEN",
        "docker",
        ".jupyter",
    ):
        assert topic in security


def test_diataxis_pages_cover_issue_requested_topics() -> None:
    how_to = Path("wiki/How-To.md").read_text(encoding="utf-8")
    reference = Path("wiki/Reference.md").read_text(encoding="utf-8")
    explanation = Path("wiki/Explanation.md").read_text(encoding="utf-8")

    for topic in ("Add packages", "Change Python", "Use GPU"):
        assert topic in how_to
    for topic in ("Config files", "compose.yaml", ".jupyter/"):
        assert topic in reference
    for topic in ("Image levels", "Docker model", "Security model"):
        assert topic in explanation
