from __future__ import annotations

import re

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text:
        return []
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename in {"gemfile", "gemfile.lock"} or filename.endswith(".gemspec"):
        return _parse_ruby_deps(file, filename)
    return []


def _parse_ruby_deps(file: FileSnapshot, filename: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    if filename == "gemfile.lock":
        for line_number, line in enumerate(file.text.splitlines(), start=1):
            match = re.match(r"\s{4}([A-Za-z0-9_.-]+)\s+\(([^)]+)\)", line)
            if match:
                dependencies.append(_dep(file, match.group(1), match.group(2), line_number, "lockfile", "transitive", line.strip()))
        return dependencies
    for line_number, line in enumerate(file.text.splitlines(), start=1):
        match = re.search(r"\bgem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line)
        if match:
            dependencies.append(_dep(file, match.group(1), match.group(2), line_number, "manifest", "direct", line.strip()))
    return dependencies


def _dep(file: FileSnapshot, name: str, version: str | None, line_number: int, source_type, relationship, text: str) -> Dependency:
    return Dependency(
        name=name,
        version=version,
        ecosystem="ruby",
        relationship=relationship,
        source_type=source_type,
        source_file=file.path,
        source_line=line_number,
        evidence=[
            LicenseEvidence(
                source="lockfile" if source_type == "lockfile" else "local_manifest",
                file=file.path,
                line=line_number,
                text=text,
                detected_license=None,
                confidence="none",
            )
        ],
    )
