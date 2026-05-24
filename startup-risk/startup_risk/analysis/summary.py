from __future__ import annotations

from startup_risk.core.models import ScanResult


def has_blocking_findings(result: ScanResult) -> bool:
    return any(finding.severity in {"high", "critical"} for finding in result.findings)

