from __future__ import annotations

from typing import Protocol

from startup_risk.core.models import Finding, RepositorySnapshot


class Scanner(Protocol):
    name: str

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        """Return findings from a static repository snapshot."""

