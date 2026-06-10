from __future__ import annotations

import json

from typer.testing import CliRunner

import startup_risk.cli as cli_module
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
    assert "LLM provider is not configured" in result.output


def test_cli_license_only_excludes_static_hygiene_findings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("SECRET_KEY=demo\n", encoding="utf-8")
    (repo / "package-lock.json").write_text(
        json.dumps({"packages": {"node_modules/copyleft": {"version": "1.0.0", "license": "GPL-3.0"}}}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["scan", str(repo), "--format", "json", "--deterministic-only", "--license-only"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["findings"]
    assert {finding["scanner_id"] for finding in payload["findings"]} == {"license_risk"}


def test_cli_legal_ingest_writes_normalized_authorities(tmp_path):
    input_path = tmp_path / "authorities.jsonl"
    store_dir = tmp_path / "legal-store"
    input_path.write_text(
        json.dumps(
            {
                "source_id": "ca-privacy-guidance",
                "title": "Example Privacy Guidance",
                "type": "agency guidance",
                "jurisdiction": "CA",
                "topic": "privacy",
                "citation": "Example Guidance § 1",
                "text": "Businesses should provide notice before collecting personal information.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["legal-ingest", str(input_path), "--store-dir", str(store_dir)],
    )

    assert result.exit_code == 0
    rows = [
        json.loads(line)
        for line in (store_dir / "authorities.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["source_id"] == "ca-privacy-guidance"
    assert rows[0]["authority_type"] == "agency_guidance"


def test_cli_legal_fetch_writes_public_api_results(tmp_path, monkeypatch):
    store_dir = tmp_path / "legal-store"

    def fake_fetch_public_legal_authorities(*, source, query, limit, topic, jurisdiction):
        return [
            cli_module.normalize_authority(
                {
                    "source_id": f"{source}-privacy",
                    "title": "Fetched Privacy Source",
                    "type": "agency guidance",
                    "jurisdiction": jurisdiction,
                    "topic": topic,
                    "citation": "Fetched Citation",
                    "text": f"Fetched {query} source.",
                }
            )
        ]

    monkeypatch.setattr(cli_module, "fetch_public_legal_authorities", fake_fetch_public_legal_authorities)

    result = CliRunner().invoke(
        app,
        [
            "legal-fetch",
            "privacy",
            "--source",
            "federal_register",
            "--store-dir",
            str(store_dir),
            "--topic",
            "privacy",
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    rows = [
        json.loads(line)
        for line in (store_dir / "authorities.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["source_id"] == "federal_register-privacy"
    assert rows[0]["topic"] == "privacy"


def test_cli_legal_source_setup_saves_explicit_presets(tmp_path):
    store_dir = tmp_path / "legal-store"

    result = CliRunner().invoke(
        app,
        [
            "legal-source-setup",
            "--store-dir",
            str(store_dir),
            "--industry",
            "fintech",
        ],
    )

    assert result.exit_code == 0
    rows = [
        json.loads(line)
        for line in (store_dir / "source_queries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    sources = {row["source"] for row in rows}
    assert "cfpb" in sources
    assert "bulk_sync" in sources
    assert any(row["query"] == "ecfr_financial_title_12" for row in rows)
