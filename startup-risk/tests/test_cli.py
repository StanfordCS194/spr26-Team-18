from __future__ import annotations

import json

from typer.testing import CliRunner

from startup_risk.cli import app


def test_cli_scan_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json", "--deterministic-only"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source"]["kind"] == "local"
    assert "requested_ref" in payload["source"]
    assert "resolved_ref" in payload["source"]
    assert "commit_sha" in payload["source"]
    assert "inventory" in payload
    assert "findings" in payload
    assert "summary" in payload


def test_cli_license_scan_requires_batch_llm_key_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"dependencies":{"left-pad":"1.3.0"}}\n', encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json"])

    assert result.exit_code != 0
    assert "OPENAI_API_KEY is required" in result.output
