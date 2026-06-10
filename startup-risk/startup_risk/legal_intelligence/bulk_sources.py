from __future__ import annotations

import gzip
import html
import json
import re
import zipfile
import csv
from collections.abc import Iterable
from io import BytesIO, StringIO
from pathlib import Path
from urllib import request
import xml.etree.ElementTree as ET

from startup_risk.legal_intelligence.ingest import normalize_authority
from startup_risk.legal_intelligence.models import LegalAuthority


_USER_AGENT = "startup-risk-legal-intelligence-bulk/0.1"


def import_bulk_legal_authorities(
    *,
    location: str,
    source: str = "generic_bulk",
    topic: str = "compliance",
    jurisdiction: str = "US",
    industry_tags: list[str] | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> list[LegalAuthority]:
    """Import legal authorities from local/remote bulk files without live search APIs."""

    rows: list[LegalAuthority] = []
    for name, content in _iter_bulk_payloads(location):
        for authority in _authorities_from_payload(
            name=name,
            content=content,
            source=source,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tags or [],
            query=query,
        ):
            rows.append(authority)
            if limit is not None and len(rows) >= limit:
                return rows
    return rows


def _iter_bulk_payloads(location: str) -> Iterable[tuple[str, bytes]]:
    if location.startswith(("http://", "https://")):
        yield from _payloads_from_bytes(location, _download(location))
        return

    path = Path(location).expanduser()
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file() and _looks_like_bulk_file(child.name):
                yield from _payloads_from_bytes(str(child), child.read_bytes())
        return

    yield from _payloads_from_bytes(str(path), path.read_bytes())


def _payloads_from_bytes(name: str, content: bytes) -> Iterable[tuple[str, bytes]]:
    lower = name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(content)) as archive:
            for member in archive.namelist():
                if not member.endswith("/") and _looks_like_bulk_file(member):
                    yield from _payloads_from_bytes(member, archive.read(member))
        return
    if lower.endswith(".gz"):
        inner_name = name[:-3]
        yield from _payloads_from_bytes(inner_name, gzip.decompress(content))
        return
    yield name, content


def _authorities_from_payload(
    *,
    name: str,
    content: bytes,
    source: str,
    topic: str,
    jurisdiction: str,
    industry_tags: list[str],
    query: str | None,
) -> list[LegalAuthority]:
    text = content.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return _authorities_from_xml(
            text,
            source=source,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tags,
            query=query,
        )
    if name.lower().endswith(".csv"):
        return _authorities_from_csv(
            text,
            source=source,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tags,
            query=query,
            default_name=name,
        )
    return _authorities_from_jsonish(
        text,
        source=source,
        topic=topic,
        jurisdiction=jurisdiction,
        industry_tags=industry_tags,
        query=query,
        default_name=name,
    )


def _authorities_from_csv(
    text: str,
    *,
    source: str,
    topic: str,
    jurisdiction: str,
    industry_tags: list[str],
    query: str | None,
    default_name: str,
) -> list[LegalAuthority]:
    authorities: list[LegalAuthority] = []
    reader = csv.DictReader(StringIO(text))
    for index, row in enumerate(reader):
        cleaned = {str(key): value for key, value in row.items() if key is not None}
        authority = _authority_from_mapping(
            cleaned,
            source=source,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tags,
            fallback_id=f"{source}-{default_name}-{index}",
        )
        if authority and _matches_query(authority, query):
            authorities.append(authority)
    return authorities


def _authorities_from_jsonish(
    text: str,
    *,
    source: str,
    topic: str,
    jurisdiction: str,
    industry_tags: list[str],
    query: str | None,
    default_name: str,
) -> list[LegalAuthority]:
    rows: list[object] = []
    stripped = text.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
        rows = _extract_json_rows(parsed)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in stripped.splitlines() if line.strip()]

    authorities: list[LegalAuthority] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        authority = _authority_from_mapping(
            row,
            source=source,
            topic=topic,
            jurisdiction=jurisdiction,
            industry_tags=industry_tags,
            fallback_id=f"{source}-{default_name}-{index}",
        )
        if authority and _matches_query(authority, query):
            authorities.append(authority)
    return authorities


def _extract_json_rows(parsed: object) -> list[object]:
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return []
    for key in ("results", "data", "opinions", "clusters", "documents", "packages", "items"):
        value = parsed.get(key)
        if isinstance(value, list):
            return value
    return [parsed]


