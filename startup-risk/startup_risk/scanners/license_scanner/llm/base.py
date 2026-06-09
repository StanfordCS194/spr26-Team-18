from __future__ import annotations

import json
from typing import Protocol

from startup_risk.scanners.license_scanner.models import LLMBatchResponse, LLMTask, LLMTaskItem


class BatchProvider(Protocol):
    name: str

    def submit_and_wait(
        self,
        tasks: list[LLMTask],
        *,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> list[LLMBatchResponse]:
        """Submit batch requests, block until done, and return per-task outputs."""


def build_prompt(items: list[LLMTaskItem]) -> str:
    payload = []
    for item in items:
        payload.append(
            {
                "task_item_id": item.item_id,
                "dependency": {
                    "name": item.dependency_name,
                    "ecosystem": item.ecosystem,
                    "declared_license": item.declared_license,
                },
                "evidence": [
                    {
                        "source": evidence.source,
                        "file": evidence.file,
                        "line": evidence.line,
                        "detected_license": evidence.detected_license,
                        "text": (evidence.text or "")[:4000],
                    }
                    for evidence in item.evidence[:4]
                ],
            }
        )

    return (
        "You are assisting an offline third-party dependency license scanner. "
        "Use only the provided dependency metadata and license evidence. Do not invent dependencies, files, or versions. "
        "Return only valid JSON with this exact shape: "
        '{"items":[{"task_item_id":"string","detected_license":string|null,'
        '"confidence":"low|medium|high","evidence":["short source-backed strings"],'
        '"is_custom_or_modified":boolean,"needs_review":boolean,"reason":"string"}]}. '
        "If evidence is insufficient, set detected_license to null and needs_review to true.\n\n"
        f"INPUT:\n{json.dumps(payload, sort_keys=True)}"
    )
