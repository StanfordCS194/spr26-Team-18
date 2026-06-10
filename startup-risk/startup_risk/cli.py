from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from startup_risk.core.engine import ScanEngine
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.legal_intelligence import (
    LegalGuidanceIndex,
    LegalIntelligenceStore,
    all_source_presets,
    bulk_source_presets_for_industry,
    distill_legal_guidance,
    fetch_public_legal_authorities,
    get_bulk_source_preset,
    import_bulk_legal_authorities,
    make_source_query,
    normalize_authority,
    public_source_presets_for_industry,
    refresh_legal_sources,
    run_legal_pipeline,
    sync_bulk_source_preset,
    sync_bulk_legal_authorities,
    verify_guidance_citations,
)
from startup_risk.outputs.json_output import result_to_json
from startup_risk.outputs.text_output import render_text
from startup_risk.scanners.dependency_scanner import DependencyRiskScanner
from startup_risk.scanners.license_scanner import LicenseRiskScanner
from startup_risk.scanners.registry import default_scanners


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


class LicenseLLMProvider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    gemini = "gemini"


class PublicLegalSource(str, Enum):
    bulk = "bulk"
    federal_register = "federal_register"
    courtlistener = "courtlistener"
    ecfr = "ecfr"
    govinfo = "govinfo"
    regulations_gov = "regulations_gov"
    ftc = "ftc"
    cfpb = "cfpb"
    sec = "sec"
    hhs_ocr = "hhs_ocr"
    eeoc = "eeoc"
    dol = "dol"
    irs = "irs"
    state_ag = "state_ag"
    all = "all"


class BulkLegalSource(str, Enum):
    govinfo = "govinfo"
    courtlistener = "courtlistener"
    free_law = "free_law"
    ecfr = "ecfr"
    generic = "generic"


