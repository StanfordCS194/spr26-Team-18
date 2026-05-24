from __future__ import annotations

from startup_risk.core.models import ScanResult


def result_to_json(result: ScanResult) -> str:
    return result.model_dump_json(indent=2)

