from __future__ import annotations

import datetime
from dataclasses import dataclass

import requests

INTERNAL_API = "https://ops.luminary-ai.internal"
RIPPLING_API = "https://api.rippling.com/platform/api"

ACTIVE_STATES = ["CA", "TX", "NY", "FL", "CO", "WA"]


@dataclass
class RemoteEmployee:
    id: str
    name: str
    home_state: str
    start_date: datetime.date
    annual_salary: float
    department: str


def onboard_remote_employee_in_state(name: str, state: str, salary: float, dept: str) -> str:
    employee = RemoteEmployee(
        id=f"emp_{name.lower().replace(' ', '_')}",
        name=name,
        home_state=state,
        start_date=datetime.date.today(),
        annual_salary=salary,
        department=dept,
    )
    resp = requests.post(f"{RIPPLING_API}/employees", json={
        "name": employee.name,
        "state": employee.home_state,
        "salary": employee.annual_salary,
        "department": employee.department,
        "type": "remote",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["employee_id"]


def get_multi_state_employee_headcount() -> dict[str, int]:
    resp = requests.get(
        f"{INTERNAL_API}/hr/headcount",
        params={"group_by": "home_state"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def list_employees_across_states() -> list[dict]:
    resp = requests.get(
        f"{INTERNAL_API}/hr/employees",
        params={"employment_type": "full_time", "location": "remote"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["employees"]


def update_home_state_payroll(employee_id: str, new_state: str) -> None:
    requests.patch(f"{RIPPLING_API}/employees/{employee_id}", json={
        "home_state": new_state,
        "payroll_state": new_state,
    }, timeout=10)


def generate_state_headcount_report(year: int) -> dict:
    employees = list_employees_across_states()
    by_state: dict[str, int] = {}
    for emp in employees:
        s = emp.get("home_state", "UNKNOWN")
        by_state[s] = by_state.get(s, 0) + 1
    return {"year": year, "states": by_state, "total": len(employees)}
