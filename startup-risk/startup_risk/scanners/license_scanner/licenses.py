from __future__ import annotations

import re

from startup_risk.scanners.license_scanner.models import LicenseClassification


LOW_RISK = {
    "0BSD",
    "Apache-2.0",
    "BlueOak-1.0.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "ISC",
    "MIT",
    "MIT-0",
    "Python-2.0",
    "Unlicense",
    "W3C",
}
CONTENT_DATA_LICENSES = {
    "CC-BY-3.0",
    "CC-BY-4.0",
    "CC0-1.0",
}
MEDIUM_RISK_PREFIXES = ("LGPL", "MPL", "EPL", "CDDL")
HIGH_RISK_HINTS = (
    "AGPL",
    "GPL",
    "SSPL",
    "Commons Clause",
    "Polyform-Noncommercial",
    "NonCommercial",
    "Non-Commercial",
    "source-available",
)


def classify_license(
    value: str | None,
    *,
    has_notice: bool = False,
    source: str = "deterministic",
    content_data_context: bool = False,
) -> LicenseClassification:
    normalized = normalize_license(value)
    if normalized is None:
        return LicenseClassification(
            normalized_license=None,
            priority="high",
            confidence="high",
            explanation="No license could be established for this dependency.",
            recommendation="Review the dependency license before production use or replace it with a clearly licensed alternative.",
            source="deterministic" if source != "llm" else "llm",
        )

    if _is_high_risk_license(normalized):
        return LicenseClassification(
            normalized_license=normalized,
            priority="high",
            confidence="high",
            explanation=f"{normalized} may impose strong copyleft, noncommercial, or source-available restrictions.",
            recommendation="Replace, isolate after legal review, or obtain explicit approval before production use.",
            source="deterministic" if source != "llm" else "llm",
        )

    if " OR " in normalized or " AND " in normalized:
        parts = re.split(r"\s+(?:OR|AND)\s+", normalized)
        part_results = [
            classify_license(part, has_notice=has_notice, source=source, content_data_context=content_data_context)
            for part in parts
        ]
        if any(result.priority == "high" for result in part_results):
            priority = "high"
        elif any(result.priority == "medium" for result in part_results):
            priority = "medium"
        else:
            priority = "medium" if " OR " in normalized else "low"
        return LicenseClassification(
            normalized_license=normalized,
            priority=priority,
            confidence="medium",
            explanation="The dependency uses a multi-license expression that should be reviewed for the intended usage path.",
            recommendation="Confirm which license option applies and document the selection in third-party notices.",
            source="deterministic" if source != "llm" else "llm",
        )

    if normalized == "Apache-2.0" and not has_notice:
        return LicenseClassification(
            normalized_license=normalized,
            priority="medium",
            confidence="high",
            explanation="Apache-2.0 is generally permissive, but notice handling was not detected.",
            recommendation="Add or verify third-party notice handling for Apache-2.0 dependencies.",
            source="deterministic" if source != "llm" else "llm",
        )

    if normalized in CONTENT_DATA_LICENSES:
        return LicenseClassification(
            normalized_license=normalized,
            priority="low" if content_data_context else "medium",
            confidence="high",
            explanation="Content/data license review recommended.",
            recommendation="Confirm attribution and data/documentation reuse obligations for this package.",
            source="deterministic" if source != "llm" else "llm",
        )

    if normalized in LOW_RISK:
        return LicenseClassification(
            normalized_license=normalized,
            priority="low",
            confidence="high",
            explanation=f"{normalized} is a common permissive license.",
            recommendation="Keep license attribution and notice records current.",
            source="deterministic" if source != "llm" else "llm",
        )

    if normalized.startswith(MEDIUM_RISK_PREFIXES):
        return LicenseClassification(
            normalized_license=normalized,
            priority="medium",
            confidence="high",
            explanation=f"{normalized} has reciprocal or file-level obligations that should be reviewed.",
            recommendation="Review usage, linking/distribution model, and notice obligations.",
            source="deterministic" if source != "llm" else "llm",
        )

    return LicenseClassification(
        normalized_license=normalized,
        priority="medium",
        confidence="medium",
        explanation=f"{normalized} is not in the scanner's low-risk allowlist.",
        recommendation="Review the license text and approve or replace the dependency before production use.",
        source="deterministic" if source != "llm" else "llm",
    )


