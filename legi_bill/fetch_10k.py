"""Pull a company's most recent 10-K text from SEC EDGAR.

Uses sec-edgar-downloader to grab the filing, then strips HTML and extracts the
substantive sections (Business / Risk Factors / MD&A). Returns plain text the
grader can feed to gpt-4o-mini directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sec_edgar_downloader import Downloader


# Featured companies + their SEC CIKs / tickers.
FEATURED_COMPANIES = [
    {"name": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"name": "Tesla, Inc.", "ticker": "TSLA", "cik": "0001318605"},
    {"name": "Chevron Corp.", "ticker": "CVX", "cik": "0000093410"},
    {"name": "The Coca-Cola Company", "ticker": "KO", "cik": "0000021344"},
    {"name": "Levi Strauss & Co.", "ticker": "LEVI", "cik": "0000094845"},
]


def _strip_html(html: str) -> str:
    """Regex-based HTML tag strip. Tolerant of malformed markup in SEC filings.

    Python's HTMLParser chokes on the XBRL / malformed marked sections that
    show up in raw EDGAR filings, so we just regex out tags + decode entities.
    """
    # Drop script/style blocks entirely.
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Drop comments and CDATA / marked sections.
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = re.sub(r"<!\[CDATA\[.*?\]\]>", " ", html, flags=re.DOTALL)
    # XBRL inline namespace tags often look like <ix:nonfraction ...>.
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities.
    html = (
        html.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&#160;", " ")
            .replace("&#8211;", "–")
            .replace("&#8212;", "—")
            .replace("&#8216;", "‘")
            .replace("&#8217;", "’")
            .replace("&#8220;", "“")
            .replace("&#8221;", "”")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
    )
    # Numeric entities.
    html = re.sub(r"&#\d+;", " ", html)
    # Collapse whitespace.
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\s*\n\s*", "\n", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def _truncate_around_keywords(text: str, keywords: list[str], window: int = 20000) -> str:
    """Pull a window of text around the first match of any keyword (Items 1, 1A, 7).

    Keeps the bits the grader actually needs and discards boilerplate / financials.
    """
    lower = text.lower()
    best_idx = -1
    for kw in keywords:
        idx = lower.find(kw.lower())
        if idx >= 0 and (best_idx < 0 or idx < best_idx):
            best_idx = idx
    if best_idx < 0:
        return text[:window]
    end = min(len(text), best_idx + window)
    return text[best_idx:end]


def fetch_10k_text(ticker: str, name: str = "Legi-Bill Demo Researcher", email: str = "demo@legibill.org") -> str:
    """Download the most recent 10-K for `ticker` and return its plain text.

    Uses a temp dir under /tmp; sec-edgar-downloader insists on a User-Agent
    contact (name + email) per SEC EDGAR rate-limit policy.
    """
    download_root = Path("/tmp/legibill-edgar")
    download_root.mkdir(parents=True, exist_ok=True)

    dl = Downloader(name, email, str(download_root))
    dl.get("10-K", ticker, limit=1)

    # sec-edgar-downloader saves to: {root}/sec-edgar-filings/{ticker}/10-K/{accession}/
    base = download_root / "sec-edgar-filings" / ticker / "10-K"
    if not base.exists():
        raise FileNotFoundError(f"No 10-K downloaded for {ticker} at {base}")

    # Pick the most recent accession folder (alphabetically last is fine — names sort).
    accession_dirs = sorted([p for p in base.iterdir() if p.is_dir()])
    if not accession_dirs:
        raise FileNotFoundError(f"No accession directories under {base}")
    latest = accession_dirs[-1]

    # The primary doc is named full-submission.txt or similar; just merge all .htm/.txt.
    chunks = []
    for f in sorted(latest.iterdir()):
        if f.suffix.lower() in (".htm", ".html", ".txt"):
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "<" in raw and ">" in raw:
                chunks.append(_strip_html(raw))
            else:
                chunks.append(raw)
    full_text = "\n\n".join(chunks)

    # Trim to the substantive sections. Items 1 / 1A / 7 capture business + risk + MD&A.
    extracted = _truncate_around_keywords(
        full_text,
        keywords=["Item 1.", "Item 1A.", "Item 7.", "ITEM 1.", "ITEM 1A.", "ITEM 7."],
        window=24000,
    )
    return extracted


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    text = fetch_10k_text(ticker)
    print(f"Fetched {len(text)} chars of 10-K text for {ticker}.")
    print("---FIRST 500 CHARS---")
    print(text[:500])
