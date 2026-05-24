from __future__ import annotations

from startup_risk.ingest.repository import RepositoryIngestor


def test_ingestor_reads_text_files_without_executing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo / "script.py").write_text("print('do not run')\n", encoding="utf-8")

    snapshot = RepositoryIngestor().ingest(str(repo))

    assert snapshot.source.kind == "local"
    assert [file.path for file in snapshot.files] == ["README.md", "script.py"]
    assert snapshot.files[1].text == "print('do not run')\n"


def test_ingestor_skips_binary_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "image.bin").write_bytes(b"\x00\x01\x02")

    snapshot = RepositoryIngestor().ingest(str(repo))

    assert snapshot.files[0].path == "image.bin"
    assert snapshot.files[0].text is None
    assert snapshot.files[0].skipped_reason == "binary file"

