from __future__ import annotations

from collections.abc import Iterable

from startup_risk.core.models import Finding, RepositoryInventory, ScanResult
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.scanners.base import InventoryScanner, Scanner
from startup_risk.scanners.registry import default_inventory_scanner


class ScanEngine:
    """Coordinates static ingestion and scanner execution."""

    def __init__(
        self,
        ingestor: RepositoryIngestor,
        scanners: Iterable[Scanner],
        inventory_scanner: InventoryScanner | None = None,
    ) -> None:
        self._ingestor = ingestor
        self._scanners = list(scanners)
        self._inventory_scanner = inventory_scanner or default_inventory_scanner()
        self._validate_scanner(self._inventory_scanner)
        for scanner in self._scanners:
            self._validate_scanner(scanner)

    def scan(self, target: str) -> ScanResult:
        snapshot = self._ingestor.ingest(target)
        inventory = self._inventory_scanner.scan(snapshot)
        if not isinstance(inventory, RepositoryInventory):
            raise TypeError("inventory scanner must return RepositoryInventory")

        findings: list[Finding] = []

        for scanner in self._scanners:
            scanner_findings = scanner.scan(snapshot)
            for finding in scanner_findings:
                if finding.scanner_id != scanner.id:
                    raise ValueError(
                        f"scanner {scanner.id} returned finding for {finding.scanner_id}"
                    )
            findings.extend(scanner_findings)

        return ScanResult.from_findings(
            source=snapshot.source,
            inventory=inventory,
            findings=findings,
        )

    def _validate_scanner(self, scanner: Scanner) -> None:
        for attr in ("id", "name", "version", "scan"):
            if not hasattr(scanner, attr):
                raise TypeError(f"scanner is missing required attribute: {attr}")
