from __future__ import annotations

from typing import Any

from startup_risk.core.models import Finding, Severity


_MAX_PROFILE_VALUE_CHARS = 80
_PROFILE_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Company", ("companyName", "company_name")),
    ("Product", ("product_name", "productName")),
    ("Industry", ("industry",)),
    ("Stage", ("stage",)),
    ("Customers", ("customers", "customerType", "customer_type")),
    ("Sensitive data", ("sensitiveData", "sensitive_data")),
    ("Regulated industry", ("regulated_industry", "regulatedIndustry")),
    ("GTM", ("gtm", "goToMarket", "go_to_market")),
)

_SEVERITY_ORDER: tuple[Severity, ...] = ("info", "low", "medium", "high", "critical")


def format_startup_profile_context(profile: dict[str, Any] | None) -> str:
    """Return bounded profile context for scanner prompts."""

    items = profile_context_items(profile)
    if not items:
        return ""
    lines = [
        "Startup profile context:",
        "Use this profile only to focus and prioritize review.",
        "Do not invent repository facts, legal duties, files, or line numbers from this profile alone.",
        "Findings still require concrete repository evidence.",
    ]
    lines.extend(f"- {label}: {value}" for label, value in items)
    return "\n".join(lines)


def profile_context_items(profile: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not profile:
        return []
    items: list[tuple[str, str]] = []
    for label, aliases in _PROFILE_FIELDS:
        value = _first_profile_value(profile, aliases)
        if value:
            items.append((label, value))
    return items


def adjust_findings_for_profile(findings: list[Finding], profile: dict[str, Any] | None) -> list[Finding]:
    """Raise severity by one bounded step when startup profile materially increases exposure."""

    if not profile_context_items(profile):
        return findings

    adjusted: list[Finding] = []
    for finding in findings:
        reason = _profile_boost_reason(finding, profile)
        if reason is None:
            adjusted.append(finding)
            continue
        boosted = _boost_severity(finding.severity)
        if boosted == finding.severity:
            adjusted.append(finding)
            continue
        description = finding.description
        if "Startup profile priority:" not in description:
            description = (
                f"{description} Startup profile priority: severity raised from "
                f"{finding.severity} to {boosted} because {reason}."
            )[:900]
        adjusted.append(finding.model_copy(update={"severity": boosted, "description": description}))
    return adjusted


def _first_profile_value(profile: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
    for key in aliases:
        if key in profile:
            value = _sanitize_profile_value(profile[key])
            if value:
                return value
    return None


def _sanitize_profile_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, (list, tuple, set)):
        pieces = [
            _sanitize_profile_value(item)
            for item in value
            if not isinstance(item, (dict, list, tuple, set))
        ]
        text = ", ".join(piece for piece in pieces if piece)
    elif isinstance(value, dict):
        return None
    else:
        text = str(value)
    text = " ".join(text.replace("\n", " ").replace("\r", " ").replace("\t", " ").split())
    if not text:
        return None
    return text[:_MAX_PROFILE_VALUE_CHARS]


def _boost_severity(severity: Severity) -> Severity:
    if severity in {"info", "critical"}:
        return severity
    index = _SEVERITY_ORDER.index(severity)
    return _SEVERITY_ORDER[index + 1]


def _profile_boost_reason(finding: Finding, profile: dict[str, Any] | None) -> str | None:
    profile_text = _profile_text(profile)
    if not profile_text:
        return None
    finding_text = _finding_text(finding)
    finding_tags = _finding_tags(finding)

    if _has(profile_text, {"health", "healthcare", "medical", "patient", "patients", "phi", "hipaa", "clinical"}) and _finding_matches(
        finding_text,
        finding_tags,
        categories={
            "privacy",
            "analytics_privacy",
            "data_privacy",
            "pii_data_flow",
            "access_control",
            "auth_access_control",
            "secret_exposure",
            "secret_scanner",
            "legal",
            "legal_docs",
            "security_controls",
            "code_compliance",
        },
        terms={"health", "medical", "patient", "phi", "privacy", "personal", "tracking", "auth", "access", "secret", "security", "policy"},
    ):
        return "the startup profile indicates healthcare or health/PHI exposure"

    if _has(profile_text, {"fintech", "finance", "financial", "payment", "payments", "bank", "banking", "card", "cards", "pci", "kyc", "aml"}) and _finding_matches(
        finding_text,
        finding_tags,
        categories={
            "financial_compliance",
            "privacy",
            "analytics_privacy",
            "data_privacy",
            "pii_data_flow",
            "access_control",
            "auth_access_control",
            "secret_exposure",
            "secret_scanner",
            "security_controls",
            "code_compliance",
        },
        terms={"payment", "financial", "card", "bank", "privacy", "personal", "tracking", "audit", "auth", "access", "secret", "security"},
    ):
        return "the startup profile indicates fintech, payment, or financial-data exposure"

    if _has(profile_text, {"edtech", "education", "student", "students", "school", "children", "child", "minor", "minors", "ferpa", "coppa"}) and _finding_matches(
        finding_text,
        finding_tags,
        categories={
            "privacy",
            "analytics_privacy",
            "data_privacy",
            "pii_data_flow",
            "legal",
            "legal_docs",
            "access_control",
            "auth_access_control",
            "code_compliance",
        },
        terms={"student", "child", "minor", "education", "privacy", "personal", "tracking", "auth", "access", "policy"},
    ):
        return "the startup profile indicates education, student, or child-data exposure"

    if _has(profile_text, {"ai", "ml", "llm", "model", "models", "training", "automated", "decisioning", "generative"}) and _finding_matches(
        finding_text,
        finding_tags,
        categories={"ai_governance", "privacy", "data_privacy", "pii_data_flow", "code_compliance", "custom_compliance"},
        terms={"model", "training", "automated", "decisioning", "retention", "privacy", "personal", "prompt"},
    ):
        return "the startup profile indicates AI/ML or automated-decisioning exposure"

    if _has(profile_text, {"enterprise", "b2b", "mid", "market", "midmarket", "sales", "procurement", "soc2", "soc"}) and _finding_matches(
        finding_text,
        finding_tags,
        categories={
            "access_control",
            "auth_access_control",
            "secret_exposure",
            "secret_scanner",
            "cicd_security",
            "error_disclosure",
            "repository_hygiene",
            "security_controls",
            "static_hygiene",
        },
        terms={"security", "vulnerability", "disclosure", "auth", "access", "secret", "cicd", "ci", "debug", "enterprise", "soc"},
    ):
        return "the startup profile indicates enterprise, B2B, or sales-led customer exposure"

    return None


def _profile_text(profile: dict[str, Any] | None) -> str:
    items = profile_context_items(profile)
    return _normalize_text(" ".join(value for _, value in items))


def _finding_text(finding: Finding) -> str:
    parts = [
        finding.title,
        finding.description,
        finding.category,
        finding.recommendation,
        finding.scanner_id,
    ]
    for evidence in finding.evidence:
        parts.append(evidence.description)
        if evidence.excerpt:
            parts.append(evidence.excerpt)
    return _normalize_text(" ".join(parts))


def _finding_tags(finding: Finding) -> set[str]:
    values = {finding.category.lower(), finding.scanner_id.lower()}
    values.update(_tokens(finding.category))
    values.update(_tokens(finding.scanner_id))
    return values


def _finding_matches(
    finding_text: str,
    finding_tags: set[str],
    *,
    categories: set[str],
    terms: set[str],
) -> bool:
    return bool(categories & finding_tags) or _has(finding_text, terms)


def _has(text: str, terms: set[str]) -> bool:
    tokens = _tokens(text)
    return bool(tokens & terms)


def _tokens(text: str) -> set[str]:
    return set(_normalize_text(text).split())


def _normalize_text(text: str) -> str:
    return "".join(char.lower() if char.isalnum() else " " for char in text)
