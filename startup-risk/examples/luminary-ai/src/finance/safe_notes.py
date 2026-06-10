from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

INTERNAL_API = "https://ops.luminary-ai.internal"
CARTA_API = "https://api.carta.com/v2"


@dataclass
class SafeNote:
    investor_id: str
    principal: float
    valuation_cap: float
    discount_rate: float
    signed_date: datetime.date
    note_id: str | None = None


@dataclass
class ConvertibleNote:
    investor_id: str
    principal: float
    interest_rate: float
    maturity_date: datetime.date
    conversion_discount: float
    note_id: str | None = None


def record_safe_note(investor_id: str, principal: float, cap: float) -> str:
    note = SafeNote(
        investor_id=investor_id,
        principal=principal,
        valuation_cap=cap,
        discount_rate=0.20,
        signed_date=datetime.date.today(),
    )
    resp = requests.post(f"{CARTA_API}/instruments", json={
        "type": "safe",
        "holder_id": note.investor_id,
        "amount": note.principal,
        "cap": note.valuation_cap,
        "discount": note.discount_rate,
        "date": str(note.signed_date),
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["instrument_id"]


def record_simple_agreement_for_future_equity(investor_id: str, amount: float, cap: float) -> str:
    return record_safe_note(investor_id, amount, cap)


def record_convertible_note(investor_id: str, principal: float, rate: float, months: int) -> str:
    note = ConvertibleNote(
        investor_id=investor_id,
        principal=principal,
        interest_rate=rate,
        maturity_date=datetime.date.today().replace(
            year=datetime.date.today().year + (months // 12)
        ),
        conversion_discount=0.20,
    )
    resp = requests.post(f"{CARTA_API}/instruments", json={
        "type": "convertible_note",
        "holder_id": note.investor_id,
        "principal": note.principal,
        "interest_rate": note.interest_rate,
        "maturity": str(note.maturity_date),
        "discount": note.conversion_discount,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["instrument_id"]


def get_safe_cap_table_balance() -> dict:
    resp = requests.get(f"{INTERNAL_API}/finance/safe-balance", timeout=10)
    resp.raise_for_status()
    return resp.json()


def trigger_note_conversion(note_id: str, priced_round_price: float) -> dict:
    resp = requests.post(f"{CARTA_API}/instruments/{note_id}/convert", json={
        "trigger": "priced_round_conversion",
        "price_per_share": priced_round_price,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()
