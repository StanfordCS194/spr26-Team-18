from __future__ import annotations

import json
from importlib.resources import files


def _load_terms(filename: str) -> tuple[str, ...]:
    path = files(__package__).joinpath(filename)
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return tuple(terms)


def _load_json(filename: str) -> dict:
    path = files(__package__).joinpath(filename)
    return json.loads(path.read_text(encoding="utf-8"))


PACKAGING_TERMS = _load_terms("packaging.txt")
WATER_TERMS = _load_terms("water.txt")
OIL_GAS_TERMS = _load_terms("oil_gas.txt")
MANUFACTURING_TERMS = _load_terms("manufacturing.txt")
FLEET_TERMS = _load_terms("fleet.txt")
CLIMATE_CLAIM_TERMS = _load_terms("climate_claims.txt")
PUBLIC_COMPANY_TERMS = _load_terms("public_company.txt")
CALIFORNIA_TERMS = _load_terms("california.txt")

BILL_PACKAGING_TERMS = _load_terms("bill_packaging.txt")
BILL_WATER_TERMS = _load_terms("bill_water.txt")
BILL_OIL_GAS_TERMS = _load_terms("bill_oil_gas.txt")
BILL_HEAT_LABOR_TERMS = _load_terms("bill_heat_labor.txt")
BILL_FLEET_TERMS = _load_terms("bill_fleet.txt")
BILL_GENERIC_CLIMATE_TERMS = _load_terms("bill_generic_climate.txt")
RANKING_WEIGHTS = _load_json("weights.json")
