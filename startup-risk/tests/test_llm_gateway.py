from __future__ import annotations

import pytest

import startup_risk.llm as llm
from startup_risk.llm import (
    GeminiBatchProvider,
    LLMConfigError,
    estimate_batch_request_bytes,
    get_batch_provider,
    load_llm_config,
)
from startup_risk.scanners.license_scanner.models import LLMTask


class FakeHTTPResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json_bytes(self.payload)


def json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


def _clear_llm_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_MODEL",
        "ANTHROPIC_MODEL",
        "GEMINI_MODEL",
        "LICENSE_SCANNER_LLM_PROVIDER",
        "LICENSE_SCANNER_OPENAI_MODEL",
        "LICENSE_SCANNER_ANTHROPIC_MODEL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_llm_config_auto_detects_first_available_provider_key(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    config = load_llm_config()

    assert config.provider == "anthropic"
    assert config.model == "claude-3-5-haiku-latest"
    assert config.api_key == "anthropic-key"


def test_llm_config_explicit_provider_and_model_win(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    config = load_llm_config(provider="anthropic", model="claude-custom")

    assert config.provider == "anthropic"
    assert config.model == "claude-custom"
    assert config.api_key == "anthropic-key"


def test_llm_config_uses_legacy_license_provider_env(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("LICENSE_SCANNER_LLM_PROVIDER", "openai")
    monkeypatch.setenv("LICENSE_SCANNER_OPENAI_MODEL", "gpt-legacy")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    config = load_llm_config()

    assert config.provider == "openai"
    assert config.model == "gpt-legacy"


def test_llm_config_missing_keys_raises_provider_neutral_error(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)

    with pytest.raises(LLMConfigError, match="LLM provider is not configured"):
        load_llm_config()


def test_batch_factory_supports_gemini(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    provider = get_batch_provider(provider="gemini", model="gemini-test")

    assert isinstance(provider, GeminiBatchProvider)
    assert provider.model == "gemini-test"


def test_batch_estimation_does_not_require_api_key(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    task = LLMTask(task_id="license-scan-0001", items=[], prompt='Return {"items":[]}')

    estimated = estimate_batch_request_bytes(task, provider="gemini", model="gemini-test")

    assert estimated > len(task.prompt)


def test_openai_chat_client_parses_json_mode_response(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("LLM_BATCH_POLL_INTERVAL_SECONDS", "0")
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if req.full_url == "https://api.openai.com/v1/files":
            return FakeHTTPResponse({"id": "file-input"})
        if req.full_url == "https://api.openai.com/v1/batches":
            return FakeHTTPResponse({"id": "batch-1"})
        if req.full_url == "https://api.openai.com/v1/batches/batch-1":
            return FakeHTTPResponse({"status": "completed", "output_file_id": "file-output"})
        if req.full_url == "https://api.openai.com/v1/files/file-output/content":
            return FakeHTTPResponse(
                {
                    "custom_id": "llm-chat-ignored",
                    "response": {"body": {"choices": [{"message": {"content": "ignored"}}]}},
                }
            )
        raise AssertionError(req.full_url)

    fixed_time = iter([1000.0, 1000.0, 1000.0])

    def fake_time():
        return next(fixed_time, 1000.0)

    def fake_monotonic():
        return 1000.0

    def fake_read_output(self, batch, custom_id):
        assert batch["output_file_id"] == "file-output"
        return llm.ChatResponse(
            content='{"ok": true}',
            model="gpt-test",
            provider="openai",
            usage=llm.ChatUsage(input_tokens=3, output_tokens=4),
        )

    monkeypatch.setattr(llm.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm.time, "time", fake_time)
    monkeypatch.setattr(llm.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(llm.ChatClient, "_read_openai_batch_chat_output", fake_read_output)
    client = llm.get_chat_client(provider="openai", model="gpt-test")

    response = client.complete(
        messages=[{"role": "user", "content": "return json"}],
        response_format={"type": "json_object"},
    )

    assert response.content == '{"ok": true}'
    assert response.model == "gpt-test"
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 4
    assert calls[:3] == [
        "https://api.openai.com/v1/files",
        "https://api.openai.com/v1/batches",
        "https://api.openai.com/v1/batches/batch-1",
    ]


def test_anthropic_chat_client_parses_text_response(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    def fake_urlopen(req, timeout):
        assert req.full_url == "https://api.anthropic.com/v1/messages"
        return FakeHTTPResponse(
            {
                "model": "claude-test",
                "content": [{"type": "text", "text": '{"ok": true}'}],
                "usage": {"input_tokens": 5, "output_tokens": 6},
            }
        )

    monkeypatch.setattr(llm.request, "urlopen", fake_urlopen)
    client = llm.get_chat_client(provider="anthropic", model="claude-test")

    response = client.complete(
        messages=[{"role": "system", "content": "json only"}, {"role": "user", "content": "return json"}],
        response_format={"type": "json_object"},
    )

    assert response.content == '{"ok": true}'
    assert response.provider == "anthropic"
    assert response.usage.input_tokens == 5


def test_gemini_chat_client_parses_text_response(monkeypatch, tmp_path):
    _clear_llm_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    def fake_urlopen(req, timeout):
        assert req.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        return FakeHTTPResponse(
            {
                "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 8},
            }
        )

    monkeypatch.setattr(llm.request, "urlopen", fake_urlopen)
    client = llm.get_chat_client(provider="gemini", model="gemini-test")

    response = client.complete(
        messages=[{"role": "user", "content": "return json"}],
        response_format={"type": "json_object"},
    )

    assert response.content == '{"ok": true}'
    assert response.provider == "gemini"
    assert response.usage.output_tokens == 8
