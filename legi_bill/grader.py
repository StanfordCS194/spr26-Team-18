"""Grade a company's exposure to CA environmental bills across 5 axes.

One LLM call combines: per-axis exposure scoring + per-axis evidence
extraction (which bills contributed, with rationale + quoted snippet) +
top-3 overall bill selection. The composite score and letter grade are
computed deterministically in Python after the LLM returns axis scores.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, Tuple

from app.ranking import rank_bills
from .llm import ChatClient
from .models import Bill

AXES = ("emissions", "water", "packaging", "labor", "disclosure")
AXIS_WEIGHTS = {"emissions": 1.0, "water": 1.0, "packaging": 1.0, "labor": 1.0, "disclosure": 1.5}

# How many bills to feed into the LLM call (after filter + anchor merge).
TOP_K = 12
# Snippet length per bill in the prompt (chars).
BILL_SNIPPET_CHARS = 600
# Cap company text in the prompt (chars).
COMPANY_CAP_CHARS = 4000

# Bills we always include as candidates, regardless of token-overlap ranking.
# The token ranker (app.ranking.rank_bills) tends to favor high-volume bills
# (budget, hazardous-substance accounting) over short-but-targeted climate
# bills (SB-253, SB-261, AB-1305). Anchoring these guarantees the LLM at
# least sees them as options for any 10-K.
ANCHOR_BILL_NUMBERS = (
    "SB253",   # Climate Corporate Data Accountability Act
    "SB261",   # Greenhouse Gases: Climate-Related Financial Risk
    "SB54",    # Plastic Pollution Producer Responsibility
    "AB1305",  # Voluntary Carbon Market Disclosures
    "SB1137",  # Oil & Gas Setback
    "SB1383",  # Short-Lived Climate Pollutants: methane
    "AB1080",  # Single-Use Packaging Reduction
    "SB707",   # Responsible Textile Recovery Act
    # AB2782 dropped — the bill we scraped under that number is about
    # Medicare reimbursement for public employees, not workplace heat.
)

# Bills with these tokens in their title are filtered out of grading
# candidates — they're high-volume but irrelevant to env exposure.
TITLE_REJECT_TOKENS = (
    "budget",
    "trailer bill",
    "maintenance of the codes",
    "agencies: boards, commissions",
    "housing",
    "school transportation",
    "youth offender",
    "synthetic cannabinoids",
    "elected officers",
    "personal protective",
    "service: elected",
)


SYSTEM_PROMPT = """You are a California environmental policy analyst.

Given a company's 10-K (or company description) and a list of California bills, you must:
(1) Score the company's exposure to each of 5 regulatory axes on a 0-100 scale where 0 = essentially unaffected and 100 = a primary, highly-impacted target.
(2) For each axis, identify 1-3 of the provided bills that drive the score. For each bill, give:
    - rationale: 1-2 sentences tying THIS specific company's operations (drawn from the 10-K text) to THIS bill's clauses. No generic statements.
    - bill_quote: a 15-50 word VERBATIM snippet from that bill's title/description/text.
    - company_quote: a 15-50 word VERBATIM snippet from the company's 10-K or description that justifies why this bill applies. This is the evidence anchor — it must be a real phrase from the input, not paraphrased.
(3) Pick the 3 most relevant bills overall, each labeled with its primary axis.

The 5 axes:
- emissions: greenhouse gas, air quality, oil & gas, transportation emissions
- water: water quality, water rights, drought, wastewater, agricultural water use
- packaging: producer responsibility, single-use plastics, recycling, textile recovery
- labor: workplace heat standards, hazardous-materials worker safety, environmental justice for workers
- disclosure: corporate climate disclosure, voluntary carbon market disclosures, SB-253 / SB-261 style reporting

