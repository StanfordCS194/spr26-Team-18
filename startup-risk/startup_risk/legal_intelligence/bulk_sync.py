from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from pathlib import Path
from urllib import parse, request
import xml.etree.ElementTree as ET

from startup_risk.legal_intelligence.bulk_sources import import_bulk_legal_authorities
from startup_risk.legal_intelligence.models import LegalAuthority


_USER_AGENT = "startup-risk-legal-intelligence-bulk-sync/0.1"
_ECFR_TITLES_URL = "https://www.ecfr.gov/api/versioner/v1/titles.json"
_BULK_FILE_SUFFIXES = (
    ".csv",
    ".json",
    ".jsonl",
    ".xml",
    ".txt",
    ".csv.gz",
    ".json.gz",
    ".jsonl.gz",
    ".xml.gz",
    ".zip",
)


@dataclass(frozen=True)
class BulkSyncResult:
    source: str
    dataset: str
    seed_locations: list[str]
    discovered_locations: list[str]
    authorities: list[LegalAuthority]


def sync_bulk_legal_authorities(
    *,
    source: str,
    dataset: str,
    topic: str = "compliance",
    jurisdiction: str = "US",
    industry_tags: list[str] | None = None,
    query: str | None = None,
    limit: int | None = None,
    max_files: int = 10,
    max_depth: int = 2,
    bulk_base_url: str | None = None,
) -> BulkSyncResult:
    """Discover and import bulk legal files from known public bulk endpoints."""

    normalized_source = source.strip().lower().replace("-", "_")
    seed_locations = known_bulk_seed_locations(source=source, dataset=dataset, bulk_base_url=bulk_base_url)
    name_filter = dataset if normalized_source in {"courtlistener", "free_law"} else None
    discovered: list[str] = []
    for seed in seed_locations:
        for location in discover_bulk_locations(
            seed,
            max_files=max_files - len(discovered),
            max_depth=max_depth,
            name_filter=name_filter,
        ):
            if location not in discovered:
                discovered.append(location)
            if len(discovered) >= max_files:
                break
        if len(discovered) >= max_files:
            break

    authorities: list[LegalAuthority] = []
    source_name = f"{source}_bulk"
    for location in discovered:
        remaining = None if limit is None else max(limit - len(authorities), 0)
        if remaining == 0:
            break
        authorities.extend(
            import_bulk_legal_authorities(
                location=location,
                source=source_name,
                topic=topic,
                jurisdiction=jurisdiction,
                industry_tags=industry_tags or [],
                query=query,
                limit=remaining,
            )
        )

    return BulkSyncResult(
        source=source,
        dataset=dataset,
        seed_locations=seed_locations,
        discovered_locations=discovered,
        authorities=authorities,
    )


def sync_bulk_source_preset(
    preset_id: str,
    *,
    limit: int | None = None,
    max_files: int | None = None,
) -> BulkSyncResult:
    from startup_risk.legal_intelligence.source_catalog import get_bulk_source_preset

    preset = get_bulk_source_preset(preset_id)
    return sync_bulk_legal_authorities(
        source=preset.source,
        dataset=preset.dataset,
        topic=preset.topic,
        jurisdiction=preset.jurisdiction,
        industry_tags=list(preset.industry_tags),
        query=preset.query_filter,
        limit=limit if limit is not None else preset.limit,
        max_files=max_files if max_files is not None else preset.max_files,
        max_depth=preset.max_depth,
        bulk_base_url=preset.bulk_base_url,
    )


def known_bulk_seed_locations(*, source: str, dataset: str, bulk_base_url: str | None = None) -> list[str]:
    normalized_source = source.strip().lower().replace("-", "_")
    normalized_dataset = dataset.strip().strip("/")
    if not normalized_dataset:
        raise ValueError("dataset is required for bulk sync.")

    if bulk_base_url:
        return [_join_location(bulk_base_url, normalized_dataset)]

    if normalized_source == "govinfo":
        return [f"https://www.govinfo.gov/bulkdata/{normalized_dataset.upper()}"]

    if normalized_source in {"courtlistener", "free_law"}:
        base = os.getenv("COURTLISTENER_BULK_BASE_URL") or os.getenv("FREE_LAW_BULK_BASE_URL")
        if not base:
            raise ValueError(
                "CourtListener/Free Law bulk sync requires --bulk-base-url, "
                "COURTLISTENER_BULK_BASE_URL, or FREE_LAW_BULK_BASE_URL."
            )
        return [_join_location(base, normalized_dataset)]

    if normalized_source == "ecfr":
        if normalized_dataset.lower().startswith("title-"):
            title_number = normalized_dataset.lower().removeprefix("title-")
            latest_date = _latest_ecfr_title_date(title_number)
            return [f"https://www.ecfr.gov/api/versioner/v1/full/{latest_date}/title-{title_number}.xml"]
        raise ValueError("eCFR bulk sync dataset should look like title-16, title-21, or another title-N value.")

    return [normalized_dataset]


def discover_bulk_locations(
    seed_location: str,
    *,
    max_files: int = 10,
    max_depth: int = 2,
    name_filter: str | None = None,
) -> list[str]:
    if max_files <= 0:
        return []

    local_path = Path(seed_location).expanduser()
    if local_path.exists():
        return _filter_locations(_discover_local_locations(local_path, max_files=max_files), name_filter)[:max_files]

    if _looks_like_bulk_file(seed_location) and _matches_name_filter(seed_location, name_filter):
        return [seed_location]

    discovered: list[str] = []
    visited: set[str] = set()

    def walk(url: str, depth: int) -> None:
        if len(discovered) >= max_files or depth < 0 or url in visited:
            return
        visited.add(url)
        text = _download_text(url)
        links = _links_from_listing(url, text)
        for link in links:
            if len(discovered) >= max_files:
                return
            if _looks_like_bulk_file(link) and _matches_name_filter(link, name_filter):
                discovered.append(link)
            elif depth > 0 and _looks_like_directory_link(link):
                walk(link, depth - 1)

    walk(seed_location, max_depth)
    fallback = [seed_location] if _looks_like_bulk_file(seed_location) and _matches_name_filter(seed_location, name_filter) else []
    return discovered or fallback


def _discover_local_locations(path: Path, *, max_files: int) -> list[str]:
    if path.is_file():
        return [str(path)] if _looks_like_bulk_file(path.name) else []
    locations: list[str] = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and _looks_like_bulk_file(child.name):
            locations.append(str(child))
            if len(locations) >= max_files:
                break
    return locations


def _links_from_listing(base_url: str, text: str) -> list[str]:
    links = _s3_keys_from_xml(base_url, text)
    if links:
        return links

    hrefs = re.findall(r"""href=["']([^"']+)["']""", text, flags=re.IGNORECASE)
    results: list[str] = []
    for href in hrefs:
        if href.startswith(("#", "?", "mailto:")) or href in {"../", "./"}:
            continue
        results.append(parse.urljoin(_directory_base(base_url), href))
    return results


def _s3_keys_from_xml(base_url: str, text: str) -> list[str]:
    stripped = text.lstrip()
    if not stripped.startswith("<"):
        return []
    try:
        root = ET.fromstring(stripped)
    except ET.ParseError:
        return []
    keys: list[str] = []
    for node in root.iter():
        if node.tag.rsplit("}", maxsplit=1)[-1] == "Key" and node.text:
            keys.append(parse.urljoin(_origin_base(base_url), node.text.strip()))
    return keys


def _join_location(base: str, child: str) -> str:
    if base.startswith(("http://", "https://")):
        return parse.urljoin(_directory_base(base), child)
    return str(Path(base).expanduser() / child)


def _directory_base(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _origin_base(url: str) -> str:
    parsed = parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def _looks_like_directory_link(location: str) -> bool:
    if location.endswith("/"):
        return True
    suffix = Path(parse.urlparse(location).path).suffix
    return not suffix


def _looks_like_bulk_file(name: str) -> bool:
    lower = parse.urlparse(name).path.lower()
    return lower.endswith(_BULK_FILE_SUFFIXES)


def _filter_locations(locations: list[str], name_filter: str | None) -> list[str]:
    return [location for location in locations if _matches_name_filter(location, name_filter)]


def _matches_name_filter(location: str, name_filter: str | None) -> bool:
    if not name_filter:
        return True
    normalized = name_filter.lower().replace("-", "_")
    if normalized in {"cfr", "fr", "uscode"} or normalized.startswith("title_"):
        return True
    path = parse.unquote(parse.urlparse(location).path.lower()).replace("-", "_")
    return normalized in path


def _download_text(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xml,*/*"})
    with request.urlopen(req, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


def _latest_ecfr_title_date(title_number: str) -> str:
    payload = json.loads(_download_text(_ECFR_TITLES_URL))
    for title in payload.get("titles", []):
        if str(title.get("number")) == str(title_number):
            latest = title.get("latest_issue_date") or title.get("latest_amended_on") or title.get("up_to_date_as_of")
            if latest:
                return str(latest)
    raise ValueError(f"Could not resolve latest eCFR date for title-{title_number}.")
