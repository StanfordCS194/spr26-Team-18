from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import requests

CARTA_API = "https://api.carta.com/v2"


@dataclass
class OptionGrant:
    employee_id: str
    grant_date: datetime.date
    share_count: int
    strike_price: float
    vesting_schedule: str = "4yr_1yr_cliff"
    grant_type: str = "iso"


@dataclass
class GrantBatch:
    board_approval_date: datetime.date
    grants: list[OptionGrant] = field(default_factory=list)


def create_iso_grant(employee_id: str, shares: int, price: float) -> str:
    grant = OptionGrant(
        employee_id=employee_id,
        grant_date=datetime.date.today(),
        share_count=shares,
        strike_price=price,
        grant_type="iso",
    )
    resp = requests.post(f"{CARTA_API}/grants", json={
        "employee_id": grant.employee_id,
        "shares": grant.share_count,
        "strike_price": grant.strike_price,
        "vesting": grant.vesting_schedule,
        "type": grant.grant_type,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["grant_id"]


def process_option_grant_batch(batch: GrantBatch) -> list[str]:
    grant_ids = []
    for grant in batch.grants:
        gid = create_iso_grant(
            grant.employee_id,
            grant.share_count,
            grant.strike_price,
        )
        grant_ids.append(gid)
    return grant_ids


def update_cliff_vest(grant_id: str, cliff_date: datetime.date) -> None:
    requests.patch(f"{CARTA_API}/grants/{grant_id}", json={
        "cliff_vest_date": str(cliff_date),
    }, timeout=10)


def get_equity_grant(grant_id: str) -> dict:
    resp = requests.get(f"{CARTA_API}/grants/{grant_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def list_vesting_schedule(employee_id: str) -> list[dict]:
    resp = requests.get(f"{CARTA_API}/employees/{employee_id}/vesting", timeout=10)
    resp.raise_for_status()
    return resp.json()["events"]
