from __future__ import annotations

import json
import gzip
from pathlib import Path

import startup_risk.legal_intelligence.pipeline as pipeline_module
import startup_risk.legal_intelligence.public_sources as public_sources
from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    RepositorySource,
)
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.core.engine import ScanEngine
from startup_risk.legal_intelligence import (
    LegalGuidanceIndex,
    LegalIntelligenceStore,
    all_source_presets,
    discover_bulk_locations,
    distill_legal_guidance,
    import_bulk_legal_authorities,
    make_source_query,
    normalize_authority,
    refresh_legal_sources,
    sync_bulk_legal_authorities,
    verify_guidance_citations,
)
import startup_risk.legal_intelligence.bulk_sync as bulk_sync
from startup_risk.legal_intelligence.models import LegalAuthority, LegalCitation, LegalGuidanceRule
from startup_risk.scanners.license_scanner.models import LLMBatchResponse


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MockLegalBatchProvider:
    name = "mock-legal-batch"

    def __init__(self) -> None:
        self.calls = []

    def submit_and_wait(self, tasks, *, timeout_seconds: int, poll_interval_seconds: int):
        self.calls.append(
            {
                "tasks": tasks,
                "timeout_seconds": timeout_seconds,
                "poll_interval_seconds": poll_interval_seconds,
            }
        )
        return [
            LLMBatchResponse(
                task.task_id,
                json.dumps(
                    {
                        "rules": [
                            {
                                "category": "privacy",
                                "title": "Consumer privacy notice required",
                                "legal_basis": "The authority requires notice before collecting consumer data.",
                                "risk_signal": "Repositories collecting personal data should expose a privacy notice.",
                                "detection_hints": ["privacy policy", "personal data collection"],
                                "finding_rationale": "Missing notices can make data collection legally risky.",
                                "recommendation": "Publish a clear privacy notice near collection points.",
                                "confidence": "high",
                            }
                        ]
                    }
                ),
            )
            for task in tasks
        ]


