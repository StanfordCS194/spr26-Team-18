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
    if filename == "yarn.lock":
        return _parse_yarn_lock(file)
    if filename == "pnpm-lock.yaml":
        return _parse_pnpm_lock(file)
    return []


def _parse_package_json(file: FileSnapshot) -> list[Dependency]:
    data = _load_json(file.text)
    if not isinstance(data, dict):
        return []
    dependencies: list[Dependency] = []

    if file.path == "package.json" and data.get("name"):
        license_value = data.get("license")
        flags = ["local_project"]
        flags.extend(_package_role_flags(file, data))
        dependencies.append(
            Dependency(
                name=str(data.get("name")),
                version=str(data.get("version")) if data.get("version") else None,
                ecosystem="npm",
                relationship="unknown",
                source_type="metadata",
                source_file=file.path,
                source_line=find_line(file.text, '"name"'),
                declared_license=str(license_value) if license_value else None,
                flags=flags,
                evidence=[
                    LicenseEvidence(
                        source="local_manifest",
                        file=file.path,
                        line=find_line(file.text, '"name"'),
                        text=str(license_value or data.get("name")),
                        detected_license=str(license_value) if license_value else None,
                        confidence="high" if license_value else "none",
                    )
                ],
            )
        )

    for section in DEPENDENCY_SECTIONS:
        raw_deps = data.get(section)
        if not isinstance(raw_deps, dict):
            continue
        for name, version_spec in raw_deps.items():
            flags = [f"dependency_scope:{section}"]
            flags.extend(_package_role_flags(file, data))
            dependencies.append(
                Dependency(
                    name=str(name),
                    version=str(version_spec) if version_spec is not None else None,
                    ecosystem="npm",
                    relationship="direct",
                    source_type="manifest",
                    source_file=file.path,
                    source_line=find_line(file.text, f'"{name}"'),
                    flags=flags,
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


def _package_role_flags(file: FileSnapshot, data: dict[str, Any]) -> list[str]:
    if file.path != "package.json":
        return []
    flags: list[str] = []
    if data.get("private") is True:
        flags.append("package_role:app")
    elif data.get("name"):
        flags.append("package_role:library")
    if data.get("workspaces"):
        flags.append("package_workspace_root")
    return flags


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
            flags = _lockfile_flags(metadata, package_path)
            if metadata.get("resolved"):
                flags.append(f"artifact_url:{metadata.get('resolved')}")
            if metadata.get("integrity"):
                flags.append(f"integrity:{metadata.get('integrity')}")
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
                    flags=flags,
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
            flags = _lockfile_flags(metadata, name)
            if metadata.get("resolved"):
                flags.append(f"artifact_url:{metadata.get('resolved')}")
            if metadata.get("integrity"):
                flags.append(f"integrity:{metadata.get('integrity')}")
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
                    flags=flags,
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


def _parse_yarn_lock(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    current_specs: list[str] = []
    current_block: list[str] = []
    current_line = 1

    def flush() -> None:
        if not current_specs:
            return
        block = "\n".join(current_block)
        version = _yaml_quoted_value(block, "version")
        resolved = _yaml_quoted_value(block, "resolved")
        integrity = _yaml_quoted_value(block, "integrity")
        for spec in current_specs:
            name = _name_from_yarn_spec(spec)
            if not name:
                continue
            flags: list[str] = []
            if resolved:
                flags.append(f"artifact_url:{resolved}")
            if integrity:
                flags.append(f"integrity:{integrity}")
            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    relationship="transitive",
                    source_type="lockfile",
                    source_file=file.path,
                    source_line=current_line,
                    flags=flags,
                    evidence=[
                        LicenseEvidence(
                            source="lockfile",
                            file=file.path,
                            line=current_line,
                            text=f"{name}@{version}",
                            detected_license=None,
                            confidence="none",
                        )
                    ],
                )
            )

    for line_number, line in enumerate(file.text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and line.rstrip().endswith(":"):
            flush()
            current_line = line_number
            key = line.rstrip()[:-1].strip().strip('"').strip("'")
            current_specs = [part.strip().strip('"').strip("'") for part in key.split(",")]
            current_block = []
            continue
        if current_specs:
            current_block.append(line)
    flush()
    return dependencies


def _parse_pnpm_lock(file: FileSnapshot) -> list[Dependency]:
    dependencies: list[Dependency] = []
    lines = file.text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped.endswith(":") or stripped.startswith(("-", "specifier:", "version:")):
            continue
        if not (stripped.startswith("/") or "@" in stripped):
            continue
        key = stripped[:-1].strip("'\"")
        parsed = _name_version_from_pnpm_key(key)
        if parsed is None:
            continue
        name, version = parsed
        block = "\n".join(lines[line_number : min(len(lines), line_number + 12)])
        flags: list[str] = []
        resolution = _yaml_quoted_value(block, "tarball")
        integrity = _yaml_quoted_value(block, "integrity")
        if resolution:
            flags.append(f"artifact_url:{resolution}")
        if integrity:
            flags.append(f"integrity:{integrity}")
        dependencies.append(
            Dependency(
                name=name,
                version=version,
                ecosystem="npm",
                relationship="transitive",
                source_type="lockfile",
                source_file=file.path,
                source_line=line_number,
                flags=flags,
                evidence=[
                    LicenseEvidence(
                        source="lockfile",
                        file=file.path,
                        line=line_number,
                        text=f"{name}@{version}",
                        detected_license=None,
                        confidence="none",
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


def _lockfile_flags(metadata: dict[str, Any], package_path: str) -> list[str]:
    flags: list[str] = []
    if metadata.get("dev") is True or metadata.get("devOptional") is True:
        flags.append("dependency_scope:lockfile_dev")
    if metadata.get("optional") is True or metadata.get("devOptional") is True:
        flags.append("dependency_scope:optionalDependencies")
    lower_path = package_path.lower()
    if any(part in lower_path for part in ("test", "tests", "fixture", "fixtures", "devtools", "tooling")):
        flags.append("dependency_scope:lockfile_dev")
    return flags


def _yaml_quoted_value(block: str, key: str) -> str | None:
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith(f"{key}:"):
            continue
        value = stripped.split(":", maxsplit=1)[1].strip()
        return value.strip('"').strip("'") or None
    return None


def _name_from_yarn_spec(spec: str) -> str | None:
    spec = spec.strip()
    if not spec:
        return None
    if spec.startswith("@"):
        parts = spec.split("@")
        if len(parts) >= 3:
            return "@" + parts[1]
        return spec
    return spec.split("@", maxsplit=1)[0] or None


def _name_version_from_pnpm_key(key: str) -> tuple[str, str | None] | None:
    cleaned = key.split("(", maxsplit=1)[0].strip("/")
    if not cleaned:
        return None
    if cleaned.startswith("@"):
        parts = cleaned.split("/")
        if len(parts) < 2:
            return None
        scope = parts[0]
        name_and_version = parts[1]
        if "@" not in name_and_version:
            return None
        name, version = name_and_version.rsplit("@", maxsplit=1)
        return f"{scope}/{name}", version or None
    if "@" not in cleaned:
        return None
    name, version = cleaned.rsplit("@", maxsplit=1)
    return name, version or None
