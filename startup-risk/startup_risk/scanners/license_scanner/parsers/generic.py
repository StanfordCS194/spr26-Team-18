from __future__ import annotations

from collections import defaultdict

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.licenses import detect_license_from_text
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import bounded_text


VENDORED_DIRS = {"vendor", "third_party", "external", "deps"}
LICENSE_NAMES = ("license", "license.", "copying", "notice")


def parse_vendored(files: list[FileSnapshot]) -> list[Dependency]:
    by_component: dict[tuple[str, str], list[FileSnapshot]] = defaultdict(list)
    for file in files:
        parts = file.path.split("/")
        for index, part in enumerate(parts[:-1]):
            if part.lower() in VENDORED_DIRS and index + 1 < len(parts):
                by_component[(part, parts[index + 1])].append(file)
                break

    dependencies: list[Dependency] = []
    for (vendor_root, name), component_files in sorted(by_component.items()):
        license_file = _first_license_file(component_files)
        if license_file is None:
            sample = component_files[0]
            dependencies.append(
                Dependency(
                    name=name,
                    version=None,
                    ecosystem="vendored",
                    relationship="vendored",
                    source_type="vendored_code",
                    source_file=sample.path,
                    source_line=None,
                    flags=["vendored_missing_license", f"vendored_root:{vendor_root}"],
                    evidence=[
                        LicenseEvidence(
                            source="local_license_file",
                            file=sample.path,
                            line=None,
                            text="Vendored component has no detected LICENSE/COPYING/NOTICE file.",
                            detected_license=None,
                            confidence="none",
                        )
                    ],
                )
            )
            continue
        text = bounded_text(license_file.text, limit=8000)
        detected = detect_license_from_text(text)
        dependencies.append(
            Dependency(
                name=name,
                version=None,
                ecosystem="vendored",
                relationship="vendored",
                source_type="vendored_code",
                source_file=license_file.path,
                source_line=1,
                declared_license=detected,
                evidence=[
                    LicenseEvidence(
                        source="local_license_file",
                        file=license_file.path,
                        line=1,
                        text=text,
                        detected_license=detected,
                        confidence="high" if detected else "low",
                    )
                ],
                flags=[f"vendored_root:{vendor_root}"],
            )
        )
    return dependencies


def _first_license_file(files: list[FileSnapshot]) -> FileSnapshot | None:
    for file in sorted(files, key=lambda item: item.path):
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if filename.startswith(LICENSE_NAMES):
            return file
    return None
