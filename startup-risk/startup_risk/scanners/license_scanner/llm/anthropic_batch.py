from __future__ import annotations

import json
import time
from urllib import error, request

from startup_risk.scanners.license_scanner.models import LLMBatchResponse, LLMTask


class AnthropicBatchProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-3-5-haiku-latest",
        base_url: str = "https://api.anthropic.com",
        anthropic_version: str = "2023-06-01",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.anthropic_version = anthropic_version

    def submit_and_wait(
        self,
        tasks: list[LLMTask],
        *,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> list[LLMBatchResponse]:
        if not tasks:
            return []
        batch = self._post_json(
            "/v1/messages/batches",
            {
                "requests": [
                    {
                        "custom_id": task.task_id,
                        "params": {
                            "model": self.model,
                            "max_tokens": 1200,
                            "temperature": 0,
                            "system": "Return only valid JSON for license evidence review.",
                            "messages": [{"role": "user", "content": task.prompt}],
                        },
                    }
                    for task in tasks
                ]
            },
        )
        batch_id = batch["id"]
        deadline = time.monotonic() + timeout_seconds
        last_poll_error: str | None = None
        while time.monotonic() < deadline:
            try:
                current = self._get_json(f"/v1/messages/batches/{batch_id}")
            except (OSError, error.URLError, TimeoutError) as exc:
                last_poll_error = f"Anthropic batch polling failed transiently: {exc}"
                time.sleep(poll_interval_seconds)
                continue
            if current.get("processing_status") == "ended":
                try:
                    return self._read_results(batch_id, tasks)
                except (OSError, error.URLError, TimeoutError) as exc:
                    last_poll_error = f"Anthropic batch result fetch failed transiently: {exc}"
                    time.sleep(poll_interval_seconds)
                    continue
            time.sleep(poll_interval_seconds)
        message = "Anthropic batch timed out"
        if last_poll_error:
            message = f"{message}; last provider error: {last_poll_error}"
        return [LLMBatchResponse(task.task_id, None, message) for task in tasks]

    def _read_results(self, batch_id: str, tasks: list[LLMTask]) -> list[LLMBatchResponse]:
        content = self._get_text(f"/v1/messages/batches/{batch_id}/results")
        by_task: dict[str, LLMBatchResponse] = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            custom_id = row.get("custom_id")
            result = row.get("result", {})
            result_type = result.get("type")
            if result_type == "succeeded":
                blocks = result.get("message", {}).get("content", [])
                text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
                by_task[custom_id] = LLMBatchResponse(custom_id, text, None)
            else:
                by_task[custom_id] = LLMBatchResponse(custom_id, None, json.dumps(result))
        return [by_task.get(task.task_id, LLMBatchResponse(task.task_id, None, "missing Anthropic batch result")) for task in tasks]

    def _post_json(self, path: str, payload: dict) -> dict:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers() | {"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_json(self, path: str) -> dict:
        return json.loads(self._get_text(path))

    def _get_text(self, path: str) -> str:
        req = request.Request(f"{self.base_url}{path}", headers=self._headers())
        with request.urlopen(req, timeout=120) as response:
            return response.read().decode("utf-8")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
        }
