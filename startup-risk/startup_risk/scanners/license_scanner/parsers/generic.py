from __future__ import annotations

from collections import defaultdict

from startup_risk.core.models import FileSnapshot
from startup_risk.scanners.license_scanner.licenses import detect_license_from_text
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.parsers.common import bounded_text


VENDORED_DIRS = {"vendor", "third_party", "external", "deps"}
LICENSE_NAMES = ("license", "license.", "copying", "notice")
LICENSE_METADATA_NAMES = {
    "readme.chromium",
    "package.json",
    "cargo.toml",
    "pyproject.toml",
    "composer.json",
    "gemfile",
    "pom.xml",
}
METADATA_ONLY_NAMES = {
    ".clang-format",
    ".gitignore",
    "owners",
    "readme.md",
    "visibility.gni",
}
SUBSTANTIVE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
    ".wasm",
}
HELPER_ONLY_COMPONENTS = {
    ("third_party", "node"),
}


def parse_vendored(files: list[FileSnapshot]) -> list[Dependency]:
    by_component: dict[tuple[str, str], list[FileSnapshot]] = defaultdict(list)
    for file in files:
        if _is_ignored_dependency_helper_path(file.path):
            continue
        parts = file.path.split("/")
        for index, part in enumerate(parts[:-1]):
            if part.lower() in VENDORED_DIRS and index + 2 < len(parts):
                by_component[(part, parts[index + 1])].append(file)
                break

    dependencies: list[Dependency] = []
    for (vendor_root, name), component_files in sorted(by_component.items()):
        if _is_helper_only_component(vendor_root, name, component_files):
            continue
        license_file = _first_license_file(component_files)
        if license_file is None:
            weak_metadata = _first_weak_license_metadata_file(component_files)
            if weak_metadata is not None and _has_substantive_component_content(component_files):
                dependencies.append(_unknown_vendored_dependency(vendor_root, name, weak_metadata))
                continue
            if not _has_substantive_component_content(component_files):
                continue
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
        flags = [f"vendored_root:{vendor_root}", "vendored_license_metadata_present"]
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
                flags=flags,
            )
        )
    return dependencies


def _first_license_file(files: list[FileSnapshot]) -> FileSnapshot | None:
    for file in sorted(files, key=lambda item: item.path):
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if filename.startswith(LICENSE_NAMES):
            return file
        if filename in LICENSE_METADATA_NAMES and _has_useful_license_metadata(file):
            return file
    return None


def _first_weak_license_metadata_file(files: list[FileSnapshot]) -> FileSnapshot | None:
    for file in sorted(files, key=lambda item: item.path):
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if filename in LICENSE_METADATA_NAMES:
            return file
    return None


def _has_substantive_component_content(files: list[FileSnapshot]) -> bool:
    for file in files:
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if filename in METADATA_ONLY_NAMES:
            continue
        if file.extension.lower() in SUBSTANTIVE_EXTENSIONS:
            return True
    return False


def _has_useful_license_metadata(file: FileSnapshot) -> bool:
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename != "readme.chromium":
        return True
    text = (file.text or "").lower()
    return any(field in text for field in ("license", "license file", "url:", "name:"))


def _is_ignored_dependency_helper_path(path: str) -> bool:
    lower = path.lower()
    return lower.startswith("scripts/deps/")


def _is_helper_only_component(vendor_root: str, name: str, files: list[FileSnapshot]) -> bool:
    if (vendor_root.lower(), name.lower()) not in HELPER_ONLY_COMPONENTS:
        return False
    filenames = {file.path.lower().rsplit("/", maxsplit=1)[-1] for file in files}
    return filenames.issubset({"node.py", "node_path.py"})


def _unknown_vendored_dependency(vendor_root: str, name: str, metadata_file: FileSnapshot) -> Dependency:
    text = bounded_text(metadata_file.text, limit=8000)
    return Dependency(
        name=name,
        version=None,
        ecosystem="vendored",
        relationship="vendored",
        source_type="vendored_code",
        source_file=metadata_file.path,
        source_line=1,
        evidence=[
            LicenseEvidence(
                source="local_license_file",
                file=metadata_file.path,
                line=1,
                text=text or "Vendored component metadata did not establish a license.",
                detected_license=None,
                confidence="low",
            )
        ],
        flags=[f"vendored_root:{vendor_root}", "vendored_license_metadata_present"],
    )
