from __future__ import annotations

from startup_risk.core.models import Finding, RepositorySnapshot


SECRET_NAME_HINTS = (".env", "secret", "secrets", "credential", "credentials")


class StaticHygieneScanner:
    """Small baseline scanner for static repository hygiene signals."""

    name = "static-hygiene"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        has_readme = any(file.path.lower() == "readme.md" for file in snapshot.files)

        if not has_readme:
            findings.append(
                Finding(
                    rule_id="repo.missing_readme",
                    title="Missing README",
                    severity="low",
                    scanner=self.name,
                    message="Repository does not include a top-level README.md file.",
                )
            )

        for file in snapshot.files:
            lower_path = file.path.lower()
            if any(hint in lower_path for hint in SECRET_NAME_HINTS):
                findings.append(
                    Finding(
                        rule_id="repo.sensitive_filename",
                        title="Sensitive filename",
                        severity="medium",
                        scanner=self.name,
                        path=file.path,
                        message="Filename suggests secrets or credentials may be present.",
                    )
                )

        return findings

