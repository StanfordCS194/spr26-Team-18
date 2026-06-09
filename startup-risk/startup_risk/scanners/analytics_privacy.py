from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)


SOURCE_EXTENSIONS = frozenset(
    {".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".java", ".go", ".cs", ".php", ".kt", ".rs"}
)
CONFIG_EXTENSIONS = frozenset({".yml", ".yaml", ".json", ".toml"})
SCHEMA_EXTENSIONS = frozenset({".sql", ".prisma"})

# Analytics/telemetry SDK import patterns → display name
_ANALYTICS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""(?:import|require|from)\s+['"]mixpanel"""), "Mixpanel"),
    (re.compile(r"""(?:import|require|from)\s+['"]@?amplitude"""), "Amplitude"),
    (re.compile(r"""(?:import|require|from)\s+['"](?:@segment/|analytics-node)"""), "Segment"),
    (re.compile(r"""(?:import|require|from)\s+['"]posthog"""), "PostHog"),
    (re.compile(r"""(?:import|require|from)\s+['"]heap"""), "Heap Analytics"),
    (re.compile(r"""(?:import|require|from)\s+['"]@fullstory/"""), "FullStory"),
    (re.compile(r"""(?:import|require|from)\s+['"]logrocket"""), "LogRocket"),
    (re.compile(r"""(?:import|require|from)\s+['"]@datadog/browser-logs"""), "Datadog Browser Logs"),
    (re.compile(r"^(?:import|from)\s+mixpanel\b", re.MULTILINE), "Mixpanel"),
    (re.compile(r"^(?:import|from)\s+amplitude\b", re.MULTILINE), "Amplitude"),
    (re.compile(r"^(?:import|from)\s+posthog\b", re.MULTILINE), "PostHog"),
    (re.compile(r"^(?:import|from)\s+segment\b", re.MULTILINE), "Segment"),
]

_CONSENT_PATTERN = re.compile(
    r"\b(?:consent|opt.?out|gdpr|ccpa|cookie.?polic|privacy.?notice|do.?not.?track|anonymi[sz]e)\b",
    re.IGNORECASE,
)

# Log call keywords across major languages
_LOG_CALL_PATTERN = re.compile(
    r"(?:"
    r"console\.(?:log|warn|error|info|debug)"
    r"|(?:logger?|log|logging)\.(?:debug|info|warn(?:ing)?|error|critical|fatal|trace|print)"
    r"|fmt\.Print(?:f|ln)?"
    r"|log\.Print(?:f|ln)?"
    r"|System\.out\.print(?:ln)?"
    r"|\bputs\b"
    r"|\bprint\b"
    r")",
    re.IGNORECASE,
)

# PII field name patterns split by severity
_HIGH_PII_PATTERN = re.compile(
    r"\b(?:password|passwd|pwd|ssn|social.?security|credit.?card|card.?number|cvv|cvc)\b",
    re.IGNORECASE,
)
_MEDIUM_PII_PATTERN = re.compile(
    r"\b(?:date.?of.?birth|dob|birthdate|ip.?address|tax.?id|national.?id|passport)\b",
    re.IGNORECASE,
)

_REQUEST_BODY_PATTERN = re.compile(
    r"(?:req|request|ctx|c|r|event)(?:\.|->)(?:body|data|form|json|payload)",
    re.IGNORECASE,
)

_HTTP_ANALYTICS_PATTERN = re.compile(
    r"http://[^\s'\"`]*(?:mixpanel\.com|amplitude\.com|segment\.io|"
    r"heap\.io|fullstory\.com|hotjar\.com|logrocket\.com|"
    r"datadoghq\.com|newrelic\.com)",
    re.IGNORECASE,
)

# retentionInDays: 0 means logs never expire (CloudWatch / CDK YAML and JSON patterns)
_CLOUDWATCH_ZERO_RETENTION = re.compile(r'"?retentionInDays"?\s*[:=]\s*0\b', re.IGNORECASE)

_WINSTON_FILE_TRANSPORT = re.compile(r"winston\.transports\.File", re.IGNORECASE)
_WINSTON_ROTATION = re.compile(r"\b(?:maxFiles|maxDays|maxsize)\b", re.IGNORECASE)

_SQL_LOG_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w*(?:log|event|audit|telemetry|metric|analytic)\w*)[`\"\]]?",
    re.IGNORECASE,
)
_SQL_TTL_HINTS = re.compile(
    r"\b(?:TTL|PARTITION\s+BY\s+RANGE|EXPIRES?\s+IN|cleanup|retention|scheduled_delete)\b",
    re.IGNORECASE,
)

_PRISMA_LOG_MODEL = re.compile(
    r"^model\s+(\w*(?:Log|Event|Audit|Telemetry|Metric|Analytic)\w*)\s*\{",
    re.MULTILINE,
)
_PRISMA_TTL_HINTS = re.compile(
    r"@@index.*expir|deletedAt|expiresAt|retentionDate",
    re.IGNORECASE,
)


class AnalyticsPrivacyScanner:
    """Static checks for analytics and logging privacy law compliance signals."""

    id = "analytics_privacy"
    name = "Analytics & Logging Privacy"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []

        analytics_usage = self._collect_analytics_usage(snapshot)
        if analytics_usage and not self._repo_has_consent(snapshot):
            findings.append(self._analytics_without_consent_finding(analytics_usage))

        for file in snapshot.files:
            if file.text is None:
                continue

            if file.extension in SOURCE_EXTENSIONS:
                findings.extend(self._check_pii_in_log_calls(file))
                findings.extend(self._check_request_body_logging(file))
                findings.extend(self._check_unencrypted_endpoints(file))
                findings.extend(self._check_winston_no_rotation(file))

            if file.extension in CONFIG_EXTENSIONS:
                findings.extend(self._check_cloudwatch_no_retention(file))
                findings.extend(self._check_unencrypted_endpoints(file))
                findings.extend(self._check_winston_no_rotation(file))

            if file.extension in SCHEMA_EXTENSIONS:
                findings.extend(self._check_log_table_no_ttl(file))

        return findings

    # --- repo-level: analytics imports + consent ---

    def _collect_analytics_usage(
        self, snapshot: RepositorySnapshot
    ) -> list[tuple[str, str, int]]:
        """Return (file_path, sdk_name, line_no) for each detected analytics import."""
        usage: list[tuple[str, str, int]] = []
        for file in snapshot.files:
            if file.text is None or file.extension not in SOURCE_EXTENSIONS:
                continue
            for line_no, line in enumerate(file.text.splitlines(), start=1):
                for pattern, sdk_name in _ANALYTICS_PATTERNS:
                    if pattern.search(line):
                        usage.append((file.path, sdk_name, line_no))
                        break
        return usage

    def _repo_has_consent(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _CONSENT_PATTERN.search(file.text) for file in snapshot.files
        )

    def _analytics_without_consent_finding(
        self, usage: list[tuple[str, str, int]]
    ) -> Finding:
        capped = usage[:5]
        seed = "|".join(sorted(f"{path}:{sdk}" for path, sdk, _ in capped))
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=path, line_start=line_no, line_end=line_no),
                description=f"{sdk_name} SDK imported — no opt-out or consent mechanism found in the repository.",
            )
            for path, sdk_name, line_no in capped
        ]
        return Finding(
            id=stable_finding_id(self.id, "analytics_without_consent", seed),
            title="Analytics SDK used without visible consent or opt-out mechanism",
            description=(
                "The repository imports one or more analytics or telemetry SDKs but contains "
                "no detectable consent, opt-out, or privacy-notice logic. GDPR Art. 7 and CCPA "
                "§1798.120 require that users can withdraw consent or opt out of behavioral data "
                "collection. If consent handling lives in a separate service or repository, this "
                "finding may be a false positive."
            ),
            category="analytics_privacy",
            severity="medium",
            confidence="low",
            evidence=evidence,
            recommendation=(
                "Add a consent mechanism (cookie banner, privacy preference center, or opt-out API) "
                "before initializing analytics SDKs, and disable collection for users who decline."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )

    # --- PII in log calls ---

    def _check_pii_in_log_calls(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        is_test = file.path_role in {"tests", "examples"}

        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if not _LOG_CALL_PATTERN.search(line):
                continue

            high_match = _HIGH_PII_PATTERN.search(line)
            if high_match:
                field = high_match.group(0)
                severity = "medium" if is_test else "high"
                confidence: str = "medium"
            elif _MEDIUM_PII_PATTERN.search(line):
                field = _MEDIUM_PII_PATTERN.search(line).group(0)  # type: ignore[union-attr]
                severity = "low" if is_test else "medium"
                confidence = "medium"
            else:
                continue

            findings.append(
                Finding(
                    id=stable_finding_id(self.id, "pii_in_log_call", f"{file.path}:{line_no}"),
                    title=f"Possible PII ({field}) in log statement",
                    description=(
                        f"A logging statement on this line references '{field}', which may indicate "
                        "that personal data is written to application logs. GDPR Art. 5(1)(e) "
                        "requires that personal data not be kept longer than necessary, and logging "
                        "PII makes it difficult to honour deletion requests or limit exposure if "
                        "logs are forwarded to third-party services."
                    ),
                    category="analytics_privacy",
                    severity=severity,  # type: ignore[arg-type]
                    confidence=confidence,  # type: ignore[arg-type]
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=file.path, line_start=line_no, line_end=line_no
                            ),
                            description=f"Log call references sensitive field '{field}'.",
                            excerpt=line.strip()[:120],
                        )
                    ],
                    recommendation=(
                        "Remove the PII field from the log call, or mask it before logging "
                        "(e.g., show only the first three characters). Consider a structured "
                        "logging library that supports field-level redaction."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )

        return findings

    # --- request body logging ---

    def _check_request_body_logging(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []

        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if not _LOG_CALL_PATTERN.search(line):
                continue
            if not _REQUEST_BODY_PATTERN.search(line):
                continue

            findings.append(
                Finding(
                    id=stable_finding_id(
                        self.id, "request_body_logged", f"{file.path}:{line_no}"
                    ),
                    title="Full HTTP request body may be logged",
                    description=(
                        "A logging statement appears to log an entire HTTP request body. Request "
                        "bodies frequently contain passwords, tokens, or other personal data. "
                        "Logging them wholesale can violate GDPR Art. 5 (data minimisation) and "
                        "create liability if logs are retained by or forwarded to third-party "
                        "log aggregation services."
                    ),
                    category="analytics_privacy",
                    severity="high",
                    confidence="medium",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=file.path, line_start=line_no, line_end=line_no
                            ),
                            description="Log call references request body.",
                            excerpt=line.strip()[:120],
                        )
                    ],
                    recommendation=(
                        "Log only the specific fields needed for debugging. Exclude authentication "
                        "fields (password, token, api_key) and PII. Use a middleware allowlist that "
                        "explicitly names safe-to-log request fields."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )

        return findings

    # --- plaintext analytics endpoints ---

    def _check_unencrypted_endpoints(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []

        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            match = _HTTP_ANALYTICS_PATTERN.search(line)
            if match is None:
                continue

            url = match.group(0)[:80]
            findings.append(
                Finding(
                    id=stable_finding_id(
                        self.id, "unencrypted_analytics_endpoint", f"{file.path}:{line_no}"
                    ),
                    title="Analytics or logging data sent over unencrypted HTTP",
                    description=(
                        f"An HTTP (not HTTPS) URL for an analytics or logging service was found: "
                        f"'{url}'. Transmitting behavioural or log data over plaintext HTTP exposes "
                        "it to network interception. GDPR Art. 32 requires appropriate technical "
                        "measures including encryption of data in transit."
                    ),
                    category="analytics_privacy",
                    severity="medium",
                    confidence="high",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=file.path, line_start=line_no, line_end=line_no
                            ),
                            description=f"Plaintext HTTP endpoint: {url}",
                            excerpt=line.strip()[:120],
                        )
                    ],
                    recommendation=(
                        "Replace all analytics and logging endpoints with their HTTPS equivalents."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )

        return findings

    # --- CloudWatch log retention ---

    def _check_cloudwatch_no_retention(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []

        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if not _CLOUDWATCH_ZERO_RETENTION.search(line):
                continue

            findings.append(
                Finding(
                    id=stable_finding_id(
                        self.id, "cloudwatch_no_log_retention", f"{file.path}:{line_no}"
                    ),
                    title="CloudWatch log group configured to never expire logs",
                    description=(
                        "A CloudWatch log group has `retentionInDays` set to 0, which means logs "
                        "are retained indefinitely. GDPR Art. 5(1)(e) (storage limitation) and CCPA "
                        "require that personal data not be kept longer than necessary. Indefinite "
                        "log retention increases breach exposure and makes deletion requests harder "
                        "to satisfy."
                    ),
                    category="analytics_privacy",
                    severity="medium",
                    confidence="high",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(
                                path=file.path, line_start=line_no, line_end=line_no
                            ),
                            description="Log retention set to 0 (never expire).",
                            excerpt=line.strip()[:120],
                        )
                    ],
                    recommendation=(
                        "Set `retentionInDays` to a value appropriate for your retention policy "
                        "(e.g., 30, 90, or 365 days). Consult your legal team to confirm the "
                        "minimum retention period required by applicable law."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )

        return findings

    # --- Winston log rotation ---

    def _check_winston_no_rotation(self, file: FileSnapshot) -> list[Finding]:
        text = file.text  # type: ignore[union-attr]
        if not _WINSTON_FILE_TRANSPORT.search(text):
            return []
        if _WINSTON_ROTATION.search(text):
            return []

        for line_no, line in enumerate(text.splitlines(), start=1):
            if _WINSTON_FILE_TRANSPORT.search(line):
                return [
                    Finding(
                        id=stable_finding_id(self.id, "winston_no_log_rotation", file.path),
                        title="Winston file logger configured without a rotation or size limit",
                        description=(
                            "A Winston File transport is configured without `maxFiles`, `maxDays`, "
                            "or `maxsize`. Without rotation limits, log files can grow indefinitely, "
                            "retaining personal data far longer than necessary. GDPR Art. 5(1)(e) "
                            "requires that data be kept no longer than needed for the original purpose."
                        ),
                        category="analytics_privacy",
                        severity="low",
                        confidence="medium",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(
                                    path=file.path, line_start=line_no, line_end=line_no
                                ),
                                description="Winston File transport without rotation configuration.",
                                excerpt=line.strip()[:120],
                            )
                        ],
                        recommendation=(
                            "Add `maxFiles`, `maxDays`, or `maxsize` to the Winston File transport "
                            "to enforce a retention limit on local log files."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                ]

        return []

    # --- Database log table TTL ---

    def _check_log_table_no_ttl(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        text = file.text  # type: ignore[union-attr]

        if file.extension == ".sql":
            if _SQL_TTL_HINTS.search(text):
                return []
            for match in _SQL_LOG_TABLE.finditer(text):
                table_name = match.group(1)
                line_no = text[: match.start()].count("\n") + 1
                findings.append(self._log_table_finding(file.path, table_name, line_no))

        elif file.extension == ".prisma":
            if _PRISMA_TTL_HINTS.search(text):
                return []
            for match in _PRISMA_LOG_MODEL.finditer(text):
                model_name = match.group(1)
                line_no = text[: match.start()].count("\n") + 1
                findings.append(self._log_table_finding(file.path, model_name, line_no))

        return findings

    def _log_table_finding(self, path: str, table_name: str, line_no: int) -> Finding:
        return Finding(
            id=stable_finding_id(self.id, "log_table_no_ttl", f"{path}:{table_name}"),
            title=f"Log/event table '{table_name}' has no apparent TTL or expiry policy",
            description=(
                f"The table or model '{table_name}' appears to store logs, events, or audit data "
                "but no TTL index, partition-based expiry, or retention comment was detected. "
                "Without a cleanup mechanism, this table retains data indefinitely. GDPR Art. "
                "5(1)(e) and CCPA require that personal data not be stored longer than necessary."
            ),
            category="analytics_privacy",
            severity="medium",
            confidence="low",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=path, line_start=line_no, line_end=line_no),
                    description=f"Table/model '{table_name}' stores log or event data with no visible TTL.",
                )
            ],
            recommendation=(
                "Add a data retention policy for this table: a TTL index (e.g., MongoDB TTL "
                "index), PostgreSQL partition pruning (`PARTITION BY RANGE`), a scheduled DELETE "
                "job, or an archival pipeline. Document the retention period in a comment."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )
