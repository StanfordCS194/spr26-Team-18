from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

from startup_risk.legal_intelligence.models import AuthorityType, LegalAuthority


_AUTHORITY_ALIASES: dict[str, AuthorityType] = {
    "agency guidance": "agency_guidance",
    "guidance": "agency_guidance",
    "agency decision": "agency_decision",
    "enforcement": "enforcement_action",
    "enforcement action": "enforcement_action",
    "case": "court_decision",
    "court case": "court_decision",
    "court decision": "court_decision",
    "opinion": "court_decision",
    "rule": "regulation",
}


def normalize_authority(payload: dict[str, Any]) -> LegalAuthority:
    """Normalize a raw legal-source dictionary into the canonical model."""

    source_text = str(
        payload.get("source_text")
        or payload.get("text")
        or payload.get("body")
        or payload.get("content")
        or ""
    )
    title = str(payload.get("title") or payload.get("name") or "Untitled legal authority")
    citation = _clean_optional(payload.get("citation") or payload.get("cite"))
    url = _clean_optional(payload.get("url") or payload.get("source_url"))
    authority_type = _normalize_authority_type(payload.get("authority_type") or payload.get("type"))
    jurisdiction = str(payload.get("jurisdiction") or payload.get("state") or payload.get("country") or "US")
    topic = str(payload.get("topic") or payload.get("category") or "compliance")
    source_id = _clean_optional(payload.get("source_id") or payload.get("id")) or _stable_source_id(
        title=title,
        citation=citation,
        url=url,
        source_text=source_text,
    )

    return LegalAuthority(
        source_id=source_id,
        title=title,
        authority_type=authority_type,
        jurisdiction=jurisdiction,
        topic=topic,
        source_text=source_text,
        citation=citation,
        url=url,
        effective_date=_parse_date(payload.get("effective_date") or payload.get("date")),
        content_hash=_clean_optional(payload.get("content_hash")),
        first_seen=_parse_datetime(payload.get("first_seen")),
        last_seen=_parse_datetime(payload.get("last_seen")),
        last_checked=_parse_datetime(payload.get("last_checked")),
        metadata=dict(payload.get("metadata") or {}),
    )


def _normalize_authority_type(value: object) -> AuthorityType:
    raw = str(value or "other").strip().lower().replace("-", "_")
    raw = _AUTHORITY_ALIASES.get(raw.replace("_", " "), raw)
    accepted = set(AuthorityType.__args__)  # type: ignore[attr-defined]
    return raw if raw in accepted else "other"  # type: ignore[return-value]


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _stable_source_id(*, title: str, citation: str | None, url: str | None, source_text: str) -> str:
    digest = hashlib.sha256(
        "\n".join([title, citation or "", url or "", source_text[:1000]]).encode("utf-8")
    ).hexdigest()[:16]
    return f"legal-{digest}"
