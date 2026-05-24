from __future__ import annotations

from rich.table import Table

from startup_risk.core.models import ScanResult


def render_text(result: ScanResult) -> Table:
    table = Table(title="startup-risk scan")
    table.add_column("Severity")
    table.add_column("Finding")
    table.add_column("Path")
    table.add_column("Description")

    if not result.findings:
        table.add_row("info", "scan.clean", "-", "No findings.")
        return table

    for finding in result.findings:
        table.add_row(
            finding.severity,
            finding.id,
            _primary_path(finding),
            finding.description,
        )

    return table


def _primary_path(finding) -> str:
    for evidence in finding.evidence:
        if evidence.location is not None:
            return evidence.location.path
    return "-"