def _authority_from_mapping(
    row: dict,
    *,
    source: str,
    topic: str,
    jurisdiction: str,
    industry_tags: list[str],
    fallback_id: str,
) -> LegalAuthority | None:
    title = _first(
        row,
        "caseName",
        "caseNameFull",
        "case_name",
        "case_name_full",
        "case_name_short",
        "title",
        "name",
        "packageId",
    )
    text = _strip_html(
        _first(
            row,
            "plain_text",
            "html_with_citations",
            "html",
            "text",
            "snippet",
            "summary",
            "description",
            "abstract",
            "body",
            "sibling_html",
            "summary",
            default=title,
        )
    )
    if not title and not text:
        return None

    citation = _citation(row)
    url = _url(row)
    source_id = _first(row, "opinion_id", "cluster_id", "id", "resource_uri", "document_number", "packageId", default=fallback_id)
    authority_type = _authority_type_for_source(source, row)
    return normalize_authority(
        {
            "source_id": f"{source}-{source_id}",
            "title": title or "Bulk legal authority",
            "type": authority_type,
            "jurisdiction": jurisdiction,
            "topic": topic,
            "citation": citation,
            "url": url,
            "date": _first(row, "dateFiled", "date_filed", "date", "publication_date", "dateIssued", "lastModified"),
            "text": text or title,
            "metadata": {
                "source": source,
                "bulk_import": True,
                "industry_tags": industry_tags,
            },
        }
    )


def _authorities_from_xml(
    text: str,
    *,
    source: str,
    topic: str,
    jurisdiction: str,
    industry_tags: list[str],
    query: str | None,
) -> list[LegalAuthority]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    nodes = _document_nodes(root)
    authorities: list[LegalAuthority] = []
    for index, node in enumerate(nodes):
        title = _xml_text(node, "title", "heading", "head", "name", "subject", "doctitle") or "Bulk legal authority"
        body = _strip_html(" ".join(part.strip() for part in node.itertext() if part.strip()))
        citation = _xml_text(node, "citation", "document_number", "docnumber", "packageid")
        url = _xml_text(node, "url", "link", "html_url")
        authority = normalize_authority(
            {
                "source_id": f"{source}-{citation or index}",
                "title": title,
                "type": _authority_type_for_source(source, {}),
                "jurisdiction": jurisdiction,
                "topic": topic,
                "citation": citation,
                "url": url,
                "date": _xml_text(node, "date", "publication_date", "dateissued"),
                "text": body or title,
                "metadata": {
                    "source": source,
                    "bulk_import": True,
                    "industry_tags": industry_tags,
                },
            }
        )
        if _matches_query(authority, query):
            authorities.append(authority)
    return authorities


def _document_nodes(root: ET.Element) -> list[ET.Element]:
    candidates = []
    for node in root.iter():
        tag = _local_name(node.tag).lower()
        if tag in {"item", "document", "doc", "package", "opinion"}:
            candidates.append(node)
    return candidates or [root]


def _matches_query(authority: LegalAuthority, query: str | None) -> bool:
    if not query:
        return True
    haystack = f"{authority.title} {authority.source_text} {authority.citation or ''}".lower()
    return all(term in haystack for term in query.lower().split())


def _first(row: dict, *keys: str, default: object = None) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            if isinstance(value, list):
                return ", ".join(str(item) for item in value if item)
            return str(value)
    return str(default) if default else None


def _citation(row: dict) -> str | None:
    value = row.get("citation") or row.get("citations") or row.get("neutral_cite")
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _url(row: dict) -> str | None:
    value = _first(row, "absolute_url", "url", "html_url", "download_url", "packageLink", "detailsLink")
    if not value:
        return None
    if value.startswith("http"):
        return value
    if value.startswith("/"):
        return f"https://www.courtlistener.com{value}"
    return value


def _authority_type_for_source(source: str, row: dict) -> str:
    normalized = source.lower()
    if "court" in normalized or "listener" in normalized or "free_law" in normalized or row.get("caseName"):
        return "court_decision"
    if "ecfr" in normalized or "cfr" in normalized or "govinfo" in normalized:
        return "regulation"
    if "federal_register" in normalized:
        row_type = str(row.get("type") or row.get("document_type") or "").lower()
        return "regulation" if "rule" in row_type else "agency_guidance"
    return "other"


def _xml_text(node: ET.Element, *tags: str) -> str | None:
    wanted = {tag.lower() for tag in tags}
    for child in node.iter():
        if _local_name(child.tag).lower() in wanted and child.text and child.text.strip():
            return child.text.strip()
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_bulk_file(name: str) -> bool:
    lower = name.lower()
    return lower.endswith((".csv", ".json", ".jsonl", ".xml", ".txt", ".csv.gz", ".json.gz", ".jsonl.gz", ".xml.gz", ".zip"))


def _download(url: str) -> bytes:
    req = request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with request.urlopen(req, timeout=120) as response:
        return response.read()
