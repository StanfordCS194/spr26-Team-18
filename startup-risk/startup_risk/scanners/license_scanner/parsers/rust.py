from __future__ import annotations

import re

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename == "cargo.toml":
        return _parse_cargo_toml(file)
    if filename == "cargo.lock":
        return _parse_cargo_lock(file)
    return []


def _parse_cargo_toml(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    current_section = None
    package_name = None
    package_version = None
    package_license = None
    for line_number, line in enumerate(file.text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped.strip("[]")
            continue
        if current_section == "package":
            if stripped.startswith("name"):
                package_name = _quoted_value(stripped)
            elif stripped.startswith("version"):
                package_version = _quoted_value(stripped)
            elif stripped.startswith("license"):
                package_license = _quoted_value(stripped)
        if current_section in {"dependencies", "dev-dependencies", "build-dependencies"}:
            match = re.match(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", stripped)
            if not match:
                continue
            name = match.group(1)
            spec = match.group(2).strip()
            dependencies.append(
                Dependency(
                    name=name,
                    version=_quoted_value(spec),
                    ecosystem="rust",
                    relationship="direct",
                    source_type="manifest",
                    source_file=file.path,
                    source_line=line_number,
                    evidence=[
                        LicenseEvidence(
                            source="local_manifest",
                            file=file.path,
                            line=line_number,
                            text=stripped,
                            detected_license=None,
                            confidence="none",
                        )
                    ],
                )
            )
    if package_name or package_license:
        dependencies.append(
            Dependency(
                name=package_name or "(rust project)",
                version=package_version,
                ecosystem="rust",
                relationship="unknown",
                source_type="metadata",
                source_file=file.path,
                source_line=find_line(file.text, "name") or find_line(file.text, "license"),
                declared_license=package_license,
                flags=["local_project"],
                evidence=[
                    LicenseEvidence(
                        source="local_manifest",
                        file=file.path,
                        line=find_line(file.text, "name") or find_line(file.text, "license"),
                        text=package_license or package_name,
                        detected_license=package_license,
                        confidence="high" if package_license else "none",
                    )
                ],
            )
        )
    return dependencies


def _parse_cargo_lock(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for block in re.split(r"\n(?=\[\[package\]\])", file.text):
        if "[[package]]" not in block:
            continue
        name = _field(block, "name")
        if not name:
            continue
        version = _field(block, "version")
        line = find_line(file.text, f'name = "{name}"')
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="rust",
                relationship="transitive",
                source_type="lockfile",
                source_file=file.path,
                source_line=line,
                evidence=[
                    LicenseEvidence(
                        source="lockfile",
                        file=file.path,
                        line=line,
                        text=f"{name}@{version}",
                        detected_license=None,
                        confidence="none",
                    )
                ],
            )
        )
    return dependencies


def _field(block: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}\s*=\s*\"([^\"]+)\"", block, flags=re.MULTILINE)
    return match.group(1) if match else None


def _quoted_value(value: str) -> str | None:
    match = re.search(r'"([^"]+)"', value)
    return match.group(1) if match else None
