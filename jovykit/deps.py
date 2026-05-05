"""Project dependency manifest helpers."""

from __future__ import annotations

from pathlib import Path


def add_packages(requirements_path: Path, packages: list[str]) -> list[str]:
    """Append packages that are not already present."""
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    if requirements_path.exists():
        lines = requirements_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Project packages managed by JovyKit."]

    existing = {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }
    added: list[str] = []
    for package in packages:
        normalized = package.strip()
        if normalized and normalized not in existing:
            lines.append(normalized)
            existing.add(normalized)
            added.append(normalized)

    requirements_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return added


def remove_packages(requirements_path: Path, packages: list[str]) -> list[str]:
    """Remove exact package entries from the manifest."""
    if not requirements_path.exists():
        return []

    targets = {package.strip() for package in packages if package.strip()}
    lines = requirements_path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    removed: list[str] = []
    for line in lines:
        entry = line.strip()
        if entry and not entry.startswith("#") and entry in targets:
            removed.append(entry)
            continue
        kept.append(line)

    requirements_path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return removed
