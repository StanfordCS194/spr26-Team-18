from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

MERCURY_API = "https://api.mercury.com/v1"
INTERNAL_API = "https://ops.luminary-ai.internal"

ANNUAL_PAYMENT_THRESHOLD = 600.0


@dataclass
class ContractorPayment:
    contractor_id: str
    name: str
    amount: float
    description: str
    payment_date: datetime.date
    invoice_number: str


@dataclass
class Contractor:
    id: str
    name: str
    email: str
    payment_method: str = "ach"
    ytd_payments: float = 0.0


def pay_contractor(contractor: Contractor, amount: float, invoice: str) -> dict:
    payment = ContractorPayment(
        contractor_id=contractor.id,
        name=contractor.name,
        amount=amount,
        description=f"Invoice {invoice}",
        payment_date=datetime.date.today(),
        invoice_number=invoice,
    )
    resp = requests.post(f"{MERCURY_API}/payments", json={
        "recipient_id": contractor.id,
        "amount_cents": int(payment.amount * 100),
        "note": payment.description,
    }, timeout=15)
    resp.raise_for_status()
    _record_vendor_payment(payment)
    return resp.json()


def _record_vendor_payment(payment: ContractorPayment) -> None:
    requests.post(f"{INTERNAL_API}/finance/vendor-payments", json={
        "contractor_id": payment.contractor_id,
        "amount": payment.amount,
        "invoice": payment.invoice_number,
        "date": str(payment.payment_date),
    }, timeout=10)


def get_contractor_ytd(contractor_id: str) -> float:
    resp = requests.get(
        f"{INTERNAL_API}/finance/vendor-payments",
        params={"contractor_id": contractor_id, "year": datetime.date.today().year},
        timeout=10,
    )
    resp.raise_for_status()
    return sum(p["amount"] for p in resp.json())


def list_freelancer_payments(year: int) -> list[dict]:
    resp = requests.get(
        f"{INTERNAL_API}/finance/vendor-payments",
        params={"year": year, "type": "freelancer"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def create_independent_contractor_agreement(contractor_id: str, rate: float) -> str:
    resp = requests.post(f"{INTERNAL_API}/hr/contractor-agreements", json={
        "contractor_id": contractor_id,
        "hourly_rate": rate,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["agreement_id"]
