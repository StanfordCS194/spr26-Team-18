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
    SourceLocation,
)
from startup_risk.scanners.license_scanner.discovery import discover
from startup_risk.scanners.license_scanner.models import Dependency
from startup_risk.scanners.license_scanner.parsers import (
    dotnet, generic, go, java, npm, php, python, ruby, rust,
)


_REQUEST_TIMEOUT = 10
_DEFAULT_MAX_PER_ECOSYSTEM = 30  # registry rate-limit guard

_SUPPORTED_ECOSYSTEMS = frozenset({"python", "npm", "cargo", "rubygems"})


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


def _clean_version(raw: str | None) -> str | None:
    """Extract the leading semver-like number from a raw version string."""
    if not raw:
        return None
    m = re.match(r"^([0-9]+(?:\.[0-9a-zA-Z]+)*(?:[-+][a-zA-Z0-9.]+)?)", raw)
    return m.group(1) if m else None


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert a version string to a tuple of ints for simple comparison."""
    parts = re.split(r"[.\-+]", v)
    result: list[int] = []
    for part in parts:
        if part.isdigit():
            result.append(int(part))
        else:
            break
    return tuple(result) if result else (0,)


def _fetch_latest(ecosystem: str, name: str) -> str | None:
    """Return the latest published version string, or None on any failure."""
    try:
        if ecosystem == "python":
            url = f"https://pypi.org/pypi/{name}/json"
            with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT) as r:
                return json.loads(r.read().decode()).get("info", {}).get("version")

        if ecosystem == "npm":
            # The /latest dist-tag endpoint is lighter than the full document.
            url = f"https://registry.npmjs.org/{name}/latest"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as r:
                return json.loads(r.read().decode()).get("version")

        if ecosystem == "cargo":
            url = f"https://crates.io/api/v1/crates/{name}"
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    # crates.io requires a descriptive User-Agent.
                    "User-Agent": "startup-risk-scanner/1.0 (security-analysis-tool)",
                },
            )
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as r:
                return json.loads(r.read().decode()).get("crate", {}).get("newest_version")

        if ecosystem == "rubygems":
            url = f"https://rubygems.org/api/v1/gems/{name}.json"
            with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT) as r:
                return json.loads(r.read().decode()).get("version")

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        pass
    return None


class OutdatedDepsScanner:
    """Checks pinned dependency versions against current registry releases."""

    id = "outdated_deps"
    name = "Outdated Dependencies"
    version = "1.0.0"

    def __init__(
        self,
        *,
        enable_registry: bool = True,
        max_per_ecosystem: int = _DEFAULT_MAX_PER_ECOSYSTEM,
    ) -> None:
        self.enable_registry = enable_registry
        self.max_per_ecosystem = max_per_ecosystem

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not self.enable_registry:
            return []

        deps = _parse_deps(snapshot)

        # Dedupe: keep one representative dep per (ecosystem, normalised name).
        by_eco: dict[str, dict[str, Dependency]] = {}
        for dep in deps:
            if dep.ecosystem not in _SUPPORTED_ECOSYSTEMS:
                continue
            if not _clean_version(dep.version):
                continue
            by_eco.setdefault(dep.ecosystem, {}).setdefault(dep.name.lower(), dep)

        findings: list[Finding] = []
        for ecosystem, packages in by_eco.items():
            checked = 0
            for dep in packages.values():
                if checked >= self.max_per_ecosystem:
                    break
                pinned = _clean_version(dep.version)
                if not pinned:
                    continue
                latest = _fetch_latest(ecosystem, dep.name)
                checked += 1
                if not latest:
                    continue
                if _version_tuple(pinned) >= _version_tuple(latest):
                    continue

                findings.append(Finding(
                    id=stable_finding_id(
                        self.id, "outdated_dependency",
                        f"{ecosystem}:{dep.name}:{pinned}",
                    ),
                    title=f"Outdated dependency: {dep.name} {pinned} → {latest}",
                    description=(
                        f"{dep.name} ({ecosystem}) is pinned to {pinned} but the "
                        f"latest release is {latest}. Outdated packages may contain "
                        f"unpatched vulnerabilities or miss important security fixes."
                    ),
                    category="outdated_dependency",
                    severity="low",
                    confidence="high",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=dep.source_file,
                                line_start=dep.source_line,
                            ),
                            description=f"Pinned to {pinned}, latest release is {latest}.",
                            excerpt=f"{dep.name}=={pinned}",
                        )
                    ],
                    recommendation=(
                        f"Upgrade {dep.name} from {pinned} to {latest}. "
                        f"Review the changelog for breaking changes before upgrading."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                ))

        return findings
