from __future__ import annotations

from typing import Protocol, runtime_checkable

from startup_risk.core.models import Finding, RepositorySnapshot


@runtime_checkable
class Scanner(Protocol):
    id: str
    name: str
    version: str

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        """Return findings from a static repository snapshot."""
