from __future__ import annotations

import re
from collections.abc import Iterable

from models import Evidence, ProductRiskProfile


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_AGE_RE = re.compile(
    r"\b(?:ages?|aged|users?|children|kids|teens?)\s*(?:from|between|:)?\s*"
    r"(\d{1,2})(?:\s*(?:\+|and up|or older)|\s*(?:-|to|through)\s*(\d{1,2}))?",
    re.IGNORECASE,
)


KEYWORDS = {
    "children": ("children", "kids", "under 13", "under thirteen", "elementary school"),
    "teens": ("teen", "minor", "under 18", "under eighteen", "13-17", "13 to 17"),
    "health": (
        "health data",
        "health information",
        "health activity",
        "wellness",
        "symptom",
        "medical",
        "patient",
        "clinical",
        "diagnosis",
        "treatment",
        "therapy",
        "mental health",
        "medication",
        "provider",
        "doctor",
        "clinic",
    ),
    "healthcare_context": (
        "covered entity",
        "business associate",
        "baa",
        "health plan",
        "health care clearinghouse",
        "provider portal",
        "ehr",
        "emr",
    ),
    "messaging": ("chat", "message", "dm", "direct message", "inbox", "comment"),
    "ugc": ("post", "upload", "user-generated", "user generated", "profile", "avatar"),
    "ads_tracking": (
        "ad network",
        "targeted ads",
        "targeted advertising",
        "targeted email",
        "targeted sms",
        "marketing campaign",
        "behavioral ads",
        "analytics sdk",
        "tracking",
        "cookie",
        "device id",
        "persistent identifier",
    ),
    "geolocation": ("location", "geolocation", "gps", "street address", "home address", "nearby"),
    "biometric": ("biometric", "face scan", "facial recognition", "voiceprint", "liveness", "selfie"),
    "education": ("school", "student", "teacher", "classroom", "district", "ferpa", "lms"),
    "financial": (
        "payment",
        "credit",
        "loan",
        "bank",
        "financial",
        "insurance",
        "debit",
        "card",
        "billing",
    ),
    "adult_content": ("adult content", "porn", "sexually explicit", "harmful to minors", "18+"),
    "social_recs": (
        "social feed",
        "social profile",
        "social graph",
        "feed",
        "recommendation",
        "algorithmic",
        "followers",
        "friends",
        "creator",
    ),
}

DATA_TERMS = {
    "name": ("full name", "name"),
    "email": ("email", "email address"),
    "phone": ("phone", "telephone"),
    "address": ("street address", "home address", "physical address", "mailing address"),
    "device identifiers": ("device id", "device identifier", "ip address", "cookie"),
    "photo/video/audio": ("photo", "video", "audio", "avatar", "voice"),
    "geolocation": ("gps", "geolocation", "precise location"),
    "health information": (
        "health data",
        "health information",
        "health activity",
        "medical",
        "diagnosis",
        "medication",
        "symptom",
    ),
    "payment information": ("payment", "credit card", "billing"),
    "biometric data": ("biometric", "face scan", "voiceprint", "liveness"),
}

SENSITIVE_TERMS = {
    "health information",
    "payment information",
    "biometric data",
    "geolocation",
    "photo/video/audio",
}

US_JURISDICTIONS = (
    "United States",
    "US",
    "U.S.",
    "California",
    "Texas",
    "Utah",
    "Florida",
    "New York",
    "Colorado",
    "Virginia",
    "Connecticut",
    "Oregon",
    "Delaware",
)


