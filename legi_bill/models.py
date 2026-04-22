from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Bill:
    bill_id: int
    bill_number: str
    title: str
    description: str
    state: str
    status: str
    session_year: int
    url: str
    subjects: list
    text: Optional[str] = None
    text_doc_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BillSummary:
    bill_id: int
    summary_text: str
    model_used: str
    cache_hit: bool
    input_tokens: int
    output_tokens: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComplianceQuestion:
    bill_id: int
    question_number: int
    question_text: str
    created_at: datetime = field(default_factory=datetime.utcnow)
