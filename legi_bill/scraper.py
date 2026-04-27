import base64
import sys
import time
from html.parser import HTMLParser
from typing import Optional

import requests

from .config import LEGISCAN_BASE_URL, DEFAULT_STATE, ENVIRONMENTAL_KEYWORDS, ENVIRONMENTAL_SUBJECTS
from .models import Bill


class _TagStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def _strip_html(html: str) -> str:
    parser = _TagStripper()
    parser.feed(html)
    return parser.get_text()


class LegiScanClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "LegiBill/1.0"})

    def _get(self, op: str, params: dict) -> dict:
        params = {"key": self.api_key, "op": op, **params}
        response = self.session.get(LEGISCAN_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "ERROR":
            raise RuntimeError(f"LegiScan API error: {data.get('alert', {}).get('message', 'unknown')}")
        return data

    def search_raw(self, state: str, query: str, year: int = 1, page: int = 1) -> dict:
        return self._get("getSearchRaw", {"state": state, "query": query, "year": year, "page": page})

    def get_bill(self, bill_id: int) -> dict:
        return self._get("getBill", {"id": bill_id})

    def get_bill_text(self, doc_id: int) -> Optional[str]:
        data = self._get("getBillText", {"id": doc_id})
        text_data = data.get("text", {})
        mime_type = text_data.get("mime", "")
        encoded = text_data.get("doc", "")

        if "pdf" in mime_type.lower():
            return None

        try:
            decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
            if "<" in decoded and ">" in decoded:
                return _strip_html(decoded)
            return decoded
        except Exception:
            return None


def build_search_query(keywords: list) -> str:
    return " OR ".join(f'"{kw}"' for kw in keywords)


SKIP_TITLE_PATTERNS = ("budget act", "trailer bill", "maintenance of the codes")


def is_environmental(bill_detail: dict, subject_allowlist: set) -> bool:
    subjects = [s["subject_name"] for s in bill_detail.get("subjects", [])]
    return bool(set(subjects) & subject_allowlist)


def _get_best_text_doc_id(bill_detail: dict) -> Optional[int]:
    texts = bill_detail.get("texts", [])
    # prefer non-PDF, most recent (highest doc_id)
    html_docs = [t for t in texts if "pdf" not in t.get("mime", "").lower()]
    if html_docs:
        return max(html_docs, key=lambda t: t.get("doc_id", 0))["doc_id"]
    if texts:
        return max(texts, key=lambda t: t.get("doc_id", 0))["doc_id"]
    return None


def scrape_environmental_bills(
    api_key: str,
    session_year: int,
    keywords: list = None,
    subject_allowlist: set = None,
    limit: int = 200,
    delay: float = 0.5,
) -> list:
    if keywords is None:
        keywords = ENVIRONMENTAL_KEYWORDS
    if subject_allowlist is None:
        subject_allowlist = ENVIRONMENTAL_SUBJECTS

    client = LegiScanClient(api_key)
    query = build_search_query(keywords)
    collected_ids = set()
    bills = []

    print(f"Searching LegiScan for CA environmental bills (session {session_year})...", file=sys.stderr)

    page = 1
    while len(bills) < limit:
        time.sleep(delay)
        try:
            data = client.search_raw(state=DEFAULT_STATE, query=query, year=1, page=page)
        except Exception as e:
            print(f"Search page {page} failed: {e}", file=sys.stderr)
            break

        results = data.get("searchresult", {})
        summary = results.get("summary", {})
        total_pages = int(summary.get("page_total", 1))
        total_found = summary.get("count", 0)
        if page == 1:
            print(f"LegiScan returned {total_found} total results across {total_pages} page(s).", file=sys.stderr)
            print(f"Response keys: {list(results.keys())[:10]}", file=sys.stderr)

        # handle both numbered-dict and list response shapes
        raw_entries = results.get("results", None)
        if raw_entries is not None and isinstance(raw_entries, list):
            bill_entries = raw_entries
        else:
            bill_entries = [v for k, v in results.items() if k not in ("summary",) and isinstance(v, dict)]

        if not bill_entries:
            print(f"No bill entries on page {page} — stopping.", file=sys.stderr)
            break

        for entry in bill_entries:
            if len(bills) >= limit:
                break

            bill_id = entry.get("bill_id")
            if not bill_id or bill_id in collected_ids:
                continue
            collected_ids.add(bill_id)

            time.sleep(delay)
            try:
                bill_data = client.get_bill(bill_id)
            except Exception as e:
                print(f"getBill({bill_id}) failed: {e}", file=sys.stderr)
                continue

            detail = bill_data.get("bill", {})

            # subject filter skipped — LegiScan doesn't populate subjects for CA bills
            title_lc = (detail.get("title") or "").lower()
            if any(p in title_lc for p in SKIP_TITLE_PATTERNS):
                continue

            doc_id = _get_best_text_doc_id(detail)
            text = None
            if doc_id:
                time.sleep(delay)
                try:
                    text = client.get_bill_text(doc_id)
                    if text is None:
                        print(f"  {detail.get('bill_number')}: PDF text skipped, using description.", file=sys.stderr)
                except Exception as e:
                    print(f"  getBillText({doc_id}) failed: {e}", file=sys.stderr)

            subjects = [s["subject_name"] for s in detail.get("subjects", [])]

            # parse session year from the session object if available
            bill_session_year = session_year
            if "session" in detail:
                bill_session_year = int(detail["session"].get("year_start", session_year))

            bill = Bill(
                bill_id=bill_id,
                bill_number=detail.get("bill_number", ""),
                title=detail.get("title", ""),
                description=detail.get("description", ""),
                state=detail.get("state", DEFAULT_STATE),
                status=detail.get("status", ""),
                session_year=bill_session_year,
                url=detail.get("url", ""),
                subjects=subjects,
                text=text or detail.get("description", ""),
                text_doc_id=doc_id,
            )
            bills.append(bill)
            print(f"  [{len(bills)}/{limit}] {bill.bill_number}: {bill.title[:60]}", file=sys.stderr)

        if page >= total_pages:
            break
        page += 1

    print(f"Done. {len(bills)} environmental bills collected.", file=sys.stderr)
    return bills
