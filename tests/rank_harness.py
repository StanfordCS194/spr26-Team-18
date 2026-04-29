#!/usr/bin/env python3
"""Local calibration harness for bill ranking heuristics.

Usage:
  python3 tests/rank_harness.py
  python3 tests/rank_harness.py --case beverage
  python3 tests/rank_harness.py --top 15 --json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


CASES = [
    {
        "slug": "public-tech",
        "name": "Large Public Tech Company",
        "expected_top_bills": ["SB-253", "SB-261", "AB-1305"],
        "description": (
            "We are a publicly traded technology company listed on Nasdaq with annual net sales "
            "of $14.2 billion. We design consumer hardware, cloud software, and related services. "
            "We sell products throughout the United States, including California, through retail, "
            "online, and enterprise channels. Our annual report on Form 10-K discusses greenhouse "
            "gas emissions, supplier emissions, renewable electricity procurement, and our net-zero "
            "goal across operations and value chain. We use packaging for consumer devices and make "
            "public climate-related claims on our website and in investor materials."
        ),
    },
    {
        "slug": "beverage",
        "name": "Beverage and Packaged Goods Company",
        "expected_top_bills": ["SB-54", "AB-1080", "SB-253"],
        "description": (
            "We are a publicly traded beverage company with annual revenue of $6.8 billion and "
            "significant operations in California. We manufacture, bottle, package, market, and "
            "distribute soft drinks and other beverages. Our operations use substantial process "
            "water and generate wastewater. We rely heavily on plastic bottles, secondary packaging, "
            "and retail distribution. Our Form 10-K discusses climate-related risks, emissions "
            "reduction efforts, and packaging sustainability commitments."
        ),
    },
    {
        "slug": "oil-gas",
        "name": "Oil and Gas Operator",
        "expected_top_bills": ["SB-1137", "SB-253", "SB-261"],
        "description": (
            "We are a NYSE-listed energy company with more than $30 billion in annual revenue and "
            "substantial operations in California. We engage in upstream exploration and production, "
            "operate wells and production facilities, and refine petroleum products. Our annual "
            "report describes greenhouse gas regulation, air emissions, climate-related financial "
            "risk, and the operational impact of permitting and setback requirements near sensitive "
            "receptors."
        ),
    },
    {
        "slug": "manufacturer",
        "name": "Industrial Manufacturer",
        "expected_top_bills": ["SB-253", "SB-261"],
        "description": (
            "We are a public manufacturing company with annual revenue of $2.1 billion, including "
            "facilities and distribution centers in California. We operate assembly lines, industrial "
            "plants, warehouses, and fabrication processes that consume electricity and water. Our "
            "workforce includes indoor workers in hot environments, and our annual report discusses "
            "worker safety, hazardous materials handling, and climate-related operational risks."
        ),
    },
    {
        "slug": "software",
        "name": "Lower-Exposure Software Company",
        "expected_top_bills": ["SB-253", "SB-261"],
        "description": (
            "We are a publicly traded software company with $1.6 billion in annual revenue and "
            "sales to customers in California. Our primary operations are office-based software "
            "development and cloud services. We discuss climate-related risks and greenhouse gas "
            "emissions associated with leased offices and data center providers, but we do not "
            "operate manufacturing plants, bottling operations, refineries, or significant consumer "
            "packaging lines."
        ),
    },
]


def _default_db_path() -> str:
    raw = os.getenv("LEGI_BILL_DB_PATH", "~/.legi_bill/bills.db")
    return str(Path(raw).expanduser())


def _load_enriched_bills(db_path: str) -> list[tuple]:
    from legi_bill.storage import get_all_bills, get_bill_with_summary_and_questions, init_db

    conn = init_db(db_path)
    bills = get_all_bills(conn)
    enriched = []
    for bill in bills:
        rec = get_bill_with_summary_and_questions(conn, bill.bill_number)
        summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        enriched.append((bill, summary_text))
    return enriched


def _score_case(case: dict, enriched_bills: list[tuple], top_n: int) -> dict:
    from app.ranking import rank_bills

    ranked = rank_bills(case["description"], enriched_bills)
    top = [(bill, score, tier) for bill, score, tier in ranked if score > 0][:top_n]
    actual_top_bills = [bill.bill_number for bill, _, _ in top]
    expected = case["expected_top_bills"]
    missing = [bill for bill in expected if bill not in actual_top_bills]
    return {
        "case": case["slug"],
        "name": case["name"],
        "expected_top_bills": expected,
        "actual_top_bills": actual_top_bills,
        "missing_expected_bills": missing,
        "top_ranked": [
            {
                "rank": i,
                "bill_number": bill.bill_number,
                "title": bill.title,
                "score": round(score, 4),
                "tier": tier,
            }
            for i, (bill, score, tier) in enumerate(top, 1)
        ],
    }


def _print_case(result: dict) -> None:
    print(f"\n== {result['name']} ({result['case']}) ==")
    print("Expected top bills:", ", ".join(result["expected_top_bills"]))
    print("Actual top bills:  ", ", ".join(result["actual_top_bills"][:5]) or "(none)")
    if result["missing_expected_bills"]:
        print("Missing expected:  ", ", ".join(result["missing_expected_bills"]))
    else:
        print("Missing expected:   none")

    print("\nTop ranked bills:")
    for row in result["top_ranked"]:
        print(
            f"  {row['rank']:>2}. {row['bill_number']:<8} "
            f"{row['score']:.4f} {row['tier']:<6} {row['title']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local calibration cases against rank_bills().")
    parser.add_argument("--db-path", default=_default_db_path(), help="SQLite bills DB path")
    parser.add_argument("--case", action="append", help="Case slug to run; may be passed multiple times")
    parser.add_argument("--top", type=int, default=10, help="How many ranked bills to print")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    selected = set(args.case or [])
    cases = [c for c in CASES if not selected or c["slug"] in selected]
    if not cases:
        raise SystemExit("No matching cases. Use one of: " + ", ".join(c["slug"] for c in CASES))

    try:
        from app.ranking import rank_bills as _rank_bills  # noqa: F401
        from legi_bill.storage import init_db as _init_db  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing Python dependency for the harness "
            f"({exc.name}). Install project dependencies with `pip install -r requirements.txt`."
        ) from exc

    enriched_bills = _load_enriched_bills(args.db_path)
    if not enriched_bills:
        raise SystemExit(
            f"No bills found in {args.db_path}. Run scrape/scrape-bills first to populate the DB."
        )

    results = [_score_case(case, enriched_bills, args.top) for case in cases]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Using DB: {args.db_path}")
        for result in results:
            _print_case(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
