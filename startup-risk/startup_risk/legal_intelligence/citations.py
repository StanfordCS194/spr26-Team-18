from __future__ import annotations

from startup_risk.legal_intelligence.models import LegalGuidanceRule
from startup_risk.legal_intelligence.public_sources import verify_citation_with_courtlistener


def verify_guidance_citations(
    rules: list[LegalGuidanceRule],
    *,
    lookup=verify_citation_with_courtlistener,
) -> list[LegalGuidanceRule]:
    """Verify or downgrade rules based on citation support."""

    verified: list[LegalGuidanceRule] = []
    for rule in rules:
        has_source = any(citation.url or citation.citation for citation in rule.citations)
        citation_ok = False
        for citation in rule.citations:
            if citation.url:
                citation_ok = True
                break
            if citation.citation:
                try:
                    citation_ok = bool(lookup(citation.citation))
                except Exception:
                    citation_ok = False
                if citation_ok:
                    break

        updates = {"citation_verified": citation_ok}
        if not has_source or not citation_ok:
            updates["confidence"] = "low"
        verified.append(rule.model_copy(update=updates))
    return verified
