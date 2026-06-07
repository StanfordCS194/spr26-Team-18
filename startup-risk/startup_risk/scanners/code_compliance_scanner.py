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


_SOURCE_EXTENSIONS = frozenset({
    ".js", ".jsx", ".ts", ".tsx",
    ".py", ".go", ".rb", ".java", ".kt", ".cs",
    ".swift", ".php", ".c", ".cpp", ".rs", ".scala",
})

_SKIP_PATH_ROLES = frozenset({"docs"})
_MAX_LINE_LEN = 500
_CONTEXT_RADIUS = 4  # lines above/below to check for nearby controls


# Rule 1 — auth token in browser storage (JS/TS only but harmless elsewhere)
_TOKEN_STORAGE = re.compile(
    r"""(?:localStorage|sessionStorage)\.setItem\s*\(\s*["'][^"']*["']\s*,"""
    r"""[^)]*(?:token|jwt|auth|session)""",
    re.IGNORECASE,
)

# Rule 2 — cookie set without security flags
_COOKIE_SET = re.compile(
    r"""(?:document\.cookie\s*=|setCookie\s*\(|res\.cookie\s*\("""
    r"""|response\.set_cookie\s*\(|cookies\.set\s*\()""",
    re.IGNORECASE,
)
_COOKIE_SECURE = re.compile(r"(?:httponly|secure|samesite)", re.IGNORECASE)

# Rule 3 — child/minor flow without consent
_MINOR_SIGNAL = re.compile(
    r"\b(?:child(?:ren)?|minor|under.?13|coppa)\b", re.IGNORECASE
)
_MINOR_CONTROLS = re.compile(
    r"\b(?:coppa|parental|guardian|consent|age.?gate|age.?verif)\b", re.IGNORECASE
)

# Rule 4 — health/clinical data without PHI controls
_HEALTH_DATA = re.compile(
    r"\b(?:patient|diagnosis|medication|therapy|clinical|health[_-]?data|symptom|phi|ehr|hl7|fhir)\b",
    re.IGNORECASE,
)
_HEALTH_CONTROLS = re.compile(
    r"\b(?:encrypt|audit|hipaa|phi|baa|retention|access.?control|de.?identif)\b",
    re.IGNORECASE,
)

# Rule 5 — third-party tracking/analytics SDK
_TRACKING_SDK = re.compile(
    r"""(?:posthog|mixpanel|amplitude|segment\.(?:io|analytics|load)|gtag\s*\("""
    r"""|google-analytics|fbq\s*\(|facebook.?pixel|heap\.io|fullstory|hotjar|clarity\.ms)""",
    re.IGNORECASE,
)

# Rule 6 — personal data field without data-governance handling
_PERSONAL_DATA = re.compile(
    r"""\b(?:email|phone(?:_number)?|address|birthdate|date_of_birth|dob"""
    r"""|ssn|social_security|geolocation|location_data|ip_address)\b""",
    re.IGNORECASE,
)
_DATA_GOVERNANCE = re.compile(
    r"""\b(?:delet|retention|minimiz|consent|privacy|encrypt|anonymize|pseudonymize)\b""",
    re.IGNORECASE,
)


def _context(lines: list[str], index: int) -> str:
    lo = max(0, index - _CONTEXT_RADIUS)
    hi = min(len(lines), index + _CONTEXT_RADIUS + 1)
    return " ".join(lines[lo:hi])


