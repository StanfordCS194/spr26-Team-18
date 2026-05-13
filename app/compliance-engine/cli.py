from __future__ import annotations

import argparse

from engine import analyze_prd_file
from report import render_markdown_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a PRD for US compliance focus areas.")
    parser.add_argument("prd", help="Path to a PDF, DOCX, TXT, MD, or Markdown PRD.")
    parser.add_argument(
        "--include-not-flagged",
        action="store_true",
        help="Include rules that were evaluated but not flagged.",
    )
    args = parser.parse_args()

    report = analyze_prd_file(args.prd)
    print(render_markdown_report(report, include_not_flagged=args.include_not_flagged))


if __name__ == "__main__":
    main()
