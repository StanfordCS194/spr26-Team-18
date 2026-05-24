from __future__ import annotations

from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)


SUSPICIOUS_FILENAME_HINTS = (
    ".env",
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
            if _looks_sensitive(file.path):
                findings.append(
                    Finding(
                        id=f"{self.id}.suspicious_sensitive_filename.{file.path}",
                        title="Filename may indicate sensitive material",
                        description=(
                            "A repository file name contains wording often associated with "
                            "secrets, credentials, tokens, or private keys. This is a filename "
                            "signal only and does not prove the file contains sensitive data."
                        ),
                        category="repository_hygiene",
                        severity="medium",
                        confidence="medium",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(path=file.path),
                                description="The file path matches a cautious sensitive-name heuristic.",
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
            id=f"{self.id}.{rule}",
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


def _looks_sensitive(path: str) -> bool:
    lower_path = path.lower()
    filename = lower_path.rsplit("/", maxsplit=1)[-1]
    extension = "." + filename.rsplit(".", maxsplit=1)[-1] if "." in filename else ""
    return (
        filename in SUSPICIOUS_EXACT_FILENAMES
        or extension in SUSPICIOUS_EXTENSIONS
        or any(hint in lower_path for hint in SUSPICIOUS_FILENAME_HINTS)
    )
