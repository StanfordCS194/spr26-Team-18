from __future__ import annotations

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Literal
from urllib import parse, request

from startup_risk.legal_intelligence.ingest import normalize_authority
from startup_risk.legal_intelligence.models import LegalAuthority


PublicLegalSource = Literal[
    "federal_register",
    "courtlistener",
    "ecfr",
    "govinfo",
    "regulations_gov",
    "ftc",
    "cfpb",
    "sec",
    "hhs_ocr",
    "eeoc",
    "dol",
    "irs",
    "state_ag",
]

_FEDERAL_REGISTER_URL = "https://www.federalregister.gov/api/v1/documents.json"
_COURTLISTENER_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
_COURTLISTENER_CITATION_LOOKUP_URL = "https://www.courtlistener.com/api/rest/v4/citation-lookup/"
_ECFR_SEARCH_URL = "https://www.ecfr.gov/api/search/v1/results"
_REGULATIONS_GOV_DOCUMENTS_URL = "https://api.regulations.gov/v4/documents"
_GOVINFO_PACKAGES_URL = "https://api.govinfo.gov/packages"
_USER_AGENT = "startup-risk-legal-intelligence/0.1"

_AGENCY_FEEDS: dict[str, tuple[str, str, str]] = {
    "ftc": ("https://www.ftc.gov/feeds/press-release.xml", "FTC", "enforcement_action"),
    "cfpb": ("https://www.consumerfinance.gov/about-us/newsroom/feed/", "CFPB", "agency_guidance"),
    "sec": ("https://www.sec.gov/news/pressreleases.rss", "SEC", "enforcement_action"),
    "hhs_ocr": ("https://www.hhs.gov/ocr/newsroom/news-releases/index.xml", "HHS OCR", "enforcement_action"),
    "eeoc": ("https://www.eeoc.gov/newsroom/rss", "EEOC", "enforcement_action"),
    "dol": ("https://www.dol.gov/rss/releases.xml", "DOL", "agency_guidance"),
    "irs": ("https://www.irs.gov/newsroom/rss.xml", "IRS", "agency_guidance"),
    "state_ag": ("https://oag.ca.gov/rss/news", "State Attorney General", "enforcement_action"),
}


