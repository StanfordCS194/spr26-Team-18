from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Iterable

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import Finding, FindingEvidence, RepositorySnapshot, SourceLocation
from startup_risk.scanners.dependency_scanner.parser_adapter import parse_repository_dependencies
from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence
from startup_risk.scanners.license_scanner.reporting import is_dev_dependency


SCANNER_ID = "dependency_risk"
SCANNER_VERSION = "1.0.0"
MAX_EVIDENCE_EXCERPT_CHARS = 500

LOCKFILES_BY_ECOSYSTEM = {
    "npm": {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"},
    "python": {"poetry.lock", "pipfile.lock", "uv.lock"},
    "rust": {"cargo.lock"},
}

RISKY_SOURCE_PATTERNS = (
    "git+",
    "git://",
    "ssh://",
    "github:",
    "gitlab:",
    "bitbucket:",
    "http://",
    "https://",
    "file:",
    "link:",
    "workspace:",
)


class DependencyRiskScanner:
    """Offline dependency supply-chain hygiene scanner."""

    id = SCANNER_ID
    name = "Dependency Risk"
    version = SCANNER_VERSION

    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        parsed = parse_repository_dependencies(snapshot)
        dependencies = [
            dependency
            for dependency in parsed.dependencies
            if "self_dependency" not in dependency.flags
        ]
        manifest_paths = {file.path for file in parsed.discovery.manifests}
        lockfile_index = _lockfile_index(manifest_paths)
        resolved_index = _resolved_lockfile_dependencies(dependencies)
        missing_lockfile_groups = _missing_lockfile_groups(dependencies, lockfile_index)

        findings: list[Finding] = []
        for skipped in parsed.discovery.skipped:
            findings.append(_finding_for_skipped(skipped))
        for manifest_path, manifest_dependencies in missing_lockfile_groups.items():
            findings.append(_finding_for_missing_lockfile_group(manifest_path, manifest_dependencies))

        for dependency in dependencies:
            if dependency.source_type == "metadata":
                findings.extend(_findings_for_metadata_flags(dependency))
                continue

            if dependency.source_type == "manifest":
                vendored_manifest = _is_vendored_manifest_context(dependency)
                has_lockfile = has_lockfile_for_ecosystem(dependency, lockfile_index)
                if self.verbose and not vendored_manifest and not has_lockfile:
                    findings.append(_finding_for_missing_lockfile(dependency))
                if is_risky_source_spec(dependency):
                    findings.append(_finding_for_risky_source(dependency))
                elif (
                    not vendored_manifest
                    and is_unpinned_spec(dependency)
                    and _dependency_name_key(dependency) not in resolved_index
                    and (has_lockfile or self.verbose or _is_highly_floating_spec(dependency))
                ):
                    findings.append(_finding_for_unpinned_spec(dependency))

            if _should_report_lockfile_metadata_gap(dependency):
                gaps = _lockfile_metadata_gaps(dependency)
                if gaps:
                    findings.append(_finding_for_lockfile_metadata_gap(dependency, gaps))

            if dependency.relationship == "vendored" and not has_vendored_provenance_metadata(dependency):
                findings.append(_finding_for_vendored_provenance_gap(dependency))

        deduped = _dedupe_findings(findings)
        summary = _finding_for_summary(deduped)
        return [summary, *deduped] if summary else deduped


def _findings_for_metadata_flags(dependency: Dependency) -> list[Finding]:
    findings: list[Finding] = []
    for flag in dependency.flags:
        if flag.startswith("npm_lifecycle_script:"):
            script = flag.split(":", maxsplit=1)[1]
            findings.append(_finding_for_lifecycle_script(dependency, script))
    return findings


def is_runtime_dependency(dependency: Dependency) -> bool:
    return not is_dev_dependency(dependency)


def is_unpinned_spec(dependency: Dependency) -> bool:
    if dependency.source_type != "manifest":
        return False
    spec = _dependency_spec(dependency)
    if not spec:
        return True
    lower = spec.lower().strip()
    if lower in {"*", "latest", "x"}:
        return True
    if dependency.ecosystem == "python":
        return not re.search(r"(^|[^=!<>~])==\s*[^;\s]+", spec)
    if dependency.ecosystem == "npm":
        npm_spec = (dependency.version or spec).lower().strip()
        return npm_spec in {"", "*", "latest", "x"} or any(
            marker in npm_spec for marker in ("^", "~", ">=", "<=", ">", "<", "*", "latest")
        )
    if dependency.ecosystem == "rust":
        return bool(re.search(r"(^|\s|[\"':])(?:\^|~|>=|<=|>|<|\*|x\b)", lower)) or _looks_like_major_only(spec)
    return dependency.version is None or bool(re.search(r"(^|\s)(?:\*|latest|>=|<=|>|<)", lower))


def is_risky_source_spec(dependency: Dependency) -> bool:
    return _source_spec_kind(dependency) is not None


def has_lockfile_for_ecosystem(dependency: Dependency, lockfile_index: dict[str, set[str]]) -> bool:
    expected = LOCKFILES_BY_ECOSYSTEM.get(dependency.ecosystem)
    if not expected:
        return True
    directory = _directory(dependency.source_file)
    if dependency.ecosystem == "rust":
        return _has_lockfile_in_directory_or_ancestor(directory, lockfile_index, expected)
    if dependency.ecosystem in {"npm", "python"} and _is_workspace_manifest_path(dependency.source_file):
        return _has_lockfile_in_directory_or_ancestor(directory, lockfile_index, expected)
    return bool(lockfile_index.get(directory, set()) & expected)


def has_lockfile_resolution_metadata(dependency: Dependency) -> bool:
    if dependency.ecosystem != "npm" or dependency.source_type != "lockfile":
        return True
    return bool(dependency.version and _flag_value(dependency, "artifact_url") and _flag_value(dependency, "integrity"))


def has_vendored_provenance_metadata(dependency: Dependency) -> bool:
    if "vendored_missing_license" in dependency.flags:
        return False
    if "vendored_license_metadata_present" in dependency.flags:
        return True
    for evidence in dependency.evidence:
        filename = (evidence.file or "").lower().rsplit("/", maxsplit=1)[-1]
        text = (evidence.text or "").lower()
        if filename in {"readme.chromium", "package.json", "cargo.toml", "pyproject.toml"}:
            return True
        if any(marker in text for marker in ("license", "url:", "version", "source")):
            return True
    return False


def _lockfile_metadata_gaps(dependency: Dependency) -> list[str]:
    gaps: list[str] = []
    if not dependency.version:
        gaps.append("resolved version")
    if not _flag_value(dependency, "artifact_url"):
        gaps.append("resolved artifact URL")
    if not _flag_value(dependency, "integrity"):
        gaps.append("integrity hash")
    return gaps


def _should_report_lockfile_metadata_gap(dependency: Dependency) -> bool:
    if dependency.ecosystem != "npm" or dependency.source_type != "lockfile":
        return False
    if not _is_direct_manifest_dependency(dependency):
        return False
    return True


def _is_direct_manifest_dependency(dependency: Dependency) -> bool:
    return any(evidence.source == "local_manifest" for evidence in dependency.evidence)


def _is_vendored_manifest_context(dependency: Dependency) -> bool:
    if dependency.source_type != "manifest":
        return False
    path_parts = PurePosixPath(dependency.source_file).parts
    return any(part in {"third_party", "vendor", "external", "deps"} for part in path_parts)


def _missing_lockfile_groups(
    dependencies: Iterable[Dependency], lockfile_index: dict[str, set[str]]
) -> dict[str, list[Dependency]]:
    groups: dict[str, list[Dependency]] = {}
    for dependency in dependencies:
        if dependency.source_type != "manifest":
            continue
        if _is_vendored_manifest_context(dependency):
            continue
        if has_lockfile_for_ecosystem(dependency, lockfile_index):
            continue
        groups.setdefault(dependency.source_file, []).append(dependency)
    return groups


def _is_workspace_manifest_path(path: str) -> bool:
    parts = PurePosixPath(path).parts[:-1]
    return any(part in {"apps", "packages", "libs", "workspaces"} for part in parts)


def _finding_for_missing_lockfile(dependency: Dependency) -> Finding:
    expected = ", ".join(sorted(LOCKFILES_BY_ECOSYSTEM.get(dependency.ecosystem, set())))
    return _dependency_finding(
        rule="missing_lockfile",
        dependency=dependency,
        title=f"Dependency manifest has no matching lockfile for {dependency.name}",
        description=f"{dependency.source_file} declares {dependency.name}, but no matching {expected} was found in the same directory.",
        recommendation="Commit the ecosystem lockfile so dependency resolution is reproducible.",
        severity=_scoped_severity(dependency, runtime="medium", dev="low"),
        confidence="high",
    )


def _finding_for_missing_lockfile_group(manifest_path: str, dependencies: list[Dependency]) -> Finding:
    ecosystem = dependencies[0].ecosystem if dependencies else "unknown"
    expected = ", ".join(sorted(LOCKFILES_BY_ECOSYSTEM.get(ecosystem, set())))
    runtime_count = sum(1 for dependency in dependencies if is_runtime_dependency(dependency))
    dev_count = len(dependencies) - runtime_count
    examples = ", ".join(dependency.name for dependency in dependencies[:8])
    if len(dependencies) > 8:
        examples += f", and {len(dependencies) - 8} more"
    scope_text = f"{runtime_count} runtime and {dev_count} dev/test" if dev_count else f"{runtime_count} runtime"
    return Finding(
        id=stable_finding_id(SCANNER_ID, "missing_lockfile_manifest", manifest_path),
        title=f"Dependency manifest has no matching lockfile: {manifest_path}",
        description=(
            f"{manifest_path} declares {scope_text} dependencies, but no matching {expected} was found. "
            f"Examples: {examples}."
        ),
        category="dependency_supply_chain",
        severity=_manifest_missing_lockfile_severity(dependencies),  # type: ignore[arg-type]
        confidence="high",
        evidence=_manifest_group_evidence(dependencies),
        recommendation="Commit the ecosystem lockfile so dependency resolution is reproducible.",
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def _finding_for_unpinned_spec(dependency: Dependency) -> Finding:
    return _dependency_finding(
        rule="unpinned_spec",
        dependency=dependency,
        title=f"Dependency spec is not pinned for {dependency.name}",
        description="The dependency declaration allows a floating or range-based version without local lockfile resolution evidence.",
        recommendation="Pin the dependency or commit a lockfile with the resolved version.",
        severity=_scoped_severity(dependency, runtime="medium", dev="low"),
        confidence="medium",
    )


def _finding_for_risky_source(dependency: Dependency) -> Finding:
    source_kind = _source_spec_kind(dependency) or "non_registry"
    if source_kind == "local_path":
        description = "The dependency declaration references a local file or path source outside normal registry resolution."
        recommendation = "Use workspace metadata for local project dependencies or document why this local path is required."
        severity = _scoped_severity(dependency, runtime="medium", dev="low")
    else:
        description = "The dependency declaration references a Git, URL, or non-registry package source."
        recommendation = "Use a registry version or pin the external source to an immutable commit/artifact with review."
        severity = _scoped_severity(dependency, runtime="high", dev="medium")
    return _dependency_finding(
        rule="risky_source_spec",
        dependency=dependency,
        title=f"Dependency uses a non-registry source for {dependency.name}",
        description=description,
        recommendation=recommendation,
        severity=severity,
        confidence="high",
    )


def _finding_for_lifecycle_script(dependency: Dependency, script: str) -> Finding:
    return _dependency_finding(
        rule=f"npm_lifecycle_script_{script}",
        dependency=dependency,
        title=f"NPM lifecycle script declared: {script}",
        description=(
            f"The package metadata declares an npm {script} lifecycle script. "
            "The dependency scanner records this as metadata only and does not execute it."
        ),
        recommendation="Review install-time scripts before installing dependencies in privileged or production workflows.",
        severity="medium",
        confidence="high",
    )


def _finding_for_lockfile_metadata_gap(dependency: Dependency, gaps: list[str]) -> Finding:
    return _dependency_finding(
        rule="lockfile_metadata_gap",
        dependency=dependency,
        title=f"Lockfile entry lacks resolution metadata for {dependency.name}",
        description=f"The npm lockfile entry is missing: {', '.join(gaps)}.",
        recommendation="Regenerate the lockfile with resolved artifact and integrity metadata.",
        severity=_scoped_severity(dependency, runtime="medium", dev="low"),
        confidence="medium",
    )


def _finding_for_vendored_provenance_gap(dependency: Dependency) -> Finding:
    return _dependency_finding(
        rule="vendored_provenance_gap",
        dependency=dependency,
        title=f"Vendored component lacks provenance metadata for {dependency.name}",
        description="A vendored component with substantive files lacks nearby provenance metadata such as README.chromium, package metadata, LICENSE, NOTICE, source URL, or version marker.",
        recommendation="Add provenance metadata that identifies the upstream source, version, and review owner.",
        severity=_scoped_severity(dependency, runtime="medium", dev="low"),
        confidence="medium",
    )


def _finding_for_skipped(path_and_reason: str) -> Finding:
    return Finding(
        id=stable_finding_id(SCANNER_ID, "skipped_dependency_input", path_and_reason),
        title="Dependency scanner skipped an input",
        description=f"The scanner could not use this potential dependency input: {path_and_reason}",
        category="dependency_supply_chain",
        severity="medium",
        confidence="high",
        evidence=[FindingEvidence(description=path_and_reason)],
        recommendation="Increase scanner limits or inspect this file manually if it contains dependency data.",
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def _finding_for_summary(findings: list[Finding]) -> Finding | None:
    counted = [finding for finding in findings if finding.scanner_id == SCANNER_ID and not finding.id.startswith(f"{SCANNER_ID}.summary")]
    if not counted:
        return None
    rule_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for finding in counted:
        parts = finding.id.split(".")
        rule = parts[1] if len(parts) > 2 else "other"
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
    rule_text = ", ".join(f"{rule}={count}" for rule, count in sorted(rule_counts.items()))
    severity_text = ", ".join(f"{severity}={count}" for severity, count in sorted(severity_counts.items()))
    return Finding(
        id=stable_finding_id(SCANNER_ID, "summary", f"{rule_text}|{severity_text}"),
        title="Dependency scanner summary",
        description=f"Grouped dependency-risk summary: {rule_text}. Severity counts: {severity_text}.",
        category="dependency_supply_chain",
        severity="info",
        confidence="high",
        evidence=[FindingEvidence(description="Dependency scanner grouped summary.", excerpt=rule_text)],
        recommendation="Review higher-severity dependency supply-chain findings first, then inspect low-severity hygiene gaps.",
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def _dependency_finding(
    *,
    rule: str,
    dependency: Dependency,
    title: str,
    description: str,
    recommendation: str,
    severity: str,
    confidence: str,
) -> Finding:
    return Finding(
        id=stable_finding_id(SCANNER_ID, rule, dependency.key),
        title=title,
        description=description,
        category="dependency_supply_chain",
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        evidence=_finding_evidence(dependency),
        recommendation=recommendation,
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def _finding_evidence(dependency: Dependency) -> list[FindingEvidence]:
    evidence = [_evidence_from_dependency(item) for item in dependency.evidence]
    if evidence:
        return evidence
    return [
        FindingEvidence(
            location=_location(dependency.source_file, dependency.source_line),
            description="Dependency source location.",
        )
    ]


def _manifest_group_evidence(dependencies: list[Dependency]) -> list[FindingEvidence]:
    evidence = []
    for dependency in dependencies[:12]:
        evidence.append(
            FindingEvidence(
                location=_location(dependency.source_file, dependency.source_line),
                description=f"{dependency.name} dependency declaration.",
                excerpt=_bounded_excerpt(_dependency_spec(dependency)),
            )
        )
    return evidence


def _evidence_from_dependency(evidence: LicenseEvidence) -> FindingEvidence:
    return FindingEvidence(
        location=_location(evidence.file, evidence.line),
        description=f"{evidence.source} dependency metadata.",
        excerpt=_bounded_excerpt(evidence.text),
    )


def _location(path: str | None, line: int | None) -> SourceLocation | None:
    if path is None:
        return None
    return SourceLocation(path=path, line_start=line, line_end=line)


def _bounded_excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if len(stripped) <= MAX_EVIDENCE_EXCERPT_CHARS:
        return stripped
    return stripped[:MAX_EVIDENCE_EXCERPT_CHARS].rstrip() + "..."


def _dependency_spec(dependency: Dependency) -> str:
    if dependency.evidence:
        return " ".join(evidence.text or "" for evidence in dependency.evidence)
    return dependency.version or ""


def _looks_like_major_only(spec: str) -> bool:
    cleaned = spec.strip().strip('"').strip("'")
    return bool(re.fullmatch(r"\d+", cleaned))


def _is_highly_floating_spec(dependency: Dependency) -> bool:
    spec = _dependency_spec(dependency).lower().strip()
    version = (dependency.version or "").lower().strip()
    if not version:
        return True
    if version in {"*", "latest", "x"} or spec in {"*", "latest", "x"}:
        return True
    if version.startswith(">="):
        return True
    if ">=" in spec and "," not in spec:
        return True
    return bool(re.search(r"(?:^|[\s\"':])>=\s*[^,<\s]+(?:$|[\s\"'}\]])", spec))


def _source_spec_kind(dependency: Dependency) -> str | None:
    spec = _dependency_spec(dependency).lower()
    if spec.startswith("workspace:") or "workspace:" in spec:
        return None
    if any(pattern in spec for pattern in ("git+", "git://", "ssh://", "github:", "gitlab:", "bitbucket:")):
        return "external"
    if "http://" in spec or "https://" in spec:
        return "external"
    if any(pattern in spec for pattern in ("file:", "link:")):
        return "local_path"
    if re.search(r"(^|[\s\"'=])\.\.?/", spec):
        return "local_path"
    return None


def _scoped_severity(dependency: Dependency, *, runtime: str, dev: str) -> str:
    return dev if is_dev_dependency(dependency) else runtime


def _manifest_missing_lockfile_severity(dependencies: list[Dependency]) -> str:
    if not any(is_runtime_dependency(dependency) for dependency in dependencies):
        return "low"
    if all("package_role:library" in dependency.flags for dependency in dependencies):
        return "low"
    return "medium"


def _directory(path: str) -> str:
    parent = PurePosixPath(path).parent.as_posix()
    return "" if parent == "." else parent


def _lockfile_index(paths: Iterable[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for path in paths:
        filename = path.lower().rsplit("/", maxsplit=1)[-1]
        directory = _directory(path)
        index.setdefault(directory, set()).add(filename)
    return index


def _has_lockfile_in_directory_or_ancestor(
    directory: str, lockfile_index: dict[str, set[str]], expected: set[str]
) -> bool:
    current = directory
    while True:
        if lockfile_index.get(current, set()) & expected:
            return True
        if current == "":
            return False
        parent = PurePosixPath(current).parent.as_posix()
        current = "" if parent == "." else parent


def _resolved_lockfile_dependencies(dependencies: Iterable[Dependency]) -> set[tuple[str, str]]:
    return {
        _dependency_name_key(dependency)
        for dependency in dependencies
        if dependency.source_type == "lockfile" and dependency.version
    }


def _dependency_name_key(dependency: Dependency) -> tuple[str, str]:
    return (dependency.ecosystem, re.sub(r"[-_.]+", "-", dependency.name).lower())


def _flag_value(dependency: Dependency, prefix: str) -> str | None:
    marker = prefix + ":"
    for flag in dependency.flags:
        if flag.startswith(marker):
            return flag.removeprefix(marker)
    return None


def _dedupe_findings(findings: Iterable[Finding]) -> list[Finding]:
    by_id = {finding.id: finding for finding in findings}
    return sorted(by_id.values(), key=lambda finding: finding.id)
