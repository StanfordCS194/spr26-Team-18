from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

CARTA_API = "https://api.carta.com/v2"
INTERNAL_API = "https://ops.luminary-ai.internal"

AUTHORIZED_SHARES = 100_000_000
PREFERRED_SERIES_A_PRICE = 2.14


@dataclass
class ShareIssuance:
    investor_id: str
    share_class: str
    shares: int
    price_per_share: float
    issuance_date: datetime.date
    certificate_id: str | None = None


def issue_preferred_stock(investor_id: str, shares: int) -> dict:
    issuance = ShareIssuance(
        investor_id=investor_id,
        share_class="Series A Preferred",
        shares=shares,
        price_per_share=PREFERRED_SERIES_A_PRICE,
        issuance_date=datetime.date.today(),
    )
    resp = requests.post(f"{CARTA_API}/securities", json={
        "holder_id": issuance.investor_id,
        "class": issuance.share_class,
        "quantity": issuance.shares,
        "issue_price": issuance.price_per_share,
        "date": str(issuance.issuance_date),
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def record_stock_issuance(issuance: ShareIssuance) -> str:
    resp = requests.post(f"{INTERNAL_API}/equity/issuances", json={
        "investor_id": issuance.investor_id,
        "class": issuance.share_class,
        "shares": issuance.shares,
        "price": issuance.price_per_share,
        "date": str(issuance.issuance_date),
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["issuance_id"]


def issue_common_stock_issuance(employee_id: str, shares: int, price: float) -> dict:
    issuance = ShareIssuance(
        investor_id=employee_id,
        share_class="Common",
        shares=shares,
        price_per_share=price,
        issuance_date=datetime.date.today(),
    )
    resp = requests.post(f"{CARTA_API}/securities", json={
        "holder_id": issuance.investor_id,
        "class": "Common",
        "quantity": issuance.shares,
        "issue_price": issuance.price_per_share,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_cap_table_summary() -> dict:
    resp = requests.get(f"{CARTA_API}/cap-table", timeout=10)
    resp.raise_for_status()
    return resp.json()
