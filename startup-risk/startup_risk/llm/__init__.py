from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib import error, parse, request

from startup_risk.scanners.license_scanner.llm.anthropic_batch import AnthropicBatchProvider
from startup_risk.scanners.license_scanner.llm.openai_batch import (
    OpenAIBatchProvider,
    estimate_openai_request_bytes,
)
from startup_risk.scanners.license_scanner.models import LLMBatchResponse, LLMTask


ProviderName = Literal["openai", "anthropic", "gemini"]

DEFAULT_MODELS: dict[ProviderName, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-3.5-flash",
}

PROVIDER_KEY_ENV: dict[ProviderName, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

PROVIDER_ORDER: tuple[ProviderName, ...] = ("openai", "anthropic", "gemini")


class LLMConfigError(ValueError):
    """Raised when provider/model configuration is missing or invalid."""


class LLMProviderCapabilityError(RuntimeError):
    """Raised when the selected provider cannot satisfy a requested feature."""


@dataclass(frozen=True)
class LLMConfig:
    provider: ProviderName
    model: str
    api_key: str
    base_url: str


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class ChatUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class ChatResponse:
    content: str
    model: str
    provider: ProviderName
    usage: ChatUsage
    tool_calls: list[Any] | None = None


def load_llm_config(provider: str | None = None, model: str | None = None) -> LLMConfig:
    """Resolve provider/model/API key from explicit args, env, and local .env files."""
    load_local_dotenv()
    selected_provider = _resolve_provider(provider)
    selected_model = _resolve_model(selected_provider, model)
    api_key = os.getenv(PROVIDER_KEY_ENV[selected_provider])
    if not api_key or api_key.startswith("stub"):
        accepted = ", ".join(PROVIDER_KEY_ENV.values())
        raise LLMConfigError(
            "LLM provider is not configured. Set LLM_PROVIDER or one provider key "
            f"({accepted}) in .env/environment."
        )
    return LLMConfig(
        provider=selected_provider,
        model=selected_model,
        api_key=api_key,
        base_url=_resolve_base_url(selected_provider),
    )


def get_chat_client(provider: str | None = None, model: str | None = None) -> "ChatClient":
    return ChatClient(load_llm_config(provider=provider, model=model))


def get_batch_provider(
    provider: str | None = None,
    model: str | None = None,
    *,
    max_batch_requests: int = 50_000,
    max_batch_file_bytes: int = 200_000_000,
    max_prompt_tokens: int = 200_000,
):
    config = load_llm_config(provider=provider, model=model)
    if config.provider == "openai":
        return OpenAIBatchProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_batch_requests=max_batch_requests,
            max_batch_file_bytes=max_batch_file_bytes,
            max_prompt_tokens=max_prompt_tokens,
        )
    if config.provider == "anthropic":
        return AnthropicBatchProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
        )
    if config.provider == "gemini":
        return GeminiBatchProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_batch_requests=max_batch_requests,
            max_batch_file_bytes=max_batch_file_bytes,
            max_prompt_tokens=max_prompt_tokens,
        )
    raise LLMConfigError(f"Unsupported LLM provider: {config.provider}")


def estimate_batch_request_bytes(task: LLMTask, provider: str | None = None, model: str | None = None) -> int:
    load_local_dotenv()
    selected_provider = _resolve_provider(provider, allow_default=True)
    selected_model = _resolve_model(selected_provider, model)
    if selected_provider == "openai":
        return estimate_openai_request_bytes(task, selected_model)
    if selected_provider == "anthropic":
        return len(json.dumps(_anthropic_batch_request(task, selected_model)).encode("utf-8"))
    if selected_provider == "gemini":
        return len(json.dumps(_gemini_inline_request(task)).encode("utf-8"))
    raise LLMConfigError(f"Unsupported LLM provider: {selected_provider}")


def load_local_dotenv() -> None:
    """Load simple KEY=VALUE pairs from the nearest .env without overriding env vars."""
    for directory in [Path.cwd(), *Path.cwd().parents]:
        env_path = directory / ".env"
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


class ChatClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def provider(self) -> ProviderName:
        return self.config.provider

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatResponse:
        if self.config.provider == "openai":
            return self._openai_complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                tools=tools,
                tool_choice=tool_choice,
            )
        if tools:
            raise LLMProviderCapabilityError(
                f"Provider '{self.config.provider}' does not support this repo's OpenAI-style tool calls yet."
            )
        if self.config.provider == "anthropic":
            return self._anthropic_complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        if self.config.provider == "gemini":
            return self._gemini_complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        raise LLMConfigError(f"Unsupported LLM provider: {self.config.provider}")

    def _openai_complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        return self._openai_batch_complete(payload)

    def _openai_batch_complete(self, payload: dict[str, Any]) -> ChatResponse:
        custom_id = f"llm-chat-{int(time.time() * 1000)}"
        content = json.dumps(
            {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": payload,
            }
        ) + "\n"
        input_file_id = self._upload_openai_batch_file(content, "llm-chat-completion.jsonl")
        body = self._post_json(
            f"{self.config.base_url}/v1/batches",
            {
                "input_file_id": input_file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {"source": "repo-llm-gateway"},
            },
            {"Authorization": f"Bearer {self.config.api_key}"},
        )
        batch_id = body.get("id")
        if not batch_id:
            raise RuntimeError("OpenAI batch response missing batch id")

        timeout_seconds = int(os.getenv("LLM_BATCH_TIMEOUT_SECONDS", "86400"))
        poll_interval_seconds = int(os.getenv("LLM_BATCH_POLL_INTERVAL_SECONDS", "10"))
        deadline = time.monotonic() + timeout_seconds
        current: dict[str, Any] = {}
        while time.monotonic() < deadline:
            current = self._get_json(
                f"{self.config.base_url}/v1/batches/{batch_id}",
                {"Authorization": f"Bearer {self.config.api_key}"},
            )
            status = current.get("status")
            if status == "completed":
                return self._read_openai_batch_chat_output(current, custom_id)
            if status in {"failed", "cancelled", "expired"}:
                raise RuntimeError(f"OpenAI batch {status}")
            time.sleep(poll_interval_seconds)
        raise RuntimeError(f"OpenAI batch timed out after {timeout_seconds} seconds")

    def _read_openai_batch_chat_output(self, batch: dict[str, Any], custom_id: str) -> ChatResponse:
        output_file_id = batch.get("output_file_id")
        error_file_id = batch.get("error_file_id")
        if output_file_id:
            content = self._get_text(
                f"{self.config.base_url}/v1/files/{output_file_id}/content",
                {"Authorization": f"Bearer {self.config.api_key}"},
            )
            for line in content.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("custom_id") != custom_id:
                    continue
                body = row.get("response", {}).get("body", {}) or {}
                message = body.get("choices", [{}])[0].get("message", {}) or {}
                usage = body.get("usage", {}) or {}
                return ChatResponse(
                    content=message.get("content") or "",
                    model=body.get("model") or self.config.model,
                    provider=self.config.provider,
                    usage=ChatUsage(
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                    ),
                    tool_calls=message.get("tool_calls"),
                )
        if error_file_id:
            error_content = self._get_text(
                f"{self.config.base_url}/v1/files/{error_file_id}/content",
                {"Authorization": f"Bearer {self.config.api_key}"},
            )
            raise RuntimeError(f"OpenAI batch returned errors: {error_content[:1000]}")
        raise RuntimeError("OpenAI batch completed without an output file")

    def _upload_openai_batch_file(self, content: str, filename: str) -> str:
        boundary = f"----repo-llm-{int(time.time() * 1000)}"
        body = _multipart_form(boundary, {"purpose": "batch"}, {"file": (filename, content, "application/jsonl")})
        req = request.Request(
            f"{self.config.base_url}/v1/files",
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))["id"]
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI batch file upload failed {exc.code}: {detail}") from exc

    def _get_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        return json.loads(self._get_text(url, headers))

    def _get_text(self, url: str, headers: dict[str, str]) -> str:
        req = request.Request(url, headers=headers)
        try:
            with request.urlopen(req, timeout=120) as response:
                return response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.config.provider} API error {exc.code}: {detail}") from exc

    def _anthropic_complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
    ) -> ChatResponse:
        system, converted = _messages_for_anthropic(messages)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or 1024,
            "messages": converted,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if _wants_json(response_format):
            payload["system"] = (payload.get("system", "") + "\nReturn only valid JSON.").strip()

        body = self._post_json(
            f"{self.config.base_url}/v1/messages",
            payload,
            {
                "x-api-key": self.config.api_key,
                "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
            },
        )
        text = "\n".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
        usage = body.get("usage", {}) or {}
        return ChatResponse(
            content=text,
            model=body.get("model") or self.config.model,
            provider=self.config.provider,
            usage=ChatUsage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            ),
        )

    def _gemini_complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
    ) -> ChatResponse:
        system, contents = _messages_for_gemini(messages)
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        generation_config: dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if _wants_json(response_format):
            generation_config["responseMimeType"] = "application/json"
        if generation_config:
            payload["generationConfig"] = generation_config

        model = self.config.model.removeprefix("models/")
        url = f"{self.config.base_url}/v1beta/models/{parse.quote(model, safe='')}:generateContent"
        body = self._post_json(url, payload, {"x-goog-api-key": self.config.api_key})
        candidates = body.get("candidates", []) or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "\n".join(part.get("text", "") for part in parts if "text" in part)
        usage = body.get("usageMetadata", {}) or {}
        return ChatResponse(
            content=text,
            model=self.config.model,
            provider=self.config.provider,
            usage=ChatUsage(
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            ),
        )

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers | {"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.config.provider} API error {exc.code}: {detail}") from exc


class GeminiBatchProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODELS["gemini"],
        base_url: str = "https://generativelanguage.googleapis.com",
        max_batch_requests: int = 50_000,
        max_batch_file_bytes: int = 20_000_000,
        max_prompt_tokens: int = 200_000,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_batch_requests = max_batch_requests
        self.max_batch_file_bytes = min(max_batch_file_bytes, 20_000_000)
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
        payload = self._batch_payload(tasks)
        self._validate_limits(tasks, payload)
        model = self.model.removeprefix("models/")
        batch = self._post_json(f"/v1beta/models/{parse.quote(model, safe='')}:batchGenerateContent", payload)
        batch_name = batch.get("name") or batch.get("batch", {}).get("name")
        if not batch_name:
            return [LLMBatchResponse(task.task_id, None, "Gemini batch response missing job name") for task in tasks]

        deadline = time.monotonic() + timeout_seconds
        last_poll_error: str | None = None
        complete_states = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        while time.monotonic() < deadline:
            try:
                current = self._get_json(f"/v1beta/{batch_name}")
            except (OSError, error.URLError, TimeoutError) as exc:
                last_poll_error = f"Gemini batch polling failed transiently: {exc}"
                time.sleep(poll_interval_seconds)
                continue
            state = _state_name(current.get("state"))
            if state == "JOB_STATE_SUCCEEDED":
                return self._read_inline_results(current, tasks)
            if state in complete_states:
                return [LLMBatchResponse(task.task_id, None, f"Gemini batch {state}") for task in tasks]
            time.sleep(poll_interval_seconds)
        message = "Gemini batch timed out"
        if last_poll_error:
            message = f"{message}; last provider error: {last_poll_error}"
        return [LLMBatchResponse(task.task_id, None, message) for task in tasks]

    def _batch_payload(self, tasks: list[LLMTask]) -> dict[str, Any]:
        return {
            "batch": {
                "display_name": "startup-risk-license-scanner",
                "input_config": {
                    "requests": {
                        "requests": [_gemini_inline_request(task) for task in tasks],
                    },
                },
            },
        }

    def _read_inline_results(self, payload: dict[str, Any], tasks: list[LLMTask]) -> list[LLMBatchResponse]:
        responses = payload.get("dest", {}).get("inlinedResponses") or payload.get("dest", {}).get("inlined_responses") or []
        by_task: dict[str, LLMBatchResponse] = {}
        task_ids = [task.task_id for task in tasks]
        for index, row in enumerate(responses):
            task_id = (
                row.get("metadata", {}).get("key")
                or row.get("key")
                or row.get("request", {}).get("metadata", {}).get("key")
                or (task_ids[index] if index < len(task_ids) else None)
            )
            if not task_id:
                continue
            if row.get("error"):
                by_task[task_id] = LLMBatchResponse(task_id, None, json.dumps(row.get("error")))
                continue
            response_body = row.get("response") or {}
            candidates = response_body.get("candidates", []) or []
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            text = "\n".join(part.get("text", "") for part in parts if "text" in part)
            by_task[task_id] = LLMBatchResponse(task_id, text or None, None if text else "missing Gemini response text")
        return [by_task.get(task.task_id, LLMBatchResponse(task.task_id, None, "missing Gemini batch result")) for task in tasks]

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini batch API error {exc.code}: {detail}") from exc

    def _get_json(self, path: str) -> dict[str, Any]:
        req = request.Request(f"{self.base_url}{path}", headers={"x-goog-api-key": self.api_key})
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    def _validate_limits(self, tasks: list[LLMTask], payload: dict[str, Any]) -> None:
        if len(tasks) > self.max_batch_requests:
            raise ValueError(
                f"Gemini batch request count {len(tasks)} exceeds configured limit {self.max_batch_requests}."
            )
        file_bytes = len(json.dumps(payload).encode("utf-8"))
        if file_bytes > self.max_batch_file_bytes:
            raise ValueError(
                "Gemini inline batch input is "
                f"{file_bytes} bytes, exceeding configured limit {self.max_batch_file_bytes}. "
                "Use fewer license tasks or add Gemini file-upload batch support."
            )
        prompt_tokens = sum(task.estimated_prompt_tokens for task in tasks)
        if prompt_tokens > self.max_prompt_tokens:
            raise ValueError(
                f"Gemini batch estimated prompt tokens {prompt_tokens} exceed configured limit {self.max_prompt_tokens}."
            )


