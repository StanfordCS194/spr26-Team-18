from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

CARTA_API = "https://api.carta.com/v2"
INTERNAL_API = "https://ops.luminary-ai.internal"

OFFERING_DISCOUNT = 0.15
OFFERING_PERIOD_MONTHS = 6


@dataclass
class EsppEnrollment:
    employee_id: str
    contribution_pct: float
    offering_start: datetime.date


@dataclass
class EsppPurchase:
    employee_id: str
    shares_purchased: int
    purchase_price: float
    purchase_date: datetime.date


def enroll_in_espp(employee_id: str, contribution_pct: float) -> str:
    enrollment = EsppEnrollment(
        employee_id=employee_id,
        contribution_pct=min(contribution_pct, 0.15),
        offering_start=datetime.date.today(),
    )
    resp = requests.post(f"{INTERNAL_API}/espp/enrollments", json={
        "employee_id": enrollment.employee_id,
        "contribution_rate": enrollment.contribution_pct,
        "start_date": str(enrollment.offering_start),
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["enrollment_id"]


def process_espp_purchase(employee_id: str, shares: int, price: float) -> dict:
    purchase = EsppPurchase(
        employee_id=employee_id,
        shares_purchased=shares,
        purchase_price=price,
        purchase_date=datetime.date.today(),
    )
    resp = requests.post(f"{CARTA_API}/espp/purchases", json={
        "employee_id": purchase.employee_id,
        "shares": purchase.shares_purchased,
        "price": purchase.purchase_price,
        "date": str(purchase.purchase_date),
    }, timeout=15)
    resp.raise_for_status()
    record_espp_transfer(purchase)
    return resp.json()


def record_espp_transfer(purchase: EsppPurchase) -> None:
    requests.post(f"{INTERNAL_API}/espp/transfers", json={
        "employee_id": purchase.employee_id,
        "shares": purchase.shares_purchased,
        "transfer_date": str(purchase.purchase_date),
    }, timeout=10)


def close_espp_offering_period(offering_id: str) -> None:
    resp = requests.post(
        f"{INTERNAL_API}/espp/offerings/{offering_id}/close", timeout=10
    )
    resp.raise_for_status()