PRIORITIZATION RULES (apply these when picking evidence and top_bills):
- Public companies with revenue >$1B in the 10-K MUST evaluate disclosure exposure against SB253 and SB261 if those bills are in the candidate list. Public reporters at this scale are squarely in scope for both.
- Companies that "purchase carbon offsets," "make net-zero claims," or "disclose voluntary carbon market participation" in their 10-K MUST evaluate against AB1305 if available.
- Bills with "Climate Corporate Data Accountability," "Greenhouse Gases: climate-related financial risk," "Voluntary carbon market disclosures," "Plastic Pollution Producer Responsibility," "Solid waste: packaging," or "Responsible Textile Recovery" in their TITLE are high-signal — prefer them over generic-sounding bills (titles like "An act to amend Sections..." with no domain-specific content) when both are available.
- Avoid using methane-only bills (e.g. SB1383 "Short-lived climate pollutants: methane: dairy and livestock") for non-agricultural / non-oil&gas companies; they're a poor fit for tech and apparel.
- top_bills should reflect the company's TRUE primary regulatory exposure, not just what scored high on token overlap. If the company is a beverage producer, packaging bills go in top_bills. If the company is an oil major, oil-and-gas siting bills go in top_bills. If the company is a public reporter, disclosure bills go in top_bills.

Be honest. If a company has minimal exposure on an axis, score it low. Do not fabricate quotes — both bill_quote AND company_quote must be verbatim from the inputs. Do not pad evidence. If an axis truly has no relevant bills in the provided list, return an empty evidence array for that axis and a low score (under 20). If you cannot find a verbatim company_quote that supports a bill, drop that evidence item rather than fabricating one.

