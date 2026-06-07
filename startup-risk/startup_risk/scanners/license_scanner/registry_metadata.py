from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from startup_risk.scanners.license_scanner.models import Dependency, LicenseEvidence


class RegistryMetadataError(ValueError):
    """Raised when registry metadata cannot be retrieved or parsed."""


@dataclass(frozen=True)
class RegistryPackageMetadata:
    evidence: LicenseEvidence | None = None
    artifact_url: str | None = None
    source_repo_url: str | None = None


def fetch_registry_license_evidence(dependency: Dependency, *, timeout: int = 20) -> LicenseEvidence | None:
    """Fetch license metadata as data only. Does not install, build, or execute packages."""
    return fetch_registry_metadata(dependency, timeout=timeout).evidence


def fetch_registry_metadata(dependency: Dependency, *, timeout: int = 20) -> RegistryPackageMetadata:
    url = _metadata_url(dependency)
    if url is None:
        return RegistryPackageMetadata()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "startup-risk-license-scanner/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as exc:
        raise RegistryMetadataError(str(exc)) from exc
    license_value, artifact_url, source_repo_url = _extract_metadata(dependency, raw)
    evidence = None
    if license_value:
        evidence = LicenseEvidence(
            source="registry_metadata",
            file=url,
            line=None,
            text=f"{dependency.name}@{dependency.version or '?'} registry license metadata",
            detected_license=license_value,
            confidence="medium",
        )
    return RegistryPackageMetadata(
        evidence=evidence,
        artifact_url=artifact_url,
        source_repo_url=source_repo_url,
    )


def _metadata_url(dependency: Dependency) -> str | None:
    name = urllib.parse.quote(dependency.name, safe="")
    if dependency.ecosystem == "npm":
        return f"https://registry.npmjs.org/{name}"
    if dependency.ecosystem == "python":
        return f"https://pypi.org/pypi/{name}/json"
    if dependency.ecosystem == "rust":
        return f"https://crates.io/api/v1/crates/{name}"
    if dependency.ecosystem == "ruby":
        return f"https://rubygems.org/api/v1/gems/{name}.json"
    if dependency.ecosystem == "php":
        return f"https://repo.packagist.org/p2/{dependency.name}.json"
    if dependency.ecosystem == "dotnet":
        lower = dependency.name.lower()
        return f"https://api.nuget.org/v3/registration5-gz-semver2/{lower}/index.json"
    if dependency.ecosystem == "java" and ":" in dependency.name:
        group_id, artifact_id = dependency.name.split(":", maxsplit=1)
        query = urllib.parse.quote(f'g:"{group_id}" AND a:"{artifact_id}"')
        return f"https://search.maven.org/solrsearch/select?q={query}&rows=1&wt=json"
    if dependency.ecosystem == "go":
        return f"https://pkg.go.dev/{dependency.name}?tab=licenses"
    return None


def _extract_metadata(dependency: Dependency, raw: str) -> tuple[str | None, str | None, str | None]:
    if dependency.ecosystem == "go":
        return None, None, f"https://{dependency.name}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, None, None
    artifact_url = None
    source_repo_url = None
    if dependency.ecosystem == "npm":
        value = data.get("license")
        source_repo_url = _repo_url(data.get("repository"))
        dist_tags = data.get("dist-tags") if isinstance(data.get("dist-tags"), dict) else {}
        version_key = dependency.version if dependency.version in (data.get("versions") or {}) else dist_tags.get("latest")
        if isinstance(value, str):
            pass
        else:
            value = None
        versions = data.get("versions")
        if isinstance(versions, dict) and version_key in versions:
            version_meta = versions[version_key]
            value = value or version_meta.get("license")
            dist = version_meta.get("dist") if isinstance(version_meta, dict) else None
            if isinstance(dist, dict):
                artifact_url = dist.get("tarball")
        return (value if isinstance(value, str) else None), artifact_url, source_repo_url
    if dependency.ecosystem == "python":
        info = data.get("info", {})
        value = info.get("license")
        source_repo_url = _project_url(info)
        classifiers = info.get("classifiers") or []
        urls = data.get("urls")
        if isinstance(urls, list):
            selected = _select_pypi_artifact(urls, dependency.version)
            artifact_url = selected.get("url") if selected else None
        if value:
            return str(value), artifact_url, source_repo_url
        for classifier in classifiers:
            if "License ::" in classifier:
                return str(classifier).split("::")[-1].strip(), artifact_url, source_repo_url
        return None, artifact_url, source_repo_url
    if dependency.ecosystem == "rust":
        crate = data.get("crate", {})
        value = crate.get("license")
        source_repo_url = crate.get("repository")
        artifact_url = f"https://crates.io/api/v1/crates/{urllib.parse.quote(dependency.name, safe='')}/{dependency.version}/download" if dependency.version else None
        return (value if isinstance(value, str) else None), artifact_url, source_repo_url
    if dependency.ecosystem == "ruby":
        licenses = data.get("licenses")
        source_repo_url = data.get("source_code_uri") or data.get("homepage_uri")
        artifact_url = data.get("gem_uri")
        if isinstance(licenses, list) and licenses:
            return " OR ".join(str(item) for item in licenses), artifact_url, source_repo_url
        return None, artifact_url, source_repo_url
    if dependency.ecosystem == "php":
        packages = data.get("packages")
        if isinstance(packages, dict):
            versions = packages.get(dependency.name)
            if isinstance(versions, list) and versions:
                source = versions[0].get("source") if isinstance(versions[0].get("source"), dict) else {}
                dist = versions[0].get("dist") if isinstance(versions[0].get("dist"), dict) else {}
                source_repo_url = source.get("url")
                artifact_url = dist.get("url")
                licenses = versions[0].get("license")
                if isinstance(licenses, list) and licenses:
                    return " OR ".join(str(item) for item in licenses), artifact_url, source_repo_url
        return None, artifact_url, source_repo_url
    if dependency.ecosystem == "dotnet":
        items = data.get("items")
        if isinstance(items, list):
            for page in items:
                for item in page.get("items", []) if isinstance(page, dict) else []:
                    catalog = item.get("catalogEntry", {})
                    source_repo_url = catalog.get("projectUrl")
                    artifact_url = catalog.get("packageContent")
                    value = catalog.get("licenseExpression")
                    if value:
                        return str(value), artifact_url, source_repo_url
        return None, artifact_url, source_repo_url
    if dependency.ecosystem == "java":
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return docs[0].get("license"), None, None
    return None, artifact_url, source_repo_url


def _repo_url(repository) -> str | None:
    if isinstance(repository, str):
        return repository
    if isinstance(repository, dict):
        return repository.get("url")
    return None


def _project_url(info: dict) -> str | None:
    project_urls = info.get("project_urls")
    if isinstance(project_urls, dict):
        for key in ("Source", "Source Code", "Code", "Repository", "Homepage"):
            if project_urls.get(key):
                return project_urls[key]
    return info.get("home_page")


def _select_pypi_artifact(urls: list, version: str | None) -> dict | None:
    candidates = [item for item in urls if isinstance(item, dict) and (version is None or item.get("packagetype") == "sdist" or item.get("filename", "").find(version) >= 0)]
    if not candidates:
        candidates = [item for item in urls if isinstance(item, dict)]
    for item in candidates:
        if item.get("packagetype") == "sdist":
            return item
    return candidates[0] if candidates else None
