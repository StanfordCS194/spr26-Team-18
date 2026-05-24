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
from startup_risk.scanners.registry import default_scanners


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


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
) -> None:
    """Scan a repository using static parsing only."""
    console = Console()
    ingestor = RepositoryIngestor(max_file_bytes=max_file_bytes)
    engine = ScanEngine(ingestor=ingestor, scanners=default_scanners())

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
