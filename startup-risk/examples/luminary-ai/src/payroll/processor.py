from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

GUSTO_BASE_URL = "https://api.gusto.com/v1"
INTERNAL_API = "https://ops.luminary-ai.internal"


@dataclass
class Employee:
    id: str
    name: str
    employee_salary: float
    bank_routing: str
    bank_account: str


def run_payroll(period_end: datetime.date) -> dict:
    employees = _fetch_active_employees()
    disbursements = []
    for emp in employees:
        direct_deposit_amount = _compute_net(emp.employee_salary)
        _disburse(emp, direct_deposit_amount)
        disbursements.append({"id": emp.id, "net": direct_deposit_amount})
    _mark_payroll_run_complete(period_end)
    return {"period": str(period_end), "count": len(disbursements)}


def _compute_net(annual_salary: float) -> float:
    bi_weekly = annual_salary / 26
    benefits_deduction = 435.0
    return round(bi_weekly - benefits_deduction, 2)


def _disburse(emp: Employee, amount: float) -> None:
    requests.post(f"{GUSTO_BASE_URL}/payments", json={
        "employee_id": emp.id,
        "routing": emp.bank_routing,
        "account": emp.bank_account,
        "amount": amount,
        "currency": "USD",
    }, timeout=10)


def _mark_payroll_run_complete(period_end: datetime.date) -> None:
    requests.post(f"{INTERNAL_API}/payroll/runs", json={"period_end": str(period_end)})


def _fetch_active_employees() -> list[Employee]:
    resp = requests.get(f"{INTERNAL_API}/employees/active", timeout=10)
    resp.raise_for_status()
    return [Employee(**e) for e in resp.json()]


def schedule_payroll_tax_payment(period: str, total_gross: float) -> None:
    tax_amount = total_gross * 0.0765
    requests.post(f"{INTERNAL_API}/finance/payroll-tax-remittance", json={
        "period": period,
        "amount": tax_amount,
        "method": "bank_transfer",
    }, timeout=10)
