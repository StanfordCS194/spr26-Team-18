from __future__ import annotations

import json
from datetime import datetime, timezone

from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositoryInventory,
    RepositorySnapshot,
    RepositorySource,
    ScanResult,
    ScanSummary,
)
from startup_risk.outputs.json_output import result_to_json


def test_json_output_is_deterministic_and_sorted():
    result = ScanResult(
        source=RepositorySource(kind="local", location="fixture"),
        scanned_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        inventory=RepositoryInventory(),
        findings=[
            Finding(
                id="b.finding",
                title="B",
                description="Second finding.",
                category="test",
                severity="low",
                confidence="high",
                evidence=[FindingEvidence(description="B evidence.")],
                recommendation="Review B.",
                scanner_id="test",
                scanner_version="1.0.0",
            ),
            Finding(
                id="c.finding",
                title="C",
                description="High finding.",
                category="test",
                severity="high",
                confidence="high",
                evidence=[FindingEvidence(description="C evidence.")],
                recommendation="Review C.",
                scanner_id="test",
                scanner_version="1.0.0",
            ),
            Finding(
                id="a.finding",
                title="A",
                description="First finding.",
                category="test",
                severity="info",
                confidence="high",
                evidence=[FindingEvidence(description="A evidence.")],
                recommendation="Review A.",
                scanner_id="test",
                scanner_version="1.0.0",
            ),
        ],
        summary=ScanSummary(
            actionable_findings=2,
            informational_inventory_signals=0,
            by_severity={
                "info": 1,
                "low": 1,
                "medium": 0,
                "high": 1,
                "critical": 0,
            },
        ),
    )

    first = result_to_json(result)
    second = result_to_json(result)

    assert first == second
    parsed = json.loads(first)
    assert list(parsed.keys()) == ["findings", "inventory", "scanned_at", "source", "summary"]
    assert [finding["id"] for finding in parsed["findings"]] == ["c.finding", "b.finding", "a.finding"]


def test_repository_snapshot_output_excludes_local_root():
    snapshot = RepositorySnapshot(
        source=RepositorySource(kind="github", location="https://github.com/org/repo"),
        root="/private/tmp/startup-risk-random/repo",
        files=[FileSnapshot(path="README.md", size_bytes=1, extension=".md", text="#")],
    )

    dumped = snapshot.model_dump(mode="json")

    assert "root" not in dumped
    assert dumped["files"][0]["path"] == "README.md"


def test_summary_counts_only_findings_in_severity_counts():
    result = ScanResult.from_findings(
        source=RepositorySource(kind="local", location="fixture"),
        inventory=RepositoryInventory(
            docs_files={"count": 12, "examples": ["README.md"]},
            manifest_files={"count": 1, "examples": ["pyproject.toml"]},
        ),
        findings=[
            Finding(
                id="test.low.123",
                title="Low finding",
                description="Actionable low finding.",
                category="test",
                severity="low",
                confidence="high",
                evidence=[],
                recommendation="Review.",
                scanner_id="test",
                scanner_version="1.0.0",
            )
        ],
    )

    assert result.summary.actionable_findings == 1
    assert result.summary.informational_inventory_signals == 2
    assert result.summary.by_severity == {
        "info": 0,
        "low": 1,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }
