from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    Severity,
    SourceLocation,
)
from startup_risk.scanners.license_scanner.discovery import discover
from startup_risk.scanners.license_scanner.models import Dependency
from startup_risk.scanners.license_scanner.parsers import (
    dotnet, generic, go, java, npm, php, python, ruby, rust,
)


_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_REQUEST_TIMEOUT = 30
_MAX_PACKAGES = 500

# Maps internal ecosystem names to OSV ecosystem identifiers.
_ECOSYSTEM_MAP: dict[str, str] = {
    "python": "PyPI",
    "npm": "npm",
    "cargo": "crates.io",
    "go": "Go",
    "maven": "Maven",
    "rubygems": "RubyGems",
    "composer": "Packagist",
    "nuget": "NuGet",
}

_OSV_SEVERITY_MAP: dict[str, Severity] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MODERATE": "medium",
    "MEDIUM": "medium",
    "LOW": "low",
}


def _clean_version(raw: str | None) -> str | None:
    """Extract the leading semver-like version number from a raw version string."""
    if not raw:
        return None
    m = re.match(r"^([0-9]+(?:\.[0-9a-zA-Z]+)*(?:[-+][a-zA-Z0-9.]+)?)", raw)
    return m.group(1) if m else None


def _dispatch_parser(file) -> list[Dependency]:
    filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
    if filename in {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}:
        return npm.parse(file)
    if filename in {"requirements.txt", "pyproject.toml", "poetry.lock", "pipfile.lock", "setup.py", "setup.cfg"}:
        return python.parse(file)
    if filename in {"cargo.toml", "cargo.lock"}:
        return rust.parse(file)
    if filename in {"go.mod", "go.sum"}:
        return go.parse(file)
    if filename in {"pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile"}:
        return java.parse(file)
    if filename in {"gemfile", "gemfile.lock"} or filename.endswith(".gemspec"):
        return ruby.parse(file)
    if filename in {"composer.json", "composer.lock"}:
        return php.parse(file)
    if filename.endswith(".csproj") or filename == "packages.lock.json":
        return dotnet.parse(file)
    return generic.parse(file)


def _parse_deps(snapshot: RepositorySnapshot) -> list[Dependency]:
    discovered = discover(snapshot)
    deps: list[Dependency] = []
    for manifest in discovered.manifests:
        deps.extend(_dispatch_parser(manifest))
    return deps


def _severity_from_osv(vuln: dict) -> Severity:
    # Prefer database_specific.severity (GitHub Advisory style).
    raw = vuln.get("database_specific", {}).get("severity", "")
    if raw.upper() in _OSV_SEVERITY_MAP:
        return _OSV_SEVERITY_MAP[raw.upper()]
    # Fall back to presence of any CVSS rating → high.
    if any(s.get("type", "").startswith("CVSS") for s in vuln.get("severity", [])):
        return "high"
    return "medium"


def _query_osv(queries: list[dict]) -> list[dict]:
    """POST to OSV batch endpoint. Returns per-query result dicts (same order)."""
    payload = json.dumps({"queries": queries}).encode()
    req = urllib.request.Request(
        _OSV_BATCH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode()).get("results", [])
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []


class DependencyVulnScanner:
    """Checks pinned dependency versions against the OSV vulnerability database."""

    id = "dependency_vuln"
    name = "Dependency Vulnerability"
    version = "1.0.0"

    def __init__(self, *, enable_osv: bool = True, max_packages: int = _MAX_PACKAGES) -> None:
        self.enable_osv = enable_osv
        self.max_packages = max_packages

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not self.enable_osv:
            return []

        deps = _parse_deps(snapshot)

        # Collect unique (osv_ecosystem, name, version) triples with pinned versions.
        seen: set[tuple[str, str, str]] = set()
        candidates: list[tuple[Dependency, str, str]] = []

        for dep in deps:
            osv_eco = _ECOSYSTEM_MAP.get(dep.ecosystem)
            if not osv_eco:
                continue
            version = _clean_version(dep.version)
            if not version:
                continue
            key = (osv_eco, dep.name.lower(), version)
            if key in seen:
                continue
            seen.add(key)
            candidates.append((dep, osv_eco, version))
            if len(candidates) >= self.max_packages:
                break

        if not candidates:
            return []

        queries = [
            {"package": {"name": dep.name, "ecosystem": eco}, "version": ver}
            for dep, eco, ver in candidates
        ]
        results = _query_osv(queries)
        if not results:
            return []

        findings: list[Finding] = []
        for (dep, eco, ver), result in zip(candidates, results):
            for vuln in result.get("vulns", []):
                vuln_id = vuln.get("id", "UNKNOWN")
                summary = vuln.get("summary") or "No summary available."
                severity = _severity_from_osv(vuln)
                detail_url = f"https://osv.dev/vulnerability/{vuln_id}"

                findings.append(Finding(
                    id=stable_finding_id(
                        self.id, "known_vulnerability",
                        f"{eco}:{dep.name}:{ver}:{vuln_id}",
                    ),
                    title=f"Known vulnerability in {dep.name} {ver} ({vuln_id})",
                    description=(
                        f"{summary} "
                        f"The package {dep.name}@{ver} ({eco}) is affected by a "
                        f"vulnerability tracked in the OSV database."
                    ),
                    category="dependency_vulnerability",
                    severity=severity,
                    confidence="high",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=dep.source_file,
                                line_start=dep.source_line,
                            ),
                            description=f"{vuln_id}: {summary}",
                            excerpt=detail_url,
                        )
                    ],
                    recommendation=(
                        f"Upgrade {dep.name} to a patched version. "
                        f"See {detail_url} for affected version ranges and patches."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                ))

        return findings