class CodeComplianceScanner:
    """Detects privacy and security compliance risks in source code."""

    id = "code_compliance"
    name = "Code Compliance"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[str] = set()
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.path_role in _SKIP_PATH_ROLES:
                continue
            if file.extension not in _SOURCE_EXTENSIONS:
                continue
            for finding in self._scan_file(file):
                if finding.id not in seen:
                    seen.add(finding.id)
                    findings.append(finding)
        return findings

    def _scan_file(self, file) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()

        for i, line in enumerate(lines):
            if len(line) > _MAX_LINE_LEN:
                continue
            stripped = line.strip()
            if not stripped:
                continue

            ctx = _context(lines, i)
            lineno = i + 1

            if _TOKEN_STORAGE.search(stripped):
                findings.append(self._finding(
                    rule="token_in_browser_storage",
                    title="Auth token stored in browser storage",
                    description=(
                        "An auth token is being written to localStorage or "
                        "sessionStorage, which is readable by any JavaScript on the "
                        "page — including injected scripts (XSS attack vector)."
                    ),
                    severity="high",
                    recommendation=(
                        "Store auth tokens in HttpOnly, Secure, SameSite=Lax cookies "
                        "or a server-side session. Never store bearer tokens in "
                        "web storage."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            elif _COOKIE_SET.search(stripped) and not _COOKIE_SECURE.search(ctx):
                findings.append(self._finding(
                    rule="insecure_cookie",
                    title="Cookie set without evident security flags",
                    description=(
                        "A cookie is being set without HttpOnly, Secure, and SameSite "
                        "flags visible in the surrounding code. Missing flags expose "
                        "session tokens to XSS and CSRF attacks."
                    ),
                    severity="high",
                    recommendation=(
                        "Set HttpOnly, Secure, and SameSite=Lax (or Strict) on all "
                        "session and auth cookies."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            elif _MINOR_SIGNAL.search(stripped) and not _MINOR_CONTROLS.search(ctx):
                findings.append(self._finding(
                    rule="minor_flow_no_consent",
                    title="Minor-user code path without visible consent handling",
                    description=(
                        "Code references children or under-13 users without a nearby "
                        "consent gate, age-verification check, or COPPA acknowledgment. "
                        "COPPA violations start at $51,744 per violation."
                    ),
                    severity="high",
                    recommendation=(
                        "Add an age-aware onboarding branch and parental/guardian "
                        "consent handling before collecting any data from users under 13."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            elif _HEALTH_DATA.search(stripped) and not _HEALTH_CONTROLS.search(ctx):
                findings.append(self._finding(
                    rule="health_data_no_controls",
                    title="Health or clinical data without visible PHI safeguards",
                    description=(
                        "Code handles patient or clinical terminology without nearby "
                        "encryption, audit logging, access control, or HIPAA controls."
                    ),
                    severity="high",
                    recommendation=(
                        "Add explicit PHI safeguards around this code path: access "
                        "control, audit logging, encryption at rest and in transit, "
                        "retention policy, and BAA assumptions."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            elif _TRACKING_SDK.search(stripped):
                findings.append(self._finding(
                    rule="tracking_sdk",
                    title="Third-party tracking or analytics SDK detected",
                    description=(
                        "An analytics or tracking SDK is initialized in source code. "
                        "Data sharing with third parties must be disclosed and may "
                        "require user consent under GDPR, CCPA, and similar laws."
                    ),
                    severity="medium",
                    recommendation=(
                        "Gate analytics initialization behind a consent check. Disable "
                        "targeted advertising for minors. Document data sharing in your "
                        "Privacy Policy."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            elif _PERSONAL_DATA.search(stripped) and not _DATA_GOVERNANCE.search(ctx):
                findings.append(self._finding(
                    rule="personal_data_no_controls",
                    title="Personal data field without data-governance handling",
                    description=(
                        "A PII field is referenced without nearby deletion, retention, "
                        "consent, or encryption logic in the surrounding code."
                    ),
                    severity="medium",
                    recommendation=(
                        "Add a retention/deletion path and privacy rationale for this "
                        "data field, or document why it is exempt from standard "
                        "governance controls."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
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
        file,
        lineno: int,
        excerpt: str,
    ) -> Finding:
        return Finding(
            id=stable_finding_id(self.id, rule, f"{file.path}:{lineno}"),
            title=title,
            description=description,
            category="code_compliance",
            severity=severity,
            confidence="medium",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=lineno),
                    description=f"Matched {rule} pattern.",
                    excerpt=excerpt,
                )
            ],
            recommendation=recommendation,
            scanner_id=self.id,
            scanner_version=self.version,
        )
