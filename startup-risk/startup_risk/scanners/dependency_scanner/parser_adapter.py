from __future__ import annotations

from dataclasses import dataclass

from startup_risk.core.models import RepositorySnapshot
from startup_risk.scanners.license_scanner.discovery import LicenseDiscovery, discover
from startup_risk.scanners.license_scanner.models import Dependency
from startup_risk.scanners.license_scanner.parsers import dotnet, generic, go, java, npm, php, python, ruby, rust
from startup_risk.scanners.license_scanner.scanner import _dedupe_dependencies, _mark_self_dependencies


@dataclass(frozen=True)
class DependencyParseResult:
    dependencies: list[Dependency]
    discovery: LicenseDiscovery


def parse_repository_dependencies(snapshot: RepositorySnapshot) -> DependencyParseResult:
    discovery = discover(snapshot)
    dependencies: list[Dependency] = []
    for file in discovery.manifests:
        dependencies.extend(npm.parse(file))
        dependencies.extend(python.parse(file))
        dependencies.extend(rust.parse(file))
        dependencies.extend(go.parse(file))
        dependencies.extend(java.parse(file))
        dependencies.extend(ruby.parse(file))
        dependencies.extend(php.parse(file))
        dependencies.extend(dotnet.parse(file))
    dependencies.extend(generic.parse_vendored(discovery.vendored_files))
    dependencies = _dedupe_dependencies(dependencies)
    _mark_self_dependencies(dependencies)
    return DependencyParseResult(dependencies=dependencies, discovery=discovery)
