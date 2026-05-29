from __future__ import annotations

import json

from startup_risk.core.models import ScanResult


def result_to_json(result: ScanResult) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)
