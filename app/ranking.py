import re
from typing import Iterable, List, Tuple

from app.terms import (
    BILL_FLEET_TERMS,
    BILL_GENERIC_CLIMATE_TERMS,
    BILL_HEAT_LABOR_TERMS,
    BILL_OIL_GAS_TERMS,
    BILL_PACKAGING_TERMS,
    BILL_WATER_TERMS,
    CALIFORNIA_TERMS,
    CLIMATE_CLAIM_TERMS,
    FLEET_TERMS,
    MANUFACTURING_TERMS,
    OIL_GAS_TERMS,
    PACKAGING_TERMS,
    PUBLIC_COMPANY_TERMS,
    RANKING_WEIGHTS,
    WATER_TERMS,
)
from legi_bill.config import ENVIRONMENTAL_KEYWORDS, ENVIRONMENTAL_SUBJECTS
from legi_bill.models import Bill

_STOPWORDS = frozenset(
    """
    a an and or the of to in on for with by at from is are was were be been being
    this that these those it its as if not no yes we you our your their they them
    company inc llc corp corporation business operations revenue fiscal year filed
    shall may must any such other than more less also which who whom whose where when
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z][a-z\-]{2,}")
_REVENUE_RE = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(billion|million|b|m)\b",
    re.IGNORECASE,
)
_NEGATION_RE = r"\b(?:no|not|without|do not|does not|did not|do n't|does n't|did n't)\b"


def _phrase_re(phrase: str) -> re.Pattern:
    parts = [re.escape(part) for part in phrase.split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


def _contains_phrase(text: str, phrase: str) -> bool:
    return _phrase_re(phrase).search(text) is not None


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_all(text: str, phrases: tuple[str, ...]) -> bool:
    return all(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_unnegated(text: str, phrases: tuple[str, ...]) -> bool:
    sentences = re.split(r"[.;:!?]\s*", text)
    for sentence in sentences:
        for phrase in phrases:
            match = _phrase_re(phrase).search(sentence)
            if not match:
                continue
            prefix = sentence[:match.start()]
            if re.search(_NEGATION_RE, prefix):
                continue
            return True
    return False


def _normalize_bill_number(bill_number: str) -> str:
    return (bill_number or "").replace("-", "").replace(" ", "").upper()


def _tokenize(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS}


def _extract_company_profile(company_text: str) -> dict:
    text = company_text or ""
    text_lc = text.lower()

    def has_regex(pattern: str) -> bool:
        return re.search(pattern, text_lc) is not None

    revenue_millions = []
    for match in _REVENUE_RE.finditer(text):
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit in {"billion", "b"}:
            value *= 1000
        revenue_millions.append(value)
    max_revenue_millions = max(revenue_millions) if revenue_millions else None

    # A rough but useful public-company signal for 10-K style inputs.
    is_public = _contains_any(text_lc, PUBLIC_COMPANY_TERMS)
    does_business_in_ca = _contains_any(text_lc, CALIFORNIA_TERMS) or has_regex(r"\bca\b")

    return {
        "is_public": is_public,
        "does_business_in_ca": does_business_in_ca,
        "revenue_over_500m": bool(max_revenue_millions and max_revenue_millions >= 500),
        "revenue_over_1b": bool(max_revenue_millions and max_revenue_millions >= 1000),
        "has_packaging_obligations": _contains_unnegated(text_lc, PACKAGING_TERMS),
        "water_intensive": _contains_unnegated(text_lc, WATER_TERMS),
        "oil_gas_operations": _contains_unnegated(text_lc, OIL_GAS_TERMS),
        "manufacturing_or_hot_indoor_work": _contains_unnegated(text_lc, MANUFACTURING_TERMS),
        "commercial_fleet": _contains_unnegated(text_lc, FLEET_TERMS),
        "makes_climate_claims": _contains_unnegated(text_lc, CLIMATE_CLAIM_TERMS),
    }


def _profile_bill_boost(profile: dict, bill: Bill) -> float:
    title_lc = (bill.title or "").lower()
    desc_lc = (bill.description or "").lower()
    subjects_lc = " ".join((bill.subjects or [])).lower()
    corpus = " ".join([title_lc, desc_lc, subjects_lc])
    bill_number = _normalize_bill_number(bill.bill_number)

    boost = 0.0

    if (
        profile["is_public"]
        and profile["does_business_in_ca"]
        and profile["revenue_over_1b"]
        and bill_number == "SB253"
    ):
        boost += RANKING_WEIGHTS["sb253_public_over_1b"]
    if (
        profile["is_public"]
        and profile["does_business_in_ca"]
        and profile["revenue_over_500m"]
        and bill_number == "SB261"
    ):
        boost += RANKING_WEIGHTS["sb261_public_over_500m"]
    if profile["makes_climate_claims"] and bill_number == "AB1305":
        boost += RANKING_WEIGHTS["ab1305_climate_claims"]

    if profile["has_packaging_obligations"] and _contains_any(corpus, BILL_PACKAGING_TERMS):
        boost += RANKING_WEIGHTS["packaging_applicability"]

    if profile["water_intensive"] and _contains_any(corpus, BILL_WATER_TERMS):
        boost += RANKING_WEIGHTS["water_applicability"]

    if profile["oil_gas_operations"] and _contains_any(corpus, BILL_OIL_GAS_TERMS):
        boost += RANKING_WEIGHTS["oil_gas_applicability"]

    if profile["manufacturing_or_hot_indoor_work"] and _contains_any(corpus, BILL_HEAT_LABOR_TERMS):
        boost += RANKING_WEIGHTS["heat_labor_applicability"]

    return boost


def _profile_bill_penalty(profile: dict, bill: Bill) -> float:
    title_lc = (bill.title or "").lower()
    desc_lc = (bill.description or "").lower()
    subjects_lc = " ".join((bill.subjects or [])).lower()
    corpus = " ".join([title_lc, desc_lc, subjects_lc])
    bill_number = _normalize_bill_number(bill.bill_number)

    penalty = 0.0

    is_oil_gas_bill = _contains_any(corpus, BILL_OIL_GAS_TERMS)
    if is_oil_gas_bill and not profile["oil_gas_operations"]:
        penalty += RANKING_WEIGHTS["oil_gas_mismatch"]

    is_packaging_bill = _contains_any(corpus, BILL_PACKAGING_TERMS)
    if is_packaging_bill and not profile["has_packaging_obligations"]:
        penalty += RANKING_WEIGHTS["packaging_mismatch"]

    is_water_bill = _contains_any(corpus, BILL_WATER_TERMS)
    if is_water_bill and not profile["water_intensive"]:
        penalty += RANKING_WEIGHTS["water_mismatch"]

    is_heat_or_worker_safety_bill = _contains_any(corpus, BILL_HEAT_LABOR_TERMS)
    if is_heat_or_worker_safety_bill and not profile["manufacturing_or_hot_indoor_work"]:
        penalty += RANKING_WEIGHTS["heat_labor_mismatch"]

    is_fleet_electrification_bill = _contains_any(corpus, BILL_FLEET_TERMS)
    if is_fleet_electrification_bill and not profile["commercial_fleet"]:
        penalty += RANKING_WEIGHTS["fleet_mismatch"]

    if bill_number == "AB1305" and not profile["makes_climate_claims"]:
        penalty += RANKING_WEIGHTS["ab1305_no_climate_claims"]

    # Broader climate target bills often look relevant to every public company
    # on token overlap alone. Keep them below more directly applicable bills
    # unless the company has real operational emissions language.
    is_generic_climate_bill = bill_number == "AB1279" or (
        _contains_all(corpus, BILL_GENERIC_CLIMATE_TERMS) and not _contains_phrase(corpus, "disclose")
    )
    if is_generic_climate_bill and not (
        profile["oil_gas_operations"]
        or profile["water_intensive"]
        or profile["manufacturing_or_hot_indoor_work"]
    ):
        penalty += RANKING_WEIGHTS["generic_climate_mismatch"]

    return penalty


def _assign_tiers(scored: List[Tuple[Bill, float]]) -> List[Tuple[Bill, float, str]]:
    """Assign relative High/Medium/Low tiers among non-zero scores.

    Top third of non-zero scorers = High, middle third = Medium, bottom third =
    Low. Zero-score bills are always Low. Relative tiering keeps the badge
    spread meaningful regardless of absolute score magnitudes.
    """
    nonzero = [(b, s) for b, s in scored if s > 0]
    zero = [(b, s) for b, s in scored if s <= 0]
    nonzero.sort(key=lambda x: x[1], reverse=True)

    n = len(nonzero)
    out: List[Tuple[Bill, float, str]] = []
    if n == 0:
        pass
    elif n == 1:
        out.append((nonzero[0][0], nonzero[0][1], "High"))
    elif n == 2:
        out.append((nonzero[0][0], nonzero[0][1], "High"))
        out.append((nonzero[1][0], nonzero[1][1], "Medium"))
    else:
        third = max(1, n // 3)
        for i, (b, s) in enumerate(nonzero):
            if i < third:
                tier = "High"
            elif i < n - third:
                tier = "Medium"
            else:
                tier = "Low"
            out.append((b, s, tier))

    out.extend((b, s, "Low") for b, s in zero)
    return out


def rank_bills(
    company_text: str, bills_with_summary: Iterable[Tuple[Bill, str]]
) -> List[Tuple[Bill, float, str]]:
    """Return bills sorted by descending relevance score."""
    company_tokens = _tokenize(company_text)
    if not company_tokens:
        return []

    env_keyword_tokens = _tokenize(" ".join(ENVIRONMENTAL_KEYWORDS))
    has_env_signal = bool(company_tokens & env_keyword_tokens)
    env_factor = 1.0 if has_env_signal else 0.5
    profile = _extract_company_profile(company_text)

    scored: List[Tuple[Bill, float]] = []
    for bill, summary_text in bills_with_summary:
        subjects = " ".join(bill.subjects) if bill.subjects else ""
        corpus = f"{bill.title} {bill.description} {subjects} {summary_text} {bill.text or ''}"
        bill_tokens = _tokenize(corpus)
        profile_boost = _profile_bill_boost(profile, bill)
        profile_penalty = _profile_bill_penalty(profile, bill)
        if not bill_tokens:
            scored.append((bill, max(0.0, profile_boost - profile_penalty)))
            continue

        overlap = company_tokens & bill_tokens
        if not overlap and profile_boost <= 0:
            scored.append((bill, 0.0))
            continue

        base = len(overlap) / max(1, min(len(company_tokens), len(bill_tokens))) if overlap else 0.0
        subject_boost = 0.02 * sum(
            1 for s in (bill.subjects or []) if s in ENVIRONMENTAL_SUBJECTS
        )
        total = (base + subject_boost) * env_factor + profile_boost - profile_penalty
        scored.append((bill, max(0.0, total)))

    return _assign_tiers(scored)
