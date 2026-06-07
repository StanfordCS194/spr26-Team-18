from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import find_line


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename == "pom.xml":
        return _parse_pom(file)
    if filename in {"build.gradle", "build.gradle.kts", "gradle.lockfile"}:
        return _parse_gradle(file)
    return []


def _parse_pom(file: FileSnapshot) -> list[Dependency]:
    try:
        root = ET.fromstring(file.text)
    except ET.ParseError:
        return []
    dependencies: list[Dependency] = []
    for dep in root.findall(".//{*}dependency"):
        group_id = _text(dep, "groupId")
        artifact_id = _text(dep, "artifactId")
        if not group_id or not artifact_id:
            continue
        version = _text(dep, "version")
        name = f"{group_id}:{artifact_id}"
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="java",
                relationship="direct",
                source_type="manifest",
                source_file=file.path,
                source_line=find_line(file.text, f"<artifactId>{artifact_id}</artifactId>"),
                evidence=[
                    LicenseEvidence(
                        source="local_manifest",
                        file=file.path,
                        line=find_line(file.text, f"<artifactId>{artifact_id}</artifactId>"),
                        text=name,
                        detected_license=None,
                        confidence="none",
                    )
                ],
            )
        )
    return dependencies


def _parse_gradle(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    pattern = re.compile(r"['\"]([A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[^'\"]+)['\"]")
    for line_number, line in enumerate(file.text.splitlines(), start=1):
        for match in pattern.finditer(line):
            parts = match.group(1).split(":")
            if len(parts) < 3:
                continue
            dependencies.append(
                Dependency(
                    name=f"{parts[0]}:{parts[1]}",
                    version=":".join(parts[2:]),
                    ecosystem="java",
                    relationship="direct",
                    source_type="manifest",
                    source_file=file.path,
                    source_line=line_number,
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


def _text(element: ET.Element, tag: str) -> str | None:
    child = element.find(f"{{*}}{tag}")
    if child is None or child.text is None:
        return None
    return child.text.strip()
