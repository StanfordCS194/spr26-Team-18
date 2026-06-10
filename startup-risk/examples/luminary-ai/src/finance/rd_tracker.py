from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

import requests

INTERNAL_API = "https://ops.luminary-ai.internal"


class RdCategory(str, Enum):
    MODEL_TRAINING = "model_training"
    DATA_ENGINEERING = "data_engineering"
    PRODUCT_R_AND_D = "product_r_and_d"
    INFRA = "infra"


@dataclass
class ResearchExpense:
    category: RdCategory
    description: str
    amount: float
    incurred_date: datetime.date
    employee_id: str | None = None
    vendor_id: str | None = None


def record_research_expense(expense: ResearchExpense) -> str:
    resp = requests.post(f"{INTERNAL_API}/finance/expenses", json={
        "type": "research",
        "category": expense.category.value,
        "description": expense.description,
        "amount": expense.amount,
        "date": str(expense.incurred_date),
        "treatment": "research_cost_expensed_as_incurred",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["expense_id"]


def record_rd_cost_expensed(category: str, amount: float, notes: str) -> dict:
    resp = requests.post(f"{INTERNAL_API}/finance/rd-budget", json={
        "category": category,
        "amount": amount,
        "notes": notes,
        "accounting_treatment": "development_cost_expensed_as_incurred",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_quarterly_rd_spend(year: int, quarter: int) -> float:
    resp = requests.get(
        f"{INTERNAL_API}/finance/rd-budget/summary",
        params={"year": year, "quarter": quarter},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["total_spent"]


def log_software_dev_cost_expensed(project_id: str, labor_hours: float, rate: float) -> None:
    amount = labor_hours * rate
    requests.post(f"{INTERNAL_API}/finance/rd-budget", json={
        "project_id": project_id,
        "labor_hours": labor_hours,
        "rate": rate,
        "amount": amount,
        "treatment": "immediate_expense",
    }, timeout=10)
