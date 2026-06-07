from __future__ import annotations

from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.secret_scanner import SecretScanner


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


scanner = SecretScanner()


def test_detects_pem_private_key():
    snap = _snapshot(("config/deploy.pem", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."))
    findings = scanner.scan(snap)
    assert any("pem_private_key" in f.id for f in findings)
    assert all(f.scanner_id == "secret_scanner" for f in findings)


def test_pem_key_is_critical_in_src_file():
    snap = _snapshot(("src/certs.py", "key = '-----BEGIN PRIVATE KEY-----'"))
    findings = scanner.scan(snap)
    assert any(f.severity == "critical" for f in findings)


def test_pem_key_is_high_in_test_file():
    snap = _snapshot(("tests/fixtures/test_cert.py", "# -----BEGIN PRIVATE KEY-----"))
    findings = scanner.scan(snap)
    assert any(f.severity == "high" and "pem_private_key" in f.id for f in findings)


def test_detects_aws_access_key():
    snap = _snapshot(("app.py", "key = 'AKIAIOSFODNN7EXAMPLE'"))
    findings = scanner.scan(snap)
    assert any("aws_access_key" in f.id for f in findings)


def test_detects_hardcoded_secret_assignment():
    snap = _snapshot(("config.py", 'api_key = "sk-Z9mQvR3kXpLwY7nBdT2sUe"'))
    findings = scanner.scan(snap)
    assert any("hardcoded_secret" in f.id for f in findings)


def test_ignores_placeholder_values():
    snap = _snapshot(("config.py", 'api_key = "your_api_key_here_replace_me"'))
    findings = scanner.scan(snap)
    assert not any("hardcoded_secret" in f.id for f in findings)


def test_ignores_template_syntax():
    snap = _snapshot(("config.py", 'api_key = "${API_KEY_FROM_ENV}"'))
    findings = scanner.scan(snap)
    assert not any("hardcoded_secret" in f.id for f in findings)


def test_detects_credential_in_connection_url():
    snap = _snapshot(("db.py", "DB_URL = 'postgres://admin:s3cr3tpassword@localhost/mydb'"))
    findings = scanner.scan(snap)
    assert any("credential_in_url" in f.id for f in findings)


def test_skips_binary_files():
    snap = RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[FileSnapshot(path="assets/key.bin", size_bytes=10, extension=".bin", is_binary=True)],
    )
    assert scanner.scan(snap) == []


def test_skips_lock_file_extension():
    snap = _snapshot(("yarn.lock", 'password = "realpassword123456789"'))
    assert scanner.scan(snap) == []


def test_finding_ids_are_stable_and_url_safe():
    snap = _snapshot(("src/app.py", 'secret_key = "AKIAIOSFODNN7EXAMPLEabc"'))
    first = scanner.scan(snap)
    second = scanner.scan(snap)
    assert [f.id for f in first] == [f.id for f in second]
    for f in first:
        assert f.id == f.id.lower()
        assert "/" not in f.id
        assert f.id.startswith("secret_scanner.")


def test_redacts_secret_from_excerpt():
    snap = _snapshot(("src/cfg.py", 'password = "myrealpassword1234567"'))
    findings = scanner.scan(snap)
    secret_findings = [f for f in findings if "hardcoded_secret" in f.id]
    if secret_findings:
        excerpt = secret_findings[0].evidence[0].excerpt or ""
        assert "myrealpassword1234567" not in excerpt


def test_evidence_includes_line_number():
    snap = _snapshot(("app.py", "x = 1\napi_key = 'sk-realkey123456789abc'\ny = 2"))
    findings = scanner.scan(snap)
    secret = [f for f in findings if "hardcoded_secret" in f.id]
    if secret:
        assert secret[0].evidence[0].location.line_start == 2
