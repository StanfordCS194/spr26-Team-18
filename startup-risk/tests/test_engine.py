from __future__ import annotations

import pytest

from startup_risk.core.engine import ScanEngine
from startup_risk.core.models import Finding, FindingEvidence, RepositoryInventory, RepositorySnapshot
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
