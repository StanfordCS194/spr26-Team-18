from __future__ import annotations

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    Severity,
    SourceLocation,
)


SUSPICIOUS_FILENAME_HINTS = (
    "credential",
    "credentials",
    "private_key",
    "private-key",
    "secret",
    "secrets",
    "token",
)

SUSPICIOUS_EXACT_FILENAMES = {
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}

SUSPICIOUS_EXTENSIONS = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
}


class StaticHygieneScanner:
    """Baseline scanner for repository hygiene signals visible from static files."""

    id = "static_hygiene"
    name = "Static Hygiene"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        files = {file.path.lower(): file for file in snapshot.files}
        findings: list[Finding] = []

        if "readme.md" not in files:
            findings.append(self._missing_file_finding("missing_readme", "README.md"))
        if not any(path in files for path in ("license", "license.md", "license.txt")):
            findings.append(self._missing_file_finding("missing_license", "LICENSE"))
        if ".gitignore" not in files:
            findings.append(self._missing_file_finding("missing_gitignore", ".gitignore"))
        if "security.md" not in files:
            findings.append(self._missing_file_finding("missing_security", "SECURITY.md"))

        for file in snapshot.files:
            sensitive_rule = _sensitive_filename_rule(file.path)
            if sensitive_rule is not None:
                severity = _sensitive_filename_severity(file.path_role)
                findings.append(
                    Finding(
                        id=stable_finding_id(
                            self.id,
                            "suspicious_sensitive_filename",
                            file.path,
                        ),
                        title="Filename may indicate sensitive material",
                        description=(
                            "A repository file name contains wording often associated with "
                            "secrets, credentials, tokens, or private keys. This is a filename "
                            "signal only and does not prove the file contains sensitive data."
                        ),
                        category="repository_hygiene",
                        severity=severity,
                        confidence="medium",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(path=file.path),
                                description=(
                                    f"The {file.path_role} path matches the "
                                    f"{sensitive_rule} filename heuristic."
                                ),
                            )
                        ],
                        recommendation=(
                            "Review the file contents and repository history. If it contains "
                            "sensitive material, rotate the credential and remove it from history."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                )

        return findings

    def _missing_file_finding(self, rule: str, filename: str) -> Finding:
        return Finding(
            id=stable_finding_id(self.id, rule, "repository-root"),
            title=f"Missing {filename}",
            description=(
                f"The repository does not include a top-level {filename}. This may make "
                "ownership, usage, or security expectations harder to understand."
            ),
            category="repository_hygiene",
            severity="low",
            confidence="high",
            evidence=[
                FindingEvidence(
                    description=f"No top-level {filename} file was found in the static snapshot."
                )
            ],
            recommendation=f"Add a top-level {filename} if this repository is intended to be shared.",
            scanner_id=self.id,
            scanner_version=self.version,
        )


def _sensitive_filename_rule(path: str) -> str | None:
    lower_path = path.lower()
    filename = lower_path.rsplit("/", maxsplit=1)[-1]
    extension = "." + filename.rsplit(".", maxsplit=1)[-1] if "." in filename else ""

    if filename in {".env.example", ".env.sample", ".env.template"}:
        return None
    if filename == ".env" or filename.startswith(".env."):
        return "env_file"
    if filename in SUSPICIOUS_EXACT_FILENAMES:
        return "private_key_filename"
    if extension in SUSPICIOUS_EXTENSIONS:
        return "private_key_extension"
    if any(hint in filename for hint in SUSPICIOUS_FILENAME_HINTS):
        return "sensitive_name"
    return None


def _sensitive_filename_severity(path_role: str) -> Severity:
    if path_role == "root":
        return "high"
    if path_role in {"tests", "examples", "docs"}:
        return "low"
    return "medium"
