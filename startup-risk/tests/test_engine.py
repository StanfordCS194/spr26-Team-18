from __future__ import annotations

from startup_risk.core.engine import ScanEngine
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.scanners.registry import default_scanners


def test_engine_returns_structured_findings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("TOKEN=example\n", encoding="utf-8")

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=default_scanners(),
    ).scan(str(repo))

    assert result.summary.total_findings == 2
    assert {finding.rule_id for finding in result.findings} == {
        "repo.missing_readme",
        "repo.sensitive_filename",
    }
    assert result.summary.by_severity["medium"] == 1

