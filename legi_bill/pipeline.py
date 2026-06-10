"""
Nightly bill pipeline: fetch new LegiScan bills → upsert → summarize unseen ones.

Can be invoked three ways:
  1. CLI:      python -m legi_bill.cli run-pipeline
  2. FastAPI:  POST /api/pipeline/run  (also runs automatically via APScheduler)
  3. CI:       python -m legi_bill.pipeline  (used by GitHub Actions)
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

SKIP_TITLE_PATTERNS = ["budget act", "trailer bill"]


def run_nightly_pipeline(
    cfg: dict,
    conn: sqlite3.Connection,
    *,
    session_year: int | None = None,
    limit: int = 200,
    summarize: bool = True,
) -> dict[str, Any]:
    """
    Fetch the latest LegiScan bills, store them, and summarize any that are new.

    Returns a stats dict:
      {
        "started_at": str,
        "finished_at": str,
        "bills_fetched": int,
        "bills_new": int,
        "bills_updated": int,
        "summaries_attempted": int,
        "summaries_ok": int,
        "summaries_failed": int,
        "errors": [str],
      }
    """
    from .scraper import scrape_environmental_bills
    from .storage import upsert_bill, get_bills_without_summary, upsert_summary, insert_compliance_questions, clear_bill_text, vacuum_db
    from .llm import get_chat_client, LLMConfigError
    from .summarizer import process_bill

    started_at = datetime.now(timezone.utc).isoformat()
    stats: dict[str, Any] = {
        "started_at": started_at,
        "finished_at": None,
        "bills_fetched": 0,
        "bills_new": 0,
        "bills_updated": 0,
        "summaries_attempted": 0,
        "summaries_ok": 0,
        "summaries_failed": 0,
        "errors": [],
    }

    api_key = cfg.get("legiscan_api_key") or cfg.get("api_key")
    if not api_key:
        stats["errors"].append("LEGISCAN_API_KEY not set — aborting fetch.")
        log.error(stats["errors"][-1])
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    year = session_year or datetime.now(timezone.utc).year

    # ------------------------------------------------------------------
    # 1. Fetch bills from LegiScan
    # ------------------------------------------------------------------
    log.info("Fetching LegiScan bills for session %s (limit=%s)…", year, limit)
    try:
        bills = scrape_environmental_bills(api_key=api_key, session_year=year, limit=limit)
    except Exception as exc:
        stats["errors"].append(f"LegiScan fetch failed: {exc}")
        log.exception("LegiScan fetch error")
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    stats["bills_fetched"] = len(bills)
    log.info("Fetched %d bill(s) from LegiScan.", len(bills))

    # ------------------------------------------------------------------
    # 2. Upsert into the database
    # ------------------------------------------------------------------
    existing_ids: set[int] = {
        row[0]
        for row in conn.execute("SELECT bill_id FROM bills").fetchall()
    }

    for bill in bills:
        try:
            upsert_bill(conn, bill)
            if bill.bill_id in existing_ids:
                stats["bills_updated"] += 1
            else:
                stats["bills_new"] += 1
        except Exception as exc:
            msg = f"upsert_bill failed for {bill.bill_number}: {exc}"
            stats["errors"].append(msg)
            log.warning(msg)

    log.info(
        "DB upsert done — %d new, %d updated.",
        stats["bills_new"],
        stats["bills_updated"],
    )

    # ------------------------------------------------------------------
    # 3. Summarize bills that have no summary yet
    # ------------------------------------------------------------------
    if not summarize:
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    try:
        client = get_chat_client()
    except LLMConfigError as exc:
        msg = f"LLM not configured — skipping summaries: {exc}"
        stats["errors"].append(msg)
        log.warning(msg)
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    unsummarized = [
        b for b in get_bills_without_summary(conn)
        if not any(p in b.title.lower() for p in SKIP_TITLE_PATTERNS)
    ]

    log.info("Summarizing %d unseen bill(s)…", len(unsummarized))

    for bill in unsummarized:
        stats["summaries_attempted"] += 1
        try:
            summary, questions = process_bill(client, bill)
            upsert_summary(conn, summary)
            insert_compliance_questions(conn, bill.bill_id, questions)
            clear_bill_text(conn, bill.bill_id)  # drop raw HTML to keep DB small
            stats["summaries_ok"] += 1
            log.info("  Summarized %s (%d tokens).", bill.bill_number, summary.output_tokens)
        except Exception as exc:
            stats["summaries_failed"] += 1
            msg = f"summarize {bill.bill_number}: {exc}"
            stats["errors"].append(msg)
            log.warning(msg)

    vacuum_db(conn)  # reclaim space from cleared text fields
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    log.info(
        "Pipeline complete — %d/%d summaries OK.",
        stats["summaries_ok"],
        stats["summaries_attempted"],
    )
    return stats


# ---------------------------------------------------------------------------
# Standalone entry point (used by GitHub Actions)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    from .config import load_config
    from .storage import init_db

    cfg = load_config()
    conn = init_db(cfg["db_path"])
    stats = run_nightly_pipeline(cfg, conn)

    print(json.dumps(stats, indent=2))
    if stats["errors"]:
        sys.exit(1)
