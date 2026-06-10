"""Legal intelligence pipeline for scanner guidance."""

from startup_risk.legal_intelligence.distill import distill_legal_guidance
from startup_risk.legal_intelligence.enrich import LegalGuidanceIndex, enrich_findings
from startup_risk.legal_intelligence.ingest import normalize_authority
from startup_risk.legal_intelligence.pipeline import (
    legal_source_query_id,
    make_source_query,
    refresh_legal_sources,
    run_legal_pipeline,
)
from startup_risk.legal_intelligence.profile import source_queries_for_profile
from startup_risk.legal_intelligence.citations import verify_guidance_citations
from startup_risk.legal_intelligence.bulk_sources import import_bulk_legal_authorities
from startup_risk.legal_intelligence.bulk_sync import (
    BulkSyncResult,
    discover_bulk_locations,
    sync_bulk_source_preset,
    sync_bulk_legal_authorities,
)
from startup_risk.legal_intelligence.source_catalog import (
    BULK_SOURCE_PRESETS,
    PUBLIC_SOURCE_PRESETS,
    all_source_presets,
    bulk_source_presets_for_industry,
    get_bulk_source_preset,
    public_source_presets_for_industry,
)
from startup_risk.legal_intelligence.models import (
    LegalAuthority,
    LegalGuidanceRule,
    LegalSourceQuery,
)
from startup_risk.legal_intelligence.public_sources import fetch_public_legal_authorities
from startup_risk.core.models import LegalCitation, LegalFindingContext
from startup_risk.legal_intelligence.store import LegalIntelligenceStore

__all__ = [
    "LegalAuthority",
    "LegalCitation",
    "LegalFindingContext",
    "LegalGuidanceIndex",
    "LegalGuidanceRule",
    "LegalSourceQuery",
    "LegalIntelligenceStore",
    "BulkSyncResult",
    "BULK_SOURCE_PRESETS",
    "PUBLIC_SOURCE_PRESETS",
    "all_source_presets",
    "bulk_source_presets_for_industry",
    "discover_bulk_locations",
    "distill_legal_guidance",
    "fetch_public_legal_authorities",
    "get_bulk_source_preset",
    "import_bulk_legal_authorities",
    "enrich_findings",
    "legal_source_query_id",
    "make_source_query",
    "normalize_authority",
    "refresh_legal_sources",
    "run_legal_pipeline",
    "source_queries_for_profile",
    "public_source_presets_for_industry",
    "sync_bulk_source_preset",
    "sync_bulk_legal_authorities",
    "verify_guidance_citations",
]
