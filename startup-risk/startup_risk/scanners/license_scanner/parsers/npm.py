from __future__ import annotations

import json
from typing import Any

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line


DEPENDENCY_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
LIFECYCLE_SCRIPTS = ("preinstall", "install", "postinstall", "prepublish", "prepare")


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename == "package.json":
        return _parse_package_json(file)
    if filename == "package-lock.json":
        return _parse_package_lock(file)
    return []


def _parse_package_json(file: FileSnapshot) -> list[Dependency]:
    data = _load_json(file.text)
    if not isinstance(data, dict):
        return []
    dependencies: list[Dependency] = []

    for section in DEPENDENCY_SECTIONS:
        raw_deps = data.get(section)
        if not isinstance(raw_deps, dict):
            continue
        for name, version_spec in raw_deps.items():
            dependencies.append(
                Dependency(
                    name=str(name),
                    version=str(version_spec) if version_spec is not None else None,
                    ecosystem="npm",
                    relationship="direct",
                    source_type="manifest",
                    source_file=file.path,
                    source_line=find_line(file.text, f'"{name}"'),
                    flags=[f"dependency_scope:{section}"],
                    evidence=[
                        LicenseEvidence(
                            source="local_manifest",
                            file=file.path,
                            line=find_line(file.text, f'"{name}"'),
                            text=f"{section}: {name}@{version_spec}",
                            detected_license=None,
                            confidence="none",
                        )
                    ],
                )
            )

    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        flagged = [name for name in LIFECYCLE_SCRIPTS if name in scripts]
        if flagged:
            dependencies.append(
                Dependency(
                    name=data.get("name") or "(npm project)",
                    version=data.get("version"),
                    ecosystem="npm",
                    relationship="unknown",
                    source_type="metadata",
                    source_file=file.path,
                    source_line=find_line(file.text, f'"{flagged[0]}"'),
                    flags=[f"npm_lifecycle_script:{name}" for name in flagged],
                    evidence=[
                        LicenseEvidence(
                            source="local_manifest",
                            file=file.path,
                            line=find_line(file.text, f'"{flagged[0]}"'),
                            text=", ".join(flagged),
                            detected_license=None,
                            confidence="none",
                        )
                    ],
                )
            )
    return dependencies


def _parse_package_lock(file: FileSnapshot) -> list[Dependency]:
    data = _load_json(file.text)
    if not isinstance(data, dict):
        return []
    dependencies: list[Dependency] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for package_path, metadata in packages.items():
            if not package_path or not isinstance(metadata, dict):
                continue
            if "node_modules/" not in package_path:
                continue
            name = package_path.split("node_modules/")[-1]
            license_value = metadata.get("license")
            line = find_line(file.text, f'"{package_path}"') or find_line(file.text, f'"{name}"')
            evidence = [
                LicenseEvidence(
                    source="lockfile",
                    file=file.path,
                    line=line,
                    text=f"{name}@{metadata.get('version')}",
                    detected_license=str(license_value) if license_value else None,
                    confidence="high" if license_value else "none",
                )
            ]
            dependencies.append(
                Dependency(
                    name=name,
                    version=str(metadata.get("version")) if metadata.get("version") else None,
                    ecosystem="npm",
                    relationship="transitive",
                    source_type="lockfile",
                    source_file=file.path,
                    source_line=line,
                    declared_license=str(license_value) if license_value else None,
                    evidence=evidence,
                )
            )
        return dependencies

    lock_deps = data.get("dependencies")
    if isinstance(lock_deps, dict):
        for name, metadata in lock_deps.items():
            if not isinstance(metadata, dict):
                continue
            license_value = metadata.get("license")
            line = find_line(file.text, f'"{name}"')
            dependencies.append(
                Dependency(
                    name=name,
                    version=str(metadata.get("version")) if metadata.get("version") else None,
                    ecosystem="npm",
                    relationship="transitive",
                    source_type="lockfile",
                    source_file=file.path,
                    source_line=line,
                    declared_license=str(license_value) if license_value else None,
                    evidence=[
                        LicenseEvidence(
                            source="lockfile",
                            file=file.path,
                            line=line,
                            text=f"{name}@{metadata.get('version')}",
                            detected_license=str(license_value) if license_value else None,
                            confidence="high" if license_value else "none",
                        )
                    ],
                )
            )
    return dependencies


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