Return ONLY valid JSON matching this exact schema:
{
  "axes": {
    "emissions":  {"score": <int 0-100>, "evidence": [{"bill_number": str, "rationale": str, "bill_quote": str, "company_quote": str}, ...]},
    "water":      {"score": <int 0-100>, "evidence": [...]},
    "packaging":  {"score": <int 0-100>, "evidence": [...]},
    "labor":      {"score": <int 0-100>, "evidence": [...]},
    "disclosure": {"score": <int 0-100>, "evidence": [...]}
  },
  "top_bills": [
    {"bill_number": str, "primary_axis": str, "rationale": str}
  ]
}
"""


def _format_bills_for_prompt(top_bills: list[Tuple[Bill, float, str]]) -> str:
    lines = []
    for i, (b, score, tier) in enumerate(top_bills, 1):
        subjects = ", ".join(b.subjects) if b.subjects else "(none)"
        snippet = (b.text or b.description or "").strip().replace("\n", " ")
        if len(snippet) > BILL_SNIPPET_CHARS:
            snippet = snippet[:BILL_SNIPPET_CHARS] + "..."
        lines.append(
            f"{i}. {b.bill_number} — {b.title}\n"
            f"   subjects: {subjects}\n"
            f"   relevance_tier: {tier} (raw_score={score:.3f})\n"
            f"   text_or_description: {snippet}"
        )
    return "\n\n".join(lines)


def _composite_and_letter(axes: dict) -> tuple[int, str]:
    """Deterministic composite score + letter grade from per-axis scores."""
    num = 0.0
    den = 0.0
    for a in AXES:
        s = max(0, min(100, int(axes.get(a, {}).get("score", 0))))
        w = AXIS_WEIGHTS[a]
        num += s * w
        den += w
    composite = round(num / den) if den > 0 else 0

    # Higher exposure = worse grade.
    if composite >= 85: letter = "F"
    elif composite >= 75: letter = "D"
    elif composite >= 65: letter = "D+"
    elif composite >= 55: letter = "C-"
    elif composite >= 45: letter = "C"
    elif composite >= 38: letter = "C+"
    elif composite >= 32: letter = "B-"
    elif composite >= 26: letter = "B"
    elif composite >= 20: letter = "B+"
    elif composite >= 14: letter = "A-"
    else: letter = "A"
    return composite, letter


def grade_company(
    client: ChatClient,
    bills_with_summary: Iterable[Tuple[Bill, str]],
    company_text: str,
    company_name: str | None = None,
) -> dict:
    """Score a company across 5 axes with evidence.

    Returns a dict matching the /api/grade response shape. Raises
    on LLM failure; caller is responsible for HTTP error handling.
    """
    company_text = (company_text or "").strip()
    if not company_text:
        raise ValueError("company_text is required")

    # Materialize iterable so we can both rank AND look up anchors against it.
    bills_with_summary = list(bills_with_summary)

    # Rank bills by token-overlap first; filter junk; merge in anchor bills.
    ranked = rank_bills(company_text, bills_with_summary)

    def _keep(bill) -> bool:
        title_lc = (bill.title or "").lower()
        return not any(tok in title_lc for tok in TITLE_REJECT_TOKENS)

    filtered = [(b, s, t) for b, s, t in ranked if s > 0 and _keep(b)]

    # Build anchor list from the original bill set (anchors keep score=0 placeholder).
    bills_by_number = {}
    for b, _ in bills_with_summary:
        bills_by_number[b.bill_number.replace("-", "").replace(" ", "").upper()] = b

    anchor_bills = []
    seen_numbers = {b.bill_number for b, _, _ in filtered}
    for anchor in ANCHOR_BILL_NUMBERS:
        if anchor in bills_by_number and bills_by_number[anchor].bill_number not in seen_numbers:
            anchor_bills.append((bills_by_number[anchor], 0.0, "Anchor"))
            seen_numbers.add(bills_by_number[anchor].bill_number)

    # Combine: anchors first (LLM sees them prominently), then top filtered, capped at TOP_K.
    combined = anchor_bills + filtered
    top_bills = combined[:TOP_K]

    if not top_bills:
        # Graceful no-signal case.
        return {
            "company": company_name or "(unspecified)",
            "is_featured": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "axes": {a: {"score": 0, "evidence": []} for a in AXES},
            "composite": 0,
            "grade": "low exposure",
            "top_bills": [],
            "no_signal": True,
        }

    # Build prompt.
    company_excerpt = company_text[:COMPANY_CAP_CHARS]
    user_prompt = (
        f"COMPANY DESCRIPTION:\n{company_excerpt}\n\n"
        f"TOP {len(top_bills)} BILLS (pre-ranked by token-overlap relevance, you may re-weight):\n\n"
        f"{_format_bills_for_prompt(top_bills)}"
    )

    response = client.complete(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.content or "{}"
    parsed = json.loads(raw)

    # Validate + fill defaults; trust nothing from the LLM.
    axes_out = {}
    for a in AXES:
        ax = parsed.get("axes", {}).get(a, {}) or {}
        score = ax.get("score", 0)
        try:
            score = max(0, min(100, int(score)))
        except (TypeError, ValueError):
            score = 0
        evidence = ax.get("evidence", []) or []
        clean_ev = []
        for e in evidence[:3]:
            if not isinstance(e, dict):
                continue
            # Backward compat: older results used `quote` for the bill quote.
            bill_quote = e.get("bill_quote") or e.get("quote") or ""
            clean_ev.append({
                "bill_number": str(e.get("bill_number", ""))[:32],
                "rationale": str(e.get("rationale", ""))[:600],
                "bill_quote": str(bill_quote)[:600],
                "company_quote": str(e.get("company_quote", ""))[:600],
            })
        axes_out[a] = {"score": score, "evidence": clean_ev}

    composite, letter = _composite_and_letter(axes_out)

    # Top bills: take what LLM provided, fall back to the ranked list.
    top_bills_out = []
    seen = set()
    for tb in (parsed.get("top_bills") or [])[:5]:
        if not isinstance(tb, dict):
            continue
        bn = str(tb.get("bill_number", "")).strip()
        if not bn or bn in seen:
            continue
        # Pull title from our actual bills list.
        match = next((b for b, _, _ in top_bills if b.bill_number == bn), None)
        if not match:
            continue
        primary_axis = str(tb.get("primary_axis", "")).strip()
        if primary_axis not in AXES:
            primary_axis = "disclosure"  # safe default
        top_bills_out.append({
            "bill_number": match.bill_number,
            "title": match.title,
            "primary_axis": primary_axis,
            "rationale": str(tb.get("rationale", ""))[:400],
            "url": match.url,
        })
        seen.add(bn)
        if len(top_bills_out) >= 3:
            break

    # Backfill if LLM gave us fewer than 3.
    if len(top_bills_out) < 3:
        for b, score, _ in top_bills:
            if b.bill_number in seen:
                continue
            top_bills_out.append({
                "bill_number": b.bill_number,
                "title": b.title,
                "primary_axis": "disclosure",
                "rationale": f"High token-overlap relevance ({score:.2f}).",
                "url": b.url,
            })
            seen.add(b.bill_number)
            if len(top_bills_out) >= 3:
                break

    return {
        "company": company_name or "(unspecified)",
        "is_featured": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "axes": axes_out,
        "composite": composite,
        "grade": letter,
        "top_bills": top_bills_out,
        "no_signal": False,
    }
