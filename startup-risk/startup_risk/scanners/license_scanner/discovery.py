from __future__ import annotations

from dataclasses import dataclass, field

from startup_risk.core.models import FileSnapshot, RepositorySnapshot


MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile.lock",
    "setup.py",
    "setup.cfg",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gradle.lockfile",
    "gemfile",
    "gemfile.lock",
    "composer.json",
    "composer.lock",
    "packages.lock.json",
}
LICENSE_PREFIXES = ("license", "license.", "copying", "notice", "third_party_notices")
VENDORED_DIRS = {"vendor", "third_party", "external", "deps"}


@dataclass
class LicenseDiscovery:
    manifests: list[FileSnapshot] = field(default_factory=list)
    license_files: list[FileSnapshot] = field(default_factory=list)
    vendored_files: list[FileSnapshot] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def discover(snapshot: RepositorySnapshot) -> LicenseDiscovery:
    result = LicenseDiscovery()
    for file in snapshot.files:
        lower = file.path.lower()
        filename = lower.rsplit("/", maxsplit=1)[-1]
        parts = lower.split("/")

        is_manifest = filename in MANIFEST_NAMES or filename.endswith((".gemspec", ".csproj"))
        if file.skipped_reason and is_manifest:
            result.skipped.append(f"{file.path}: {file.skipped_reason}")
            continue
        if is_manifest:
            result.manifests.append(file)
        if filename.startswith(LICENSE_PREFIXES):
            result.license_files.append(file)
        if any(part in VENDORED_DIRS for part in parts[:-1]):
            result.vendored_files.append(file)

    return result