def normalize_license(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw or raw.upper() in {"UNKNOWN", "UNLICENSED", "SEE LICENSE IN LICENSE", "SEE LICENSE"}:
        return None
    raw = raw.strip("()").strip()
    expression = _normalize_license_expression(raw)
    if expression != raw:
        return expression
    exact = {
        "0BSD": "0BSD",
        "MIT": "MIT",
        "MIT-0": "MIT-0",
        "ISC": "ISC",
        "UNLICENSE": "Unlicense",
        "UNLICENSED": None,
        "APACHE-2.0": "Apache-2.0",
        "APACHE 2": "Apache-2.0",
        "APACHE LICENSE 2.0": "Apache-2.0",
        "APACHE-2": "Apache-2.0",
        "BSD-2-CLAUSE": "BSD-2-Clause",
        "BSD 2-CLAUSE": "BSD-2-Clause",
        "BSD-3-CLAUSE": "BSD-3-Clause",
        "BSD 3-CLAUSE": "BSD-3-Clause",
        "BSD": "BSD-3-Clause",
        "BLUEOAK-1.0.0": "BlueOak-1.0.0",
        "PYTHON-2.0": "Python-2.0",
        "W3C": "W3C",
        "CC-BY-3.0": "CC-BY-3.0",
        "CC-BY-4.0": "CC-BY-4.0",
        "CC0-1.0": "CC0-1.0",
        "CC0": "CC0-1.0",
        "GPLV2": "GPL-2.0",
        "GPLV3": "GPL-3.0",
        "AGPLV3": "AGPL-3.0",
    }
    compact = raw.upper()
    if compact in exact:
        return exact[compact]
    return raw


def _normalize_license_expression(raw: str) -> str:
    parts = re.split(r"\s+(OR|AND)\s+", raw, flags=re.IGNORECASE)
    if len(parts) == 1:
        return raw
    normalized_parts: list[str] = []
    changed = False
    for index, part in enumerate(parts):
        if index % 2 == 1:
            operator = part.upper()
            normalized_parts.append(operator)
            changed = changed or operator != part
            continue
        normalized = normalize_license(part.strip())
        if normalized is None:
            normalized = part.strip()
        normalized_parts.append(normalized)
        changed = changed or normalized != part.strip()
    return " ".join(normalized_parts) if changed else raw


def detect_license_from_text(text: str | None) -> str | None:
    if not text:
        return None
    sample = text[:40_000].lower()
    if "mozilla public license" in sample:
        return "MPL-2.0"
    if "gnu affero general public license" in sample:
        return "AGPL-3.0"
    if "gnu general public license" in sample:
        return "GPL-3.0"
    if "gnu lesser general public license" in sample:
        return "LGPL-3.0"
    if "apache license" in sample and "version 2.0" in sample:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in sample and "mit" in sample[:1000]:
        return "MIT"
    if "permission is hereby granted, free of charge" in sample and "software" in sample:
        return "MIT"
    if "redistribution and use in source and binary forms" in sample:
        return "BSD-3-Clause"
    if "isc license" in sample:
        return "ISC"
    if "commons clause" in sample:
        return "Commons Clause"
    if "noncommercial" in sample or "non-commercial" in sample:
        return "custom noncommercial"
    return None


def is_known_spdx_like(value: str | None) -> bool:
    normalized = normalize_license(value)
    if normalized is None:
        return False
    if normalized in LOW_RISK or normalized in CONTENT_DATA_LICENSES:
        return True
    if normalized.startswith(MEDIUM_RISK_PREFIXES):
        return True
    return _is_high_risk_license(normalized)


def _is_high_risk_license(normalized: str) -> bool:
    lower = normalized.lower()
    if lower.startswith("lgpl"):
        return False
    if lower.startswith(("agpl", "gpl", "sspl")):
        return True
    return any(
        hint.lower() in lower
        for hint in (
            "Commons Clause",
            "Polyform-Noncommercial",
            "NonCommercial",
            "Non-Commercial",
            "source-available",
        )
    )
