from __future__ import annotations

import hashlib
import re


def stable_finding_id(scanner_id: str, rule_id: str, seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"{_slug(scanner_id)}.{_slug(rule_id)}.{digest}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")
    return slug or "unknown"
