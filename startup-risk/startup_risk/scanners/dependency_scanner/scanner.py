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
    "python": {"poetry.lock", "pipfile.lock"},
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

        findings: list[Finding] = []
        for skipped in parsed.discovery.skipped:
            findings.append(_finding_for_skipped(skipped))

        for dependency in dependencies:
            if dependency.source_type == "metadata":
                findings.extend(_findings_for_metadata_flags(dependency))
                continue

            if dependency.source_type == "manifest":
                vendored_manifest = _is_vendored_manifest_context(dependency)
                if not vendored_manifest and not has_lockfile_for_ecosystem(dependency, lockfile_index):
                    findings.append(_finding_for_missing_lockfile(dependency))
                if is_risky_source_spec(dependency):
                    findings.append(_finding_for_risky_source(dependency))
                elif (
                    not vendored_manifest
                    and is_unpinned_spec(dependency)
                    and _dependency_name_key(dependency) not in resolved_index
                ):
                    findings.append(_finding_for_unpinned_spec(dependency))

            if _should_report_lockfile_metadata_gap(dependency):
                gaps = _lockfile_metadata_gaps(dependency)
                if gaps:
                    findings.append(_finding_for_lockfile_metadata_gap(dependency, gaps))

            if dependency.relationship == "vendored" and not has_vendored_provenance_metadata(dependency):
                findings.append(_finding_for_vendored_provenance_gap(dependency))

        return _dedupe_findings(findings)


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
    spec = _dependency_spec(dependency).lower()
    if any(pattern in spec for pattern in RISKY_SOURCE_PATTERNS):
        return True
    return bool(re.search(r"(^|[\s\"'])\.\.?/", spec))


def has_lockfile_for_ecosystem(dependency: Dependency, lockfile_index: dict[str, set[str]]) -> bool:
    expected = LOCKFILES_BY_ECOSYSTEM.get(dependency.ecosystem)
    if not expected:
        return True
    directory = _directory(dependency.source_file)
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
    return _dependency_finding(
        rule="risky_source_spec",
        dependency=dependency,
        title=f"Dependency uses a non-registry source for {dependency.name}",
        description="The dependency declaration references a Git, URL, workspace, file, or local path source.",
        recommendation="Use a registry version or pin the external source to an immutable commit/artifact with review.",
        severity=_scoped_severity(dependency, runtime="high", dev="medium"),
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


def _scoped_severity(dependency: Dependency, *, runtime: str, dev: str) -> str:
    return dev if is_dev_dependency(dependency) else runtime


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
