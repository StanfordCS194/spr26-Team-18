"""Bake real LLM-generated grades for the featured companies.

For each company in FEATURED_COMPANIES:
- Pull the most recent 10-K from SEC EDGAR
- Run the existing grader against it (uses bills already scraped into the DB)
- Save the result to legi_bill/data/featured_grades.json

The frontend reads this cached JSON via GET /api/grade/featured. Re-run this
script after scraping more bills or when 10-Ks update.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .config import load_config
from .fetch_10k import FEATURED_COMPANIES, fetch_10k_text
from .grader import grade_company
from .llm import get_chat_client
from .storage import init_db, get_all_bills, get_bill_with_summary_and_questions


CACHE_PATH = Path(__file__).parent / "data" / "featured_grades.json"


def bake() -> None:
    cfg = load_config()
    conn = init_db(cfg["db_path"])
    bills = get_all_bills(conn)
    enriched = []
    for b in bills:
        rec = get_bill_with_summary_and_questions(conn, b.bill_number)
        summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        enriched.append((b, summary_text))

    print(f"Loaded {len(bills)} bills from DB.", file=sys.stderr)

    client = get_chat_client()

    out = {}
    for c in FEATURED_COMPANIES:
        ticker = c["ticker"]
        name = c["name"]
        print(f"\n=== {ticker} ({name}) ===", file=sys.stderr)
        try:
            t0 = time.time()
            print(f"  fetching 10-K from SEC EDGAR…", file=sys.stderr)
            text = fetch_10k_text(ticker)
            print(f"  10-K {len(text)} chars in {time.time()-t0:.1f}s", file=sys.stderr)
        except Exception as e:
            print(f"  10-K fetch FAILED: {e}", file=sys.stderr)
            continue

        try:
            t1 = time.time()
            print(f"  grading…", file=sys.stderr)
            result = grade_company(client, enriched, text, company_name=name)
            print(f"  graded in {time.time()-t1:.1f}s → {result['grade']} (composite {result['composite']})", file=sys.stderr)
        except Exception as e:
            print(f"  grading FAILED: {e}", file=sys.stderr)
            continue

        # Stamp identifying fields the frontend expects.
        result["ticker"] = ticker
        result["name"] = name
        result["is_featured"] = True
        out[ticker] = result

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nWrote {len(out)} graded companies to {CACHE_PATH}", file=sys.stderr)


if __name__ == "__main__":
    bake()
