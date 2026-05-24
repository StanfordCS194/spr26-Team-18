from __future__ import annotations

from startup_risk.scanners.base import Scanner
from startup_risk.scanners.repo_inventory import RepoInventoryScanner
from startup_risk.scanners.static_hygiene import StaticHygieneScanner


def default_scanners() -> list[Scanner]:
    return [
        StaticHygieneScanner(),
        RepoInventoryScanner(),
    ]
