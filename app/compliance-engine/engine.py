from __future__ import annotations

from pathlib import Path

from document import extract_text_from_path
from extractor import extract_product_risk_profile
from models import ComplianceReport
from rules import analyze_profile


def analyze_prd_text(text: str, source: str | None = None) -> ComplianceReport:
    profile = extract_product_risk_profile(text, source=source)
    return analyze_profile(profile)


def analyze_prd_file(path: str | Path) -> ComplianceReport:
    path = Path(path)
    text = extract_text_from_path(path)
    return analyze_prd_text(text, source=path.name)