app = typer.Typer(
    name="startup-risk",
    help="Static startup repository risk scanner.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Static startup repository risk scanner."""


@app.command()
def scan(
    target: Annotated[str, typer.Argument(help="Local path or public GitHub HTTPS URL.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.text,
    max_file_bytes: Annotated[
        int,
        typer.Option(help="Maximum bytes to read from an individual text file."),
    ] = 256_000,
    license_llm_provider: Annotated[
        LicenseLLMProvider | None,
        typer.Option("--license-llm-provider", help="Batch LLM provider for license scanning."),
    ] = None,
    license_llm_model: Annotated[
        str | None,
        typer.Option("--license-llm-model", help="Batch LLM model for license scanning."),
    ] = None,
    license_batch_timeout_hours: Annotated[
        float,
        typer.Option("--license-batch-timeout-hours", help="Maximum hours to block waiting for license LLM batch output."),
    ] = 24,
    license_poll_interval_seconds: Annotated[
        int,
        typer.Option("--license-poll-interval-seconds", help="Seconds between license batch status polls."),
    ] = 60,
    license_llm_prompt_token_budget: Annotated[
        int,
        typer.Option("--license-llm-prompt-token-budget", help="Maximum estimated prompt tokens to enqueue for license batch work."),
    ] = 200_000,
    license_llm_max_batch_requests: Annotated[
        int,
        typer.Option("--license-llm-max-batch-requests", help="Maximum requests in one license scanner batch."),
    ] = 50_000,
    license_llm_max_batch_file_bytes: Annotated[
        int,
        typer.Option("--license-llm-max-batch-file-bytes", help="Maximum license scanner batch input JSONL bytes."),
    ] = 200_000_000,
    license_registry_metadata: Annotated[
        bool,
        typer.Option("--license-registry-metadata", help="Fetch registry license metadata as data before LLM review."),
    ] = False,
    license_artifact_inspection: Annotated[
        bool,
        typer.Option("--license-artifact-inspection", help="Download and safely inspect published package artifacts as data."),
    ] = False,
    license_source_repo: Annotated[
        bool,
        typer.Option("--license-source-repo", help="Fetch source repository license files when registry metadata links to one."),
    ] = False,
    deterministic_only: Annotated[
        bool,
        typer.Option("--deterministic-only", help="Skip mandatory batch LLM review for local debugging/tests."),
    ] = False,
    license_only: Annotated[
        bool,
        typer.Option("--license-only", help="Run only the license scanner, excluding repository hygiene findings."),
    ] = False,
    dependency_only: Annotated[
        bool,
        typer.Option("--dependency-only", help="Run only the dependency supply-chain scanner."),
    ] = False,
    dependency_verbose: Annotated[
        bool,
        typer.Option("--dependency-verbose", help="Include verbose dependency-level hygiene findings."),
    ] = False,
    vuln_osv: Annotated[
        bool,
        typer.Option("--vuln-osv", help="Query the OSV vulnerability database for known CVEs in pinned dependencies."),
    ] = False,
    funding_round: Annotated[
        str | None,
        typer.Option(
            "--funding-round",
            help=(
                "Funding stage for IRS/tax compliance rules. Accepted values: "
                "pre-seed, seed, series-a, series-b, series-c (or c+), growth, pre-ipo. "
                "Defaults to seed when omitted."
            ),
        ),
    ] = None,
    entity_type: Annotated[
        str | None,
        typer.Option(
            "--entity-type",
            help="Legal entity type: c_corp, s_corp, llc, other. Skips inapplicable rules (e.g. ISOs/QSBS for non-C-Corps).",
        ),
    ] = None,
    industry: Annotated[
        str | None,
        typer.Option(
            "--industry",
            help="Primary industry: saas, fintech, hardware, biotech, ecommerce, other. Skips irrelevant rules (e.g. R&D rules for non-tech).",
        ),
    ] = None,
    international: Annotated[
        bool | None,
        typer.Option(
            "--international/--no-international",
            help="Whether the company has foreign operations or bank accounts. Skips FBAR/GILTI/§482 rules when --no-international.",
        ),
    ] = None,
    multi_state: Annotated[
        bool | None,
        typer.Option(
            "--multi-state/--no-multi-state",
            help="Whether the company has employees in more than one state. Enables state income tax nexus checks when --multi-state.",
        ),
    ] = None,
    legal_guidance_store: Annotated[
        Path | None,
        typer.Option(
            "--legal-guidance-store",
            help=(
                "Directory containing distilled legal guidance rules. "
                "Also configurable with STARTUP_RISK_LEGAL_INTELLIGENCE_DIR."
            ),
        ),
    ] = None,
) -> None:
    """Scan a repository using static parsing only."""
    console = Console()
    if license_only and dependency_only:
        raise typer.BadParameter("--license-only and --dependency-only cannot be used together.")
    ingestor = RepositoryIngestor(max_file_bytes=max_file_bytes)
    if dependency_only:
        scanners = [DependencyRiskScanner(verbose=dependency_verbose)]
    elif license_only:
        scanners = [
            LicenseRiskScanner(
                deterministic_only=deterministic_only,
                provider_name=license_llm_provider.value if license_llm_provider else None,
                model_name=license_llm_model,
                batch_timeout_seconds=int(license_batch_timeout_hours * 60 * 60),
                poll_interval_seconds=license_poll_interval_seconds,
                llm_prompt_token_budget=license_llm_prompt_token_budget,
                llm_max_batch_requests=license_llm_max_batch_requests,
                llm_max_batch_file_bytes=license_llm_max_batch_file_bytes,
                enable_registry_metadata=license_registry_metadata,
                enable_artifact_inspection=license_artifact_inspection,
                enable_source_repo=license_source_repo,
            )
        ]
    else:
        scanners = default_scanners(
            deterministic_license_only=deterministic_only,
            license_llm_provider=license_llm_provider.value if license_llm_provider else None,
            license_llm_model=license_llm_model,
            license_batch_timeout_seconds=int(license_batch_timeout_hours * 60 * 60),
            license_poll_interval_seconds=license_poll_interval_seconds,
            license_llm_prompt_token_budget=license_llm_prompt_token_budget,
            license_llm_max_batch_requests=license_llm_max_batch_requests,
            license_llm_max_batch_file_bytes=license_llm_max_batch_file_bytes,
            license_registry_metadata=license_registry_metadata,
            license_artifact_inspection=license_artifact_inspection,
            license_source_repo=license_source_repo,
            vuln_osv=vuln_osv,
            funding_round=funding_round,
            entity_type=entity_type,
            industry=industry,
            international=international,
            multi_state=multi_state,
        )
    engine = ScanEngine(
        ingestor=ingestor,
        scanners=scanners,
        legal_guidance_index=_load_legal_guidance_index(legal_guidance_store, profile={"industry": industry}),
    )

    try:
        result = engine.scan(target)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_format is OutputFormat.json:
        console.print_json(result_to_json(result))
        return

    console.print(render_text(result))


@app.command("legal-ingest")
def legal_ingest(
    input_path: Annotated[Path, typer.Argument(help="JSON or JSONL file containing legal authority records.")],
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
) -> None:
    """Normalize legal source records into the legal-intelligence store."""
    rows = _load_legal_authority_rows(input_path)
    authorities = [normalize_authority(row) for row in rows]
    store = LegalIntelligenceStore(store_dir)
    store.append_authorities(authorities)
    Console().print(f"Ingested {len(authorities)} legal authorities into {store.authorities_path}")


@app.command("legal-fetch")
def legal_fetch(
    query: Annotated[str, typer.Argument(help="Search query for public legal sources.")],
    source: Annotated[
        PublicLegalSource,
        typer.Option("--source", help="Free public legal API to query."),
    ] = PublicLegalSource.all,
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    topic: Annotated[
        str,
        typer.Option("--topic", help="Scanner topic/category to attach to fetched sources."),
    ] = "compliance",
    jurisdiction: Annotated[
        str,
        typer.Option("--jurisdiction", help="Jurisdiction label to attach to fetched sources."),
    ] = "US",
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum records to fetch per source."),
    ] = 10,
) -> None:
    """Fetch legal authorities from free public APIs into the legal-intelligence store."""
    selected_sources = (
        ["federal_register", "courtlistener", "ecfr", "regulations_gov", "ftc", "cfpb"]
        if source is PublicLegalSource.all
        else [source.value]
    )
    authorities = []
    for selected in selected_sources:
        authorities.extend(
            fetch_public_legal_authorities(
                source=selected,
                query=query,
                limit=limit,
                topic=topic,
                jurisdiction=jurisdiction,
            )
        )
    store = LegalIntelligenceStore(store_dir)
    store.append_authorities(authorities)
    Console().print(
        f"Fetched {len(authorities)} legal authorities from {', '.join(selected_sources)} into {store.authorities_path}"
    )


@app.command("legal-source-add")
def legal_source_add(
    query: Annotated[str, typer.Argument(help="Search query to save for future legal-refresh runs.")],
    source: Annotated[
        PublicLegalSource,
        typer.Option("--source", help="Public legal source to query."),
    ] = PublicLegalSource.federal_register,
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    topic: Annotated[
        str,
        typer.Option("--topic", help="Scanner topic/category to attach to fetched sources."),
    ] = "compliance",
    jurisdiction: Annotated[
        str,
        typer.Option("--jurisdiction", help="Jurisdiction label to attach to fetched sources."),
    ] = "US",
    industry_tag: Annotated[
        list[str] | None,
        typer.Option("--industry-tag", help="Industry tag used to target rules during scans."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum records to fetch for this query."),
    ] = 10,
) -> None:
    """Save a reusable public-source query for legal-refresh/legal-pipeline."""
    if source is PublicLegalSource.all:
        raise typer.BadParameter("--source all is only valid for legal-fetch.")
    store = LegalIntelligenceStore(store_dir)
    source_query = make_source_query(
        source=source.value,
        query=query,
        topic=topic,
        jurisdiction=jurisdiction,
        industry_tags=industry_tag or [],
        limit=limit,
    )
    store.append_source_query(source_query)
    Console().print(f"Saved legal source query {source_query.id} into {store.sources_path}")


@app.command("legal-bulk-import")
def legal_bulk_import(
    location: Annotated[str, typer.Argument(help="Local file/directory or HTTPS URL for a bulk legal data dump.")],
    source_name: Annotated[
        str,
        typer.Option("--source-name", help="Source label to attach to imported records."),
    ] = "bulk",
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    topic: Annotated[
        str,
        typer.Option("--topic", help="Scanner topic/category to attach to imported sources."),
    ] = "compliance",
    jurisdiction: Annotated[
        str,
        typer.Option("--jurisdiction", help="Jurisdiction label to attach to imported sources."),
    ] = "US",
    industry_tag: Annotated[
        list[str] | None,
        typer.Option("--industry-tag", help="Industry tag used to target rules during scans."),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option("--query-filter", help="Optional term filter applied locally while importing."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Maximum records to import."),
    ] = None,
    save_source: Annotated[
        bool,
        typer.Option("--save-source/--no-save-source", help="Save this bulk location for legal-refresh."),
    ] = True,
) -> None:
    """Import legal authorities from bulk files instead of live APIs."""
    store = LegalIntelligenceStore(store_dir)
    authorities = import_bulk_legal_authorities(
        location=location,
        source=source_name,
        topic=topic,
        jurisdiction=jurisdiction,
        industry_tags=industry_tag or [],
        query=query_filter,
        limit=limit,
    )
    changed = store.upsert_authorities(authorities)
    if save_source:
        store.append_source_query(
            make_source_query(
                source="bulk",
                query=location,
                topic=topic,
                jurisdiction=jurisdiction,
                industry_tags=industry_tag or [],
                limit=limit or 100,
            )
        )
    Console().print(
        f"Imported {len(authorities)} bulk authorities; {len(changed)} changed/new into {store.authorities_path}"
    )


@app.command("legal-bulk-sync")
def legal_bulk_sync(
    dataset: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Bulk dataset to sync, such as CFR, FR, USCODE, title-16, "
                "a dataset path under --bulk-base-url, or omitted with --preset."
            )
        ),
    ] = None,
    preset: Annotated[
        str | None,
        typer.Option("--preset", help="Explicit built-in bulk source preset ID, such as govinfo_cfr or free_law_opinions."),
    ] = None,
    source: Annotated[
        BulkLegalSource,
        typer.Option("--source", help="Bulk source to discover/download."),
    ] = BulkLegalSource.govinfo,
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    topic: Annotated[
        str,
        typer.Option("--topic", help="Scanner topic/category to attach to imported sources."),
    ] = "compliance",
    jurisdiction: Annotated[
        str,
        typer.Option("--jurisdiction", help="Jurisdiction label to attach to imported sources."),
    ] = "US",
    industry_tag: Annotated[
        list[str] | None,
        typer.Option("--industry-tag", help="Industry tag used to target rules during scans."),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option("--query-filter", help="Optional term filter applied locally while importing."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Maximum records to import across discovered files."),
    ] = 500,
    max_files: Annotated[
        int,
        typer.Option("--max-files", help="Maximum bulk files to download/import in one sync."),
    ] = 10,
    max_depth: Annotated[
        int,
        typer.Option("--max-depth", help="Maximum directory/listing depth to follow while discovering files."),
    ] = 3,
    bulk_base_url: Annotated[
        str | None,
        typer.Option(
            "--bulk-base-url",
            help="Override source root for S3/static bulk listings or a local bulk directory.",
        ),
    ] = None,
    save_source: Annotated[
        bool,
        typer.Option("--save-source/--no-save-source", help="Save discovered bulk file locations for legal-refresh."),
    ] = True,
) -> None:
    """Automatically discover and import legal authorities from public bulk datasets."""
    if preset:
        result = sync_bulk_source_preset(preset, limit=limit, max_files=max_files)
        source_query_id = preset
    else:
        if not dataset:
            raise typer.BadParameter("DATASET is required unless --preset is provided.")
        result = sync_bulk_legal_authorities(
            source=source.value,
            dataset=dataset,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tag or [],
            query=query_filter,
            limit=limit,
            max_files=max_files,
            max_depth=max_depth,
            bulk_base_url=bulk_base_url,
        )
        source_query_id = None
    store = LegalIntelligenceStore(store_dir)
    changed = store.upsert_authorities(result.authorities)
    if save_source:
        if source_query_id:
            bulk_preset = get_bulk_source_preset(source_query_id)
            store.append_source_query(
                make_source_query(
                    source="bulk_sync",
                    query=source_query_id,
                    topic=bulk_preset.topic,
                    jurisdiction=bulk_preset.jurisdiction,
                    industry_tags=list(bulk_preset.industry_tags),
                    limit=min(limit or bulk_preset.limit, 10000),
                )
            )
        else:
            for location in result.discovered_locations:
                store.append_source_query(
                    make_source_query(
                        source="bulk",
                        query=location,
                        topic=topic,
                        jurisdiction=jurisdiction,
                        industry_tags=industry_tag or [],
                        limit=min(limit or 100, 10000),
                    )
                )
    Console().print(
        f"Synced {len(result.discovered_locations)} bulk files from {result.source}/{result.dataset}; "
        f"imported {len(result.authorities)} authorities; {len(changed)} changed/new."
    )


@app.command("legal-sources")
def legal_sources() -> None:
    """List the explicit built-in legal intelligence source presets."""
    Console().print_json(data=all_source_presets())


@app.command("legal-source-setup")
def legal_source_setup(
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory for legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    industry: Annotated[
        str | None,
        typer.Option("--industry", help="Only install presets relevant to an industry/profile tag."),
    ] = None,
    include_bulk: Annotated[
        bool,
        typer.Option("--include-bulk/--api-only", help="Save bulk sync presets in addition to API/feed presets."),
    ] = True,
) -> None:
    """Save the explicit built-in legal data sources into the store."""
    store = LegalIntelligenceStore(store_dir)
    public_presets = public_source_presets_for_industry(industry)
    bulk_presets = bulk_source_presets_for_industry(industry) if include_bulk else []
    for source_preset in public_presets:
        store.append_source_query(source_preset.to_source_query())
    for bulk_preset in bulk_presets:
        store.append_source_query(bulk_preset.to_source_query())
    Console().print(
        f"Configured {len(public_presets)} API/feed sources and {len(bulk_presets)} bulk sources in {store.sources_path}"
    )


@app.command("legal-refresh")
def legal_refresh(
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory containing legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
) -> None:
    """Refresh saved legal source queries and store changed/new authorities."""
    store = LegalIntelligenceStore(store_dir)
    result = refresh_legal_sources(store)
    Console().print(
        f"Fetched {result.fetched_count} authorities; {result.changed_count} changed/new. "
        f"Errors: {len(result.errors)}"
    )


@app.command("legal-distill")
def legal_distill(
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory containing legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    llm_provider: Annotated[
        LicenseLLMProvider | None,
        typer.Option("--llm-provider", help="Batch LLM provider for legal distillation."),
    ] = None,
    llm_model: Annotated[
        str | None,
        typer.Option("--llm-model", help="Batch LLM model for legal distillation."),
    ] = None,
    batch_timeout_hours: Annotated[
        float,
        typer.Option("--batch-timeout-hours", help="Maximum hours to block waiting for legal distillation batch output."),
    ] = 24,
    poll_interval_seconds: Annotated[
        int,
        typer.Option("--poll-interval-seconds", help="Seconds between legal distillation batch status polls."),
    ] = 30,
    changed_only: Annotated[
        bool,
        typer.Option("--changed-only/--all-authorities", help="Distill only authorities whose content hash has no current rule."),
    ] = False,
    verify_citations: Annotated[
        bool,
        typer.Option("--verify-citations/--skip-citation-verify", help="Verify/downgrade citations after distillation."),
    ] = True,
) -> None:
    """Batch-distill normalized legal authorities into scanner guidance rules."""
    store = LegalIntelligenceStore(store_dir)
    authorities = store.load_authorities()
    if not authorities:
        raise typer.BadParameter(f"No legal authorities found at {store.authorities_path}")

    if changed_only:
        existing_hashes = {rule.source_hash for rule in store.load_rules() if rule.source_hash}
        authorities = [authority for authority in authorities if authority.content_hash not in existing_hashes]

    rules = distill_legal_guidance(
        authorities,
        provider=llm_provider.value if llm_provider else None,
        model=llm_model,
        timeout_seconds=int(batch_timeout_hours * 60 * 60),
        poll_interval_seconds=poll_interval_seconds,
    )
    if verify_citations:
        rules = verify_guidance_citations(rules)
    store.append_rules(rules)
    Console().print(f"Distilled {len(rules)} legal guidance rules into {store.rules_path}")


@app.command("legal-pipeline")
def legal_pipeline(
    store_dir: Annotated[
        Path,
        typer.Option("--store-dir", help="Directory containing legal intelligence JSONL storage."),
    ] = Path(".startup-risk/legal-intelligence"),
    llm_provider: Annotated[
        LicenseLLMProvider | None,
        typer.Option("--llm-provider", help="Batch LLM provider for legal distillation."),
    ] = None,
    llm_model: Annotated[
        str | None,
        typer.Option("--llm-model", help="Batch LLM model for legal distillation."),
    ] = None,
    changed_only: Annotated[
        bool,
        typer.Option("--changed-only/--all-authorities", help="Distill only changed/new authorities."),
    ] = True,
) -> None:
    """Run legal-refresh, legal-distill, and citation verification."""
    store = LegalIntelligenceStore(store_dir)
    result = run_legal_pipeline(
        store,
        provider=llm_provider.value if llm_provider else None,
        model=llm_model,
        changed_only=changed_only,
        verify_citations=True,
    )
    Console().print_json(data=result)


def _load_legal_authority_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise typer.BadParameter(f"Input file does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        parsed = json.loads(text)
        rows = parsed if isinstance(parsed, list) else [parsed]
    if not all(isinstance(row, dict) for row in rows):
        raise typer.BadParameter("Legal authority input must be a JSON object, array of objects, or JSONL objects.")
    return rows


def _load_legal_guidance_index(path: Path | None, *, profile: dict | None = None) -> LegalGuidanceIndex | None:
    configured = path or (Path(os.environ["STARTUP_RISK_LEGAL_INTELLIGENCE_DIR"]) if os.getenv("STARTUP_RISK_LEGAL_INTELLIGENCE_DIR") else None)
    if configured is None:
        return None
    store = LegalIntelligenceStore(configured)
    rules = store.load_rules()
    return LegalGuidanceIndex(rules, profile=profile) if rules else None


if __name__ == "__main__":
    app()
