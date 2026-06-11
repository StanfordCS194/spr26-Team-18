from __future__ import annotations

from typing import Protocol, runtime_checkable

from startup_risk.core.models import Finding, RepositoryInventory, RepositorySnapshot, ScanContext


@runtime_checkable
class Scanner(Protocol):
    id: str
    name: str
    version: str

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        """Return findings from a static repository snapshot."""


@runtime_checkable
class ContextAwareScanner(Protocol):
    id: str
    name: str
    version: str

    def scan_with_context(self, snapshot: RepositorySnapshot, context: ScanContext) -> list[Finding]:
        """Return findings using optional scan context."""


@runtime_checkable
class InventoryScanner(Protocol):
    id: str
    name: str
    version: str

    def scan(self, snapshot: RepositorySnapshot) -> RepositoryInventory:
        """Return static repository inventory metadata."""
