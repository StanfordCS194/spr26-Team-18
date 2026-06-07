from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename.endswith(".csproj"):
        return _parse_csproj(file)
    if filename == "packages.lock.json":
        return _parse_packages_lock(file)
    return []


def _parse_csproj(file: FileSnapshot) -> list[Dependency]:
    try:
        root = ET.fromstring(file.text)
    except ET.ParseError:
        return []
    dependencies: list[Dependency] = []
    for reference in root.findall(".//{*}PackageReference"):
        name = reference.attrib.get("Include") or reference.attrib.get("Update")
        if not name:
            continue
        version = reference.attrib.get("Version")
        dependencies.append(_dep(file, name, version, find_line(file.text, f'Include="{name}"'), "manifest", "direct"))
    return dependencies


def _parse_packages_lock(file: FileSnapshot) -> list[Dependency]:
    try:
        data = json.loads(file.text)
    except json.JSONDecodeError:
        return []
    dependencies: list[Dependency] = []
    raw_deps = data.get("dependencies")
    if not isinstance(raw_deps, dict):
        return []
    for target_deps in raw_deps.values():
        if not isinstance(target_deps, dict):
            continue
        for name, metadata in target_deps.items():
            version = metadata.get("resolved") if isinstance(metadata, dict) else None
            dependencies.append(_dep(file, name, version, find_line(file.text, f'"{name}"'), "lockfile", "transitive"))
    return dependencies


def _dep(file, name, version, line, source_type, relationship):
    return Dependency(
        name=name,
        version=version,
        ecosystem="dotnet",
        relationship=relationship,
        source_type=source_type,
        source_file=file.path,
        source_line=line,
        evidence=[
            LicenseEvidence(
                source="lockfile" if source_type == "lockfile" else "local_manifest",
                file=file.path,
                line=line,
                text=f"{name}@{version}",
                detected_license=None,
                confidence="none",
            )
        ],
    )
