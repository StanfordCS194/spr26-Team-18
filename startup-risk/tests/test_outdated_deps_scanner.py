from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.outdated_deps_scanner import OutdatedDepsScanner


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
    scanner = OutdatedDepsScanner(enable_registry=False)
    snap = _snapshot(("requirements.txt", "requests==2.26.0\n"))
    assert scanner.scan(snap) == []


def test_returns_empty_for_snapshot_with_no_manifests():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("src/app.py", "print('hello')"))
    assert scanner.scan(snap) == []


def test_produces_finding_for_outdated_package():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("requirements.txt", "requests==2.1.0\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="2.31.0"):
        findings = scanner.scan(snap)
    assert len(findings) == 1
    assert "requests" in findings[0].title
    assert "2.1.0" in findings[0].title
    assert "2.31.0" in findings[0].title
    assert findings[0].severity == "low"
    assert findings[0].scanner_id == "outdated_deps"
    assert findings[0].confidence == "high"


def test_no_finding_when_already_up_to_date():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("requirements.txt", "requests==2.31.0\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="2.31.0"):
        assert scanner.scan(snap) == []


def test_no_finding_when_registry_unavailable():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("requirements.txt", "requests==2.1.0\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value=None):
        assert scanner.scan(snap) == []


def test_skips_packages_without_pinned_version():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("requirements.txt", "requests\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest") as mock_fetch:
        scanner.scan(snap)
    mock_fetch.assert_not_called()


def test_skips_unsupported_ecosystems():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("go.mod", "module example.com/myapp\n\nrequire golang.org/x/net v0.0.1\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest") as mock_fetch:
        scanner.scan(snap)
    mock_fetch.assert_not_called()


def test_finding_id_is_stable():
    scanner = OutdatedDepsScanner(enable_registry=True)
    snap = _snapshot(("requirements.txt", "flask==1.0.0\n"))
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="3.0.0"):
        first = scanner.scan(snap)
    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="3.0.0"):
        second = scanner.scan(snap)
    assert [f.id for f in first] == [f.id for f in second]


def test_respects_max_per_ecosystem_cap():
    scanner = OutdatedDepsScanner(enable_registry=True, max_per_ecosystem=2)
    reqs = "\n".join(f"pkg{i}==1.0.0" for i in range(10))
    snap = _snapshot(("requirements.txt", reqs))
    call_count = 0

    def fake_fetch(ecosystem, name):
        nonlocal call_count
        call_count += 1
        return "2.0.0"

    with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", side_effect=fake_fetch):
        scanner.scan(snap)
    assert call_count <= 2
