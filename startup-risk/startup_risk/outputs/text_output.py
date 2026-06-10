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
            _description(finding),
        )

    return table


def _primary_path(finding) -> str:
    for evidence in finding.evidence:
        if evidence.location is not None:
            return evidence.location.path
    return "-"


def _description(finding) -> str:
    if not finding.legal_context:
        return finding.description
    context = finding.legal_context[0]
    citation = context.citations[0] if context.citations else None
    citation_text = citation.citation or citation.title if citation else "legal guidance"
    return f"{finding.description}\nLegal context: {context.why_it_matters} Source: {citation_text}"
