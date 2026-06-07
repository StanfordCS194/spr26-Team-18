from __future__ import annotations

import re
import tomllib

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line, parse_req_spec


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename == "requirements.txt":
        return _parse_requirements(file)
    if filename == "pyproject.toml":
        return _parse_pyproject(file)
    if filename == "poetry.lock":
        return _parse_poetry_lock(file)
    return []


def _parse_requirements(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    scope_flags = _scope_flags_for_path(file.path)
    for line_number, line in enumerate(file.text.splitlines(), start=1):
        parsed = parse_req_spec(line)
        if parsed is None:
            continue
        name, version = parsed
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="python",
                relationship="direct",
                source_type="manifest",
                source_file=file.path,
                source_line=line_number,
                flags=scope_flags.copy(),
                evidence=[
                    LicenseEvidence(
                        source="local_manifest",
                        file=file.path,
                        line=line_number,
                        text=line.strip(),
                        detected_license=None,
                        confidence="none",
                    )
                ],
            )
        )
    return dependencies


def _parse_pyproject(file: FileSnapshot) -> list[Dependency]:
    try:
        data = tomllib.loads(file.text)
    except tomllib.TOMLDecodeError:
        return []
    dependencies: list[Dependency] = []

    for spec in data.get("project", {}).get("dependencies", []) or []:
        parsed = parse_req_spec(str(spec))
        if parsed is None:
            continue
        name, version = parsed
        dependencies.append(_dependency_from_spec(file, name, version, spec))

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    if isinstance(poetry_deps, dict):
        for name, version in poetry_deps.items():
            if name.lower() == "python":
                continue
            dependencies.append(_dependency_from_spec(file, name, str(version), name))

    project = data.get("project", {})
    project_license = project.get("license")
    license_value = None
    if isinstance(project_license, str):
        license_value = project_license
    elif isinstance(project_license, dict):
        license_value = project_license.get("text")
    project_name = project.get("name")
    if file.path == "pyproject.toml" and (project_name or license_value):
        dependencies.append(
            Dependency(
                name=project_name or "(python project)",
                version=project.get("version"),
                ecosystem="python",
                relationship="unknown",
                source_type="metadata",
                source_file=file.path,
                source_line=find_line(file.text, "name") or find_line(file.text, "license"),
                declared_license=license_value,
                flags=["local_project"],
                evidence=[
                    LicenseEvidence(
                        source="local_manifest",
                        file=file.path,
                        line=find_line(file.text, "name") or find_line(file.text, "license"),
                        text=str(license_value or project_name),
                        detected_license=str(license_value) if license_value else None,
                        confidence="high" if license_value else "none",
                    )
                ],
            )
        )
    return dependencies


def _dependency_from_spec(file: FileSnapshot, name: str, version: str | None, needle: object) -> Dependency:
    line = find_line(file.text, str(needle)) or find_line(file.text, name)
    return Dependency(
        name=name,
        version=version,
        ecosystem="python",
        relationship="direct",
        source_type="manifest",
        source_file=file.path,
        source_line=line,
        flags=_scope_flags_for_path(file.path),
        evidence=[
            LicenseEvidence(
                source="local_manifest",
                file=file.path,
                line=line,
                text=str(needle),
                detected_license=None,
                confidence="none",
            )
        ],
    )


def _parse_poetry_lock(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    blocks = re.split(r"\n(?=\[\[package\]\])", file.text)
    for block in blocks:
        if "[[package]]" not in block:
            continue
        name = _toml_value(block, "name")
        if not name:
            continue
        version = _toml_value(block, "version")
        license_value = _toml_value(block, "license")
        line = find_line(file.text, f'name = "{name}"')
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="python",
                relationship="transitive",
                source_type="lockfile",
                source_file=file.path,
                source_line=line,
                declared_license=license_value,
                evidence=[
                    LicenseEvidence(
                        source="lockfile",
                        file=file.path,
                        line=line,
                        text=f"{name}@{version}",
                        detected_license=license_value,
                        confidence="high" if license_value else "none",
                    )
                ],
            )
        )
    return dependencies


def _toml_value(block: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}\s*=\s*\"([^\"]+)\"", block, flags=re.MULTILINE)
    return match.group(1) if match else None


def _scope_flags_for_path(path: str) -> list[str]:
    lower = path.lower()
    flags: list[str] = []
    if lower.startswith("docs/") or "/docs/" in lower:
        flags.append("dependency_scope:docs")
    if any(part in lower.split("/") for part in ("test", "tests", "fixtures", "examples")):
        flags.append("dependency_scope:test")
    return flags
