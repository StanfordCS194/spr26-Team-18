from __future__ import annotations

import json
from typing import Any

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename not in {"composer.json", "composer.lock"}:
        return []
    try:
        data = json.loads(file.text)
    except json.JSONDecodeError:
        return []
    return _parse_composer_lock(file, data) if filename == "composer.lock" else _parse_composer_json(file, data)


def _parse_composer_json(file: FileSnapshot, data: dict[str, Any]) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for section, relationship in (("require", "direct"), ("require-dev", "direct")):
        raw = data.get(section)
        if not isinstance(raw, dict):
            continue
        for name, version in raw.items():
            if name.lower() == "php" or name.startswith("ext-"):
                continue
            flags = [f"dependency_scope:{section}"]
            dependencies.append(_dep(file, name, str(version), find_line(file.text, f'"{name}"'), "manifest", relationship, flags))
    return dependencies


def _parse_composer_lock(file: FileSnapshot, data: dict[str, Any]) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for section in ("packages", "packages-dev"):
        packages = data.get(section)
        if not isinstance(packages, list):
            continue
        for package in packages:
            if not isinstance(package, dict) or not package.get("name"):
                continue
            license_value = None
            licenses = package.get("license")
            if isinstance(licenses, list) and licenses:
                license_value = " OR ".join(str(item) for item in licenses)
            dependencies.append(
                _dep(
                    file,
                    str(package["name"]),
                    str(package.get("version")) if package.get("version") else None,
                    find_line(file.text, f'"name": "{package["name"]}"'),
                    "lockfile",
                    "transitive",
                    [f"dependency_scope:{section}"],
                    license_value=license_value,
                )
            )
    return dependencies


def _dep(file, name, version, line, source_type, relationship, flags, license_value=None):
    return Dependency(
        name=name,
        version=version,
        ecosystem="php",
        relationship=relationship,
        source_type=source_type,
        source_file=file.path,
        source_line=line,
        declared_license=license_value,
        flags=flags,
        evidence=[
            LicenseEvidence(
                source="lockfile" if source_type == "lockfile" else "local_manifest",
                file=file.path,
                line=line,
                text=f"{name}@{version}",
                detected_license=license_value,
                confidence="high" if license_value else "none",
            )
        ],
    )
