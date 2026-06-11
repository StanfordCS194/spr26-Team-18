from __future__ import annotations

from startup_risk.core.models import Finding, LegalFindingContext, ScannerLegalGuidance
from startup_risk.legal_intelligence.models import LegalGuidanceRule


_CATEGORY_ALIASES: dict[str, set[str]] = {
    "privacy": {"privacy", "analytics_privacy", "pii_data_flow", "data_privacy", "code_compliance"},
    "financial_compliance": {"financial_compliance"},
    "employment_payroll": {"financial_compliance", "legal"},
    "security_controls": {
        "secrets",
        "secret",
        "auth_access_control",
        "access_control",
        "infra_misconfig",
        "infrastructure",
        "cicd_security",
        "rate_limit",
        "rate_limiting",
        "error_disclosure",
        "code_compliance",
    },
    "licensing": {"license", "license_risk", "legal"},
    "consumer_protection": {"legal", "code_compliance", "analytics_privacy"},
    "healthcare": {"privacy", "pii_data_flow", "code_compliance"},
    "ai_data_governance": {"privacy", "pii_data_flow", "code_compliance", "custom_compliance"},
    "legal": {"legal", "legal_docs"},
    "compliance": {"code_compliance", "custom_compliance", "legal", "financial_compliance"},
}


class LegalGuidanceIndex:
    """In-memory matcher from scanner findings to distilled legal guidance."""

    def __init__(self, rules: list[LegalGuidanceRule], *, profile: dict | None = None) -> None:
        self.profile = profile or {}
        profile_tags = _profile_tags(profile)
        self.rules = [
            rule
            for rule in rules
            if rule.enabled
            and rule.review_status != "rejected"
            and _rule_matches_profile(rule, profile_tags)
        ]

    def guidance_for_scanner(
        self,
        *,
        scanner_id: str,
        scanner_category: str | None = None,
        scanner_name: str | None = None,
        limit: int = 5,
    ) -> list[ScannerLegalGuidance]:
        """Return bounded legal guidance for a scanner before it emits findings."""

        scanner_values = {
            value.lower()
            for value in (scanner_id, scanner_category, scanner_name)
            if value
        }
        haystack = " ".join(scanner_values)
        scored: list[tuple[int, LegalGuidanceRule]] = []
        for rule in self.rules:
            score = _scanner_category_score(rule, scanner_values)
            score += _keyword_score(rule, haystack)
            if score > 0:
                scored.append((score, rule))

        return [
            _scanner_guidance_from_rule(rule)
            for _, rule in sorted(scored, key=lambda item: (-item[0], item[1].id))[:limit]
        ]

    def match_finding(self, finding: Finding, *, limit: int = 3) -> list[LegalFindingContext]:
        scored: list[tuple[int, LegalGuidanceRule]] = []
        haystack = _finding_text(finding)
        for rule in self.rules:
            score = _category_score(rule, finding)
            score += _keyword_score(rule, haystack)
            if score > 0:
                scored.append((score, rule))

        contexts: list[LegalFindingContext] = []
        for _, rule in sorted(scored, key=lambda item: (-item[0], item[1].id))[:limit]:
            contexts.append(
                LegalFindingContext(
                    rule_id=rule.id,
                    legal_basis=rule.legal_basis,
                    why_it_matters=rule.finding_rationale,
                    citations=rule.citations,
                    confidence=rule.confidence,
                    source_interpretation=rule.source_interpretation,
                )
            )
        return contexts


def enrich_findings(findings: list[Finding], index: LegalGuidanceIndex) -> list[Finding]:
    """Attach legal context to findings while preserving scanner evidence."""

    enriched: list[Finding] = []
    for finding in findings:
        contexts = index.match_finding(finding)
        if contexts:
            finding = finding.model_copy(update={"legal_context": contexts})
        enriched.append(finding)
    return enriched


def _category_score(rule: LegalGuidanceRule, finding: Finding) -> int:
    aliases = _CATEGORY_ALIASES.get(rule.category, {rule.category})
    finding_values = {finding.category.lower(), finding.scanner_id.lower()}
    return 8 if aliases & finding_values else 0


def _scanner_category_score(rule: LegalGuidanceRule, scanner_values: set[str]) -> int:
    aliases = _CATEGORY_ALIASES.get(rule.category, {rule.category})
    score = 8 if aliases & scanner_values else 0
    for category in rule.scanner_categories:
        normalized = category.lower()
        category_aliases = _CATEGORY_ALIASES.get(normalized, {normalized})
        if category_aliases & scanner_values:
            score += 8
    return min(score, 12)


def _keyword_score(rule: LegalGuidanceRule, haystack: str) -> int:
    terms = [rule.title, rule.risk_signal, rule.legal_basis, *rule.detection_hints]
    score = 0
    for term in terms:
        for token in _tokens(term):
            if token in haystack:
                score += 1
    return min(score, 8)


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
    return " ".join(parts).lower()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in text).split()
        if len(token) >= 5
    }


def _profile_tags(profile: dict | None) -> set[str]:
    if not profile:
        return set()
    values = [
        profile.get("industry"),
        profile.get("industryProductType"),
        profile.get("productType"),
        profile.get("customerType"),
        profile.get("goToMarket"),
    ]
    return {
        token
        for value in values
        for token in _tokens(str(value or ""))
    }


def _rule_matches_profile(rule: LegalGuidanceRule, profile_tags: set[str]) -> bool:
    if not profile_tags or not rule.industry_tags:
        return True
    rule_tags = {tag.lower() for tag in rule.industry_tags}
    return bool(rule_tags & profile_tags)


def _scanner_guidance_from_rule(rule: LegalGuidanceRule) -> ScannerLegalGuidance:
    return ScannerLegalGuidance(
        rule_id=rule.id,
        category=rule.category,
        title=rule.title[:160],
        legal_basis=rule.legal_basis[:700],
        risk_signal=rule.risk_signal[:500],
        detection_hints=[hint[:180] for hint in rule.detection_hints[:6]],
        recommendation=rule.recommendation[:300],
        citations=rule.citations[:3],
        confidence=rule.confidence,
        source_interpretation=rule.source_interpretation,
    )
