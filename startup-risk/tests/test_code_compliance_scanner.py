from __future__ import annotations

from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.code_compliance_scanner import CodeComplianceScanner


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


scanner = CodeComplianceScanner()


def test_detects_token_in_localstorage():
    snap = _snapshot(("src/auth.js", "localStorage.setItem('token', userToken)"))
    findings = scanner.scan(snap)
    assert any("token_in_browser_storage" in f.id for f in findings)


def test_detects_token_in_sessionstorage():
    snap = _snapshot(("src/login.ts", "sessionStorage.setItem('auth', jwt)"))
    findings = scanner.scan(snap)
    assert any("token_in_browser_storage" in f.id for f in findings)


def test_detects_insecure_cookie():
    snap = _snapshot(("src/server.js", "res.cookie('session', value)"))
    findings = scanner.scan(snap)
    assert any("insecure_cookie" in f.id for f in findings)


def test_secure_cookie_not_flagged():
    code = "res.cookie('session', value, { httpOnly: true, secure: true, sameSite: 'Lax' })"
    snap = _snapshot(("src/server.js", code))
    findings = scanner.scan(snap)
    assert not any("insecure_cookie" in f.id for f in findings)


def test_detects_minor_flow_without_consent():
    snap = _snapshot(("src/signup.py", "for minor in user_list: create_account(minor)"))
    findings = scanner.scan(snap)
    assert any("minor_flow_no_consent" in f.id for f in findings)


def test_minor_with_coppa_not_flagged():
    code = "# COPPA: parental consent required for under-13 users\nif is_minor: require_parent_consent()"
    snap = _snapshot(("src/signup.py", code))
    findings = scanner.scan(snap)
    assert not any("minor_flow_no_consent" in f.id for f in findings)


def test_detects_health_data_without_controls():
    snap = _snapshot(("src/records.py", "diagnosis = patient.get_diagnosis()"))
    findings = scanner.scan(snap)
    assert any("health_data_no_controls" in f.id for f in findings)


def test_health_data_with_controls_not_flagged():
    code = "# HIPAA: PHI encrypted at rest\ndiagnosis = encrypt(patient.get_diagnosis())"
    snap = _snapshot(("src/records.py", code))
    findings = scanner.scan(snap)
    assert not any("health_data_no_controls" in f.id for f in findings)


def test_detects_tracking_sdk():
    snap = _snapshot(("src/analytics.js", "posthog.init('ph_key', { api_host: 'https://app.posthog.com' })"))
    findings = scanner.scan(snap)
    assert any("tracking_sdk" in f.id for f in findings)


def test_detects_mixpanel():
    snap = _snapshot(("src/track.ts", "mixpanel.track('page_view', props)"))
    findings = scanner.scan(snap)
    assert any("tracking_sdk" in f.id for f in findings)


def test_detects_personal_data_without_governance():
    snap = _snapshot(("src/user.py", "user.email = form.email"))
    findings = scanner.scan(snap)
    assert any("personal_data_no_controls" in f.id for f in findings)


def test_personal_data_with_governance_not_flagged():
    code = "# consent obtained; encrypted; retention = 90 days\nuser.email = encrypt(form.email)"
    snap = _snapshot(("src/user.py", code))
    findings = scanner.scan(snap)
    assert not any("personal_data_no_controls" in f.id for f in findings)


def test_skips_docs_files():
    snap = _snapshot(("docs/privacy.md", "localStorage.setItem('token', value)"))
    assert scanner.scan(snap) == []


def test_skips_non_source_extensions():
    snap = _snapshot(("config.yaml", "sessionStorage.setItem('token', value)"))
    assert scanner.scan(snap) == []


def test_finding_ids_stable_and_url_safe():
    snap = _snapshot(("src/a.js", "localStorage.setItem('session', jwt)"))
    first = scanner.scan(snap)
    second = scanner.scan(snap)
    assert [f.id for f in first] == [f.id for f in second]
    for f in first:
        assert f.id == f.id.lower()
        assert f.id.startswith("code_compliance.")


def test_all_findings_have_correct_scanner_id():
    snap = _snapshot(("src/app.py", "email = user.email\ncookies.set('s', val)"))
    findings = scanner.scan(snap)
    assert all(f.scanner_id == "code_compliance" for f in findings)
