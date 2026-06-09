import json
import re

from .config import SUMMARY_SYSTEM_PROMPT, COMPLIANCE_QUESTIONS_PROMPT
from .llm import ChatClient
from .models import Bill, BillSummary, ComplianceQuestion

MAX_CHARS = 80000

STRUCTURED_SYSTEM_PROMPT = """You are a nonpartisan legislative analyst specializing in California environmental law.
Analyze the provided bill and return a JSON object with these exact fields:

{
  "summary": "150-250 word plain-language summary structured as: (1) What it does, (2) Who it affects, (3) Key requirements or deadlines, (4) Current status. Neutral tone, 8th-grade reading level.",
  "effective_date": "The date this bill takes effect or becomes enforceable. Use 'Unknown' if not specified.",
  "enforcement_agency": "The primary agency responsible for enforcement (e.g. CARB, State Water Board, CalEPA). Use 'Unknown' if not specified.",
  "penalty": "Maximum fine or penalty for non-compliance. Use 'Unknown' if not specified.",
  "exemptions": "Any key exemptions (e.g. small businesses, certain industries). Use 'None stated' if not specified.",
  "industries": ["list", "of", "affected", "industries"]
}

For industries, choose from: Agriculture, Construction, Energy, Forestry, Manufacturing, Mining, Real Estate, Retail, Technology, Transportation, Utilities, Waste Management, Water. Include only those clearly affected.

Return only valid JSON with no additional text."""


def _bill_text(bill: Bill) -> str:
    text = bill.text or bill.description or ""
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[remaining text omitted]"
    return (
        f"Bill Number: {bill.bill_number}\n"
        f"Title: {bill.title}\n"
        f"Status: {bill.status}\n"
        f"Subjects: {', '.join(bill.subjects)}\n\n"
        f"Full Text:\n{text}"
    )


def summarize_bill(client: ChatClient, bill: Bill) -> BillSummary:
    response = client.complete(
        max_tokens=800,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STRUCTURED_SYSTEM_PROMPT},
            {"role": "user", "content": _bill_text(bill)},
        ],
    )

    raw = response.content
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"summary": raw}

    summary_text = parsed.pop("summary", raw)
    metadata = {
        "effective_date": parsed.get("effective_date", "Unknown"),
        "enforcement_agency": parsed.get("enforcement_agency", "Unknown"),
        "penalty": parsed.get("penalty", "Unknown"),
        "exemptions": parsed.get("exemptions", "None stated"),
        "industries": parsed.get("industries", []),
    }

    return BillSummary(
        bill_id=bill.bill_id,
        summary_text=summary_text,
        model_used=response.model,
        cache_hit=False,
        input_tokens=response.usage.input_tokens or 0,
        output_tokens=response.usage.output_tokens or 0,
        metadata=metadata,
    )


def generate_compliance_questions(client: ChatClient, bill: Bill) -> list:
    response = client.complete(
        max_tokens=512,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": _bill_text(bill) + "\n\n" + COMPLIANCE_QUESTIONS_PROMPT},
        ],
    )
    raw = response.content
    parsed = re.findall(r"^\d+\.\s+(.+)$", raw, re.MULTILINE)
    return [
        ComplianceQuestion(
            bill_id=bill.bill_id,
            question_number=i + 1,
            question_text=q.strip(),
        )
        for i, q in enumerate(parsed[:5])
    ]


def process_bill(client: ChatClient, bill: Bill) -> tuple:
    summary = summarize_bill(client, bill)
    questions = generate_compliance_questions(client, bill)
    return summary, questions
