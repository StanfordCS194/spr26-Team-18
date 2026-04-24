import re

from openai import OpenAI

from .config import OPENAI_MODEL, SUMMARY_SYSTEM_PROMPT, COMPLIANCE_QUESTIONS_PROMPT
from .models import Bill, BillSummary, ComplianceQuestion


MAX_CHARS = 80000  # ~20k tokens — captures full text of real environmental bills

def _bill_text(bill: Bill) -> str:
    text = bill.text or bill.description or ""
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[remaining text omitted — focus summary on provisions above]"
    return (
        f"Bill Number: {bill.bill_number}\n"
        f"Title: {bill.title}\n"
        f"Status: {bill.status}\n"
        f"Subjects: {', '.join(bill.subjects)}\n\n"
        f"Full Text:\n{text}"
    )


def summarize_bill(client: OpenAI, bill: Bill) -> BillSummary:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": _bill_text(bill) + "\n\nWrite a plain-language summary of this bill."},
        ],
    )
    return BillSummary(
        bill_id=bill.bill_id,
        summary_text=response.choices[0].message.content,
        model_used=OPENAI_MODEL,
        cache_hit=False,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )


def generate_compliance_questions(client: OpenAI, bill: Bill) -> list:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": _bill_text(bill) + "\n\n" + COMPLIANCE_QUESTIONS_PROMPT},
        ],
    )
    raw = response.choices[0].message.content
    parsed = re.findall(r"^\d+\.\s+(.+)$", raw, re.MULTILINE)
    return [
        ComplianceQuestion(
            bill_id=bill.bill_id,
            question_number=i + 1,
            question_text=q.strip(),
        )
        for i, q in enumerate(parsed[:5])
    ]


def process_bill(client: OpenAI, bill: Bill) -> tuple:
    summary = summarize_bill(client, bill)
    questions = generate_compliance_questions(client, bill)
    return summary, questions
