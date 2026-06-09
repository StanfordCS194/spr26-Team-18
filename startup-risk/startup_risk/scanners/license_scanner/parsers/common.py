from __future__ import annotations

import re


def find_line(text: str | None, needle: str) -> int | None:
    if not text or not needle:
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def bounded_text(text: str | None, limit: int = 4000) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "\n[TRUNCATED]"


def parse_req_spec(spec: str) -> tuple[str, str | None] | None:
    cleaned = spec.strip().strip('"').strip("'")
    if not cleaned or cleaned.startswith(("#", "-")):
        return None
    match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|~=|>=|<=|>|<|=)\s*([^;\s]+)", cleaned)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"([A-Za-z0-9_.-]+)", cleaned)
    if match:
        return match.group(1), None
    return None
