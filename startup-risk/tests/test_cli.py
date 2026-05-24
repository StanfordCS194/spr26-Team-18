from __future__ import annotations

import json

from typer.testing import CliRunner

from startup_risk.cli import app


def test_cli_scan_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source"]["kind"] == "local"
    assert "requested_ref" in payload["source"]
    assert "resolved_ref" in payload["source"]
    assert "commit_sha" in payload["source"]
    assert "inventory" in payload
    assert "findings" in payload
    assert "summary" in payload
