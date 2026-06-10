from __future__ import annotations

from dataclasses import asdict, dataclass

from startup_risk.legal_intelligence.models import LegalSourceQuery


@dataclass(frozen=True)
class PublicSourcePreset:
    id: str
    label: str
    source: str
    query: str
    topic: str
    jurisdiction: str = "US"
    industry_tags: tuple[str, ...] = ()
    limit: int = 10
    description: str = ""

    def to_source_query(self) -> LegalSourceQuery:
        return LegalSourceQuery(
            id=f"catalog.{self.id}",
            source=self.source,
            query=self.query,
            topic=self.topic,
            jurisdiction=self.jurisdiction,
            industry_tags=list(self.industry_tags),
            limit=self.limit,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BulkSourcePreset:
    id: str
    label: str
    source: str
    dataset: str
    topic: str
    jurisdiction: str = "US"
    industry_tags: tuple[str, ...] = ()
    query_filter: str | None = None
    limit: int = 500
    max_files: int = 8
    max_depth: int = 3
    bulk_base_url: str | None = None
    description: str = ""

    def to_source_query(self) -> LegalSourceQuery:
        return LegalSourceQuery(
            id=f"catalog.{self.id}",
            source="bulk_sync",
            query=self.id,
            topic=self.topic,
            jurisdiction=self.jurisdiction,
            industry_tags=list(self.industry_tags),
            limit=self.limit,
        )

    def to_dict(self) -> dict:
        return asdict(self)


FREE_LAW_BULK_ROOT = "https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/?list-type=2&prefix=bulk-data/"


PUBLIC_SOURCE_PRESETS: tuple[PublicSourcePreset, ...] = (
    PublicSourcePreset(
        id="ftc_privacy_security",
        label="FTC privacy and data security",
        source="ftc",
        query="data security privacy enforcement",
        topic="privacy",
        industry_tags=("tech", "fintech", "ai"),
        description="FTC enforcement/guidance feed for privacy and security obligations.",
    ),
    PublicSourcePreset(
        id="cfpb_fintech",
        label="CFPB fintech and consumer finance",
        source="cfpb",
        query="consumer finance privacy data security",
        topic="financial_compliance",
        industry_tags=("finance", "fintech"),
        description="CFPB consumer-finance feed for fintech risk signals.",
    ),
    PublicSourcePreset(
        id="sec_cybersecurity",
        label="SEC cybersecurity and disclosure",
        source="sec",
        query="cybersecurity disclosure enforcement",
        topic="financial_compliance",
        industry_tags=("finance", "fintech"),
        description="SEC public releases for cybersecurity and disclosure issues.",
    ),
    PublicSourcePreset(
        id="hhs_ocr_hipaa",
        label="HHS OCR HIPAA privacy and security",
        source="hhs_ocr",
        query="HIPAA privacy security enforcement",
        topic="healthcare",
        industry_tags=("healthcare",),
        description="HHS OCR public releases for HIPAA/privacy/security signals.",
    ),
    PublicSourcePreset(
        id="dol_payroll_classification",
        label="DOL payroll and worker classification",
        source="dol",
        query="employee classification payroll wage hour",
        topic="employment_payroll",
        industry_tags=("employment", "payroll"),
        description="DOL releases for wage, hour, payroll, and worker-classification issues.",
    ),
    PublicSourcePreset(
        id="eeoc_employment",
        label="EEOC employment compliance",
        source="eeoc",
        query="employment discrimination accommodation",
        topic="employment_payroll",
        industry_tags=("employment", "payroll"),
        description="EEOC releases for employment and accommodation risk signals.",
    ),
    PublicSourcePreset(
        id="irs_payroll_tax",
        label="IRS payroll and tax compliance",
        source="irs",
        query="payroll tax contractor employee",
        topic="employment_payroll",
        industry_tags=("employment", "payroll", "finance"),
        description="IRS feed for payroll and tax compliance signals.",
    ),
    PublicSourcePreset(
        id="federal_register_ai_privacy",
        label="Federal Register AI and privacy",
        source="federal_register",
        query="artificial intelligence privacy cybersecurity",
        topic="ai_data_governance",
        industry_tags=("ai", "tech"),
        description="Federal Register API query for AI, privacy, and cybersecurity rulemaking.",
    ),
    PublicSourcePreset(
        id="regulations_gov_privacy_security",
        label="Regulations.gov privacy and security dockets",
        source="regulations_gov",
        query="privacy cybersecurity data security",
        topic="privacy",
        industry_tags=("tech", "fintech", "healthcare", "ai"),
        description="Regulations.gov query for proposed rules and docket documents.",
    ),
)


BULK_SOURCE_PRESETS: tuple[BulkSourcePreset, ...] = (
    BulkSourcePreset(
        id="govinfo_cfr",
        label="GovInfo CFR bulk",
        source="govinfo",
        dataset="CFR",
        topic="compliance",
        description="Codified federal regulations from GovInfo bulk data.",
        max_depth=4,
    ),
    BulkSourcePreset(
        id="govinfo_fr",
        label="GovInfo Federal Register bulk",
        source="govinfo",
        dataset="FR",
        topic="compliance",
        description="Federal Register bulk documents from GovInfo.",
        max_depth=4,
    ),
    BulkSourcePreset(
        id="govinfo_uscode",
        label="GovInfo U.S. Code bulk",
        source="govinfo",
        dataset="USCODE",
        topic="compliance",
        description="U.S. Code package bulk data from GovInfo.",
        max_depth=4,
    ),
    BulkSourcePreset(
        id="ecfr_financial_title_12",
        label="eCFR Title 12 banks and banking",
        source="ecfr",
        dataset="title-12",
        topic="financial_compliance",
        industry_tags=("finance", "fintech"),
        description="Current eCFR Title 12 XML for banks and banking.",
    ),
    BulkSourcePreset(
        id="ecfr_sec_title_17",
        label="eCFR Title 17 securities",
        source="ecfr",
        dataset="title-17",
        topic="financial_compliance",
        industry_tags=("finance", "fintech"),
        description="Current eCFR Title 17 XML for securities and commodities.",
    ),
    BulkSourcePreset(
        id="ecfr_ftc_title_16",
        label="eCFR Title 16 commercial practices",
        source="ecfr",
        dataset="title-16",
        topic="consumer_protection",
        industry_tags=("tech", "fintech", "ai"),
        description="Current eCFR Title 16 XML for commercial practices and FTC rules.",
    ),
    BulkSourcePreset(
        id="ecfr_health_title_21",
        label="eCFR Title 21 food and drugs",
        source="ecfr",
        dataset="title-21",
        topic="healthcare",
        industry_tags=("healthcare",),
        description="Current eCFR Title 21 XML for FDA-regulated products.",
    ),
    BulkSourcePreset(
        id="ecfr_hhs_title_45",
        label="eCFR Title 45 public welfare and HIPAA",
        source="ecfr",
        dataset="title-45",
        topic="healthcare",
        industry_tags=("healthcare",),
        query_filter="privacy security",
        description="Current eCFR Title 45 XML for HHS/public welfare rules, including HIPAA-related material.",
    ),
    BulkSourcePreset(
        id="ecfr_labor_title_29",
        label="eCFR Title 29 labor",
        source="ecfr",
        dataset="title-29",
        topic="employment_payroll",
        industry_tags=("employment", "payroll"),
        description="Current eCFR Title 29 XML for labor rules.",
    ),
    BulkSourcePreset(
        id="ecfr_tax_title_26",
        label="eCFR Title 26 internal revenue",
        source="ecfr",
        dataset="title-26",
        topic="employment_payroll",
        industry_tags=("employment", "payroll", "finance"),
        description="Current eCFR Title 26 XML for tax rules.",
    ),
    BulkSourcePreset(
        id="free_law_opinions",
        label="Free Law CourtListener opinions bulk",
        source="free_law",
        dataset="search_opinion",
        topic="compliance",
        bulk_base_url=FREE_LAW_BULK_ROOT,
        max_depth=0,
        max_files=2,
        limit=250,
        description="CourtListener/Free Law S3 bulk CSV snapshots for opinion text.",
    ),
    BulkSourcePreset(
        id="free_law_clusters",
        label="Free Law CourtListener opinion clusters bulk",
        source="free_law",
        dataset="search_opinioncluster",
        topic="compliance",
        bulk_base_url=FREE_LAW_BULK_ROOT,
        max_depth=0,
        max_files=2,
        limit=250,
        description="CourtListener/Free Law S3 bulk CSV snapshots for case metadata.",
    ),
)


def all_source_presets() -> dict:
    return {
        "public_sources": [preset.to_dict() for preset in PUBLIC_SOURCE_PRESETS],
        "bulk_sources": [preset.to_dict() for preset in BULK_SOURCE_PRESETS],
    }


def public_source_presets_for_industry(industry: str | None = None) -> list[PublicSourcePreset]:
    return _filter_presets(PUBLIC_SOURCE_PRESETS, industry)


def bulk_source_presets_for_industry(industry: str | None = None) -> list[BulkSourcePreset]:
    return _filter_presets(BULK_SOURCE_PRESETS, industry)


def get_bulk_source_preset(preset_id: str) -> BulkSourcePreset:
    for preset in BULK_SOURCE_PRESETS:
        if preset.id == preset_id:
            return preset
    raise KeyError(preset_id)


def _filter_presets(presets, industry: str | None):
    if not industry:
        return list(presets)
    normalized = industry.strip().lower()
    return [preset for preset in presets if not preset.industry_tags or normalized in preset.industry_tags]
