from __future__ import annotations

from collections.abc import Iterable

from startup_risk.core.models import ScanResult
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.scanners.base import Scanner


class ScanEngine:
    """Coordinates static ingestion and scanner execution."""

    def __init__(self, ingestor: RepositoryIngestor, scanners: Iterable[Scanner]) -> None:
        self._ingestor = ingestor
        self._scanners = list(scanners)

    def scan(self, target: str) -> ScanResult:
        snapshot = self._ingestor.ingest(target)
        findings = []

        for scanner in self._scanners:
            findings.extend(scanner.scan(snapshot))

        return ScanResult.from_findings(source=snapshot.source, findings=findings)

