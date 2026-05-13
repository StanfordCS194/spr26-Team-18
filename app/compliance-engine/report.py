from __future__ import annotations

from models import ComplianceFinding, ComplianceReport


def render_markdown_report(report: ComplianceReport, include_not_flagged: bool = False) -> str:
    findings = report.findings if include_not_flagged else report.flagged_findings()
    lines = [
        "# Compliance Focus Areas",
        "",
        "This is triage output for product/legal review, not a final legal determination.",
        "",
    ]

    if not findings:
        lines.append("No compliance focus areas were flagged from the available PRD text.")
        return "\n".join(lines)

    for finding in findings:
        lines.extend(_render_finding(finding))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_finding(finding: ComplianceFinding) -> list[str]:
    lines = [
        f"## {finding.name}",
        "",
        f"- Status: {finding.status.replace('_', ' ')}",
        f"- Priority: {finding.priority}",
        f"- Confidence: {finding.confidence}",
        "",
        "### Why flagged",
        finding.rationale,
    ]

    if finding.evidence:
        lines.extend(["", "### Evidence"])
        for item in finding.evidence:
            source = f" ({item.source})" if item.source else ""
            lines.append(f"- {item.label}{source}: {item.snippet}")

    if finding.missing_facts:
        lines.extend(["", "### Open questions"])
        lines.extend(f"- {question}" for question in finding.missing_facts)

    if finding.suggested_controls:
        lines.extend(["", "### Suggested product controls"])
        lines.extend(f"- {control}" for control in finding.suggested_controls)

    return lines
