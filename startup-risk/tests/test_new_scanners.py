from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.code_compliance_scanner import CodeComplianceScanner
from startup_risk.scanners.dependency_vuln_scanner import DependencyVulnScanner
from startup_risk.scanners.outdated_deps_scanner import OutdatedDepsScanner
from startup_risk.scanners.secret_scanner import SecretScanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot(*files: tuple[str, str]) -> RepositorySnapshot:
    """Build a minimal snapshot from (path, text) pairs."""
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


def _ids(findings) -> set[str]:
    return {f.id for f in findings}


# ===========================================================================
# SecretScanner
# ===========================================================================

class TestSecretScanner:
    scanner = SecretScanner()

    def test_detects_pem_private_key(self):
        snap = _snapshot(("config/deploy.pem", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."))
        findings = self.scanner.scan(snap)
        assert any("pem_private_key" in f.id for f in findings)
        assert all(f.scanner_id == "secret_scanner" for f in findings)

    def test_pem_key_is_critical_in_src_file(self):
        snap = _snapshot(("src/certs.py", "key = '-----BEGIN PRIVATE KEY-----'"))
        findings = self.scanner.scan(snap)
        critical = [f for f in findings if f.severity == "critical"]
        assert critical

    def test_pem_key_is_high_in_test_file(self):
        snap = _snapshot(("tests/fixtures/test_cert.py", "# -----BEGIN PRIVATE KEY-----"))
        findings = self.scanner.scan(snap)
        # Severity is reduced to high for test files.
        high = [f for f in findings if f.severity == "high" and "pem_private_key" in f.id]
        assert high

    def test_detects_aws_access_key(self):
        snap = _snapshot(("app.py", "key = 'AKIAIOSFODNN7EXAMPLE'"))
        findings = self.scanner.scan(snap)
        assert any("aws_access_key" in f.id for f in findings)

    def test_detects_hardcoded_secret_assignment(self):
        snap = _snapshot(("config.py", 'api_key = "sk-Z9mQvR3kXpLwY7nBdT2sUe"'))
        findings = self.scanner.scan(snap)
        assert any("hardcoded_secret" in f.id for f in findings)

    def test_ignores_placeholder_values(self):
        snap = _snapshot(("config.py", 'api_key = "your_api_key_here_replace_me"'))
        findings = self.scanner.scan(snap)
        assert not any("hardcoded_secret" in f.id for f in findings)

    def test_ignores_template_syntax(self):
        snap = _snapshot(("config.py", 'api_key = "${API_KEY_FROM_ENV}"'))
        findings = self.scanner.scan(snap)
        assert not any("hardcoded_secret" in f.id for f in findings)

    def test_detects_credential_in_connection_url(self):
        snap = _snapshot(("db.py", "DB_URL = 'postgres://admin:s3cr3tpassword@localhost/mydb'"))
        findings = self.scanner.scan(snap)
        assert any("credential_in_url" in f.id for f in findings)

    def test_skips_binary_files(self):
        snap = RepositorySnapshot(
            source=RepositorySource(kind="local", location="fixture"),
            root=Path("/tmp/unused"),
            files=[FileSnapshot(path="assets/key.bin", size_bytes=10, extension=".bin", is_binary=True)],
        )
        assert self.scanner.scan(snap) == []

    def test_skips_lock_files(self):
        snap = _snapshot(("package-lock.json", 'password = "realpassword123456789"'))
        findings = self.scanner.scan(snap)
        assert not findings  # .json would be scanned but .lock is skipped

    def test_finding_ids_are_stable_and_url_safe(self):
        snap = _snapshot(("src/app.py", 'secret_key = "AKIAIOSFODNN7EXAMPLEabc"'))
        first = self.scanner.scan(snap)
        second = self.scanner.scan(snap)
        assert [f.id for f in first] == [f.id for f in second]
        for f in first:
            assert f.id == f.id.lower()
            assert "/" not in f.id
            assert f.id.startswith("secret_scanner.")

    def test_redacts_secret_from_excerpt(self):
        snap = _snapshot(("src/cfg.py", 'password = "myrealpassword1234567"'))
        findings = self.scanner.scan(snap)
        secret_findings = [f for f in findings if "hardcoded_secret" in f.id]
        if secret_findings:
            excerpt = secret_findings[0].evidence[0].excerpt or ""
            assert "myrealpassword1234567" not in excerpt

    def test_evidence_includes_line_number(self):
        snap = _snapshot(("app.py", "x = 1\napi_key = 'sk-realkey123456789abc'\ny = 2"))
        findings = self.scanner.scan(snap)
        secret = [f for f in findings if "hardcoded_secret" in f.id]
        if secret:
            assert secret[0].evidence[0].location.line_start == 2


# ===========================================================================
# CodeComplianceScanner
# ===========================================================================

class TestCodeComplianceScanner:
    scanner = CodeComplianceScanner()

    def test_detects_token_in_localstorage(self):
        snap = _snapshot(("src/auth.js", "localStorage.setItem('token', userToken)"))
        findings = self.scanner.scan(snap)
        assert any("token_in_browser_storage" in f.id for f in findings)

    def test_detects_token_in_sessionstorage(self):
        snap = _snapshot(("src/login.ts", "sessionStorage.setItem('auth', jwt)"))
        findings = self.scanner.scan(snap)
        assert any("token_in_browser_storage" in f.id for f in findings)

    def test_detects_insecure_cookie(self):
        snap = _snapshot(("src/server.js", "res.cookie('session', value)"))
        findings = self.scanner.scan(snap)
        assert any("insecure_cookie" in f.id for f in findings)

    def test_secure_cookie_not_flagged(self):
        code = "res.cookie('session', value, { httpOnly: true, secure: true, sameSite: 'Lax' })"
        snap = _snapshot(("src/server.js", code))
        findings = self.scanner.scan(snap)
        assert not any("insecure_cookie" in f.id for f in findings)

    def test_detects_minor_flow_without_consent(self):
        snap = _snapshot(("src/signup.py", "for minor in user_list: create_account(minor)"))
        findings = self.scanner.scan(snap)
        assert any("minor_flow_no_consent" in f.id for f in findings)

    def test_minor_with_coppa_not_flagged(self):
        code = "# COPPA: parental consent required for under-13 users\nif is_minor: require_parent_consent()"
        snap = _snapshot(("src/signup.py", code))
        findings = self.scanner.scan(snap)
        assert not any("minor_flow_no_consent" in f.id for f in findings)

    def test_detects_health_data_without_controls(self):
        snap = _snapshot(("src/records.py", "diagnosis = patient.get_diagnosis()"))
        findings = self.scanner.scan(snap)
        assert any("health_data_no_controls" in f.id for f in findings)

    def test_health_data_with_controls_not_flagged(self):
        code = "# HIPAA: PHI encrypted at rest\ndiagnosis = encrypt(patient.get_diagnosis())"
        snap = _snapshot(("src/records.py", code))
        findings = self.scanner.scan(snap)
        assert not any("health_data_no_controls" in f.id for f in findings)

    def test_detects_tracking_sdk(self):
        snap = _snapshot(("src/analytics.js", "posthog.init('ph_key', { api_host: 'https://app.posthog.com' })"))
        findings = self.scanner.scan(snap)
        assert any("tracking_sdk" in f.id for f in findings)

    def test_detects_mixpanel(self):
        snap = _snapshot(("src/track.ts", "mixpanel.track('page_view', props)"))
        findings = self.scanner.scan(snap)
        assert any("tracking_sdk" in f.id for f in findings)

    def test_detects_personal_data_without_governance(self):
        snap = _snapshot(("src/user.py", "user.email = form.email"))
        findings = self.scanner.scan(snap)
        assert any("personal_data_no_controls" in f.id for f in findings)

    def test_personal_data_with_governance_not_flagged(self):
        code = "# consent obtained; encrypted; retention = 90 days\nuser.email = encrypt(form.email)"
        snap = _snapshot(("src/user.py", code))
        findings = self.scanner.scan(snap)
        assert not any("personal_data_no_controls" in f.id for f in findings)

    def test_skips_docs_files(self):
        snap = _snapshot(("docs/privacy.md", "localStorage.setItem('token', value)"))
        assert self.scanner.scan(snap) == []

    def test_skips_non_source_extensions(self):
        snap = _snapshot(("config.yaml", "sessionStorage.setItem('token', value)"))
        assert self.scanner.scan(snap) == []

    def test_finding_ids_stable_and_url_safe(self):
        snap = _snapshot(("src/a.js", "localStorage.setItem('session', jwt)"))
        first = self.scanner.scan(snap)
        second = self.scanner.scan(snap)
        assert [f.id for f in first] == [f.id for f in second]
        for f in first:
            assert f.id == f.id.lower()
            assert f.id.startswith("code_compliance.")

    def test_all_findings_have_scanner_id(self):
        snap = _snapshot(("src/app.py", "email = user.email\ncookies.set('s', val)"))
        findings = self.scanner.scan(snap)
        assert all(f.scanner_id == "code_compliance" for f in findings)


# ===========================================================================
# DependencyVulnScanner — network disabled
# ===========================================================================

class TestDependencyVulnScanner:
    def test_returns_empty_when_disabled(self):
        scanner = DependencyVulnScanner(enable_osv=False)
        snap = _snapshot(("requirements.txt", "requests==2.26.0\n"))
        assert scanner.scan(snap) == []

    def test_returns_empty_for_snapshot_with_no_manifests(self):
        scanner = DependencyVulnScanner(enable_osv=True)
        snap = _snapshot(("src/app.py", "print('hello')"))
        with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=[]):
            assert scanner.scan(snap) == []

    def test_produces_findings_for_osv_response(self):
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

    def test_skips_packages_without_pinned_version(self):
        scanner = DependencyVulnScanner(enable_osv=True)
        snap = _snapshot(("requirements.txt", "requests\n"))
        with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=[]) as mock_osv:
            scanner.scan(snap)
        mock_osv.assert_not_called()

    def test_finding_id_is_stable(self):
        scanner = DependencyVulnScanner(enable_osv=True)
        snap = _snapshot(("requirements.txt", "django==3.2.0\n"))
        fake = [{"vulns": [{"id": "CVE-2021-0001", "summary": "Test.", "database_specific": {"severity": "MEDIUM"}, "severity": []}]}]
        with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
            first = scanner.scan(snap)
        with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
            second = scanner.scan(snap)
        assert [f.id for f in first] == [f.id for f in second]

    def test_maps_critical_severity(self):
        scanner = DependencyVulnScanner(enable_osv=True)
        snap = _snapshot(("requirements.txt", "pillow==8.0.0\n"))
        fake = [{"vulns": [{"id": "GHSA-crit", "summary": "Critical.", "database_specific": {"severity": "CRITICAL"}, "severity": []}]}]
        with patch("startup_risk.scanners.dependency_vuln_scanner._query_osv", return_value=fake):
            findings = scanner.scan(snap)
        assert findings[0].severity == "critical"


