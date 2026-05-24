from __future__ import annotations

import pytest

from startup_risk.core.engine import ScanEngine
from startup_risk.core.models import Finding, FindingEvidence, RepositorySnapshot
from startup_risk.ingest.repository import RepositoryIngestor


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


def test_engine_runs_formal_scanner_contract(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[ContractScanner()],
    ).scan(str(repo))

    assert result.summary.total_findings == 1
    assert result.findings[0].scanner_id == "contract"
    assert result.findings[0].scanner_version == "1.0.0"


def test_engine_rejects_scanner_missing_contract_members():
    with pytest.raises(TypeError, match="missing required attribute"):
        ScanEngine(ingestor=RepositoryIngestor(), scanners=[MissingContractScanner()])


def test_engine_rejects_mismatched_finding_scanner_id(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    engine = ScanEngine(ingestor=RepositoryIngestor(), scanners=[WrongScannerId()])

    with pytest.raises(ValueError, match="returned finding"):
        engine.scan(str(repo))
