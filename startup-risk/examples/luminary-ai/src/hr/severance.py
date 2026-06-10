from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

INTERNAL_API = "https://ops.luminary-ai.internal"
DOCUSIGN_API = "https://demo.docusign.net/restapi/v2"


@dataclass
class SeveranceAgreement:
    employee_id: str
    severance_pay: float
    notice_period_days: int
    equity_acceleration: bool
    agreement_date: datetime.date


@dataclass
class RetentionBonus:
    employee_id: str
    bonus_amount: float
    deferral_months: int
    vest_date: datetime.date


def create_severance_agreement(
    employee_id: str,
    severance_pay: float,
    notice_days: int,
    accelerate_equity: bool = False,
) -> str:
    agreement = SeveranceAgreement(
        employee_id=employee_id,
        severance_pay=severance_pay,
        notice_period_days=notice_days,
        equity_acceleration=accelerate_equity,
        agreement_date=datetime.date.today(),
    )
    resp = requests.post(f"{INTERNAL_API}/hr/severance", json={
        "employee_id": agreement.employee_id,
        "amount": agreement.severance_pay,
        "notice_days": agreement.notice_period_days,
        "equity_accelerate": agreement.equity_acceleration,
        "date": str(agreement.agreement_date),
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["agreement_id"]


def schedule_retention_bonus_deferral(employee_id: str, amount: float, months: int) -> str:
    vest = datetime.date.today().replace(
        month=((datetime.date.today().month - 1 + months) % 12) + 1
    )
    bonus = RetentionBonus(
        employee_id=employee_id,
        bonus_amount=amount,
        deferral_months=months,
        vest_date=vest,
    )
    resp = requests.post(f"{INTERNAL_API}/hr/retention-bonuses", json={
        "employee_id": bonus.employee_id,
        "amount": bonus.bonus_amount,
        "deferred_until": str(bonus.vest_date),
        "type": "retention_bonus_deferral",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["bonus_id"]


def get_deferred_compensation_balance(employee_id: str) -> float:
    resp = requests.get(
        f"{INTERNAL_API}/hr/deferred-compensation/{employee_id}", timeout=10
    )
    resp.raise_for_status()
    return resp.json()["balance"]


def execute_separation_payment(employee_id: str, amount: float) -> dict:
    resp = requests.post(f"{INTERNAL_API}/finance/separation-payments", json={
        "employee_id": employee_id,
        "amount": amount,
        "date": str(datetime.date.today()),
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()
