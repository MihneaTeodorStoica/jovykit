"""Project dependency manifest helpers."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from jovykit.config import JovyKitError


@dataclass(frozen=True)
class DependencyUpdate:
    """Result of a dependency manifest update."""

    added: list[str]
    removed: list[str]
    constraints_added: list[str]


@dataclass(frozen=True)
class RequirementsImport:
    """Dependencies discovered from requirements files."""

    packages: list[str]
    constraints: list[str]


def add_packages(
    config_path: Path,
    packages: list[str],
    *,
    constraints: list[str] | None = None,
) -> DependencyUpdate:
    """Add direct package specs and constraints to jovy.toml."""
    data = _read_toml(config_path)
    python = _python_table(data)
    existing_packages = _str_list(python.get("packages", []))
    existing_constraints = _str_list(python.get("constraints", []))

    added = _append_unique(existing_packages, packages)
    constraints_added = _append_unique(existing_constraints, constraints or [])

    python["packages"] = existing_packages
    python["constraints"] = existing_constraints
    config_path.write_text(tomlkit.dumps(data), encoding="utf-8")
    return DependencyUpdate(
        added=added, removed=[], constraints_added=constraints_added
    )


def remove_packages(config_path: Path, packages: list[str]) -> DependencyUpdate:
    """Remove exact direct package specs from jovy.toml."""
    data = _read_toml(config_path)
    python = _python_table(data)
    existing_packages = _str_list(python.get("packages", []))
    targets = {package.strip() for package in packages if package.strip()}
    kept: list[str] = []
    removed: list[str] = []
    for package in existing_packages:
        if package in targets:
            removed.append(package)
        else:
            kept.append(package)

    python["packages"] = kept
    if "constraints" not in python:
        python["constraints"] = []
    config_path.write_text(tomlkit.dumps(data), encoding="utf-8")
    return DependencyUpdate(added=[], removed=removed, constraints_added=[])


def import_requirements(
    paths: list[Path],
    *,
    project_dir: Path,
) -> RequirementsImport:
    """Import package specs and constraints from requirements files."""
    packages: list[str] = []
    constraints: list[str] = []
    seen_packages: set[str] = set()
    seen_constraints: set[str] = set()
    seen_files: set[Path] = set()

    for path in paths:
        _parse_requirements_file(
            _resolve_include(path, Path.cwd()),
            project_dir=project_dir,
            packages=packages,
            constraints=constraints,
            seen_packages=seen_packages,
            seen_constraints=seen_constraints,
            seen_files=seen_files,
            mode="requirements",
        )
    return RequirementsImport(packages=packages, constraints=constraints)


def import_legacy_requirements(
    config_path: Path, requirements_path: Path
) -> DependencyUpdate:
    """Import an old .jovy/requirements.txt manifest into jovy.toml."""
    if not requirements_path.exists():
        return DependencyUpdate(added=[], removed=[], constraints_added=[])
    imported = import_requirements([requirements_path], project_dir=config_path.parent)
    return add_packages(
        config_path,
        imported.packages,
        constraints=imported.constraints,
    )


def _parse_requirements_file(
    path: Path,
    *,
    project_dir: Path,
    packages: list[str],
    constraints: list[str],
    seen_packages: set[str],
    seen_constraints: set[str],
    seen_files: set[Path],
    mode: str,
) -> None:
    path = path.resolve()
    if path in seen_files:
        return
    seen_files.add(path)
    if not path.exists():
        raise JovyKitError(f"Requirements file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_requirement_line(raw_line)
        if not line:
            continue
        directive = _include_directive(line)
        if directive is not None:
            kind, value = directive
            included = _resolve_include(Path(value), path.parent)
            if kind == "requirement" and mode == "requirements":
                _parse_requirements_file(
                    included,
                    project_dir=project_dir,
                    packages=packages,
                    constraints=constraints,
                    seen_packages=seen_packages,
                    seen_constraints=seen_constraints,
                    seen_files=seen_files,
                    mode="requirements",
                )
            else:
                constraint = _display_path(included, project_dir)
                if constraint not in seen_constraints:
                    constraints.append(constraint)
                    seen_constraints.add(constraint)
                _parse_requirements_file(
                    included,
                    project_dir=project_dir,
                    packages=packages,
                    constraints=constraints,
                    seen_packages=seen_packages,
                    seen_constraints=seen_constraints,
                    seen_files=seen_files,
                    mode="constraints",
                )
            continue
        if mode == "constraints":
            continue
        if _unsupported_option(line):
            raise JovyKitError(f"Unsupported requirement option in {path}: {line}")
        spec = _normalize_spec(line, base_dir=path.parent, project_dir=project_dir)
        if spec not in seen_packages:
            packages.append(spec)
            seen_packages.add(spec)


def _read_toml(config_path: Path) -> tomlkit.TOMLDocument:
    if not config_path.exists():
        raise JovyKitError(f"No JovyKit configuration found at {config_path}.")
    return tomlkit.parse(config_path.read_text(encoding="utf-8"))


def _python_table(data: tomlkit.TOMLDocument) -> tomlkit.items.Table:
    table = data.get("python")
    if not isinstance(table, tomlkit.items.Table):
        table = tomlkit.table()
        data["python"] = table
    if "packages" not in table:
        table["packages"] = []
    if "constraints" not in table:
        table["constraints"] = []
    return table


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _append_unique(target: list[str], values: list[str]) -> list[str]:
    existing = set(target)
    added: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in existing:
            target.append(normalized)
            existing.add(normalized)
            added.append(normalized)
    return added


def _strip_requirement_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    return re.sub(r"\s+#.*$", "", stripped).strip()


def _include_directive(line: str) -> tuple[str, str] | None:
    if line.startswith("--requirement="):
        return ("requirement", line.split("=", 1)[1].strip())
    if line.startswith("--constraint="):
        return ("constraint", line.split("=", 1)[1].strip())
    try:
        parts = shlex.split(line)
    except ValueError as exc:
        raise JovyKitError(f"Could not parse requirements line: {line}") from exc
    if len(parts) >= 2 and parts[0] in {"-r", "--requirement"}:
        return ("requirement", parts[1])
    if len(parts) >= 2 and parts[0] in {"-c", "--constraint"}:
        return ("constraint", parts[1])
    return None


def _unsupported_option(line: str) -> bool:
    return line.startswith("-") and not line.startswith(("-e ", "--editable "))


def _normalize_spec(line: str, *, base_dir: Path, project_dir: Path) -> str:
    editable_prefix = ""
    spec = line
    if line.startswith("-e "):
        editable_prefix = "-e "
        spec = line[3:].strip()
    elif line.startswith("--editable "):
        editable_prefix = "-e "
        spec = line[len("--editable ") :].strip()
    normalized = _normalize_path_spec(spec, base_dir=base_dir, project_dir=project_dir)
    return f"{editable_prefix}{normalized}"


def _normalize_path_spec(spec: str, *, base_dir: Path, project_dir: Path) -> str:
    if "://" in spec or spec.startswith(("git+", "hg+", "svn+", "bzr+")):
        return spec
    candidate = Path(spec)
    if not candidate.is_absolute() and not _looks_like_path(spec):
        return spec
    resolved = _resolve_include(candidate, base_dir)
    return _display_path(resolved, project_dir)


def _looks_like_path(value: str) -> bool:
    return value.startswith((".", "/", "~")) or "/" in value or "\\" in value


def _resolve_include(path: Path, base_dir: Path) -> Path:
    if path.is_absolute():
        return path
    if str(path).startswith("~"):
        return path.expanduser()
    return (base_dir / path).resolve()


def _display_path(path: Path, project_dir: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return str(resolved)
