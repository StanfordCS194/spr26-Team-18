from __future__ import annotations

import re

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence


def parse(file: FileSnapshot) -> list[Dependency]:
    if not file.text or file.path.lower().rsplit("/", maxsplit=1)[-1] != "go.mod":
        return []
    dependencies: list[Dependency] = []
    in_require_block = False
    for line_number, line in enumerate(file.text.splitlines(), start=1):
        stripped = line.split("//", maxsplit=1)[0].strip()
        if not stripped:
            continue
        if stripped == "require (":
            in_require_block = True
            continue
        if in_require_block and stripped == ")":
            in_require_block = False
            continue
        spec = None
        if in_require_block:
            spec = stripped
        elif stripped.startswith("require "):
            spec = stripped.removeprefix("require ").strip()
        if not spec:
            continue
        match = re.match(r"([^\s]+)\s+([^\s]+)", spec)
        if not match:
            continue
        name, version = match.groups()
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="go",
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
