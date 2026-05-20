from __future__ import annotations

from rich.table import Table

from startup_risk.core.models import ScanResult


def render_text(result: ScanResult) -> Table:
    table = Table(title="startup-risk scan")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Path")
    table.add_column("Message")

    if not result.findings:
        table.add_row("info", "scan.clean", "-", "No findings.")
        return table

    for finding in result.findings:
        table.add_row(
            finding.severity,
            finding.rule_id,
            finding.path or "-",
            finding.message,
        )

    return table