def fetch_public_legal_authorities(
    *,
    source: PublicLegalSource,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    """Fetch legal authorities from free public APIs and normalize them."""

    if source == "federal_register":
        return fetch_federal_register_documents(
            query=query,
            limit=limit,
            topic=topic,
            jurisdiction=jurisdiction,
        )
    if source == "courtlistener":
        return fetch_courtlistener_opinions(
            query=query,
            limit=limit,
            topic=topic,
            jurisdiction=jurisdiction,
        )
    if source == "ecfr":
        return fetch_ecfr_results(query=query, limit=limit, topic=topic, jurisdiction=jurisdiction)
    if source == "govinfo":
        return fetch_govinfo_packages(query=query, limit=limit, topic=topic, jurisdiction=jurisdiction)
    if source == "regulations_gov":
        return fetch_regulations_gov_documents(query=query, limit=limit, topic=topic, jurisdiction=jurisdiction)
    if source in _AGENCY_FEEDS:
        return fetch_agency_feed(source=source, query=query, limit=limit, topic=topic, jurisdiction=jurisdiction)
    raise ValueError(f"Unsupported public legal source: {source}")


def fetch_federal_register_documents(
    *,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    params = {
        "conditions[term]": query,
        "per_page": str(_bounded_limit(limit)),
        "order": "newest",
    }
    payload = _get_json(_FEDERAL_REGISTER_URL, params=params)
    authorities: list[LegalAuthority] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Federal Register document")
        document_number = _clean(item.get("document_number"))
        abstract = _clean(item.get("abstract"))
        agency_names = [
            str(agency.get("name"))
            for agency in item.get("agencies", [])
            if isinstance(agency, dict) and agency.get("name")
        ]
        source_text = "\n".join(
            part
            for part in [
                title,
                f"Agencies: {', '.join(agency_names)}" if agency_names else "",
                abstract or "",
            ]
            if part
        )
        if not source_text.strip():
            continue
        authorities.append(
            normalize_authority(
                {
                    "source_id": f"federal-register-{document_number}" if document_number else None,
                    "title": title,
                    "type": _federal_register_authority_type(item.get("type")),
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": item.get("citation") or document_number,
                    "url": item.get("html_url") or item.get("pdf_url"),
                    "date": item.get("publication_date"),
                    "text": source_text,
                    "metadata": {
                        "source": "federal_register",
                        "document_number": document_number,
                        "document_type": item.get("type"),
                        "agencies": agency_names,
                    },
                }
            )
        )
    return authorities


def fetch_courtlistener_opinions(
    *,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    params = {
        "q": query,
        "type": "o",
        "page_size": str(_bounded_limit(limit)),
    }
    headers = {}
    token = os.getenv("COURTLISTENER_TOKEN")
    if token:
        headers["Authorization"] = f"Token {token}"
    payload = _get_json(_COURTLISTENER_SEARCH_URL, params=params, headers=headers)
    authorities: list[LegalAuthority] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        title = str(
            item.get("caseName")
            or item.get("caseNameFull")
            or item.get("case_name")
            or "Court decision"
        )
        snippet = _strip_html(
            _clean(item.get("snippet"))
            or _clean(item.get("text"))
            or _clean(item.get("plain_text"))
            or title
        )
        citation = _courtlistener_citation(item)
        source_id = _courtlistener_source_id(item)
        authorities.append(
            normalize_authority(
                {
                    "source_id": source_id,
                    "title": title,
                    "type": "court_decision",
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": citation,
                    "url": _courtlistener_url(item),
                    "date": item.get("dateFiled") or item.get("date_filed") or item.get("dateArgued"),
                    "text": snippet,
                    "metadata": {
                        "source": "courtlistener",
                        "court": item.get("court"),
                        "docket_number": item.get("docketNumber") or item.get("docket_number"),
                        "cluster_id": item.get("cluster_id"),
                        "opinion_id": item.get("opinion_id"),
                    },
                }
            )
        )
    return authorities


def fetch_ecfr_results(
    *,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    payload = _get_json(
        _ECFR_SEARCH_URL,
        params={"query": query, "page_size": str(_bounded_limit(limit))},
    )
    authorities: list[LegalAuthority] = []
    for item in _result_items(payload):
        title = str(item.get("title") or item.get("heading") or item.get("label") or "eCFR result")
        citation = _clean(item.get("citation") or item.get("hierarchy_headings") or item.get("part"))
        text = _strip_html(_clean(item.get("text")) or _clean(item.get("summary")) or title)
        url = item.get("url") or item.get("html_url")
        authorities.append(
            normalize_authority(
                {
                    "source_id": _clean(item.get("identifier") or item.get("id")) or f"ecfr-{citation or title}",
                    "title": title,
                    "type": "regulation",
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": citation,
                    "url": _absolute_url("https://www.ecfr.gov", url),
                    "text": text,
                    "metadata": {"source": "ecfr", "raw_title": item.get("title")},
                }
            )
        )
    return authorities[: _bounded_limit(limit)]


def fetch_regulations_gov_documents(
    *,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    api_key = os.getenv("REGULATIONS_GOV_API_KEY") or os.getenv("REGULATIONS_API_KEY") or "DEMO_KEY"
    payload = _get_json(
        _REGULATIONS_GOV_DOCUMENTS_URL,
        params={
            "filter[searchTerm]": query,
            "page[size]": str(_bounded_limit(limit)),
            "sort": "-postedDate",
            "api_key": api_key,
        },
    )
    authorities: list[LegalAuthority] = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
        if not isinstance(attrs, dict):
            continue
        doc_id = item.get("id") or attrs.get("documentId")
        title = str(attrs.get("title") or attrs.get("documentTitle") or "Regulations.gov document")
        text = "\n".join(
            part
            for part in [title, _strip_html(str(attrs.get("docAbstract") or ""))]
            if part.strip()
        )
        authorities.append(
            normalize_authority(
                {
                    "source_id": f"regulations-gov-{doc_id}" if doc_id else None,
                    "title": title,
                    "type": _regulations_authority_type(attrs.get("documentType")),
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": attrs.get("documentId") or doc_id,
                    "url": f"https://www.regulations.gov/document/{doc_id}" if doc_id else None,
                    "date": attrs.get("postedDate"),
                    "text": text,
                    "metadata": {
                        "source": "regulations_gov",
                        "agency_id": attrs.get("agencyId"),
                        "docket_id": attrs.get("docketId"),
                        "document_type": attrs.get("documentType"),
                    },
                }
            )
        )
    return authorities


def fetch_govinfo_packages(
    *,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    api_key = os.getenv("GOVINFO_API_KEY")
    if not api_key:
        return []
    payload = _get_json(
        _GOVINFO_PACKAGES_URL,
        params={"api_key": api_key, "pageSize": str(_bounded_limit(limit)), "query": query},
    )
    authorities: list[LegalAuthority] = []
    for item in _result_items(payload):
        package_id = _clean(item.get("packageId") or item.get("package_id") or item.get("id"))
        title = str(item.get("title") or item.get("packageId") or "GovInfo package")
        authorities.append(
            normalize_authority(
                {
                    "source_id": f"govinfo-{package_id}" if package_id else None,
                    "title": title,
                    "type": "regulation",
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": package_id,
                    "url": item.get("packageLink") or item.get("detailsLink"),
                    "date": item.get("dateIssued") or item.get("lastModified"),
                    "text": "\n".join(part for part in [title, str(item.get("collectionCode") or "")] if part),
                    "metadata": {"source": "govinfo", "package_id": package_id},
                }
            )
        )
    return authorities


def fetch_agency_feed(
    *,
    source: str,
    query: str,
    limit: int = 10,
    topic: str | None = None,
    jurisdiction: str = "US",
) -> list[LegalAuthority]:
    feed_url, agency_label, authority_type = _AGENCY_FEEDS[source]
    text = _get_text(feed_url)
    root = ET.fromstring(text)
    authorities: list[LegalAuthority] = []
    for item in root.findall(".//item"):
        title = _node_text(item, "title") or f"{agency_label} legal update"
        description = _strip_html(_node_text(item, "description") or "")
        link = _node_text(item, "link")
        pub_date = _node_text(item, "pubDate")
        haystack = f"{title} {description}".lower()
        if query.lower() not in haystack:
            continue
        authorities.append(
            normalize_authority(
                {
                    "source_id": f"{source}-{link or title}",
                    "title": title,
                    "type": authority_type,
                    "jurisdiction": jurisdiction,
                    "topic": topic or "compliance",
                    "citation": agency_label,
                    "url": link,
                    "date": pub_date,
                    "text": "\n".join(part for part in [title, description] if part),
                    "metadata": {"source": source, "agency": agency_label},
                }
            )
        )
        if len(authorities) >= _bounded_limit(limit):
            break
    return authorities


def verify_citation_with_courtlistener(citation: str) -> bool:
    if not citation.strip():
        return False
    headers = {}
    token = os.getenv("COURTLISTENER_TOKEN")
    if token:
        headers["Authorization"] = f"Token {token}"
    payload = _get_json(_COURTLISTENER_CITATION_LOOKUP_URL, params={"q": citation}, headers=headers)
    return bool(payload.get("results") or payload.get("clusters") or payload.get("citation"))


def _get_json(url: str, *, params: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    query = parse.urlencode(params)
    req = request.Request(
        f"{url}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
            **(headers or {}),
        },
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"})
    with request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _bounded_limit(limit: int) -> int:
    return max(1, min(limit, 100))


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _federal_register_authority_type(value: object) -> str:
    raw = str(value or "").lower()
    if "rule" in raw:
        return "regulation"
    if "notice" in raw:
        return "agency_guidance"
    return "other"


def _regulations_authority_type(value: object) -> str:
    raw = str(value or "").lower()
    if "rule" in raw:
        return "regulation"
    if "notice" in raw or "supporting" in raw:
        return "agency_guidance"
    return "other"


def _result_items(payload: dict) -> list[dict]:
    for key in ("results", "data", "packages"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _absolute_url(base_url: str, value: object) -> str | None:
    url = _clean(value)
    if not url:
        return None
    if url.startswith("http"):
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


def _node_text(node: ET.Element, tag: str) -> str | None:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def _courtlistener_citation(item: dict) -> str | None:
    citations = item.get("citation")
    if isinstance(citations, list) and citations:
        return str(citations[0])
    if citations:
        return str(citations)
    docket = item.get("docketNumber") or item.get("docket_number")
    return str(docket) if docket else None


def _courtlistener_source_id(item: dict) -> str | None:
    for key in ("opinion_id", "cluster_id", "id"):
        value = item.get(key)
        if value:
            return f"courtlistener-{value}"
    resource_uri = item.get("resource_uri")
    if resource_uri:
        return "courtlistener-" + str(resource_uri).strip("/").split("/")[-1]
    return None


def _courtlistener_url(item: dict) -> str | None:
    url = item.get("absolute_url") or item.get("url")
    if not url:
        return None
    url = str(url)
    if url.startswith("http"):
        return url
    return f"https://www.courtlistener.com{url}"
