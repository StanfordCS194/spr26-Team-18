from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.dependency_vuln_scanner import DependencyVulnScanner


def _snapshot(*files: tuple[str, str]) -> RepositorySnapshot:
    return RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path=path,
                size_bytes=len(text),
                extension=Path(path).suffix.lower(),
                text=text,
            )
            for path, text in files
        ],
    )


def test_returns_empty_when_disabled():
    scanner = DependencyVulnScanner(enable_osv=False)
    snap = _snapshot(("requirements.txt", "requests==2.26.0\n"))
    assert scanner.scan(snap) == []


def test_returns_empty_for_snapshot_with_no_manifests():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("src/app.py", "print('hello')"))
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=[]):
        assert scanner.scan(snap) == []


def test_produces_findings_for_osv_response():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("requirements.txt", "requests==2.26.0\n"))
    fake_response = [
        {
            "vulns": [
                {
                    "id": "GHSA-test-0001",
                    "summary": "Test vulnerability in requests.",
                    "database_specific": {"severity": "HIGH"},
                    "severity": [],
                }
            ]
        }
    ]
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake_response):
        findings = scanner.scan(snap)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "requests" in findings[0].title
    assert "GHSA-test-0001" in findings[0].title
    assert findings[0].scanner_id == "dependency_vuln"
    assert findings[0].confidence == "high"


def test_skips_packages_without_pinned_version():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("requirements.txt", "requests\n"))
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=[]) as mock_osv:
        scanner.scan(snap)
    mock_osv.assert_not_called()


def test_finding_id_is_stable():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("requirements.txt", "django==3.2.0\n"))
    fake = [{"vulns": [{"id": "CVE-2021-0001", "summary": "Test.", "database_specific": {"severity": "MEDIUM"}, "severity": []}]}]
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
        first = scanner.scan(snap)
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
        second = scanner.scan(snap)
    assert [f.id for f in first] == [f.id for f in second]


def test_maps_critical_severity():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("requirements.txt", "pillow==8.0.0\n"))
    fake = [{"vulns": [{"id": "GHSA-crit", "summary": "Critical.", "database_specific": {"severity": "CRITICAL"}, "severity": []}]}]
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
        findings = scanner.scan(snap)
    assert findings[0].severity == "critical"


def test_maps_medium_severity():
    scanner = DependencyVulnScanner(enable_osv=True)
    snap = _snapshot(("requirements.txt", "flask==1.0.0\n"))
    fake = [{"vulns": [{"id": "GHSA-med", "summary": "Medium.", "database_specific": {"severity": "MODERATE"}, "severity": []}]}]
    with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
        findings = scanner.scan(snap)
    assert findings[0].severity == "medium"
