from __future__ import annotations

from startup_risk.legal_intelligence.models import LegalSourceQuery
from startup_risk.legal_intelligence.source_catalog import public_source_presets_for_industry


def source_queries_for_profile(profile: dict | None, *, limit: int = 10) -> list[LegalSourceQuery]:
    industry = _industry_from_profile(profile)
    presets = public_source_presets_for_industry(industry) or public_source_presets_for_industry("tech")
    return [preset.to_source_query().model_copy(update={"limit": limit}) for preset in presets]


def _industry_from_profile(profile: dict | None) -> str:
    if not profile:
        return "tech"
    raw = str(
        profile.get("industry")
        or profile.get("industryProductType")
        or profile.get("productType")
        or profile.get("stage")
        or "tech"
    ).lower()
    if "fin" in raw or "bank" in raw or "payment" in raw:
        return "fintech"
    if "health" in raw or "medical" in raw or "patient" in raw:
        return "healthcare"
    if "employee" in raw or "payroll" in raw or "hr" in raw:
        return "employment"
    if "ai" in raw or "artificial" in raw or "machine learning" in raw:
        return "ai"
    known = {"finance", "fintech", "healthcare", "employment", "payroll", "ai", "tech"}
    return raw if raw in known else "tech"
