from __future__ import annotations

import json
import time
from urllib import request

from startup_risk.scanners.license_scanner.models import LLMBatchResponse, LLMTask


class OpenAIBatchProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com",
        max_batch_requests: int = 50_000,
        max_batch_file_bytes: int = 200_000_000,
        max_prompt_tokens: int = 200_000,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_batch_requests = max_batch_requests
        self.max_batch_file_bytes = max_batch_file_bytes
        self.max_prompt_tokens = max_prompt_tokens

    def submit_and_wait(
        self,
        tasks: list[LLMTask],
        *,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> list[LLMBatchResponse]:
        if not tasks:
            return []
        content = _jsonl_for_tasks(tasks, self.model)
        self._validate_limits(tasks, content)
        input_file_id = self._upload_batch_file(content, "license-scanner-batch.jsonl")
        batch = self._post_json(
            "/v1/batches",
            {
                "input_file_id": input_file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {"scanner": "startup-risk-license-scanner"},
            },
        )
        batch_id = batch["id"]
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            current = self._get_json(f"/v1/batches/{batch_id}")
            status = current.get("status")
            if status == "completed":
                return self._read_output(current.get("output_file_id"), current.get("error_file_id"), tasks)
            if status in {"failed", "cancelled", "expired"}:
                return [LLMBatchResponse(task.task_id, None, f"OpenAI batch {status}") for task in tasks]
            time.sleep(poll_interval_seconds)
        return [LLMBatchResponse(task.task_id, None, "OpenAI batch timed out") for task in tasks]

    def _read_output(self, output_file_id: str | None, error_file_id: str | None, tasks: list[LLMTask]) -> list[LLMBatchResponse]:
        by_task: dict[str, LLMBatchResponse] = {}
        if output_file_id:
            for line in self._get_file_content(output_file_id).splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                custom_id = row.get("custom_id")
                body = row.get("response", {}).get("body", {})
                content = body.get("choices", [{}])[0].get("message", {}).get("content")
                if custom_id:
                    by_task[custom_id] = LLMBatchResponse(custom_id, content, None)
        if error_file_id:
            for line in self._get_file_content(error_file_id).splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                custom_id = row.get("custom_id")
                if custom_id and custom_id not in by_task:
                    by_task[custom_id] = LLMBatchResponse(custom_id, None, json.dumps(row.get("error") or row))
        return [by_task.get(task.task_id, LLMBatchResponse(task.task_id, None, "missing OpenAI batch result")) for task in tasks]

    def _upload_batch_file(self, content: str, filename: str) -> str:
        boundary = f"----startup-risk-{int(time.time() * 1000)}"
        body = _multipart_form(boundary, {"purpose": "batch"}, {"file": (filename, content, "application/jsonl")})
        req = request.Request(
            f"{self.base_url}/v1/files",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))["id"]

    def _post_json(self, path: str, payload: dict) -> dict:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_json(self, path: str) -> dict:
        req = request.Request(f"{self.base_url}{path}", headers={"Authorization": f"Bearer {self.api_key}"})
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_file_content(self, file_id: str) -> str:
        req = request.Request(f"{self.base_url}/v1/files/{file_id}/content", headers={"Authorization": f"Bearer {self.api_key}"})
        with request.urlopen(req, timeout=120) as response:
            return response.read().decode("utf-8")

    def _validate_limits(self, tasks: list[LLMTask], content: str) -> None:
        if len(tasks) > self.max_batch_requests:
            raise ValueError(
                f"OpenAI batch request count {len(tasks)} exceeds configured limit {self.max_batch_requests}."
            )
        file_bytes = len(content.encode("utf-8"))
        if file_bytes > self.max_batch_file_bytes:
            raise ValueError(
                f"OpenAI batch input file is {file_bytes} bytes, exceeding configured limit {self.max_batch_file_bytes}."
            )
        prompt_tokens = sum(task.estimated_prompt_tokens for task in tasks)
        if prompt_tokens > self.max_prompt_tokens:
            raise ValueError(
                f"OpenAI batch estimated prompt tokens {prompt_tokens} exceed configured limit {self.max_prompt_tokens}."
            )


def _jsonl_for_tasks(tasks: list[LLMTask], model: str) -> str:
    lines = []
    for task in tasks:
        lines.append(
            json.dumps(
                {
                    "custom_id": task.task_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "Return only valid JSON for license evidence review."},
                            {"role": "user", "content": task.prompt},
                        ],
                        "temperature": 0,
                        "max_tokens": 1200,
                    },
                }
            )
        )
    return "\n".join(lines) + "\n"


def estimate_openai_request_bytes(task: LLMTask, model: str = "gpt-4o-mini") -> int:
    return len(_jsonl_for_tasks([task], model).encode("utf-8"))


def _multipart_form(boundary: str, fields: dict[str, str], files: dict[str, tuple[str, str, str]]) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])
    for name, (filename, content, content_type) in files.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content.encode("utf-8"),
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)