def _resolve_provider(provider: str | None, *, allow_default: bool = False) -> ProviderName:
    raw = provider or os.getenv("LLM_PROVIDER") or os.getenv("LICENSE_SCANNER_LLM_PROVIDER")
    if raw:
        normalized = raw.strip().lower()
        if normalized == "claude":
            normalized = "anthropic"
        if normalized == "google":
            normalized = "gemini"
        if normalized in PROVIDER_ORDER:
            return normalized  # type: ignore[return-value]
        raise LLMConfigError("LLM_PROVIDER must be one of: openai, anthropic, gemini.")
    for candidate in PROVIDER_ORDER:
        key = os.getenv(PROVIDER_KEY_ENV[candidate])
        if key and not key.startswith("stub"):
            return candidate
    if allow_default:
        return "openai"
    raise LLMConfigError(
        "LLM provider is not configured. Set LLM_PROVIDER or one provider key "
        "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY) in .env/environment."
    )


def _resolve_model(provider: ProviderName, model: str | None) -> str:
    if model:
        return model
    env_order: dict[ProviderName, tuple[str, ...]] = {
        "openai": ("LLM_MODEL", "OPENAI_MODEL", "LICENSE_SCANNER_OPENAI_MODEL"),
        "anthropic": ("LLM_MODEL", "ANTHROPIC_MODEL", "LICENSE_SCANNER_ANTHROPIC_MODEL"),
        "gemini": ("LLM_MODEL", "GEMINI_MODEL", "GOOGLE_MODEL"),
    }
    for key in env_order[provider]:
        value = os.getenv(key)
        if value:
            return value
    return DEFAULT_MODELS[provider]


def _resolve_base_url(provider: ProviderName) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    if provider == "gemini":
        return os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")
    raise LLMConfigError(f"Unsupported LLM provider: {provider}")


def _wants_json(response_format: dict[str, Any] | None) -> bool:
    if not response_format:
        return False
    return response_format.get("type") == "json_object" or response_format.get("response_mime_type") == "application/json"


def _messages_for_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    system_parts: list[str] = []
    converted: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "")
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            converted.append({"role": role, "content": content})
        elif role == "tool":
            raise LLMProviderCapabilityError("Anthropic chat adapter does not support OpenAI-style tool messages yet.")
    if not converted:
        converted.append({"role": "user", "content": ""})
    return "\n\n".join(part for part in system_parts if part), converted


def _messages_for_gemini(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "")
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                }
            )
        elif role == "tool":
            raise LLMProviderCapabilityError("Gemini chat adapter does not support OpenAI-style tool messages yet.")
    if not contents:
        contents.append({"role": "user", "parts": [{"text": ""}]})
    return "\n\n".join(part for part in system_parts if part), contents


def _anthropic_batch_request(task: LLMTask, model: str) -> dict[str, Any]:
    return {
        "custom_id": task.task_id,
        "params": {
            "model": model,
            "max_tokens": 1200,
            "temperature": 0,
            "system": "Return only valid JSON for license evidence review.",
            "messages": [{"role": "user", "content": task.prompt}],
        },
    }


def _gemini_inline_request(task: LLMTask) -> dict[str, Any]:
    return {
        "request": {
            "contents": [{"role": "user", "parts": [{"text": task.prompt}]}],
            "systemInstruction": {"parts": [{"text": "Return only valid JSON for license evidence review."}]},
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 3000,
                "responseMimeType": "application/json",
            },
        },
        "metadata": {"key": task.task_id},
    }


def _state_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    if value is None:
        return None
    return str(value)


def _multipart_form(boundary: str, fields: dict[str, str], files: dict[str, tuple[str, str, str]]) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    for name, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                content.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)
