from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Priority = Literal["low", "medium", "high"]
Confidence = Literal["low", "medium", "high"]
FindingStatus = Literal["not_flagged", "needs_more_info", "review_recommended"]


@dataclass(frozen=True)
class Evidence:
    """A source-backed product fact extracted from a PRD."""

    label: str
    snippet: str
    source: str | None = None


@dataclass
class ProductRiskProfile:
    """Structured product facts used by compliance rules.

    These fields are intentionally factual. They should not encode legal
    conclusions like "HIPAA applies"; those belong in rule findings.
    """

    target_users: list[str] = field(default_factory=list)
    minimum_age: int | None = None
    likely_minors: bool | None = None
    child_directed: bool | None = None
    data_collected: list[str] = field(default_factory=list)
    sensitive_data: list[str] = field(default_factory=list)
    health_data: bool | None = None
    healthcare_context: bool | None = None
    user_generated_content: bool | None = None
    messaging: bool | None = None
    ads_or_tracking: bool | None = None
    geolocation: bool | None = None
    biometric_data: bool | None = None
    education_context: bool | None = None
    payment_or_financial_data: bool | None = None
    adult_content: bool | None = None
    social_or_recommendation_features: bool | None = None
    jurisdictions_mentioned: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class ComplianceRule:
    id: str
    name: str
    priority: Priority
    description: str
    review_questions: tuple[str, ...]
    suggested_controls: tuple[str, ...]


@dataclass
class ComplianceFinding:
    rule_id: str
    name: str
    status: FindingStatus
    priority: Priority
    confidence: Confidence
    rationale: str
    evidence: list[Evidence] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    suggested_controls: list[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    profile: ProductRiskProfile
    findings: list[ComplianceFinding]

    def flagged_findings(self) -> list[ComplianceFinding]:
        return [finding for finding in self.findings if finding.status != "not_flagged"]
