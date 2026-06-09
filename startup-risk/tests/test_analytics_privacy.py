from __future__ import annotations

from pathlib import Path

import pytest

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.analytics_privacy import AnalyticsPrivacyScanner


def snapshot_with_content(files: list[tuple[str, str]]) -> RepositorySnapshot:
    return RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path=path,
                size_bytes=len(content),
                extension=Path(path).suffix.lower(),
                text=content,
            )
            for path, content in files
        ],
    )


# ── PII in log calls ────────────────────────────────────────────────────────

def test_password_in_log_call_flagged_as_high_severity():
    snapshot = snapshot_with_content([
        ("src/auth.py", 'logger.info(f"Login attempt: {user.password}")\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    pii = [f for f in findings if f.id.startswith("analytics_privacy.pii_in_log_call")]
    assert len(pii) == 1
    assert pii[0].severity == "high"
    assert "password" in pii[0].title.lower()
    assert pii[0].evidence[0].location is not None
    assert pii[0].evidence[0].location.path == "src/auth.py"


def test_ssn_in_log_call_flagged_as_high_severity():
    snapshot = snapshot_with_content([
        ("app/handler.js", 'console.log("SSN:", user.ssn);\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    pii = [f for f in findings if f.id.startswith("analytics_privacy.pii_in_log_call")]
    assert len(pii) == 1
    assert pii[0].severity == "high"


def test_ip_address_in_log_call_flagged_as_medium_severity():
    snapshot = snapshot_with_content([
        ("src/middleware.ts", 'logger.debug("Request from", req.ip_address);\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    pii = [f for f in findings if f.id.startswith("analytics_privacy.pii_in_log_call")]
    assert len(pii) == 1
    assert pii[0].severity == "medium"


def test_pii_without_log_call_not_flagged():
    snapshot = snapshot_with_content([
        ("src/model.py", "user_password = get_password(user)\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    pii = [f for f in findings if f.id.startswith("analytics_privacy.pii_in_log_call")]
    assert len(pii) == 0


def test_pii_in_test_file_is_lower_severity():
    snapshot = snapshot_with_content([
        ("tests/test_auth.py", 'print(f"Testing with password={test_user.password}")\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    pii = [f for f in findings if f.id.startswith("analytics_privacy.pii_in_log_call")]
    assert len(pii) == 1
    assert pii[0].severity == "medium"  # lowered from high for test files


def test_pii_finding_ids_are_stable_across_runs():
    snapshot = snapshot_with_content([
        ("src/auth.py", 'logger.info(user.password)\n'),
    ])
    first = AnalyticsPrivacyScanner().scan(snapshot)
    second = AnalyticsPrivacyScanner().scan(snapshot)
    assert [f.id for f in first] == [f.id for f in second]


# ── request body logging ─────────────────────────────────────────────────────

def test_request_body_logging_flagged():
    snapshot = snapshot_with_content([
        ("src/server.js", 'console.log("Incoming:", req.body);\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    body = [f for f in findings if f.id.startswith("analytics_privacy.request_body_logged")]
    assert len(body) == 1
    assert body[0].severity == "high"
    assert body[0].evidence[0].excerpt is not None


def test_request_body_reference_without_log_call_not_flagged():
    snapshot = snapshot_with_content([
        ("src/server.js", "const data = req.body;\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    body = [f for f in findings if f.id.startswith("analytics_privacy.request_body_logged")]
    assert len(body) == 0


def test_request_data_python_style_flagged():
    snapshot = snapshot_with_content([
        ("app/views.py", 'logging.info("Payload: %s", request.data)\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    body = [f for f in findings if f.id.startswith("analytics_privacy.request_body_logged")]
    assert len(body) == 1


# ── unencrypted analytics endpoints ──────────────────────────────────────────

def test_http_mixpanel_endpoint_flagged():
    snapshot = snapshot_with_content([
        ("src/analytics.js", 'const endpoint = "http://api.mixpanel.com/track";\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    enc = [f for f in findings if f.id.startswith("analytics_privacy.unencrypted_analytics_endpoint")]
    assert len(enc) == 1
    assert enc[0].severity == "medium"
    assert enc[0].confidence == "high"


def test_https_analytics_endpoint_not_flagged():
    snapshot = snapshot_with_content([
        ("src/analytics.js", 'const endpoint = "https://api.mixpanel.com/track";\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    enc = [f for f in findings if f.id.startswith("analytics_privacy.unencrypted_analytics_endpoint")]
    assert len(enc) == 0


def test_http_non_analytics_endpoint_not_flagged():
    snapshot = snapshot_with_content([
        ("src/api.ts", 'const base = "http://api.example.com/data";\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    enc = [f for f in findings if f.id.startswith("analytics_privacy.unencrypted_analytics_endpoint")]
    assert len(enc) == 0


# ── CloudWatch log retention ──────────────────────────────────────────────────

def test_cloudwatch_zero_retention_flagged():
    snapshot = snapshot_with_content([
        ("infra/logging.yaml", "retentionInDays: 0\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ret = [f for f in findings if f.id.startswith("analytics_privacy.cloudwatch_no_log_retention")]
    assert len(ret) == 1
    assert ret[0].severity == "medium"
    assert ret[0].confidence == "high"


def test_cloudwatch_nonzero_retention_not_flagged():
    snapshot = snapshot_with_content([
        ("infra/logging.yaml", "retentionInDays: 90\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ret = [f for f in findings if f.id.startswith("analytics_privacy.cloudwatch_no_log_retention")]
    assert len(ret) == 0


def test_cloudwatch_retention_in_json_flagged():
    snapshot = snapshot_with_content([
        ("cdk/stack.json", '{"retentionInDays": 0}\n'),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ret = [f for f in findings if f.id.startswith("analytics_privacy.cloudwatch_no_log_retention")]
    assert len(ret) == 1


# ── Winston log rotation ──────────────────────────────────────────────────────

def test_winston_file_transport_without_rotation_flagged():
    snapshot = snapshot_with_content([
        (
            "src/logger.js",
            "const logger = winston.createLogger({\n"
            "  transports: [new winston.transports.File({ filename: 'app.log' })]\n"
            "});\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    rot = [f for f in findings if f.id.startswith("analytics_privacy.winston_no_log_rotation")]
    assert len(rot) == 1
    assert rot[0].severity == "low"


def test_winston_file_transport_with_maxfiles_not_flagged():
    snapshot = snapshot_with_content([
        (
            "src/logger.js",
            "const logger = winston.createLogger({\n"
            "  transports: [new winston.transports.File({ filename: 'app.log', maxFiles: 14 })]\n"
            "});\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    rot = [f for f in findings if f.id.startswith("analytics_privacy.winston_no_log_rotation")]
    assert len(rot) == 0


def test_winston_no_file_transport_not_flagged():
    snapshot = snapshot_with_content([
        ("src/logger.js", "const logger = winston.createLogger({ transports: [] });\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    rot = [f for f in findings if f.id.startswith("analytics_privacy.winston_no_log_rotation")]
    assert len(rot) == 0


# ── analytics without consent ─────────────────────────────────────────────────

def test_analytics_import_without_consent_flagged():
    snapshot = snapshot_with_content([
        ("src/analytics.ts", "import mixpanel from 'mixpanel';\nmixpanel.init('token');\n"),
        ("src/app.ts", "import { render } from 'react-dom';\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    consent = [f for f in findings if f.id.startswith("analytics_privacy.analytics_without_consent")]
    assert len(consent) == 1
    assert consent[0].severity == "medium"
    assert consent[0].confidence == "low"


def test_analytics_import_with_consent_term_in_repo_not_flagged():
    snapshot = snapshot_with_content([
        ("src/analytics.ts", "import mixpanel from 'mixpanel';\nmixpanel.init('token');\n"),
        ("src/consent.ts", "export function showGdprConsent() { /* opt-out logic */ }\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    consent = [f for f in findings if f.id.startswith("analytics_privacy.analytics_without_consent")]
    assert len(consent) == 0


def test_no_analytics_import_no_consent_finding():
    snapshot = snapshot_with_content([
        ("src/app.py", "import flask\napp = flask.Flask(__name__)\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    consent = [f for f in findings if f.id.startswith("analytics_privacy.analytics_without_consent")]
    assert len(consent) == 0


def test_analytics_without_consent_evidence_capped_at_five():
    files = [
        (f"src/module{i}.ts", f"import mixpanel from 'mixpanel'; // module {i}\n")
        for i in range(8)
    ]
    snapshot = snapshot_with_content(files)
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    consent = [f for f in findings if f.id.startswith("analytics_privacy.analytics_without_consent")]
    assert len(consent) == 1
    assert len(consent[0].evidence) <= 5


# ── database log table TTL ────────────────────────────────────────────────────

def test_sql_log_table_without_ttl_flagged():
    snapshot = snapshot_with_content([
        (
            "db/schema.sql",
            "CREATE TABLE user_events (\n"
            "  id BIGINT PRIMARY KEY,\n"
            "  user_id BIGINT,\n"
            "  created_at TIMESTAMP\n"
            ");\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ttl = [f for f in findings if f.id.startswith("analytics_privacy.log_table_no_ttl")]
    assert len(ttl) == 1
    assert "user_events" in ttl[0].title
    assert ttl[0].severity == "medium"
    assert ttl[0].confidence == "low"


def test_sql_log_table_with_retention_hint_not_flagged():
    snapshot = snapshot_with_content([
        (
            "db/schema.sql",
            "-- retention: 90 days, cleanup job runs nightly\n"
            "CREATE TABLE audit_log (\n"
            "  id BIGINT PRIMARY KEY,\n"
            "  created_at TIMESTAMP\n"
            ");\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ttl = [f for f in findings if f.id.startswith("analytics_privacy.log_table_no_ttl")]
    assert len(ttl) == 0


def test_sql_regular_table_not_flagged():
    snapshot = snapshot_with_content([
        (
            "db/schema.sql",
            "CREATE TABLE users (\n"
            "  id BIGINT PRIMARY KEY,\n"
            "  email TEXT\n"
            ");\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ttl = [f for f in findings if f.id.startswith("analytics_privacy.log_table_no_ttl")]
    assert len(ttl) == 0


def test_prisma_log_model_without_ttl_flagged():
    snapshot = snapshot_with_content([
        (
            "prisma/schema.prisma",
            "model UserEvent {\n"
            "  id        Int      @id\n"
            "  userId    Int\n"
            "  createdAt DateTime @default(now())\n"
            "}\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ttl = [f for f in findings if f.id.startswith("analytics_privacy.log_table_no_ttl")]
    assert len(ttl) == 1
    assert "UserEvent" in ttl[0].title


def test_prisma_log_model_with_expiry_field_not_flagged():
    snapshot = snapshot_with_content([
        (
            "prisma/schema.prisma",
            "model AuditLog {\n"
            "  id        Int      @id\n"
            "  expiresAt DateTime\n"
            "}\n",
        )
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    ttl = [f for f in findings if f.id.startswith("analytics_privacy.log_table_no_ttl")]
    assert len(ttl) == 0


# ── scanner metadata ──────────────────────────────────────────────────────────

def test_scanner_metadata():
    scanner = AnalyticsPrivacyScanner()
    assert scanner.id == "analytics_privacy"
    assert scanner.name == "Analytics & Logging Privacy"
    assert scanner.version == "1.0.0"


def test_all_findings_reference_correct_scanner_id():
    snapshot = snapshot_with_content([
        ("src/auth.py", 'logger.info(f"user password={u.password}")\n'),
        ("src/logger.js", "new winston.transports.File({ filename: 'app.log' })\n"),
    ])
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    assert all(f.scanner_id == "analytics_privacy" for f in findings)
    assert all(f.id.startswith("analytics_privacy.") for f in findings)


def test_binary_and_skipped_files_ignored():
    snapshot = RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path="assets/image.png",
                size_bytes=1024,
                extension=".png",
                is_binary=True,
            ),
            FileSnapshot(
                path="data/large.py",
                size_bytes=500_000,
                extension=".py",
                skipped_reason="file exceeds max_file_bytes",
            ),
        ],
    )
    findings = AnalyticsPrivacyScanner().scan(snapshot)
    assert findings == []
