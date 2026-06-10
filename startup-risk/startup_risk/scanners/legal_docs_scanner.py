from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
)

_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".java", ".php", ".cs", ".html", ".htm",
})

# Each tuple: (key, display_name, file_pattern, route_pattern, severity, description, recommendation)
_DOC_CHECKS = [
    (
        "terms",
        "Terms of Service / Terms of Use",
        re.compile(r"\b(?:terms[-_]?(?:of[-_]?(?:service|use)|and[-_]?conditions)?|tos)\b", re.IGNORECASE),
        re.compile(r"""['"]/(?:terms|tos|terms[-_]of[-_](?:service|use))/?['"]""", re.IGNORECASE),
        "high",
        (
            "No Terms of Service or Terms of Use document was detected in this repository. "
            "Without ToS, the company cannot enforce acceptable-use rules, disclaim liability, "
            "or protect intellectual property. ToS is a standard requirement for any product "
            "with user accounts and is routinely flagged during legal due diligence."
        ),
        (
            "Create a Terms of Service page (e.g., /terms) and link it from registration flows "
            "and your footer. Have legal counsel review it before launch."
        ),
    ),
    (
        "privacy",
        "Privacy Policy",
        re.compile(r"\bprivacy[-_]?(?:policy|notice|statement)?\b", re.IGNORECASE),
        re.compile(r"""['"]/privacy[-_]?(?:policy)?/?['"]""", re.IGNORECASE),
        "high",
        (
            "No Privacy Policy was detected in this repository. A Privacy Policy is legally "
            "required by GDPR (Art. 13/14), CCPA, CalOPPA, and the app-store guidelines of "
            "Apple and Google. Its absence is an immediate disqualifier for enterprise sales "
            "and a regulatory risk for consumer-facing products."
        ),
        (
            "Create a Privacy Policy describing what data you collect, why, retention periods, "
            "and how users can exercise their rights. Link it prominently from registration, "
            "login, and your footer."
        ),
    ),
    (
        "cookie_policy",
        "Cookie Policy / Consent Banner",
        re.compile(r"\bcookie[-_]?(?:policy|notice|consent|banner)?\b", re.IGNORECASE),
        re.compile(r"""['"]/cookie[-_]?(?:policy)?/?['"]""", re.IGNORECASE),
        "medium",
        (
            "No Cookie Policy or cookie-consent mechanism was detected. The EU ePrivacy "
            "Directive and GDPR require explicit prior consent before setting non-essential "
            "cookies. Regulators have issued fines for missing cookie consent even where a "
            "Privacy Policy existed."
        ),
        (
            "Add a cookie-consent banner or preference centre, and publish a Cookie Policy "
            "that lists each cookie, its purpose, and its lifetime."
        ),
    ),
    (
        "dmca",
        "DMCA / Copyright Takedown Contact",
        re.compile(r"\bdmca\b|\bcopyright[-_]?(?:takedown|agent|notice|policy)\b", re.IGNORECASE),
        re.compile(r"""['"]/(?:dmca|copyright)/?['"]""", re.IGNORECASE),
        "medium",
        (
            "No DMCA agent registration or copyright takedown contact was detected. The US "
            "Digital Millennium Copyright Act requires platforms that host user content to "
            "designate a registered DMCA agent and publish a takedown policy. Without one, "
            "the safe-harbour protections of 17 U.S.C. § 512 do not apply."
        ),
        (
            "Register a DMCA agent with the US Copyright Office and publish a takedown policy "
            "at a discoverable URL (e.g., /dmca or /legal/dmca). Only required if the platform "
            "hosts or indexes user-submitted content."
        ),
    ),
]


class LegalDocScanner:
    """Checks that required legal documents (ToS, Privacy Policy, Cookie Policy, DMCA) exist."""

    id = "legal_docs"
    name = "Legal Document Presence"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        all_paths_lower = [f.path.lower() for f in snapshot.files]

        for key, display_name, file_pat, route_pat, severity, description, recommendation in _DOC_CHECKS:
            # 1. Any file path matches the doc pattern?
            if any(file_pat.search(p) for p in all_paths_lower):
                continue

            # 2. Any source file contains a route reference to this doc?
            route_found = any(
                file.text and route_pat.search(file.text)
                for file in snapshot.files
                if file.extension in _SOURCE_EXTENSIONS
            )
            if route_found:
                continue

            findings.append(
                Finding(
                    id=stable_finding_id(self.id, f"missing_{key}", snapshot.source.location),
                    title=f"No {display_name} detected",
                    description=description,
                    category="legal",
                    severity=severity,
                    confidence="low",
                    evidence=[
                        FindingEvidence(
                            description=(
                                f"No file name or route matching a {display_name} pattern "
                                "was found anywhere in the repository."
                            )
                        )
                    ],
                    recommendation=recommendation,
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )

        return findings
