from __future__ import annotations

import pytest

from startup_risk.core.engine import ScanEngine
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositoryInventory,
    RepositorySnapshot,
    ScanContext,
)
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.legal_intelligence import LegalGuidanceIndex
from startup_risk.legal_intelligence.models import LegalCitation, LegalGuidanceRule


class ContractScanner:
    id = "contract"
    name = "Contract Scanner"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        return [
            Finding(
                id="contract.example",
                title="Example finding",
                description="Scanner contract produced a structured finding.",
                category="test",
                severity="info",
                confidence="high",
                evidence=[FindingEvidence(description="Static test evidence.")],
                recommendation="No action required.",
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]


class MissingContractScanner:
    id = "missing"


class WrongScannerId:
    id = "right"
    name = "Wrong Scanner ID"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        return [
            Finding(
                id="wrong.example",
                title="Wrong scanner id",
                description="This finding intentionally has the wrong scanner id.",
                category="test",
                severity="info",
                confidence="high",
                evidence=[],
                recommendation="No action required.",
                scanner_id="wrong",
                scanner_version=self.version,
            )
        ]


class ContextAwareContractScanner:
    id = "analytics_privacy"
    name = "Context Aware Contract Scanner"
    version = "1.0.0"
    category = "analytics_privacy"

    def __init__(self) -> None:
        self.received_context: ScanContext | None = None

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        raise AssertionError("scan_with_context should be used when available")

    def scan_with_context(self, snapshot: RepositorySnapshot, context: ScanContext) -> list[Finding]:
        self.received_context = context
        return [
            Finding(
                id="analytics_privacy.example",
                title="Example privacy finding",
                description="Scanner contract produced a structured finding.",
                category="analytics_privacy",
                severity="info",
                confidence="high",
                evidence=[FindingEvidence(description="Static test evidence.")],
                recommendation="No action required.",
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]


class ProfileSeverityScanner:
    id = "analytics_privacy"
    name = "Profile Severity Scanner"
    version = "1.0.0"
    category = "analytics_privacy"

    def __init__(
        self,
        severity: str = "medium",
        category: str = "analytics_privacy",
        scanner_id: str = "analytics_privacy",
        title: str = "Personal data sent to analytics",
        description: str = "The scanner found personal data sent to analytics.",
        recommendation: str = "Review analytics data collection.",
        excerpt: str = "analytics.identify(email)",
    ) -> None:
        self.id = scanner_id
        self._severity = severity
        self._category = category
        self._title = title
        self._description = description
        self._recommendation = recommendation
        self._excerpt = excerpt

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        return [
            Finding(
                id=f"profile_severity.{self._severity}.{self._category}",
                title=self._title,
                description=self._description,
                category=self._category,
                severity=self._severity,
                confidence="high",
                evidence=[FindingEvidence(description="Static test evidence.", excerpt=self._excerpt)],
                recommendation=self._recommendation,
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]


def test_engine_runs_formal_scanner_contract(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[ContractScanner()],
    ).scan(str(repo))

    assert result.summary.actionable_findings == 1
    assert result.findings[0].scanner_id == "contract"
    assert result.findings[0].scanner_version == "1.0.0"
    assert isinstance(result.inventory, RepositoryInventory)


def test_engine_rejects_scanner_missing_contract_members():
    with pytest.raises(TypeError, match="missing required attribute"):
        ScanEngine(ingestor=RepositoryIngestor(), scanners=[MissingContractScanner()])


def test_engine_rejects_mismatched_finding_scanner_id(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    engine = ScanEngine(ingestor=RepositoryIngestor(), scanners=[WrongScannerId()])

    with pytest.raises(ValueError, match="returned finding"):
        engine.scan(str(repo))


def test_engine_keeps_inventory_out_of_findings_for_flask_like_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for path in (
        "README.md",
        "LICENSE",
        ".gitignore",
        "SECURITY.md",
        "pyproject.toml",
        "src/flask/app.py",
        "docs/index.rst",
        "examples/tutorial/schema.sql",
    ):
        file_path = repo / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("x\n", encoding="utf-8")

    result = ScanEngine(ingestor=RepositoryIngestor(), scanners=[]).scan(str(repo))

    assert result.findings == []
    assert result.summary.actionable_findings == 0
    assert result.summary.informational_inventory_signals > 0
    assert result.inventory.docs_files.count == 3
    assert result.inventory.manifest_files.count == 1
    assert result.inventory.schema_files.count == 1


def test_engine_passes_legal_context_to_context_aware_scanner(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    rule = LegalGuidanceRule(
        id="legal_guidance.analytics",
        authority_id="authority",
        category="privacy",
        title="Analytics disclosure",
        legal_basis="Privacy authority requires clear disclosure for analytics tracking.",
        risk_signal="analytics tracking personal data",
        detection_hints=["analytics", "tracking"],
        finding_rationale="Undisclosed tracking can create privacy risk.",
        recommendation="Disclose analytics tracking.",
        citations=[LegalCitation(title="FTC guidance", citation="FTC", authority_type="agency_guidance")],
        confidence="medium",
    )
    scanner = ContextAwareContractScanner()

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[scanner],
        legal_guidance_index=LegalGuidanceIndex([rule], profile={"industry": "tech"}),
        max_workers=1,
    ).scan(str(repo))

    assert result.findings[0].scanner_id == "analytics_privacy"
    assert scanner.received_context is not None
    assert scanner.received_context.profile == {"industry": "tech"}
    assert scanner.received_context.legal_guidance[0].rule_id == "legal_guidance.analytics"


def test_profile_context_boosts_relevant_finding_severity_and_summary(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[ProfileSeverityScanner(severity="medium")],
        scan_profile={"industry": "healthcare", "sensitiveData": "PHI"},
    ).scan(str(repo))

    finding = result.findings[0]
    assert finding.severity == "high"
    assert "Startup profile priority" in finding.description
    assert result.summary.by_severity["high"] == 1
    assert result.summary.by_severity["medium"] == 0


def test_profile_context_does_not_boost_unrelated_findings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[
            ProfileSeverityScanner(
                severity="medium",
                category="dependency_supply_chain",
                scanner_id="dependency_scanner",
                title="Outdated dependency manifest",
                description="The scanner found a dependency manifest hygiene issue.",
                recommendation="Review dependency metadata.",
                excerpt="package==1.0.0",
            )
        ],
        scan_profile={"industry": "healthcare", "sensitiveData": "PHI"},
    ).scan(str(repo))

    assert result.findings[0].severity == "medium"
    assert "Startup profile priority" not in result.findings[0].description


def test_profile_context_does_not_boost_info_or_critical_findings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    info_result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[ProfileSeverityScanner(severity="info")],
        scan_profile={"industry": "healthcare", "sensitiveData": "PHI"},
    ).scan(str(repo))
    critical_result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[ProfileSeverityScanner(severity="critical")],
        scan_profile={"industry": "healthcare", "sensitiveData": "PHI"},
    ).scan(str(repo))

    assert info_result.findings[0].severity == "info"
    assert critical_result.findings[0].severity == "critical"
