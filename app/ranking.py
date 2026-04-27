import re
from typing import Iterable, List, Tuple

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


def _tokenize(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS}


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

    scored: List[Tuple[Bill, float]] = []
    for bill, summary_text in bills_with_summary:
        subjects = " ".join(bill.subjects) if bill.subjects else ""
        corpus = f"{bill.title} {bill.description} {subjects} {summary_text} {bill.text or ''}"
        bill_tokens = _tokenize(corpus)
        if not bill_tokens:
            scored.append((bill, 0.0))
            continue

        overlap = company_tokens & bill_tokens
        if not overlap:
            scored.append((bill, 0.0))
            continue

        base = len(overlap) / max(1, min(len(company_tokens), len(bill_tokens)))
        subject_boost = 0.02 * sum(
            1 for s in (bill.subjects or []) if s in ENVIRONMENTAL_SUBJECTS
        )
        scored.append((bill, (base + subject_boost) * env_factor))

    return _assign_tiers(scored)