def extract_product_risk_profile(text: str, source: str | None = None) -> ProductRiskProfile:
    chunks = _chunks(text)
    profile = ProductRiskProfile()

    profile.minimum_age = _extract_minimum_age(text)
    profile.likely_minors = _has_any(text, KEYWORDS["children"] + KEYWORDS["teens"]) or (
        profile.minimum_age is not None and profile.minimum_age < 18
    )
    profile.child_directed = _has_any(text, KEYWORDS["children"]) or (
        profile.minimum_age is not None and profile.minimum_age < 13
    )
    profile.health_data = _has_any(text, KEYWORDS["health"])
    profile.healthcare_context = _has_any(text, KEYWORDS["healthcare_context"])
    profile.messaging = _has_any(text, KEYWORDS["messaging"])
    profile.user_generated_content = _has_any(text, KEYWORDS["ugc"])
    profile.ads_or_tracking = _has_any(text, KEYWORDS["ads_tracking"])
    profile.geolocation = _has_any(text, KEYWORDS["geolocation"])
    profile.biometric_data = _has_any(text, KEYWORDS["biometric"])
    profile.education_context = _has_any(text, KEYWORDS["education"])
    profile.payment_or_financial_data = _has_any(text, KEYWORDS["financial"])
    profile.adult_content = _has_any(text, KEYWORDS["adult_content"])
    profile.social_or_recommendation_features = _has_any(text, KEYWORDS["social_recs"])
    profile.data_collected = _extract_terms(text, DATA_TERMS)
    profile.sensitive_data = [term for term in profile.data_collected if term in SENSITIVE_TERMS]
    profile.jurisdictions_mentioned = [
        jurisdiction for jurisdiction in US_JURISDICTIONS if _contains_phrase(text, jurisdiction)
    ]
    profile.target_users = _extract_target_users(text)

    age_match = _first_age_chunk(chunks)
    if age_match:
        profile.evidence.append(Evidence(label="minor users", snippet=age_match, source=source))

    evidence_terms = {
        "minor users": KEYWORDS["children"] + KEYWORDS["teens"],
        "health data/context": KEYWORDS["health"] + KEYWORDS["healthcare_context"],
        "messaging/social features": KEYWORDS["messaging"] + KEYWORDS["social_recs"],
        "ads/tracking": KEYWORDS["ads_tracking"],
        "biometric data": KEYWORDS["biometric"],
        "education context": KEYWORDS["education"],
        "financial/payment data": KEYWORDS["financial"],
        "adult content": KEYWORDS["adult_content"],
    }
    for label, terms in evidence_terms.items():
        match = _first_matching_chunk(chunks, terms)
        if match:
            profile.evidence.append(Evidence(label=label, snippet=match, source=source))

    for data_type in profile.data_collected:
        terms = DATA_TERMS[data_type]
        match = _first_matching_chunk(chunks, terms)
        if match:
            profile.evidence.append(Evidence(label=f"data collected: {data_type}", snippet=match, source=source))

    profile.evidence = _dedupe_evidence(profile.evidence)
    return profile


def _chunks(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text or "") if part.strip()]


def _extract_minimum_age(text: str) -> int | None:
    ages: list[int] = []
    for match in _AGE_RE.finditer(text or ""):
        ages.append(int(match.group(1)))
        if match.group(2):
            ages.append(int(match.group(2)))
    return min(ages) if ages else None


def _extract_terms(text: str, term_map: dict[str, tuple[str, ...]]) -> list[str]:
    return [label for label, terms in term_map.items() if _has_any(text, terms)]


def _extract_target_users(text: str) -> list[str]:
    targets = []
    for label, terms in {
        "children": KEYWORDS["children"],
        "teens/minors": KEYWORDS["teens"],
        "patients": ("patient", "patients"),
        "clinicians/providers": ("clinician", "doctor", "provider", "therapist"),
        "students": ("student", "students"),
        "creators/social users": ("creator", "follower", "social feed", "social profile"),
    }.items():
        if _has_any(text, terms):
            targets.append(label)
    return targets


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(_contains_phrase(text, term) for term in terms)


def _first_matching_chunk(chunks: list[str], terms: Iterable[str]) -> str | None:
    for chunk in chunks:
        if _has_any(chunk, terms):
            return _clean_snippet(chunk)
    return None


def _first_age_chunk(chunks: list[str]) -> str | None:
    for chunk in chunks:
        if _AGE_RE.search(chunk):
            return _clean_snippet(chunk)
    return None


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    normalized = re.escape(phrase).replace(r"\ ", r"\s+")
    return re.search(r"\b" + normalized + r"\b", text or "", re.IGNORECASE) is not None


def _clean_snippet(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _dedupe_evidence(items: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str, str | None]] = set()
    deduped: list[Evidence] = []
    for item in items:
        key = (item.label, item.snippet, item.source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
