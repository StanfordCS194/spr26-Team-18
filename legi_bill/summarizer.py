import re

import anthropic

from .config import CLAUDE_MODEL, SUMMARY_SYSTEM_PROMPT, COMPLIANCE_QUESTIONS_PROMPT
from .models import Bill, BillSummary, ComplianceQuestion


def _bill_content_block(bill: Bill) -> dict:
    return {
        "type": "text",
        "text": (
            f"Bill Number: {bill.bill_number}\n"
            f"Title: {bill.title}\n"
            f"Status: {bill.status}\n"
            f"Subjects: {', '.join(bill.subjects)}\n\n"
            f"Full Text:\n{bill.text or bill.description}"
        ),
        "cache_control": {"type": "ephemeral"},
    }


def _system_block() -> list:
    return [
        {
            "type": "text",
            "text": SUMMARY_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def summarize_bill(client: anthropic.Anthropic, bill: Bill) -> BillSummary:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=[
            {
                "role": "user",
                "content": [
                    _bill_content_block(bill),
                    {"type": "text", "text": "Write a plain-language summary of this bill."},
                ],
            }
        ],
    )
    cache_hit = getattr(response.usage, "cache_read_input_tokens", 0) > 0
    return BillSummary(
        bill_id=bill.bill_id,
        summary_text=response.content[0].text,
        model_used=CLAUDE_MODEL,
        cache_hit=cache_hit,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def generate_compliance_questions(
    client: anthropic.Anthropic, bill: Bill
) -> list:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=[
            {
                "role": "user",
                "content": [
                    _bill_content_block(bill),
                    {"type": "text", "text": COMPLIANCE_QUESTIONS_PROMPT},
                ],
            }
        ],
    )
    raw = response.content[0].text
    parsed = re.findall(r"^\d+\.\s+(.+)$", raw, re.MULTILINE)
    return [
        ComplianceQuestion(
            bill_id=bill.bill_id,
            question_number=i + 1,
            question_text=q.strip(),
        )
        for i, q in enumerate(parsed[:5])
    ]


def process_bill(
    client: anthropic.Anthropic, bill: Bill
) -> tuple:
    summary = summarize_bill(client, bill)
    questions = generate_compliance_questions(client, bill)
    return summary, questions
