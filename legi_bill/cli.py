import json
import sys
from datetime import datetime

from openai import OpenAI
import click

from .config import load_config, ENVIRONMENTAL_KEYWORDS, ENVIRONMENTAL_SUBJECTS
from .scraper import scrape_environmental_bills
from .storage import (
    init_db,
    upsert_bill,
    upsert_summary,
    insert_compliance_questions,
    get_bill_by_number,
    get_bills_without_summary,
    get_all_bills,
    get_bill_with_summary_and_questions,
)
from .summarizer import process_bill


@click.group()
def cli():
    """Legi-Bill: California environmental bill scraper and summarizer."""


@cli.command("scrape")
@click.option("--session", default=None, help="Legislative session year, e.g. 2025")
@click.option("--keywords", default=None, help="Space-separated keyword overrides")
@click.option("--limit", default=200, show_default=True, help="Max bills to fetch")
def scrape_cmd(session, keywords, limit):
    """Scrape California environmental bills from LegiScan into the local DB."""
    cfg = load_config()
    conn = init_db(cfg["db_path"])
    kw_list = keywords.split() if keywords else ENVIRONMENTAL_KEYWORDS
    year = int(session) if session else datetime.now().year

    bills = scrape_environmental_bills(
        api_key=cfg["legiscan_api_key"],
        session_year=year,
        keywords=kw_list,
        subject_allowlist=ENVIRONMENTAL_SUBJECTS,
        limit=limit,
    )
    for bill in bills:
        upsert_bill(conn, bill)
    click.echo(f"Scraped and stored {len(bills)} environmental bills.")


@cli.command("summarize")
@click.option("--bill", "bill_number", default=None, help="Process a single bill, e.g. AB1234")
@click.option("--all", "process_all", is_flag=True, help="Process all unsummarized bills")
@click.option("--force", is_flag=True, help="Re-summarize even if summary already exists")
def summarize_cmd(bill_number, process_all, force):
    """Generate LLM summaries and compliance questions for bills."""
    if not bill_number and not process_all:
        raise click.UsageError("Provide --bill <number> or --all.")

    cfg = load_config()
    conn = init_db(cfg["db_path"])
    client = OpenAI(api_key=cfg["openai_api_key"])

    if bill_number:
        bill = get_bill_by_number(conn, bill_number)
        if not bill:
            click.echo(f"Bill {bill_number} not found in DB. Run `scrape` first.", err=True)
            sys.exit(1)
        bills = [bill]
    else:
        bills = get_bills_without_summary(conn) if not force else get_all_bills(conn)

    SKIP_PATTERNS = ["budget act", "trailer bill"]
    bills = [
        b for b in bills
        if not any(p in b.title.lower() for p in SKIP_PATTERNS)
    ]

    if not bills:
        click.echo("No bills to process.")
        return

    click.echo(f"Processing {len(bills)} bill(s)...")
    for i, bill in enumerate(bills, 1):
        click.echo(f"  [{i}/{len(bills)}] {bill.bill_number}: {bill.title[:60]}")
        try:
            summary, questions = process_bill(client, bill)
            upsert_summary(conn, summary)
            insert_compliance_questions(conn, bill.bill_id, questions)
            cache_label = " (cache hit)" if summary.cache_hit else ""
            click.echo(f"    Done. {summary.output_tokens} output tokens{cache_label}.")
        except Exception as e:
            click.echo(f"    Error: {e}", err=True)

    click.echo("Summarization complete.")


@cli.command("show")
@click.option("--bill", "bill_number", required=True, help="Bill number, e.g. AB1234")
@click.option(
    "--format", "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def show_cmd(bill_number, fmt):
    """Display a bill with its summary and compliance questions."""
    cfg = load_config()
    conn = init_db(cfg["db_path"])
    result = get_bill_with_summary_and_questions(conn, bill_number)

    if not result:
        click.echo(f"Bill {bill_number} not found.", err=True)
        sys.exit(1)

    if fmt == "json":
        bill = result["bill"]
        output = {
            "bill_number": bill.bill_number,
            "title": bill.title,
            "status": bill.status,
            "session_year": bill.session_year,
            "subjects": bill.subjects,
            "url": bill.url,
            "summary": result["summary"]["summary_text"] if result["summary"] else None,
            "compliance_questions": [q["question_text"] for q in result["questions"]],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        bill = result["bill"]
        click.echo(f"\n{'='*70}")
        click.echo(f"  {bill.bill_number} — {bill.title}")
        click.echo(f"  Status: {bill.status}  |  Session: {bill.session_year}")
        click.echo(f"  Subjects: {', '.join(bill.subjects)}")
        click.echo(f"  URL: {bill.url}")
        click.echo(f"{'='*70}")

        if result["summary"]:
            click.echo("\nSUMMARY\n")
            click.echo(result["summary"]["summary_text"])
        else:
            click.echo("\n(No summary yet — run `summarize --bill {bill.bill_number}`)")

        if result["questions"]:
            click.echo("\nCOMPLIANCE QUESTIONS\n")
            for q in result["questions"]:
                click.echo(f"  {q['question_number']}. {q['question_text']}")

        click.echo("")


@cli.command("list")
@click.option("--session", default=None, help="Filter by session year")
@click.option(
    "--format", "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def list_cmd(session, fmt):
    """List all bills in the database."""
    cfg = load_config()
    conn = init_db(cfg["db_path"])
    year = int(session) if session else None
    bills = get_all_bills(conn, session_year=year)

    if not bills:
        click.echo("No bills found.")
        return

    if fmt == "json":
        click.echo(json.dumps([
            {"bill_number": b.bill_number, "title": b.title, "status": b.status, "session_year": b.session_year}
            for b in bills
        ], indent=2))
    else:
        click.echo(f"\n{'Bill':<12} {'Status':<20} {'Year':<6} Title")
        click.echo("-" * 80)
        for b in bills:
            click.echo(f"{b.bill_number:<12} {b.status:<20} {b.session_year:<6} {b.title[:42]}")
        click.echo(f"\n{len(bills)} bill(s) total.")


@cli.command("export")
@click.option("--output", required=True, type=click.Path(), help="Output JSON file path")
def export_cmd(output):
    """Export all bills, summaries, and compliance questions to a JSON file."""
    cfg = load_config()
    conn = init_db(cfg["db_path"])
    bills = get_all_bills(conn)

    records = []
    for bill in bills:
        result = get_bill_with_summary_and_questions(conn, bill.bill_number)
        records.append({
            "bill_number": bill.bill_number,
            "title": bill.title,
            "description": bill.description,
            "status": bill.status,
            "session_year": bill.session_year,
            "subjects": bill.subjects,
            "url": bill.url,
            "summary": result["summary"]["summary_text"] if result and result["summary"] else None,
            "compliance_questions": (
                [q["question_text"] for q in result["questions"]] if result else []
            ),
        })

    with open(output, "w") as f:
        json.dump(records, f, indent=2)

    click.echo(f"Exported {len(records)} bills to {output}.")


if __name__ == "__main__":
    cli()
