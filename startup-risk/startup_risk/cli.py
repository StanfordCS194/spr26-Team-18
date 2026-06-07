from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from startup_risk.core.engine import ScanEngine
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.outputs.json_output import result_to_json
from startup_risk.outputs.text_output import render_text
from startup_risk.scanners.license_scanner import LicenseRiskScanner
from startup_risk.scanners.registry import default_scanners


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


class LicenseLLMProvider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"


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
) -> None:
    """Scan a repository using static parsing only."""
    console = Console()
    ingestor = RepositoryIngestor(max_file_bytes=max_file_bytes)
    scanners = (
        [
            LicenseRiskScanner(
                deterministic_only=deterministic_only,
                provider_name=license_llm_provider.value if license_llm_provider else None,
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
        if license_only
        else default_scanners(
            deterministic_license_only=deterministic_only,
            license_llm_provider=license_llm_provider.value if license_llm_provider else None,
            license_batch_timeout_seconds=int(license_batch_timeout_hours * 60 * 60),
            license_poll_interval_seconds=license_poll_interval_seconds,
            license_llm_prompt_token_budget=license_llm_prompt_token_budget,
            license_llm_max_batch_requests=license_llm_max_batch_requests,
            license_llm_max_batch_file_bytes=license_llm_max_batch_file_bytes,
            license_registry_metadata=license_registry_metadata,
            license_artifact_inspection=license_artifact_inspection,
            license_source_repo=license_source_repo,
        )
    )
    engine = ScanEngine(
        ingestor=ingestor,
        scanners=scanners,
    )

    try:
        result = engine.scan(target)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_format is OutputFormat.json:
        console.print_json(result_to_json(result))
        return

    console.print(render_text(result))


if __name__ == "__main__":
    app()