# ===========================================================================
# OutdatedDepsScanner — network disabled
# ===========================================================================

class TestOutdatedDepsScanner:
    def test_returns_empty_when_disabled(self):
        scanner = OutdatedDepsScanner(enable_registry=False)
        snap = _snapshot(("requirements.txt", "requests==2.26.0\n"))
        assert scanner.scan(snap) == []

    def test_returns_empty_for_snapshot_with_no_manifests(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        snap = _snapshot(("src/app.py", "print('hello')"))
        assert scanner.scan(snap) == []

    def test_produces_finding_for_outdated_package(self):
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

    def test_no_finding_when_already_up_to_date(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        snap = _snapshot(("requirements.txt", "requests==2.31.0\n"))
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="2.31.0"):
            assert scanner.scan(snap) == []

    def test_no_finding_when_registry_unavailable(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        snap = _snapshot(("requirements.txt", "requests==2.1.0\n"))
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value=None):
            assert scanner.scan(snap) == []

    def test_skips_packages_without_pinned_version(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        snap = _snapshot(("requirements.txt", "requests\n"))
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest") as mock_fetch:
            scanner.scan(snap)
        mock_fetch.assert_not_called()

    def test_skips_unsupported_ecosystems(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        # go.mod is "go" ecosystem — not in _SUPPORTED_ECOSYSTEMS
        snap = _snapshot(("go.mod", "module example.com/myapp\n\nrequire golang.org/x/net v0.0.1\n"))
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest") as mock_fetch:
            scanner.scan(snap)
        mock_fetch.assert_not_called()

    def test_finding_id_is_stable(self):
        scanner = OutdatedDepsScanner(enable_registry=True)
        snap = _snapshot(("requirements.txt", "flask==1.0.0\n"))
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="3.0.0"):
            first = scanner.scan(snap)
        with patch("startup_risk.scanners.outdated_deps_scanner._fetch_latest", return_value="3.0.0"):
            second = scanner.scan(snap)
        assert [f.id for f in first] == [f.id for f in second]

    def test_respects_max_per_ecosystem_cap(self):
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
