from __future__ import annotations

import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from startup_risk.core.models import Finding, RepositoryInventory, ScanContext, ScanResult
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.legal_intelligence.enrich import LegalGuidanceIndex, enrich_findings
from startup_risk.scanners.base import InventoryScanner, Scanner
from startup_risk.scanners.registry import default_inventory_scanner

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WORKERS = 8


class ScanEngine:
    """Coordinates static ingestion and scanner execution.

    Scanners run concurrently (they are I/O-bound: LLM and registry HTTP calls),
    and each is isolated: a scanner that raises at runtime is logged and skipped
    so one flaky agent never tanks the whole scan.
    """

    def __init__(
        self,
        ingestor: RepositoryIngestor,
        scanners: Iterable[Scanner],
        inventory_scanner: InventoryScanner | None = None,
        legal_guidance_index: LegalGuidanceIndex | None = None,
        max_workers: int = _DEFAULT_MAX_WORKERS,
    ) -> None:
        self._ingestor = ingestor
        self._scanners = list(scanners)
        self._inventory_scanner = inventory_scanner or default_inventory_scanner()
        self._legal_guidance_index = legal_guidance_index
        self._max_workers = max_workers
        self._validate_scanner(self._inventory_scanner)
        for scanner in self._scanners:
            self._validate_scanner(scanner)

    def scan(self, target: str) -> ScanResult:
        snapshot = self._ingestor.ingest(target)
        inventory = self._inventory_scanner.scan(snapshot)
        if not isinstance(inventory, RepositoryInventory):
            raise TypeError("inventory scanner must return RepositoryInventory")

        findings: list[Finding] = []
        if self._scanners:
            workers = max(1, min(self._max_workers, len(self._scanners)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                # _run_scanner swallows runtime errors, so each result is a (possibly
                # empty) finding list. A scanner_id-contract violation still raises.
                for scanner_findings in pool.map(
                    lambda s: self._run_scanner(s, snapshot), self._scanners
                ):
                    findings.extend(scanner_findings)

        if self._legal_guidance_index is not None:
            findings = enrich_findings(findings, self._legal_guidance_index)

        return ScanResult.from_findings(
            source=snapshot.source,
            inventory=inventory,
            findings=findings,
        )

    def _run_scanner(self, scanner: Scanner, snapshot) -> list[Finding]:
        try:
            scan_with_context = getattr(scanner, "scan_with_context", None)
            if callable(scan_with_context):
                scanner_findings = scan_with_context(snapshot, self._context_for_scanner(scanner))
            else:
                scanner_findings = scanner.scan(snapshot)
        except Exception as exc:
            if exc.__class__.__name__.endswith("ConfigError"):
                raise
            # Runtime failure (LLM error, timeout, rate limit, parse bug): isolate it.
            logger.exception("scanner %s failed; skipping its findings", getattr(scanner, "id", "?"))
            return []

        # A mismatched scanner_id is a programming error, not a runtime hiccup —
        # surface it loudly rather than silently mislabelling findings.
        for finding in scanner_findings:
            if finding.scanner_id != scanner.id:
                raise ValueError(
                    f"scanner {scanner.id} returned finding for {finding.scanner_id}"
                )
        return scanner_findings

    def _validate_scanner(self, scanner: Scanner) -> None:
        for attr in ("id", "name", "version", "scan"):
            if not hasattr(scanner, attr):
                raise TypeError(f"scanner is missing required attribute: {attr}")

    def _context_for_scanner(self, scanner: Scanner) -> ScanContext:
        if self._legal_guidance_index is None:
            return ScanContext()
        return ScanContext(
            profile=self._legal_guidance_index.profile,
            legal_guidance=self._legal_guidance_index.guidance_for_scanner(
                scanner_id=scanner.id,
                scanner_category=getattr(scanner, "category", None),
                scanner_name=getattr(scanner, "name", None),
            ),
        )
