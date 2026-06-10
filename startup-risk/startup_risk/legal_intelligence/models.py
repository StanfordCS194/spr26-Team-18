from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from startup_risk.core.models import LegalCitation


AuthorityType = Literal[
    "statute",
    "bill",
    "regulation",
    "agency_guidance",
    "agency_decision",
    "enforcement_action",
    "court_decision",
    "other",
]
GuidanceConfidence = Literal["low", "medium", "high"]
ReviewStatus = Literal["pending", "approved", "rejected"]

SCANNER_CATEGORIES = frozenset(
    {
        "privacy",
        "financial_compliance",
        "employment_payroll",
        "security_controls",
        "licensing",
        "consumer_protection",
        "healthcare",
        "ai_data_governance",
        "legal",
        "compliance",
    }
)


class LegalAuthority(BaseModel):
    """Normalized source material for legal-intelligence distillation."""

    source_id: str
    title: str
    authority_type: AuthorityType
    jurisdiction: str
    topic: str
    source_text: str
    citation: str | None = None
    url: str | None = None
    effective_date: date | None = None
    content_hash: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    last_checked: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_id", "title", "jurisdiction", "topic", "source_text")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class LegalGuidanceRule(BaseModel):
    """Scanner-ready legal guidance distilled from one legal authority."""

    id: str
    authority_id: str
    category: str
    title: str
    legal_basis: str
    risk_signal: str
    detection_hints: list[str] = Field(default_factory=list)
    finding_rationale: str
    recommendation: str
    citations: list[LegalCitation]
    confidence: GuidanceConfidence = "low"
    source_interpretation: bool = True
    enabled: bool = True
    review_status: ReviewStatus = "pending"
    last_distilled: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_hash: str | None = None
    citation_verified: bool = False
    industry_tags: list[str] = Field(default_factory=list)
    scanner_categories: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in SCANNER_CATEGORIES:
            return "compliance"
        return normalized


class LegalSourceQuery(BaseModel):
    """Saved public-source query used by legal-refresh/legal-pipeline."""

    id: str
    source: str
    query: str
    topic: str = "compliance"
    jurisdiction: str = "US"
    industry_tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=10000)
    enabled: bool = True
    last_checked: datetime | None = None
    fetched_count: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