class PrivacyFindingScanner:
    id = "legal_docs"
    name = "Privacy Finding Scanner"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        return [
            Finding(
                id="legal_docs.missing_privacy",
                title="No Privacy Policy detected",
                description="No Privacy Policy was detected in this repository.",
                category="legal",
                severity="high",
                confidence="low",
                evidence=[FindingEvidence(description="No matching privacy route was found.")],
                recommendation="Create a Privacy Policy.",
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]


def test_legal_source_normalization_preserves_citation_and_metadata():
    authority = normalize_authority(
        {
            "title": "Example Agency Privacy Guidance",
            "type": "agency guidance",
            "jurisdiction": "CA",
            "topic": "privacy",
            "citation": "Example Guidance § 1",
            "url": "https://example.test/guidance",
            "effective_date": "2025-01-15",
            "text": "Businesses should provide notice before collecting personal information.",
        }
    )

    assert authority.authority_type == "agency_guidance"
    assert authority.citation == "Example Guidance § 1"
    assert authority.effective_date.isoformat() == "2025-01-15"
    assert authority.source_id.startswith("legal-")


def test_legal_guidance_distillation_uses_batch_provider_and_preserves_citation():
    authority = normalize_authority(
        {
            "source_id": "ca-privacy-guidance",
            "title": "Example Agency Privacy Guidance",
            "type": "agency guidance",
            "jurisdiction": "CA",
            "topic": "privacy",
            "citation": "Example Guidance § 1",
            "text": "Businesses should provide notice before collecting personal information.",
        }
    )
    provider = MockLegalBatchProvider()

    rules = distill_legal_guidance(
        [authority],
        batch_provider=provider,
        timeout_seconds=10,
        poll_interval_seconds=0,
    )

    assert len(rules) == 1
    assert rules[0].category == "privacy"
    assert rules[0].citations[0].citation == "Example Guidance § 1"
    assert provider.calls[0]["tasks"][0].task_id == "legal-guidance-ca-privacy-guidance"


def test_legal_store_round_trips_authorities_and_rules(tmp_path):
    store = LegalIntelligenceStore(tmp_path)
    authority = normalize_authority(
        {
            "source_id": "rule-source",
            "title": "Rule Source",
            "type": "regulation",
            "jurisdiction": "US",
            "topic": "security_controls",
            "text": "A control must be implemented.",
        }
    )
    rule = LegalGuidanceRule(
        id="legal_guidance.test",
        authority_id=authority.source_id,
        category="security_controls",
        title="Access control required",
        legal_basis="A control must be implemented.",
        risk_signal="Missing access controls.",
        detection_hints=["access control"],
        finding_rationale="Access control gaps can violate the authority.",
        recommendation="Add access controls.",
        citations=[
            LegalCitation(
                title=authority.title,
                authority_type=authority.authority_type,
                jurisdiction=authority.jurisdiction,
            )
        ],
        confidence="medium",
    )

    store.save_authorities([authority])
    store.save_rules([rule])

    assert store.load_authorities()[0].source_id == "rule-source"
    assert store.load_rules()[0].citations[0].title == "Rule Source"


def test_scan_engine_enriches_findings_without_changing_scanner_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    rule = LegalGuidanceRule(
        id="legal_guidance.privacy_notice",
        authority_id="ca-privacy-guidance",
        category="privacy",
        title="Consumer privacy notice required",
        legal_basis="The authority requires notice before collecting consumer data.",
        risk_signal="privacy policy personal data",
        detection_hints=["privacy policy"],
        finding_rationale="Missing notices can make data collection legally risky.",
        recommendation="Publish a clear privacy notice.",
        citations=[
            LegalCitation(
                title="Example Agency Privacy Guidance",
                citation="Example Guidance § 1",
                authority_type="agency_guidance",
                jurisdiction="CA",
            )
        ],
        confidence="high",
    )

    result = ScanEngine(
        ingestor=RepositoryIngestor(),
        scanners=[PrivacyFindingScanner()],
        legal_guidance_index=LegalGuidanceIndex([rule]),
    ).scan(str(repo))

    finding = result.findings[0]
    assert finding.evidence[0].description == "No matching privacy route was found."
    assert finding.legal_context[0].citations[0].citation == "Example Guidance § 1"
    assert finding.legal_context[0].source_interpretation is True


def test_federal_register_fetch_normalizes_public_api_results(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url.startswith("https://www.federalregister.gov/api/v1/documents.json?")
        return FakeHTTPResponse(
            {
                "results": [
                    {
                        "document_number": "2026-12345",
                        "title": "Privacy Rule",
                        "type": "Rule",
                        "citation": "91 FR 12345",
                        "html_url": "https://www.federalregister.gov/documents/2026/01/01/privacy-rule",
                        "publication_date": "2026-01-01",
                        "abstract": "This rule addresses consumer privacy notices.",
                        "agencies": [{"name": "Example Agency"}],
                    }
                ]
            }
        )

    monkeypatch.setattr(public_sources.request, "urlopen", fake_urlopen)

    authorities = public_sources.fetch_federal_register_documents(
        query="privacy",
        topic="privacy",
        limit=1,
    )

    assert authorities[0].source_id == "federal-register-2026-12345"
    assert authorities[0].authority_type == "regulation"
    assert authorities[0].citation == "91 FR 12345"
    assert "consumer privacy notices" in authorities[0].source_text


def test_courtlistener_fetch_normalizes_public_api_results(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url.startswith("https://www.courtlistener.com/api/rest/v4/search/?")
        return FakeHTTPResponse(
            {
                "results": [
                    {
                        "opinion_id": 42,
                        "caseName": "Example v. Privacy Co.",
                        "citation": ["123 F.4th 456"],
                        "absolute_url": "/opinion/42/example/",
                        "dateFiled": "2025-02-03",
                        "snippet": "<b>Privacy</b> notice obligations were discussed.",
                        "court": "ca9",
                    }
                ]
            }
        )

    monkeypatch.setattr(public_sources.request, "urlopen", fake_urlopen)

    authorities = public_sources.fetch_courtlistener_opinions(
        query="privacy notice",
        topic="privacy",
        limit=1,
    )

    assert authorities[0].source_id == "courtlistener-42"
    assert authorities[0].authority_type == "court_decision"
    assert authorities[0].citation == "123 F.4th 456"
    assert authorities[0].url == "https://www.courtlistener.com/opinion/42/example/"


def test_ecfr_fetch_normalizes_public_api_results(monkeypatch):
    def fake_get_json(url, *, params, headers=None):
        assert "ecfr.gov" in url
        return {
            "results": [
                {
                    "identifier": "ecfr-privacy",
                    "title": "Privacy Safeguards",
                    "citation": "16 CFR 1.1",
                    "text": "Covered companies must maintain safeguards.",
                    "url": "/current/title-16/section-1.1",
                }
            ]
        }

    monkeypatch.setattr(public_sources, "_get_json", fake_get_json)

    authorities = public_sources.fetch_ecfr_results(query="privacy", topic="privacy", limit=1)

    assert authorities[0].authority_type == "regulation"
    assert authorities[0].citation == "16 CFR 1.1"
    assert authorities[0].url == "https://www.ecfr.gov/current/title-16/section-1.1"


def test_regulations_gov_fetch_normalizes_public_api_results(monkeypatch):
    def fake_get_json(url, *, params, headers=None):
        assert "regulations.gov" in url
        return {
            "data": [
                {
                    "id": "FTC-2026-0001-0001",
                    "attributes": {
                        "title": "Privacy Rulemaking",
                        "documentType": "Proposed Rule",
                        "documentId": "FTC-2026-0001-0001",
                        "postedDate": "2026-03-01",
                        "docAbstract": "Proposed privacy rule.",
                    },
                }
            ]
        }

    monkeypatch.setattr(public_sources, "_get_json", fake_get_json)

    authorities = public_sources.fetch_regulations_gov_documents(query="privacy", topic="privacy", limit=1)

    assert authorities[0].source_id == "regulations-gov-FTC-2026-0001-0001"
    assert authorities[0].authority_type == "regulation"


def test_agency_feed_fetch_normalizes_rss_results(monkeypatch):
    def fake_get_text(url):
        return """
        <rss><channel><item>
          <title>FTC privacy enforcement action</title>
          <link>https://example.test/privacy</link>
          <description><![CDATA[The agency announced a privacy settlement.]]></description>
          <pubDate>Mon, 01 Jun 2026 00:00:00 GMT</pubDate>
        </item></channel></rss>
        """

    monkeypatch.setattr(public_sources, "_get_text", fake_get_text)

    authorities = public_sources.fetch_agency_feed(source="ftc", query="privacy", topic="privacy", limit=1)

    assert authorities[0].authority_type == "enforcement_action"
    assert authorities[0].metadata["source"] == "ftc"


def test_refresh_tracks_changed_authorities_and_source_status(tmp_path):
    store = LegalIntelligenceStore(tmp_path)
    store.append_source_query(
        make_source_query(
            source="federal_register",
            query="privacy",
            topic="privacy",
            industry_tags=["tech"],
            limit=1,
        )
    )

    def fetcher(*, source, query, limit, topic, jurisdiction):
        return [
            normalize_authority(
                {
                    "source_id": "privacy-source",
                    "title": "Privacy source",
                    "type": "agency guidance",
                    "jurisdiction": jurisdiction,
                    "topic": topic,
                    "citation": "Privacy Citation",
                    "text": "Privacy notice text.",
                }
            )
        ]

    first = refresh_legal_sources(store, fetcher=fetcher)
    second = refresh_legal_sources(store, fetcher=fetcher)

    assert first.changed_count == 1
    assert second.changed_count == 0
    assert store.load_source_queries()[0].last_checked is not None
    assert store.load_authorities()[0].content_hash


def test_disabled_and_rejected_rules_do_not_enrich_findings():
    base = LegalGuidanceRule(
        id="legal_guidance.disabled",
        authority_id="authority",
        category="privacy",
        title="Privacy notice",
        legal_basis="Privacy notice basis.",
        risk_signal="privacy policy",
        finding_rationale="Privacy matters.",
        recommendation="Publish a notice.",
        citations=[LegalCitation(title="Authority", citation="A")],
        confidence="high",
    )
    disabled = base.model_copy(update={"enabled": False})
    rejected = base.model_copy(update={"id": "legal_guidance.rejected", "review_status": "rejected"})
    finding = PrivacyFindingScanner().scan(
        RepositorySnapshot(
            source=RepositorySource(kind="local", location="fixture"),
            root=Path("/tmp/unused"),
            files=[FileSnapshot(path="README.md", size_bytes=1, extension=".md", text="#")],
        )
    )[0]

    assert LegalGuidanceIndex([disabled, rejected]).match_finding(finding) == []


def test_profile_targeting_limits_industry_specific_rules():
    fintech_rule = LegalGuidanceRule(
        id="legal_guidance.fintech",
        authority_id="authority",
        category="financial_compliance",
        title="Financial privacy",
        legal_basis="Financial privacy basis.",
        risk_signal="privacy policy",
        finding_rationale="Financial privacy matters.",
        recommendation="Review financial privacy.",
        citations=[LegalCitation(title="Authority", citation="A")],
        confidence="high",
        industry_tags=["fintech"],
    )
    health_rule = fintech_rule.model_copy(
        update={
            "id": "legal_guidance.health",
            "category": "healthcare",
            "industry_tags": ["healthcare"],
        }
    )

    index = LegalGuidanceIndex([fintech_rule, health_rule], profile={"industry": "fintech"})

    assert [rule.id for rule in index.rules] == ["legal_guidance.fintech"]


def test_scanner_guidance_uses_all_authority_types_and_bounds_results():
    authority_types = [
        "regulation",
        "agency_guidance",
        "enforcement_action",
        "court_decision",
        "bill",
        "statute",
    ]
    rules = [
        LegalGuidanceRule(
            id=f"legal_guidance.{authority_type}",
            authority_id=f"authority-{authority_type}",
            category="privacy",
            title=f"{authority_type} privacy rule",
            legal_basis="Privacy authority requires safeguards for personal data.",
            risk_signal="personal data tracking analytics",
            detection_hints=["personal data", "tracking"],
            finding_rationale="Privacy context matters.",
            recommendation="Review privacy controls.",
            citations=[
                LegalCitation(
                    title=f"{authority_type} source",
                    citation=authority_type,
                    authority_type=authority_type,
                )
            ],
            confidence="medium",
        )
        for authority_type in authority_types
    ]

    index = LegalGuidanceIndex(rules)
    guidance = index.guidance_for_scanner(
        scanner_id="pii_data_flow",
        scanner_category="data_privacy",
        scanner_name="PII Data-Flow Agent",
        limit=10,
    )
    bounded = index.guidance_for_scanner(
        scanner_id="pii_data_flow",
        scanner_category="data_privacy",
        scanner_name="PII Data-Flow Agent",
        limit=4,
    )

    assert len(guidance) == len(authority_types)
    returned_types = {item.citations[0].authority_type for item in guidance}
    assert returned_types == set(authority_types)
    assert len(bounded) == 4


def test_scanner_guidance_filters_rejected_disabled_and_profile_rules():
    base = LegalGuidanceRule(
        id="legal_guidance.fintech",
        authority_id="authority",
        category="financial_compliance",
        title="Financial privacy",
        legal_basis="Financial privacy basis.",
        risk_signal="payment privacy audit logs",
        finding_rationale="Financial privacy matters.",
        recommendation="Review financial privacy.",
        citations=[LegalCitation(title="Authority", citation="A")],
        confidence="high",
        industry_tags=["fintech"],
    )
    disabled = base.model_copy(update={"id": "legal_guidance.disabled", "enabled": False})
    rejected = base.model_copy(update={"id": "legal_guidance.rejected", "review_status": "rejected"})
    health = base.model_copy(update={"id": "legal_guidance.health", "industry_tags": ["healthcare"]})

    guidance = LegalGuidanceIndex(
        [base, disabled, rejected, health],
        profile={"industry": "fintech"},
    ).guidance_for_scanner(
        scanner_id="financial_compliance",
        scanner_category="financial_compliance",
        scanner_name="Financial Compliance Scanner",
    )

    assert [item.rule_id for item in guidance] == ["legal_guidance.fintech"]


def test_scanner_guidance_matches_declared_scanner_categories():
    rule = LegalGuidanceRule(
        id="legal_guidance.scanner_category",
        authority_id="authority",
        category="compliance",
        title="Privacy safeguards",
        legal_basis="Privacy safeguard basis.",
        risk_signal="personal data handling",
        finding_rationale="Privacy safeguards matter.",
        recommendation="Review privacy safeguards.",
        citations=[LegalCitation(title="Authority", citation="A")],
        confidence="medium",
        scanner_categories=["privacy"],
    )

    guidance = LegalGuidanceIndex([rule]).guidance_for_scanner(
        scanner_id="pii_data_flow",
        scanner_category="data_privacy",
    )

    assert [item.rule_id for item in guidance] == ["legal_guidance.scanner_category"]


def test_citation_verification_downgrades_unsupported_rules():
    rule = LegalGuidanceRule(
        id="legal_guidance.unverified",
        authority_id="authority",
        category="privacy",
        title="Privacy notice",
        legal_basis="Privacy notice basis.",
        risk_signal="privacy policy",
        finding_rationale="Privacy matters.",
        recommendation="Publish a notice.",
        citations=[LegalCitation(title="Authority", citation="Unknown")],
        confidence="high",
    )

    verified = verify_guidance_citations([rule], lookup=lambda citation: False)

    assert verified[0].confidence == "low"
    assert verified[0].citation_verified is False


def test_bulk_import_normalizes_courtlistener_jsonl(tmp_path):
    dump = tmp_path / "opinions.jsonl"
    dump.write_text(
        json.dumps(
            {
                "opinion_id": 123,
                "caseName": "Example v. Startup",
                "citation": ["123 F.4th 456"],
                "absolute_url": "/opinion/123/example/",
                "dateFiled": "2026-01-02",
                "plain_text": "The court discussed privacy notice obligations.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    authorities = import_bulk_legal_authorities(
        location=str(dump),
        source="courtlistener_bulk",
        topic="privacy",
        query="privacy notice",
    )

    assert authorities[0].authority_type == "court_decision"
    assert authorities[0].citation == "123 F.4th 456"
    assert authorities[0].url == "https://www.courtlistener.com/opinion/123/example/"


def test_bulk_import_reads_gzipped_jsonl(tmp_path):
    dump = tmp_path / "opinions.jsonl.gz"
    payload = json.dumps(
        {
            "opinion_id": 456,
            "caseName": "Security Case",
            "citation": "456 F.4th 789",
            "plain_text": "Security controls and access safeguards.",
        }
    ) + "\n"
    dump.write_bytes(gzip.compress(payload.encode("utf-8")))

    authorities = import_bulk_legal_authorities(
        location=str(dump),
        source="courtlistener_bulk",
        topic="security_controls",
    )

    assert authorities[0].source_id == "courtlistener_bulk-456"
    assert "Security controls" in authorities[0].source_text


def test_bulk_import_reads_courtlistener_csv(tmp_path):
    dump = tmp_path / "search_opinion.csv"
    dump.write_text(
        "id,plain_text,html_with_citations,download_url\n"
        "789,Privacy notice and consumer data safeguards,,https://example.test/opinion.txt\n",
        encoding="utf-8",
    )

    authorities = import_bulk_legal_authorities(
        location=str(dump),
        source="free_law_bulk",
        topic="privacy",
        query="consumer data",
    )

    assert authorities[0].source_id == "free_law_bulk-789"
    assert authorities[0].authority_type == "court_decision"
    assert "Privacy notice" in authorities[0].source_text


def test_bulk_import_uses_xml_head_as_title(tmp_path):
    dump = tmp_path / "title-16.xml"
    dump.write_text(
        "<ECFR><DIV1><HEAD>Commercial Practices</HEAD><P>Consumer protection rule text.</P></DIV1></ECFR>",
        encoding="utf-8",
    )

    authorities = import_bulk_legal_authorities(
        location=str(dump),
        source="ecfr_bulk",
        topic="consumer_protection",
    )

    assert authorities[0].title == "Commercial Practices"
    assert authorities[0].authority_type == "regulation"


def test_explicit_source_catalog_includes_bulk_and_api_presets():
    catalog = all_source_presets()

    assert any(item["id"] == "govinfo_cfr" for item in catalog["bulk_sources"])
    assert any(item["id"] == "free_law_opinions" for item in catalog["bulk_sources"])
    assert any(item["id"] == "ftc_privacy_security" for item in catalog["public_sources"])


def test_bulk_sync_discovers_and_imports_local_directory(tmp_path):
    dump_dir = tmp_path / "bulk"
    dump_dir.mkdir()
    (dump_dir / "opinions.jsonl").write_text(
        json.dumps(
            {
                "id": "local-1",
                "title": "Local Privacy Rule",
                "text": "Privacy notice requirements for consumer data.",
                "citation": "Local Citation",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = sync_bulk_legal_authorities(
        source="generic",
        dataset="bulk",
        bulk_base_url=str(tmp_path),
        topic="privacy",
        query="privacy",
        limit=10,
    )

    assert result.discovered_locations == [str(dump_dir / "opinions.jsonl")]
    assert result.authorities[0].title == "Local Privacy Rule"
    assert result.authorities[0].metadata["bulk_import"] is True


def test_bulk_sync_discovers_files_from_html_listing(monkeypatch):
    def fake_download(url: str) -> str:
        if url == "https://example.test/bulk/":
            return '<a href="2026/">2026</a>'
        if url == "https://example.test/bulk/2026/":
            return '<a href="opinions.jsonl.gz">opinions</a><a href="../">parent</a>'
        raise AssertionError(url)

    monkeypatch.setattr(bulk_sync, "_download_text", fake_download)

    assert discover_bulk_locations("https://example.test/bulk/", max_files=10, max_depth=2) == [
        "https://example.test/bulk/2026/opinions.jsonl.gz"
    ]


def test_ecfr_bulk_seed_resolves_latest_title_date(monkeypatch):
    def fake_download(url: str) -> str:
        assert url == bulk_sync._ECFR_TITLES_URL
        return json.dumps(
            {
                "titles": [
                    {
                        "number": 16,
                        "latest_issue_date": "2026-05-14",
                        "latest_amended_on": "2026-05-14",
                    }
                ]
            }
        )

    monkeypatch.setattr(bulk_sync, "_download_text", fake_download)

    assert bulk_sync.known_bulk_seed_locations(source="ecfr", dataset="title-16") == [
        "https://www.ecfr.gov/api/versioner/v1/full/2026-05-14/title-16.xml"
    ]


def test_refresh_supports_saved_bulk_sync_presets(tmp_path, monkeypatch):
    store = LegalIntelligenceStore(tmp_path / "store")
    store.append_source_query(
        make_source_query(
            source="bulk_sync",
            query="govinfo_cfr",
            topic="compliance",
            limit=10,
        )
    )

    def fake_sync_bulk_source_preset(preset_id: str, *, limit=None, max_files=None):
        class Result:
            authorities = [
                LegalAuthority(
                    source_id=f"{preset_id}-authority",
                    title="Catalog Authority",
                    authority_type="regulation",
                    jurisdiction="US",
                    topic="compliance",
                    citation="Catalog Citation",
                    source_text="Catalog compliance source.",
                    metadata={"source": "bulk_sync"},
                )
            ]

        return Result()

    monkeypatch.setattr(pipeline_module, "sync_bulk_source_preset", fake_sync_bulk_source_preset)

    result = refresh_legal_sources(store)

    assert result.changed_count == 1
    assert store.load_authorities()[0].source_id == "govinfo_cfr-authority"


def test_refresh_supports_saved_bulk_sources(tmp_path):
    dump = tmp_path / "bulk.jsonl"
    dump.write_text(
        json.dumps(
            {
                "id": "bulk-1",
                "title": "Bulk Privacy Rule",
                "text": "Privacy notices are required.",
                "citation": "Bulk Citation",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store = LegalIntelligenceStore(tmp_path / "store")
    store.append_source_query(
        make_source_query(
            source="bulk",
            query=str(dump),
            topic="privacy",
            limit=10,
        )
    )

    result = refresh_legal_sources(store)

    assert result.changed_count == 1
    assert store.load_authorities()[0].metadata["bulk_import"] is True
