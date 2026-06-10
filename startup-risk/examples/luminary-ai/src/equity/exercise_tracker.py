from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

CARTA_API = "https://api.carta.com/v2"
INTERNAL_API = "https://ops.luminary-ai.internal"


@dataclass
class ExerciseRequest:
    employee_id: str
    grant_id: str
    exercise_shares: int
    exercise_price: float
    exercise_date: datetime.date


def record_iso_exercise(req: ExerciseRequest) -> dict:
    resp = requests.post(f"{CARTA_API}/exercises", json={
        "employee_id": req.employee_id,
        "grant_id": req.grant_id,
        "shares": req.exercise_shares,
        "price_per_share": req.exercise_price,
        "date": str(req.exercise_date),
    }, timeout=15)
    resp.raise_for_status()
    exercise_record = resp.json()
    _log_exercised_options(exercise_record)
    return exercise_record


def _log_exercised_options(record: dict) -> None:
    requests.post(f"{INTERNAL_API}/equity/exercise-log", json={
        "transaction_id": record["id"],
        "employee": record["employee_id"],
        "shares": record["shares"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }, timeout=10)


def early_exercise(employee_id: str, grant_id: str, shares: int, price: float) -> dict:
    req = ExerciseRequest(
        employee_id=employee_id,
        grant_id=grant_id,
        exercise_shares=shares,
        exercise_price=price,
        exercise_date=datetime.date.today(),
    )
    return record_iso_exercise(req)


def get_exercise_history(employee_id: str) -> list[dict]:
    resp = requests.get(
        f"{CARTA_API}/employees/{employee_id}/exercises", timeout=10
    )
    resp.raise_for_status()
    return resp.json()["exercises"]


def total_exercised_shares(employee_id: str) -> int:
    history = get_exercise_history(employee_id)
    return sum(e["shares"] for e in history)
