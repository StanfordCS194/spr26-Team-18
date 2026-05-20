from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceKind = Literal["local", "github"]
Severity = Literal["info", "low", "medium", "high", "critical"]


class RepositorySource(BaseModel):
    kind: SourceKind
    location: str
    ref: str | None = None


class FileSnapshot(BaseModel):
    path: str
    size_bytes: int
    extension: str
    text: str | None = None
    skipped_reason: str | None = None

    @property
    def is_text(self) -> bool:
        return self.text is not None


class RepositorySnapshot(BaseModel):
    source: RepositorySource
    root: Path
    files: list[FileSnapshot]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Finding(BaseModel):
    rule_id: str
    title: str
    severity: Severity
    message: str
    scanner: str
    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    evidence: str | None = None


class ScanSummary(BaseModel):
    total_findings: int
    by_severity: dict[Severity, int]


class ScanResult(BaseModel):
    source: RepositorySource
    scanned_at: datetime
    findings: list[Finding]
    summary: ScanSummary

    @classmethod
    def from_findings(
        cls,
        *,
        source: RepositorySource,
        findings: list[Finding],
    ) -> "ScanResult":
        severity_counts: dict[Severity, int] = {
            "info": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }
        for finding in findings:
            severity_counts[finding.severity] += 1

        return cls(
            source=source,
            scanned_at=datetime.now(timezone.utc),
            findings=findings,
            summary=ScanSummary(
                total_findings=len(findings),
                by_severity=severity_counts,
            ),
        )

