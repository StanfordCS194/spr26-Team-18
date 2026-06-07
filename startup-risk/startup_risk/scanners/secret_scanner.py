from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    Severity,
    SourceLocation,
)


_SKIP_EXTENSIONS = frozenset({
    ".lock", ".sum", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz",
    ".bin", ".exe", ".dll", ".so", ".dylib", ".map",
})

_MAX_LINE_LEN = 500

# PEM private key header — very low false-positive rate.
_PEM_HEADER = re.compile(
    r"-----BEGIN\s+(?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    re.IGNORECASE,
)

# AWS access key ID — distinctive 20-char prefix+body.
_AWS_KEY = re.compile(r"\b(AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[0-9A-Z]{16}\b")

# Generic secret assignment: keyword = "long-value"
_SECRET_ASSIGN = re.compile(
    r"""(?i)(?:api[_-]?(?:key|secret)|secret[_-]?key|access[_-]?token|auth[_-]?token"""
    r"""|private[_-]?key|db[_-]?pass(?:word)?|database[_-]?pass(?:word)?"""
    r"""|client[_-]?secret|password|passwd)\s*[:=]\s*["']([A-Za-z0-9+/=!@#$%^&*()\-_.]{16,})["']""",
)

# Credential embedded in a service URL.
_CONN_STRING = re.compile(
    r"""(?i)(?:mongodb(?:\+srv)?|mysql|postgres(?:ql)?|redis|amqp|smtp)"""
    r"""://[^:\s@/]{1,100}:([^@\s"']{8,})@""",
)

# Values that look like placeholders — suppress false positives.
_PLACEHOLDER = re.compile(
    r"""(?i)(?:example|placeholder|test|dummy|change.?me|your[-_]|replace"""
    r"""|\$\{[^}]+\}|<[a-z_]{2,}>|xxx{3,}|\*{4,}|\?{4,}|todo|fixme|abc123|foobar|12345678)""",
)


def _severity_adjust(base: Severity, path_role: str) -> Severity:
    """Lower severity one step for test / example / docs files."""
    if path_role in {"tests", "examples", "docs"}:
        return {"critical": "high", "high": "medium"}.get(base, base)  # type: ignore[return-value]
    return base


def _redact(text: str, secret: str) -> str:
    redacted = text.replace(secret, "[REDACTED]", 1)
    return redacted[:200] + "..." if len(redacted) > 200 else redacted


class SecretScanner:
    """Detects secrets and credentials committed to the repository source tree."""

    id = "secret_scanner"
    name = "Secret Scanner"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.extension in _SKIP_EXTENSIONS:
                continue
            findings.extend(self._scan_file(file))
        return findings

    def _scan_file(self, file) -> list[Finding]:
        findings: list[Finding] = []
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            if len(line) > _MAX_LINE_LEN:
                continue

            if _PEM_HEADER.search(line):
                findings.append(self._finding(
                    rule="pem_private_key",
                    title="Private key committed to repository",
                    description=(
                        "A PEM private key header was found in the source tree. "
                        "Private keys committed to version control are permanently "
                        "exposed even after deletion from HEAD."
                    ),
                    severity=_severity_adjust("critical", file.path_role),
                    recommendation=(
                        "Remove the key from version control history (git filter-repo), "
                        "rotate it immediately, and load it from a secrets manager or "
                        "environment variable."
                    ),
                    file_path=file.path,
                    path_role=file.path_role,
                    lineno=lineno,
                    excerpt=line.strip()[:200],
                ))
                continue

            m = _AWS_KEY.search(line)
            if m:
                findings.append(self._finding(
                    rule="aws_access_key",
                    title="AWS access key ID detected",
                    description=(
                        "A string matching the AWS access key ID format was found. "
                        "If this is a live credential, it should be rotated immediately "
                        "and the associated IAM user audited for unauthorized activity."
                    ),
                    severity=_severity_adjust("critical", file.path_role),
                    recommendation=(
                        "Rotate the AWS key via IAM, remove it from source control "
                        "history, and use IAM roles or environment variables instead."
                    ),
                    file_path=file.path,
                    path_role=file.path_role,
                    lineno=lineno,
                    excerpt=_redact(line.strip()[:200], m.group(0)),
                ))
                continue

            m = _SECRET_ASSIGN.search(line)
            if m:
                value = m.group(1)
                if not _PLACEHOLDER.search(value):
                    findings.append(self._finding(
                        rule="hardcoded_secret",
                        title="Possible hardcoded secret in source file",
                        description=(
                            "A source file contains what appears to be a secret or "
                            "credential assigned as a string literal."
                        ),
                        severity=_severity_adjust("high", file.path_role),
                        recommendation=(
                            "Remove the value from source control, rotate it, and load "
                            "it from a secrets manager or environment variable."
                        ),
                        file_path=file.path,
                        path_role=file.path_role,
                        lineno=lineno,
                        excerpt=_redact(line.strip()[:200], value),
                    ))
                    continue

            m = _CONN_STRING.search(line)
            if m:
                password = m.group(1)
                if not _PLACEHOLDER.search(password):
                    findings.append(self._finding(
                        rule="credential_in_url",
                        title="Credentials embedded in connection URL",
                        description=(
                            "A database or service connection URL contains an embedded "
                            "password in the source tree."
                        ),
                        severity=_severity_adjust("high", file.path_role),
                        recommendation=(
                            "Move the connection string to an environment variable or "
                            "secrets manager and remove the credential from source control."
                        ),
                        file_path=file.path,
                        path_role=file.path_role,
                        lineno=lineno,
                        excerpt=_redact(line.strip()[:200], password),
                    ))

        return findings

    def _finding(
        self,
        *,
        rule: str,
        title: str,
        description: str,
        severity: Severity,
        recommendation: str,
        file_path: str,
        path_role: str,
        lineno: int,
        excerpt: str,
    ) -> Finding:
        return Finding(
            id=stable_finding_id(self.id, rule, f"{file_path}:{lineno}"),
            title=title,
            description=description,
            category="secret_exposure",
            severity=severity,
            confidence="medium",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=file_path, line_start=lineno),
                    description=f"Matched {rule} pattern in {path_role} file.",
                    excerpt=excerpt,
                )
            ],
            recommendation=recommendation,
            scanner_id=self.id,
            scanner_version=self.version,
        )
