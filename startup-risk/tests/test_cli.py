from __future__ import annotations

from typer.testing import CliRunner

from startup_risk.cli import app


def test_cli_scan_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json"])

    assert result.exit_code == 0
    assert '"total_findings": 0' in result.stdout

