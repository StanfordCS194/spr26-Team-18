from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from startup_risk.legal_intelligence.citations import verify_guidance_citations
from startup_risk.legal_intelligence.distill import distill_legal_guidance
from startup_risk.legal_intelligence.bulk_sources import import_bulk_legal_authorities
from startup_risk.legal_intelligence.bulk_sync import sync_bulk_source_preset
from startup_risk.legal_intelligence.models import LegalAuthority, LegalSourceQuery
from startup_risk.legal_intelligence.public_sources import fetch_public_legal_authorities
from startup_risk.legal_intelligence.store import LegalIntelligenceStore


@dataclass(frozen=True)
class RefreshResult:
    fetched_count: int
    changed_count: int
    errors: dict[str, str]
    changed_authorities: list[LegalAuthority]


def legal_source_query_id(source: str, query: str, topic: str, jurisdiction: str) -> str:
    digest = hashlib.sha256(f"{source}:{query}:{topic}:{jurisdiction}".encode("utf-8")).hexdigest()[:10]
    return f"legal-source.{digest}"


def make_source_query(
    *,
    source: str,
    query: str,
    topic: str = "compliance",
    jurisdiction: str = "US",
    industry_tags: list[str] | None = None,
    limit: int = 10,
) -> LegalSourceQuery:
    return LegalSourceQuery(
        id=legal_source_query_id(source, query, topic, jurisdiction),
        source=source,
        query=query,
        topic=topic,
        jurisdiction=jurisdiction,
        industry_tags=industry_tags or [],
        limit=limit,
    )


def refresh_legal_sources(
    store: LegalIntelligenceStore,
    *,
    fetcher=fetch_public_legal_authorities,
    only_enabled: bool = True,
) -> RefreshResult:
    queries = store.load_source_queries()
    changed: list[LegalAuthority] = []
    errors: dict[str, str] = {}
    fetched_count = 0
    now = datetime.now(timezone.utc)
    updated_queries: list[LegalSourceQuery] = []

    for query in queries:
        if only_enabled and not query.enabled:
            updated_queries.append(query)
            continue
        try:
            if query.source == "bulk":
                authorities = import_bulk_legal_authorities(
                    location=query.query,
                    source="bulk",
                    topic=query.topic,
                    jurisdiction=query.jurisdiction,
                    industry_tags=query.industry_tags,
                    limit=query.limit,
                )
            elif query.source == "bulk_sync":
                sync = sync_bulk_source_preset(query.query, limit=query.limit)
                authorities = sync.authorities
            else:
                authorities = fetcher(
                    source=query.source,
                    query=query.query,
                    limit=query.limit,
                    topic=query.topic,
                    jurisdiction=query.jurisdiction,
                )
            authorities = [
                authority.model_copy(
                    update={
                        "metadata": {
                            **authority.metadata,
                            "source_query_id": query.id,
                            "industry_tags": query.industry_tags,
                        }
                    }
                )
                for authority in authorities
            ]
            fetched_count += len(authorities)
            changed.extend(store.upsert_authorities(authorities))
            updated_queries.append(
                query.model_copy(
                    update={
                        "last_checked": now,
                        "fetched_count": len(authorities),
                        "last_error": None,
                    }
                )
            )
        except Exception as exc:
            errors[query.id] = str(exc)
            updated_queries.append(
                query.model_copy(
                    update={
                        "last_checked": now,
                        "last_error": str(exc),
                    }
                )
            )

    store.save_source_queries(updated_queries)
    return RefreshResult(
        fetched_count=fetched_count,
        changed_count=len(changed),
        errors=errors,
        changed_authorities=changed,
    )


def run_legal_pipeline(
    store: LegalIntelligenceStore,
    *,
    provider: str | None = None,
    model: str | None = None,
    batch_provider=None,
    changed_only: bool = True,
    verify_citations: bool = True,
) -> dict:
    refresh = refresh_legal_sources(store)
    authorities = refresh.changed_authorities if changed_only else store.load_authorities()
    rules = distill_legal_guidance(
        authorities,
        provider=provider,
        model=model,
        batch_provider=batch_provider,
    )
    if verify_citations:
        rules = verify_guidance_citations(rules)
    store.append_rules(rules)
    return {
        "fetched_count": refresh.fetched_count,
        "changed_count": refresh.changed_count,
        "rule_count": len(rules),
        "errors": refresh.errors,
    }
